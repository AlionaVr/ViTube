"""Banning, terminating and reinstating accounts (ADR 0009): admins only, logged, and in force
from the next request whatever Redis does (ADR 0005)."""

import pytest
from fastapi import FastAPI
from httpx2 import AsyncClient
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditAction, AuditSource, TargetType
from app.modules.users.models import Role, UserStatus
from app.modules.videos.models import Video
from tests.auth.test_roles import run_cli
from tests.interactions.conftest import PASSWORD, browser, csrf, posted, signup, user_by_email
from tests.moderation.conftest import (
    ADMIN_EMAIL,
    MODERATOR_EMAIL,
    OWNER_EMAIL,
    VIEWER_EMAIL,
    as_dict,
    audit_entries,
    set_status,
)
from tests.search.test_search import found
from tests.videos.factories import set_role
from tests.videos.test_feed import feed_ids


async def handle_of(db: AsyncSession, email: str) -> str:
    return (await user_by_email(db, email)).handle


async def status_of(db: AsyncSession, email: str) -> UserStatus:
    user = await user_by_email(db, email)
    await db.refresh(user)
    return user.status


async def media_auth(client: AsyncClient, video: Video) -> int:
    headers = {"X-Original-URI": f"/media/{video.media_key}"}
    return (await client.get("/internal/media-auth", headers=headers)).status_code


async def login(client: AsyncClient, email: str, password: str = PASSWORD):
    return await client.post("/api/auth/login", json={"email": email, "password": password})


# --- Who may ---


async def test_only_admins_restrict_accounts(
    guest: AsyncClient, viewer: AsyncClient, moderator: AsyncClient, db: AsyncSession
) -> None:
    handle = await handle_of(db, VIEWER_EMAIL)

    assert (await set_status(guest, handle, "banned")).status_code == 401
    for client in (viewer, moderator):
        assert (await set_status(client, handle, "banned")).status_code == 403
        assert (await client.get("/api/moderation/users")).status_code == 403
    assert await status_of(db, VIEWER_EMAIL) is UserStatus.ACTIVE


async def test_an_admin_cant_restrict_themselves_or_another_admin(
    app: FastAPI, admin: AsyncClient, db: AsyncSession
) -> None:
    assert (await set_status(admin, await handle_of(db, ADMIN_EMAIL), "banned")).status_code == 403
    async with browser(app, "10.0.0.8") as other:
        await signup(other, "admin2@example.com")
        await set_role(db, "admin2@example.com", Role.ADMIN)
    assert (
        await set_status(admin, await handle_of(db, "admin2@example.com"), "banned")
    ).status_code == 403
    assert await audit_entries(db) == []


async def test_unknown_accounts_and_statuses_are_refused(
    admin: AsyncClient, viewer: AsyncClient, db: AsyncSession
) -> None:
    assert (await set_status(admin, "nobody-here", "banned")).status_code == 404
    assert (await set_status(admin, await handle_of(db, VIEWER_EMAIL), "frozen")).status_code == 422


# --- Ban ---


async def test_a_ban_ends_every_session_and_is_logged(
    app: FastAPI, admin: AsyncClient, viewer: AsyncClient, db: AsyncSession, video: Video
) -> None:
    async with browser(app, "10.0.0.2", cookies=viewer.cookies) as second_tab:
        response = await set_status(admin, await handle_of(db, VIEWER_EMAIL), "banned", "Spam bot")

        assert response.status_code == 204
        for tab in (viewer, second_tab):
            assert (await tab.get("/api/auth/me")).status_code == 401
            path = f"/api/videos/{video.public_id}/comments"
            assert (await tab.post(path, json={"text": "Hi"}, headers=csrf(tab))).status_code == 401
            assert (await tab.get(f"/api/videos/{video.public_id}")).status_code == 200  # a guest
    banned = await user_by_email(db, VIEWER_EMAIL)
    assert await app.state.redis.zcard(f"user_sessions:{banned.id}") == 0
    [entry] = await audit_entries(db)
    assert as_dict(entry) == {
        "source": AuditSource.API,
        "actor_id": (await user_by_email(db, ADMIN_EMAIL)).id,
        "action": AuditAction.SET_USER_STATUS,
        "target_type": TargetType.USER,
        "target_id": banned.id,
        "details": {"from": "active", "to": "banned", "reason": "Spam bot"},
    }


async def test_a_banned_account_cant_sign_in_and_only_the_password_tells(
    app: FastAPI, admin: AsyncClient, viewer: AsyncClient, db: AsyncSession
) -> None:
    await set_status(admin, await handle_of(db, VIEWER_EMAIL), "banned")

    async with browser(app, "10.0.0.7") as other:
        refused = await login(other, VIEWER_EMAIL)
        wrong = await login(other, VIEWER_EMAIL, "wrong password")

    assert (refused.status_code, refused.json()["detail"]) == (403, "This account is banned")
    assert wrong.status_code == 401  # a guesser learns nothing about the ban


