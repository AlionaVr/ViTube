"""GET /api/videos/{id}/related: the channel's other videos first, then the newest of others."""

import pytest
from httpx2 import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.videos.models import VideoStatus, Visibility
from app.modules.videos.service import UP_NEXT_PAGE_SIZE
from tests.videos.factories import make_user, make_video


async def up_next_ids(client: AsyncClient, public_id: str) -> list[str]:
    """Follow next_cursor to the end; the ids in the order the pages gave them."""
    ids: list[str] = []
    cursor = None
    while True:
        response = await client.get(
            f"/api/videos/{public_id}/related", params={"cursor": cursor} if cursor else {}
        )
        assert response.status_code == 200
        ids += [item["id"] for item in response.json()["items"]]
        cursor = response.json()["next_cursor"]
        if cursor is None:
            return ids


async def test_the_channel_comes_first_then_the_newest_of_others(
    client: AsyncClient, db: AsyncSession
) -> None:
    anna, bob = await make_user(db, "anna"), await make_user(db, "bob")
    old_anna = await make_video(db, anna)
    old_bob = await make_video(db, bob)
    current = await make_video(db, anna)
    new_bob = await make_video(db, bob)
    new_anna = await make_video(db, anna)

    response = await client.get(f"/api/videos/{current.public_id}/related")

    assert response.status_code == 200
    items = response.json()["items"]
    assert [item["id"] for item in items] == [
        new_anna.public_id,
        old_anna.public_id,
        new_bob.public_id,
        old_bob.public_id,
    ]
    assert items[0]["channel"]["handle"] == "anna"


async def test_only_listed_videos_come_up(client: AsyncClient, db: AsyncSession) -> None:
    anna, bob = await make_user(db, "anna"), await make_user(db, "bob")
    current = await make_video(db, anna)
    listed = await make_video(db, bob)
    await make_video(db, anna, visibility=Visibility.UNLISTED)
    await make_video(db, bob, visibility=Visibility.PRIVATE)
    await make_video(db, anna, status=VideoStatus.PROCESSING)

    assert await up_next_ids(client, current.public_id) == [listed.public_id]


@pytest.mark.parametrize(
    "channel_videos",
    [UP_NEXT_PAGE_SIZE - 5, UP_NEXT_PAGE_SIZE + 5],
    ids=["groups meet on page 1", "channel fills page 1"],
)
async def test_pages_have_no_gaps_or_repeats(
    client: AsyncClient, db: AsyncSession, channel_videos: int
) -> None:
    anna, bob = await make_user(db, "anna"), await make_user(db, "bob")
    current = await make_video(db, anna)
    anna_ids, bob_ids = [], []
    for _ in range(channel_videos):
        anna_ids.append((await make_video(db, anna)).public_id)
        bob_ids.append((await make_video(db, bob)).public_id)

    assert await up_next_ids(client, current.public_id) == anna_ids[::-1] + bob_ids[::-1]


async def test_a_guest_gets_404_for_a_private_videos_list(
    client: AsyncClient, db: AsyncSession
) -> None:
    anna = await make_user(db, "anna")
    private = await make_video(db, anna, visibility=Visibility.PRIVATE)
    await make_video(db, anna)

    response = await client.get(f"/api/videos/{private.public_id}/related")

    assert response.status_code == 404


async def test_an_unknown_video_is_404(client: AsyncClient) -> None:
    response = await client.get("/api/videos/abcdefghijk/related")

    assert response.status_code == 404


async def test_a_bad_cursor_is_refused(client: AsyncClient, db: AsyncSession) -> None:
    current = await make_video(db, await make_user(db, "anna"))

    response = await client.get(
        f"/api/videos/{current.public_id}/related", params={"cursor": "not-a-cursor"}
    )

    assert response.status_code == 400
