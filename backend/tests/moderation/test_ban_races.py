"""A ban against requests in flight (ADR 0005): no write commits after the ban does, and no
session works after it, whatever the timing."""

import asyncio
from typing import Any

import pytest
from fastapi import FastAPI
from httpx2 import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.comments import repository as comments_repository
from app.modules.users import repository as users_repository
from app.modules.users.models import User, UserStatus
from app.modules.videos.models import Video, VideoStatus
from tests.interactions.conftest import PASSWORD, browser, csrf, meet_after, user_by_email
from tests.moderation.conftest import ADMIN_EMAIL, OWNER_EMAIL, VIEWER_EMAIL, hold, set_status
from tests.videos.factories import get_video


async def test_a_login_racing_a_ban_gets_a_session_that_works_nowhere(
    app: FastAPI,
    admin: AsyncClient,
    viewer: AsyncClient,
    db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    handle = (await user_by_email(db, VIEWER_EMAIL)).handle
    # The login checked the status already; its session is made after the ban ended the others.
    entered, release = hold(monkeypatch, app.state.sessions, "create")
    async with browser(app, "10.0.0.7") as late:
        body = {"email": VIEWER_EMAIL, "password": PASSWORD}
        signing_in = asyncio.create_task(late.post("/api/auth/login", json=body))
        await entered.wait()
        assert (await set_status(admin, handle, "banned")).status_code == 204
        release.set()

        assert (await signing_in).status_code == 200
        session_id = late.cookies["sid"]
        assert (await late.get("/api/auth/me")).status_code == 401
        assert await app.state.sessions.read(session_id) is None  # ended on first use


async def test_a_ban_waits_for_a_write_under_way_and_stops_the_next(
    admin: AsyncClient,
    viewer: AsyncClient,
    db: AsyncSession,
    video: Video,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    handle = (await user_by_email(db, VIEWER_EMAIL)).handle
    path = f"/api/videos/{video.public_id}/comments"
    entered, release = hold(monkeypatch, comments_repository, "insert_comment")

    writing = asyncio.create_task(viewer.post(path, json={"text": "Before"}, headers=csrf(viewer)))
    await entered.wait()  # the write holds its user's write lock
    banning = asyncio.create_task(set_status(admin, handle, "banned"))
    await asyncio.sleep(0.3)
    assert not banning.done()  # the ban waits for that write
    release.set()

    assert (await writing).status_code == 201
    assert (await banning).status_code == 204
    after = await viewer.post(path, json={"text": "After"}, headers=csrf(viewer))
    assert after.status_code == 401
    assert (await get_video(db, video.public_id)).comment_count == 1


async def test_a_write_that_comes_while_a_ban_waits_goes_after_it(
    admin: AsyncClient,
    viewer: AsyncClient,
    db: AsyncSession,
    video: Video,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Row share locks would let it pass the waiting ban, and a stream of such writes would hold
    # the ban off for good; the write lock queues it behind the ban.
    handle = (await user_by_email(db, VIEWER_EMAIL)).handle
    path = f"/api/videos/{video.public_id}/comments"
    entered, release = hold(monkeypatch, comments_repository, "insert_comment")
    first = asyncio.create_task(viewer.post(path, json={"text": "First"}, headers=csrf(viewer)))
    await entered.wait()
    banning = asyncio.create_task(set_status(admin, handle, "banned"))
    await asyncio.sleep(0.3)  # the ban waits for the first write

    second = asyncio.create_task(viewer.post(path, json={"text": "Second"}, headers=csrf(viewer)))
    await asyncio.sleep(0.3)
    release.set()

    assert (await first).status_code == 201
    assert (await banning).status_code == 204
    assert (await second).status_code == 401  # it waited for the ban, then saw it
    assert (await get_video(db, video.public_id)).comment_count == 1


async def test_an_admin_clicking_twice_on_their_own_status_gets_403s(
    admin: AsyncClient, db: AsyncSession
) -> None:
    # Each request holds the admin's own write lock: locking first would deadlock them.
    handle = (await user_by_email(db, ADMIN_EMAIL)).handle

    responses = await asyncio.gather(*(set_status(admin, handle, "banned") for _ in range(2)))

    assert [response.status_code for response in responses] == [403, 403]


async def test_parallel_drafts_of_one_user_dont_deadlock(
    owner: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Both hold their user's write lock (shared), then both lock the row for the drafts count:
    # NO KEY UPDATE waits for the other, FOR UPDATE would deadlock.
    meet_after(monkeypatch, users_repository, "get_for_write", 2)

    responses = await asyncio.gather(
        *(
            owner.post("/api/videos", json={"title": f"Draft {n}"}, headers=csrf(owner))
            for n in range(2)
        )
    )

    assert [response.status_code for response in responses] == [201, 201]


async def test_a_ban_during_an_upload_keeps_the_file_from_counting(
    app: FastAPI, owner: AsyncClient, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    draft = await owner.post("/api/videos", json={"title": "Late"}, headers=csrf(owner))
    public_id = draft.json()["id"]
    upload = app.state.storage.upload

    async def banned_meanwhile(*args: Any, **kwargs: Any) -> Any:
        result = await upload(*args, **kwargs)
        # Committed while the file streamed: the request holds no lock then.
        await db.execute(
            update(User).where(User.email == OWNER_EMAIL).values(status=UserStatus.BANNED)
        )
        await db.commit()
        return result

    monkeypatch.setattr(app.state.storage, "upload", banned_meanwhile)
    response = await owner.put(
        f"/api/videos/{public_id}/file", content=b"not really a video", headers=csrf(owner)
    )

    assert response.status_code == 403
    assert (await get_video(db, public_id)).status is VideoStatus.UPLOADING
