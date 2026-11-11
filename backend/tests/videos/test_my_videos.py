"""GET /api/me/videos: Studio lists all of the user's videos, in any status, newest first."""

from itertools import product
from typing import Any

import pytest
from httpx2 import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.models import Role, User
from app.modules.videos.models import VideoStatus, Visibility
from app.modules.videos.service import MY_VIDEOS_PAGE_SIZE
from tests.videos.factories import grant, make_user, make_video, set_role

EMAIL = "me@example.com"
PASSWORD = "correct horse battery"
NOT_READY = [status for status in VideoStatus if status is not VideoStatus.READY]


@pytest.fixture
async def me(db: AsyncSession, client: AsyncClient) -> User:
    """The user `client` is signed in as. After `db`: its reset would wipe the account."""
    response = await client.post("/api/auth/signup", json={"email": EMAIL, "password": PASSWORD})
    assert response.status_code == 201
    user = await db.scalar(select(User).where(User.email == EMAIL))
    assert user is not None
    return user


async def my_videos(client: AsyncClient, cursor: str | None = None) -> dict[str, Any]:
    response = await client.get("/api/me/videos", params={"cursor": cursor} if cursor else {})
    assert response.status_code == 200
    return response.json()


async def my_ids(client: AsyncClient) -> list[str]:
    """Follow next_cursor to the end; the ids in the order the pages gave them."""
    ids: list[str] = []
    cursor = None
    while True:
        page = await my_videos(client, cursor)
        ids += [item["id"] for item in page["items"]]
        cursor = page["next_cursor"]
        if cursor is None:
            return ids


async def test_a_user_without_videos_gets_an_empty_page(client: AsyncClient, me: User) -> None:
    assert await my_videos(client) == {"items": [], "next_cursor": None}


async def test_the_owner_sees_every_status_and_visibility_once(
    client: AsyncClient, db: AsyncSession, me: User
) -> None:
    combos = list(product(VideoStatus, Visibility))
    for status, visibility in combos:
        await make_video(db, me, status=status, visibility=visibility)

    items = (await my_videos(client))["items"]

    assert sorted((item["status"], item["visibility"]) for item in items) == sorted(combos)


@pytest.mark.parametrize("viewer", ["stranger", "granted", "moderator"])
async def test_other_users_videos_are_never_listed(
    client: AsyncClient, db: AsyncSession, me: User, viewer: str
) -> None:
    bob = await make_user(db, "bob")
    await make_video(db, bob)  # public and ready: anyone may watch it, still not mine
    private = await make_video(db, bob, visibility=Visibility.PRIVATE)
    if viewer == "granted":
        await grant(db, private.public_id, EMAIL)
    if viewer == "moderator":
        await set_role(db, EMAIL, Role.MODERATOR)
    mine = await make_video(db, me)

    assert await my_ids(client) == [mine.public_id]


async def test_a_failed_video_says_why(client: AsyncClient, db: AsyncSession, me: User) -> None:
    await make_video(db, me, status=VideoStatus.FAILED)

    [item] = (await my_videos(client))["items"]

    assert item["error_message"] == "Not a video"


@pytest.mark.parametrize("status", NOT_READY)
async def test_a_video_has_no_media_urls_until_ready(
    client: AsyncClient, db: AsyncSession, me: User, status: VideoStatus
) -> None:
    await make_video(db, me, status=status)

    [item] = (await my_videos(client))["items"]

    assert item["thumbnail_url"] is None
    assert item["media_url"] is None


async def test_a_ready_video_has_media_urls_and_the_owners_channel(
    client: AsyncClient, db: AsyncSession, me: User
) -> None:
    video = await make_video(db, me, visibility=Visibility.PRIVATE)

    [item] = (await my_videos(client))["items"]

    assert item["thumbnail_url"] == f"/media/thumbs/{video.id}.jpg"
    assert item["media_url"] == f"/media/videos/{video.id}/720p.mp4"
    assert item["error_message"] is None
    assert item["channel"] == {"handle": me.handle, "name": me.handle, "avatar_url": None}


async def test_videos_come_newest_first(client: AsyncClient, db: AsyncSession, me: User) -> None:
    made = [(await make_video(db, me, status=status)).public_id for status in VideoStatus]

    assert await my_ids(client) == made[::-1]


async def test_pages_go_from_newest_to_oldest_without_gaps(
    client: AsyncClient, db: AsyncSession, me: User
) -> None:
    made = [(await make_video(db, me)).public_id for _ in range(MY_VIDEOS_PAGE_SIZE + 3)]

    first = await my_videos(client)
    last = await my_videos(client, first["next_cursor"])

    assert len(first["items"]) == MY_VIDEOS_PAGE_SIZE
    assert last["next_cursor"] is None
    assert [item["id"] for item in first["items"] + last["items"]] == made[::-1]


async def test_a_guest_gets_401(client: AsyncClient) -> None:
    response = await client.get("/api/me/videos")

    assert response.status_code == 401


async def test_a_bad_cursor_is_refused(client: AsyncClient, me: User) -> None:
    response = await client.get("/api/me/videos", params={"cursor": "not-a-cursor"})

    assert response.status_code == 400
