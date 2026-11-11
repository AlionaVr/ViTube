"""GET /api/videos: the home feed lists public ready videos, newest first."""

from datetime import datetime

import pytest
from httpx2 import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.videos.models import VideoStatus, Visibility
from app.modules.videos.service import FEED_PAGE_SIZE
from tests.videos.factories import make_user, make_video

NOT_READY = [status for status in VideoStatus if status is not VideoStatus.READY]


async def feed_ids(client: AsyncClient) -> list[str]:
    """Follow next_cursor to the end; the ids in the order the pages gave them."""
    ids: list[str] = []
    cursor = None
    while True:
        response = await client.get("/api/videos", params={"cursor": cursor} if cursor else {})
        assert response.status_code == 200
        ids += [item["id"] for item in response.json()["items"]]
        cursor = response.json()["next_cursor"]
        if cursor is None:
            return ids


async def test_a_guest_sees_a_public_video_with_its_channel(
    client: AsyncClient, db: AsyncSession
) -> None:
    owner = await make_user(db, "owner")
    video = await make_video(db, owner)

    response = await client.get("/api/videos")

    assert response.status_code == 200
    page = response.json()
    assert page["next_cursor"] is None
    [item] = page["items"]
    assert datetime.fromisoformat(item.pop("created_at")) == video.created_at
    assert item == {
        "id": video.public_id,
        "title": "A video",
        "thumbnail_url": f"/media/thumbs/{video.id}.jpg",
        "duration_sec": 10,
        "view_count": 0,
        "channel": {"handle": "owner", "name": "owner", "avatar_url": None},
    }


@pytest.mark.parametrize("visibility", [Visibility.UNLISTED, Visibility.PRIVATE])
async def test_only_public_videos_are_listed(
    client: AsyncClient, db: AsyncSession, visibility: Visibility
) -> None:
    owner = await make_user(db, "owner")
    public = await make_video(db, owner)
    await make_video(db, owner, visibility=visibility)

    assert await feed_ids(client) == [public.public_id]


@pytest.mark.parametrize("status", NOT_READY)
async def test_only_ready_videos_are_listed(
    client: AsyncClient, db: AsyncSession, status: VideoStatus
) -> None:
    owner = await make_user(db, "owner")
    ready = await make_video(db, owner)
    await make_video(db, owner, status=status)

    assert await feed_ids(client) == [ready.public_id]


async def test_pages_go_from_newest_to_oldest_without_gaps(
    client: AsyncClient, db: AsyncSession
) -> None:
    owner = await make_user(db, "owner")
    made = [(await make_video(db, owner)).public_id for _ in range(FEED_PAGE_SIZE + 1)]

    first = (await client.get("/api/videos")).json()

    assert len(first["items"]) == FEED_PAGE_SIZE
    assert first["next_cursor"] is not None
    assert await feed_ids(client) == made[::-1]


async def test_a_bad_cursor_is_refused(client: AsyncClient) -> None:
    response = await client.get("/api/videos", params={"cursor": "not-a-cursor"})

    assert response.status_code == 400
