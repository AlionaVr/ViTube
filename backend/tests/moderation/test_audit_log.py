"""GET /api/moderation/audit-log: admins read who did what, newest first, targets named."""

import pytest
from httpx2 import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.moderation import service as moderation_service
from app.modules.videos.models import Video
from tests.auth.test_roles import run_cli
from tests.interactions.conftest import csrf, posted, user_by_email
from tests.moderation.conftest import (
    ADMIN_EMAIL,
    MODERATOR_EMAIL,
    VIEWER_EMAIL,
    act,
    hide,
    set_status,
)


async def audit_page(client: AsyncClient, cursor: str | None = None):
    return await client.get(
        "/api/moderation/audit-log", params={"cursor": cursor} if cursor else {}
    )


async def test_only_admins_read_the_audit_log(
    guest: AsyncClient, viewer: AsyncClient, moderator: AsyncClient, admin: AsyncClient
) -> None:
    assert (await audit_page(guest)).status_code == 401
    assert (await audit_page(viewer)).status_code == 403
    assert (await audit_page(moderator)).status_code == 403
    assert (await audit_page(admin)).json() == {"items": [], "next_cursor": None}


async def test_entries_come_newest_first_with_their_targets_named(
    owner: AsyncClient,
    viewer: AsyncClient,
    moderator: AsyncClient,
    admin: AsyncClient,
    db: AsyncSession,
    video: Video,
) -> None:
    comment = await posted(viewer, video, "Rude words")
    await moderator.delete(f"/api/moderation/comments/{comment['id']}", headers=csrf(moderator))
    await hide(moderator, video, "violent")
    viewer_handle = (await user_by_email(db, VIEWER_EMAIL)).handle
    await set_status(admin, viewer_handle, "banned", "Spam bot")

    items = (await audit_page(admin)).json()["items"]

    assert [item["action"] for item in items] == ["set_user_status", "hide_video", "delete_comment"]
    ban, hidden, deleted = items
    assert ban["actor"]["handle"] == (await user_by_email(db, ADMIN_EMAIL)).handle
    assert ban["source"] == "api"
    assert ban["target"] == {
        "type": "user",
        "label": f"@{viewer_handle}",
        "video_id": None,
        "handle": viewer_handle,
    }
    assert ban["details"] == {"from": "active", "to": "banned", "reason": "Spam bot"}
    assert hidden["actor"]["handle"] == (await user_by_email(db, MODERATOR_EMAIL)).handle
    assert hidden["target"] == {
        "type": "video",
        "label": "A video",
        "video_id": video.public_id,
        "handle": None,
    }
    assert hidden["details"] == {"reason": "violent", "reports": 0}
    assert deleted["target"]["label"] == "Rude words"  # a soft-deleted comment keeps its text
    assert deleted["target"]["video_id"] == video.public_id


async def test_a_cli_entry_names_the_shell_user_and_by(
    viewer: AsyncClient, admin: AsyncClient
) -> None:
    await run_cli("set-status", VIEWER_EMAIL, "banned", "--by", ADMIN_EMAIL)

    [entry] = (await audit_page(admin)).json()["items"]

    assert (entry["source"], entry["actor"], entry["by"]) == ("cli", None, ADMIN_EMAIL)
    assert entry["os_user"]
    assert entry["details"] == {"from": "active", "to": "banned"}


async def test_the_log_pages_without_gaps(
    moderator: AsyncClient,
    admin: AsyncClient,
    video: Video,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(moderation_service, "AUDIT_PAGE_SIZE", 2)
    for _ in range(2):  # hide, restore, hide, restore: four entries
        await hide(moderator, video)
        await act(moderator, video, "restore")

    first = (await audit_page(admin)).json()
    second = (await audit_page(admin, first["next_cursor"])).json()

    actions = [item["action"] for item in first["items"] + second["items"]]
    assert actions == ["restore_video", "hide_video", "restore_video", "hide_video"]
    assert len({item["id"] for item in first["items"] + second["items"]}) == 4
    assert second["next_cursor"] is None


# --- Filters ---


async def test_filters_by_action_source_and_actor(
    viewer: AsyncClient, moderator: AsyncClient, admin: AsyncClient, db: AsyncSession, video: Video
) -> None:
    await hide(moderator, video)
    await act(moderator, video, "restore")
    await hide(admin, video)
    await run_cli("set-status", VIEWER_EMAIL, "banned")
    mod_handle = (await user_by_email(db, MODERATOR_EMAIL)).handle

    async def actions(**params: str | list[str]) -> list[str]:
        response = await admin.get("/api/moderation/audit-log", params=params)
        assert response.status_code == 200
        return [item["action"] for item in response.json()["items"]]

    assert await actions(action="hide_video") == ["hide_video", "hide_video"]
    assert await actions(action=["restore_video", "set_user_status"]) == [
        "set_user_status",
        "restore_video",
    ]
    assert await actions(source="cli") == ["set_user_status"]
    assert await actions(actor=mod_handle) == ["restore_video", "hide_video"]
    assert await actions(actor=mod_handle, action="hide_video") == ["hide_video"]
    assert await actions(actor="nobody-at-all") == []


async def test_the_account_filter_finds_the_account_its_videos_and_comments(
    owner: AsyncClient,
    viewer: AsyncClient,
    moderator: AsyncClient,
    admin: AsyncClient,
    db: AsyncSession,
    video: Video,
) -> None:
    owner_handle = (await user_by_email(db, "owner@example.com")).handle
    viewer_handle = (await user_by_email(db, VIEWER_EMAIL)).handle
    owners_comment = await posted(owner, video, "Mine")
    viewers_comment = await posted(viewer, video, "Theirs")
    for comment in (owners_comment, viewers_comment):
        await moderator.delete(f"/api/moderation/comments/{comment['id']}", headers=csrf(moderator))
    await hide(moderator, video)
    await set_status(admin, owner_handle, "banned")
    await set_status(admin, viewer_handle, "banned")

    response = await admin.get("/api/moderation/audit-log", params={"account": owner_handle})

    labels = [(item["action"], item["target"]["label"]) for item in response.json()["items"]]
    assert labels == [
        ("set_user_status", f"@{owner_handle}"),
        ("hide_video", "A video"),
        ("delete_comment", "Mine"),
    ]


async def test_filters_page_with_their_cursor(
    moderator: AsyncClient, admin: AsyncClient, video: Video, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(moderation_service, "AUDIT_PAGE_SIZE", 1)
    for _ in range(2):
        await hide(moderator, video)
        await act(moderator, video, "restore")
    params = {"action": "hide_video"}

    first = (await admin.get("/api/moderation/audit-log", params=params)).json()
    params["cursor"] = first["next_cursor"]
    second = (await admin.get("/api/moderation/audit-log", params=params)).json()

    assert [item["action"] for item in first["items"] + second["items"]] == ["hide_video"] * 2
    assert first["items"][0]["id"] != second["items"][0]["id"]


async def test_a_filter_needs_a_valid_handle(admin: AsyncClient) -> None:
    response = await admin.get("/api/moderation/audit-log", params={"account": "no spaces"})
    assert response.status_code == 422