async def test_a_ban_holds_when_ending_the_sessions_fails(
    app: FastAPI,
    admin: AsyncClient,
    viewer: AsyncClient,
    db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def redis_down(*args: object) -> None:
        raise RedisError("connection refused")

    monkeypatch.setattr(app.state.sessions, "revoke_all", redis_down)
    session_id = viewer.cookies["sid"]

    assert (await set_status(admin, await handle_of(db, VIEWER_EMAIL), "banned")).status_code == 204

    assert await app.state.sessions.read(session_id) is not None  # Redis kept it...
    assert (await viewer.get("/api/auth/me")).status_code == 401  # ...the DB refuses it
    assert await app.state.sessions.read(session_id) is None  # and that request ended it


async def test_banning_again_logs_nothing_but_ends_sessions_again(
    app: FastAPI, admin: AsyncClient, viewer: AsyncClient, db: AsyncSession
) -> None:
    handle = await handle_of(db, VIEWER_EMAIL)
    await set_status(admin, handle, "banned")
    leftover = await app.state.sessions.create((await user_by_email(db, VIEWER_EMAIL)).id)

    assert (await set_status(admin, handle, "banned")).status_code == 204

    assert await app.state.sessions.read(leftover.id) is None
    assert len(await audit_entries(db)) == 1


async def test_reinstating_lets_them_sign_in_again(
    app: FastAPI, admin: AsyncClient, viewer: AsyncClient, db: AsyncSession
) -> None:
    handle = await handle_of(db, VIEWER_EMAIL)
    await set_status(admin, handle, "banned")

    assert (await set_status(admin, handle, "active")).status_code == 204

    async with browser(app, "10.0.0.7") as other:
        assert (await login(other, VIEWER_EMAIL)).status_code == 200
    entries = await audit_entries(db)
    assert entries[1].details == {"from": "banned", "to": "active"}


async def test_a_banned_channels_content_stays(
    admin: AsyncClient, owner: AsyncClient, guest: AsyncClient, db: AsyncSession, video: Video
) -> None:
    comment = await posted(owner, video, "Still here")

    await set_status(admin, await handle_of(db, OWNER_EMAIL), "banned")

    assert (await guest.get(f"/api/videos/{video.public_id}")).status_code == 200
    listed = (await guest.get(f"/api/videos/{video.public_id}/comments")).json()["items"]
    assert [item["id"] for item in listed] == [comment["id"]]


# --- Terminate ---


async def test_a_terminated_channels_videos_are_gone_for_all_but_staff(
    admin: AsyncClient,
    owner: AsyncClient,
    viewer: AsyncClient,
    guest: AsyncClient,
    moderator: AsyncClient,
    db: AsyncSession,
    video: Video,
) -> None:
    video.title = "Dragon terminated"
    await db.commit()
    handle = await handle_of(db, OWNER_EMAIL)

    assert (await set_status(admin, handle, "terminated")).status_code == 204

    assert (await owner.get("/api/auth/me")).status_code == 401  # no sign-in either
    for outsider in (viewer, guest):
        assert (await outsider.get(f"/api/videos/{video.public_id}")).status_code == 404
        assert await feed_ids(outsider) == []
        assert await found(outsider, "dragon") == []
    assert await media_auth(viewer, video) == 403  # nginx shows 404
    assert await media_auth(guest, video) == 401
    assert (await moderator.get(f"/api/videos/{video.public_id}")).status_code == 200
    assert await media_auth(moderator, video) == 200
    path = f"/api/videos/{video.public_id}/comments"
    response = await moderator.post(path, json={"text": "Hi"}, headers=csrf(moderator))
    assert response.status_code == 404  # frozen, as a hidden video

    assert (await set_status(admin, handle, "active")).status_code == 204
    assert (await viewer.get(f"/api/videos/{video.public_id}")).status_code == 200
    assert await feed_ids(guest) == [video.public_id]


async def test_admins_list_restricted_accounts(
    admin: AsyncClient, viewer: AsyncClient, owner: AsyncClient, db: AsyncSession
) -> None:
    await set_status(admin, await handle_of(db, VIEWER_EMAIL), "banned")
    await set_status(admin, await handle_of(db, OWNER_EMAIL), "terminated")

    every = (await admin.get("/api/moderation/users")).json()["items"]
    banned = (await admin.get("/api/moderation/users", params={"status": "banned"})).json()

    assert sorted(item["status"] for item in every) == ["banned", "terminated"]
    assert [item["channel"]["handle"] for item in banned["items"]] == [
        await handle_of(db, VIEWER_EMAIL)
    ]


# --- CLI ---


async def test_the_cli_bans_and_logs_who_ran_it(
    viewer: AsyncClient, admin: AsyncClient, db: AsyncSession
) -> None:
    code, output = await run_cli(
        "set-status", VIEWER_EMAIL, "banned", "--by", ADMIN_EMAIL, "--reason", "Spam bot"
    )

    assert (code, output) == (0, f"{VIEWER_EMAIL}: banned\n")
    assert (await viewer.get("/api/auth/me")).status_code == 401
    [entry] = await audit_entries(db)
    assert (entry.source, entry.actor_id, entry.action) == (
        AuditSource.CLI,
        None,
        AuditAction.SET_USER_STATUS,
    )
    assert entry.details["by"] == ADMIN_EMAIL
    assert entry.details["os_user"]
    assert entry.details["reason"] == "Spam bot"


async def test_the_cli_refuses_a_by_that_is_no_admin(
    viewer: AsyncClient, moderator: AsyncClient, db: AsyncSession
) -> None:
    code, output = await run_cli("set-status", VIEWER_EMAIL, "banned", "--by", MODERATOR_EMAIL)

    assert code == 1
    assert "No admin with this email" in output
    assert await status_of(db, VIEWER_EMAIL) is UserStatus.ACTIVE


async def test_set_role_is_logged(viewer: AsyncClient, db: AsyncSession) -> None:
    code, _ = await run_cli("set-role", VIEWER_EMAIL, "moderator")
    await run_cli("set-role", VIEWER_EMAIL, "moderator")  # no change: no entry

    assert code == 0
    [entry] = await audit_entries(db)
    assert (entry.source, entry.action, entry.details["from"], entry.details["to"]) == (
        AuditSource.CLI,
        AuditAction.SET_USER_ROLE,
        "user",
        "moderator",
    )
