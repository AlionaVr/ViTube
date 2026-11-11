"""GET /api/channels/{handle}/videos: the Videos tab, its sorts and pages."""

import pytest
from fastapi import FastAPI
from httpx2 import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import encode_cursor
from app.modules.users.models import Role, User
from app.modules.videos.models import Video, VideoStatus, Visibility
from app.modules.videos.service import FEED_PAGE_SIZE
from tests.interactions.conftest import OWNER_EMAIL, browser, signup, user_by_email
from tests.videos.factories import make_user, make_video, set_role


async def videos_of(client: AsyncClient, handle: str, **params: str) -> list[str]:
    response = await client.get(f"/api/channels/{handle}/videos", params=params)
    assert response.status_code == 200
    return [item["id"] for item in response.json()["items"]]


async def all_pages(client: AsyncClient, handle: str, sort: str) -> list[str]:
    ids: list[str] = []
    cursor = None
    while True:
        params = {"sort": sort} | ({"cursor": cursor} if cursor else {})
        body = (await client.get(f"/api/channels/{handle}/videos", params=params)).json()
        ids += [item["id"] for item in body["items"]]
        if (cursor := body["next_cursor"]) is None:
            return ids


async def set_views(db: AsyncSession, video: Video, views: int) -> None:
    await db.execute(update(Video).where(Video.id == video.id).values(view_count=views))
    await db.commit()


@pytest.fixture
async def anna(db: AsyncSession) -> User:
    return await make_user(db, "anna")


async def test_lists_the_channel_videos_as_summaries(
    client: AsyncClient, db: AsyncSession, anna: User
) -> None:
    video = await make_video(db, anna)

    response = await client.get("/api/channels/anna/videos")

    assert response.status_code == 200
    [item] = response.json()["items"]
    assert item["id"] == video.public_id
    assert item["channel"] == {"handle": "anna", "name": "anna", "avatar_url": None}
    assert response.json()["next_cursor"] is None


async def test_only_public_ready_videos_for_everyone_the_owner_and_moderators_too(
    app: FastAPI, owner: AsyncClient, guest: AsyncClient, db: AsyncSession
) -> None:
    channel = await user_by_email(db, OWNER_EMAIL)
    listed = await make_video(db, channel)
    for visibility in (Visibility.UNLISTED, Visibility.PRIVATE):
        await make_video(db, channel, visibility=visibility)
    for status in VideoStatus:
        if status is not VideoStatus.READY:
            await make_video(db, channel, status=status)
    await make_video(db, await make_user(db, "bob"))  # another channel's
    async with browser(app, "10.0.0.9") as moderator:
        await signup(moderator, "mod@example.com")
        await set_role(db, "mod@example.com", Role.MODERATOR)

        for client in (guest, owner, moderator):
            assert await videos_of(client, channel.handle) == [listed.public_id]


async def test_latest_and_oldest(client: AsyncClient, db: AsyncSession, anna: User) -> None:
    ids = [(await make_video(db, anna)).public_id for _ in range(3)]

    assert await videos_of(client, "anna") == ids[::-1]
    assert await videos_of(client, "anna", sort="latest") == ids[::-1]
    assert await videos_of(client, "anna", sort="oldest") == ids


async def test_popular_is_most_viewed_first_newer_first_on_ties(
    client: AsyncClient, db: AsyncSession, anna: User
) -> None:
    videos = [await make_video(db, anna) for _ in range(4)]
    for video, views in zip(videos, [5, 50, 5, 0], strict=True):
        await set_views(db, video, views)

    assert await videos_of(client, "anna", sort="popular") == [
        videos[1].public_id,
        videos[2].public_id,
        videos[0].public_id,
        videos[3].public_id,
    ]


@pytest.mark.parametrize("sort", ["latest", "popular", "oldest"])
async def test_pages_have_no_gaps_or_repeats(
    client: AsyncClient, db: AsyncSession, anna: User, sort: str
) -> None:
    videos = [await make_video(db, anna) for _ in range(FEED_PAGE_SIZE + 5)]
    for number, video in enumerate(videos):
        await set_views(db, video, number % 3)  # many ties: the id breaks them

    ids = await all_pages(client, "anna", sort)

    assert len(ids) == len(set(ids)) == len(videos)
    first = await videos_of(client, "anna", sort=sort)
    assert len(first) == FEED_PAGE_SIZE
    assert ids[:FEED_PAGE_SIZE] == first


async def test_unknown_channel_is_not_found(client: AsyncClient, db: AsyncSession) -> None:
    response = await client.get("/api/channels/nobody/videos")

    assert response.status_code == 404


async def test_unknown_sort_is_refused(client: AsyncClient, anna: User) -> None:
    response = await client.get("/api/channels/anna/videos", params={"sort": "random"})

    assert response.status_code == 422


@pytest.mark.parametrize(
    ("sort", "cursor"),
    [
        ("latest", "not base64!"),
        ("latest", encode_cursor((1, 2))),
        ("popular", encode_cursor(("0193a5c2-0000-7000-8000-000000000001",))),
        ("popular", encode_cursor((-1, "0193a5c2-0000-7000-8000-000000000001"))),
        ("popular", encode_cursor((2**63, "0193a5c2-0000-7000-8000-000000000001"))),
    ],
)
async def test_bad_cursor_is_refused(
    client: AsyncClient, anna: User, sort: str, cursor: str
) -> None:
    response = await client.get(
        "/api/channels/anna/videos", params={"sort": sort, "cursor": cursor}
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid cursor"}
