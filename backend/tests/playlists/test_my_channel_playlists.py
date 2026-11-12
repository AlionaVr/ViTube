"""GET /api/me/channel/playlists: your own channel's Playlists tab, every visibility."""

import pytest
from fastapi import FastAPI
from httpx2 import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import encode_cursor
from app.modules.playlists import service
from app.modules.playlists.models import Playlist, PlaylistKind
from app.modules.users.models import Role, User
from app.modules.videos.models import Visibility
from tests.interactions.conftest import OWNER_EMAIL, browser, signup, user_by_email
from tests.playlists.conftest import add, create
from tests.videos.factories import make_video, set_role

URL = "/api/me/channel/playlists"


async def titles(client: AsyncClient) -> list[str]:
    response = await client.get(URL)
    assert response.status_code == 200, response.text
    return [playlist["title"] for playlist in response.json()["items"]]


@pytest.fixture
async def me(db: AsyncSession, owner: AsyncClient) -> User:
    return await user_by_email(db, OWNER_EMAIL)


async def test_lists_every_playlist_you_made_newest_first_whatever_its_visibility(
    owner: AsyncClient,
) -> None:
    for visibility in ("public", "unlisted", "private"):
        await create(owner, visibility.title(), visibility=visibility)

    response = await owner.get(URL)

    assert response.status_code == 200
    assert [(p["title"], p["visibility"]) for p in response.json()["items"]] == [
        ("Private", "private"),
        ("Unlisted", "unlisted"),
        ("Public", "public"),
    ]
    assert response.json()["next_cursor"] is None


async def test_watch_later_is_left_out(owner: AsyncClient, db: AsyncSession, me: User) -> None:
    watch_later = await db.scalar(
        select(Playlist.id).where(
            Playlist.owner_id == me.id, Playlist.kind == PlaylistKind.WATCH_LATER
        )
    )
    assert (await add(owner, str(watch_later), await make_video(db, me))).is_success

    assert await titles(owner) == []


async def test_each_user_sees_only_their_own_moderators_too(
    app: FastAPI, owner: AsyncClient, viewer: AsyncClient, db: AsyncSession
) -> None:
    await create(owner, "Owner's private")
    await create(owner, "Owner's public", visibility="public")
    await create(viewer, "Viewer's", visibility="public")
    async with browser(app, "10.0.0.9") as moderator:
        await signup(moderator, "mod@example.com")
        await set_role(db, "mod@example.com", Role.MODERATOR)

        assert await titles(owner) == ["Owner's public", "Owner's private"]
        assert await titles(viewer) == ["Viewer's"]
        assert await titles(moderator) == []


async def test_cover_can_be_your_own_private_video(
    owner: AsyncClient, db: AsyncSession, me: User
) -> None:
    playlist_id = await create(owner, "Drafts")
    video = await make_video(db, me, visibility=Visibility.PRIVATE)
    await add(owner, playlist_id, video)

    [playlist] = (await owner.get(URL)).json()["items"]

    assert playlist["video_count"] == 1
    assert playlist["thumbnail_url"] == f"/media/{video.thumbnail_key}"


async def test_comes_in_pages(owner: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(service, "FEED_PAGE_SIZE", 2)
    for visibility in ("public", "unlisted", "private"):
        await create(owner, visibility.title(), visibility=visibility)

    first = (await owner.get(URL)).json()
    second = (await owner.get(URL, params={"cursor": first["next_cursor"]})).json()

    assert [p["title"] for p in first["items"]] == ["Private", "Unlisted"]
    assert [p["title"] for p in second["items"]] == ["Public"]
    assert second["next_cursor"] is None


async def test_guest_gets_401(guest: AsyncClient) -> None:
    response = await guest.get(URL)

    assert response.status_code == 401


async def test_bad_cursor_is_refused(owner: AsyncClient) -> None:
    response = await owner.get(URL, params={"cursor": encode_cursor(("not-a-uuid",))})

    assert response.status_code == 400
