"""GET /api/me/channel/videos: your own channel's Videos tab, every visibility."""

import pytest
from fastapi import FastAPI
from httpx2 import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import encode_cursor
from app.modules.channels import service
from app.modules.users.models import Role, User
from app.modules.videos.models import Video, VideoStatus, Visibility
from tests.interactions.conftest import OWNER_EMAIL, VIEWER_EMAIL, browser, signup, user_by_email
from tests.videos.factories import grant, make_video, set_role

URL = "/api/me/channel/videos"


async def my_videos(client: AsyncClient, **params: str) -> list[str]:
    response = await client.get(URL, params=params)
    assert response.status_code == 200, response.text
    return [item["id"] for item in response.json()["items"]]


async def all_pages(client: AsyncClient, sort: str) -> list[str]:
    ids: list[str] = []
    cursor = None
    while True:
        params = {"sort": sort} | ({"cursor": cursor} if cursor else {})
        body = (await client.get(URL, params=params)).json()
        ids += [item["id"] for item in body["items"]]
        if (cursor := body["next_cursor"]) is None:
            return ids


async def update_video(db: AsyncSession, video: Video, **values: object) -> None:
    await db.execute(update(Video).where(Video.id == video.id).values(**values))
    await db.commit()


@pytest.fixture
async def me(db: AsyncSession, owner: AsyncClient) -> User:
    return await user_by_email(db, OWNER_EMAIL)


async def test_lists_ready_videos_of_every_visibility_and_says_which(
    owner: AsyncClient, db: AsyncSession, me: User
) -> None:
    videos = [await make_video(db, me, visibility=visibility) for visibility in Visibility]

    response = await owner.get(URL)

    assert response.status_code == 200
    items = response.json()["items"]
    assert [(item["id"], item["visibility"]) for item in items] == [
        (video.public_id, video.visibility.value) for video in reversed(videos)
    ]
    assert items[0]["channel"]["handle"] == me.handle
    assert response.json()["next_cursor"] is None


async def test_hidden_videos_are_left_out(owner: AsyncClient, db: AsyncSession, me: User) -> None:
    shown = await make_video(db, me)
    for visibility in Visibility:
        await update_video(db, await make_video(db, me, visibility=visibility), is_hidden=True)

    assert await my_videos(owner) == [shown.public_id]


async def test_videos_not_ready_are_left_out(
    owner: AsyncClient, db: AsyncSession, me: User
) -> None:
    ready = await make_video(db, me, visibility=Visibility.PRIVATE)
    for status in VideoStatus:
        if status is not VideoStatus.READY:
            await make_video(db, me, status=status, visibility=Visibility.PRIVATE)

    assert await my_videos(owner) == [ready.public_id]


async def test_each_user_sees_only_their_own_strangers_allowed_users_and_moderators_too(
    app: FastAPI, owner: AsyncClient, viewer: AsyncClient, db: AsyncSession, me: User
) -> None:
    private = await make_video(db, me, visibility=Visibility.PRIVATE)
    public = await make_video(db, me)
    theirs = await make_video(db, await user_by_email(db, VIEWER_EMAIL))
    async with browser(app, "10.0.0.8") as allowed, browser(app, "10.0.0.9") as moderator:
        await signup(allowed, "allowed@example.com")
        await grant(db, private.public_id, "allowed@example.com")
        await signup(moderator, "mod@example.com")
        await set_role(db, "mod@example.com", Role.MODERATOR)

        assert await my_videos(owner) == [public.public_id, private.public_id]
        assert await my_videos(viewer) == [theirs.public_id]
        assert await my_videos(allowed) == []
        assert await my_videos(moderator) == []


@pytest.mark.parametrize(
    ("sort", "order"),
    [
        ("latest", [4, 3, 2, 1, 0]),
        ("oldest", [0, 1, 2, 3, 4]),
        ("popular", [4, 2, 0, 3, 1]),  # most viewed first, newer first on ties
    ],
)
async def test_sorts_across_pages_without_gaps_or_repeats(
    owner: AsyncClient,
    db: AsyncSession,
    me: User,
    monkeypatch: pytest.MonkeyPatch,
    sort: str,
    order: list[int],
) -> None:
    monkeypatch.setattr(service, "FEED_PAGE_SIZE", 2)
    visibilities = list(Visibility)
    videos = []
    for number in range(5):
        video = await make_video(db, me, visibility=visibilities[number % len(visibilities)])
        await update_video(db, video, view_count=(number + 1) % 2)
        videos.append(video)

    assert len(await my_videos(owner, sort=sort)) == 2
    assert await all_pages(owner, sort) == [videos[number].public_id for number in order]


async def test_guest_gets_401(guest: AsyncClient) -> None:
    response = await guest.get(URL)

    assert response.status_code == 401


async def test_unknown_sort_is_refused(owner: AsyncClient) -> None:
    response = await owner.get(URL, params={"sort": "random"})

    assert response.status_code == 422


@pytest.mark.parametrize(
    ("sort", "cursor"),
    [
        ("latest", "not base64!"),
        ("latest", encode_cursor((1, 2))),
        ("popular", encode_cursor(("0193a5c2-0000-7000-8000-000000000001",))),
    ],
)
async def test_bad_cursor_is_refused(owner: AsyncClient, sort: str, cursor: str) -> None:
    response = await owner.get(URL, params={"sort": sort, "cursor": cursor})

    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid cursor"}
