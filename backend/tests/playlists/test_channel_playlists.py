"""A channel's Playlists tab: its public playlists only, the same for every viewer."""

import pytest
from httpx2 import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import encode_cursor
from app.modules.playlists import service
from app.modules.users.models import User
from app.modules.videos.models import Visibility
from tests.interactions.conftest import OWNER_EMAIL, csrf, user_by_email
from tests.playlists.conftest import add, create
from tests.videos.factories import make_video


@pytest.fixture
async def anna(db: AsyncSession, owner: AsyncClient) -> User:
    return await user_by_email(db, OWNER_EMAIL)


def url(user: User) -> str:
    return f"/api/channels/{user.handle}/playlists"


async def titles(client: AsyncClient, user: User) -> list[str]:
    response = await client.get(url(user))
    assert response.status_code == 200, response.text
    return [playlist["title"] for playlist in response.json()["items"]]


async def test_only_public_playlists_newest_first_for_everyone(
    owner: AsyncClient, viewer: AsyncClient, guest: AsyncClient, anna: User
) -> None:
    await create(owner, "Old public", visibility="public")
    await create(owner, "Unlisted", visibility="unlisted")
    await create(owner, "Private")
    await create(owner, "New public", visibility="public")
    await create(viewer, "Someone else's", visibility="public")

    # Watch later is private: never on the tab. The owner sees what everyone sees.
    for client in (guest, viewer, owner):
        assert await titles(client, anna) == ["New public", "Old public"]


async def test_a_playlist_made_private_leaves_the_tab(
    owner: AsyncClient, guest: AsyncClient, anna: User
) -> None:
    playlist_id = await create(owner, "Soon private", visibility="public")
    await owner.patch(
        f"/api/playlists/{playlist_id}",
        json={"visibility": Visibility.PRIVATE.value},
        headers=csrf(owner),
    )

    assert await titles(guest, anna) == []


async def test_each_playlist_has_its_owner_count_and_cover(
    owner: AsyncClient, guest: AsyncClient, db: AsyncSession, anna: User
) -> None:
    playlist_id = await create(owner, "Films", visibility="public")
    video = await make_video(db, anna)
    await add(owner, playlist_id, video)

    [playlist] = (await guest.get(url(anna))).json()["items"]

    assert playlist["owner"]["handle"] == anna.handle
    assert playlist["video_count"] == 1
    assert playlist["thumbnail_url"] == f"/media/{video.thumbnail_key}"


async def test_comes_in_pages(
    owner: AsyncClient, guest: AsyncClient, anna: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(service, "FEED_PAGE_SIZE", 2)
    for number in range(3):
        await create(owner, f"Public {number}", visibility="public")

    first = (await guest.get(url(anna))).json()
    second = (await guest.get(url(anna), params={"cursor": first["next_cursor"]})).json()

    assert [p["title"] for p in first["items"]] == ["Public 2", "Public 1"]
    assert [p["title"] for p in second["items"]] == ["Public 0"]
    assert second["next_cursor"] is None


async def test_unknown_or_malformed_channel_and_bad_cursor(guest: AsyncClient, anna: User) -> None:
    assert (await guest.get("/api/channels/nobody-here/playlists")).status_code == 404
    assert (await guest.get("/api/channels/bad%20handle/playlists")).status_code == 422
    bad = encode_cursor(("not-a-uuid",))
    assert (await guest.get(url(anna), params={"cursor": bad})).status_code == 400
