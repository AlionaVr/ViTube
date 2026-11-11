"""Change and delete a playlist: the owner only, never Watch later."""

import asyncio
from collections.abc import Callable
from uuid import UUID

import pytest
from httpx2 import AsyncClient, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limit import RateLimit
from app.modules.playlists import service
from app.modules.playlists.models import PlaylistItem
from app.modules.users.models import User
from app.modules.videos.models import Video
from tests.interactions.conftest import OWNER_EMAIL, csrf, user_by_email
from tests.playlists.conftest import add, create, stored
from tests.videos.factories import make_video


@pytest.fixture
async def anna(db: AsyncSession, owner: AsyncClient) -> User:
    return await user_by_email(db, OWNER_EMAIL)


async def change(client: AsyncClient, playlist_id: str, **body: object) -> Response:
    return await client.patch(f"/api/playlists/{playlist_id}", json=body, headers=csrf(client))


async def drop(client: AsyncClient, playlist_id: str) -> Response:
    return await client.delete(f"/api/playlists/{playlist_id}", headers=csrf(client))


async def watch_later_id(client: AsyncClient) -> str:
    return (await client.get("/api/me/watch-later")).json()["id"]


async def items_in(db: AsyncSession, playlist_id: str) -> int:
    query = select(func.count()).where(PlaylistItem.playlist_id == UUID(playlist_id))
    return await db.scalar(query) or 0


# --- Change ---


async def test_the_owner_changes_a_playlist(owner: AsyncClient, guest: AsyncClient) -> None:
    playlist_id = await create(owner, "Old title")
    before = (await owner.get(f"/api/playlists/{playlist_id}")).json()

    response = await change(
        owner,
        playlist_id,
        title="  New title ",
        description="Line one\nline two",
        visibility="public",
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["title"], body["description"], body["visibility"]) == (
        "New title",
        "Line one\nline two",
        "public",
    )
    assert body["updated_at"] > before["updated_at"]
    assert (await guest.get(f"/api/playlists/{playlist_id}")).json()["title"] == "New title"


async def test_only_the_given_fields_change(owner: AsyncClient) -> None:
    playlist_id = await create(owner, "Kept")

    body = (await change(owner, playlist_id, visibility="unlisted", title=None)).json()

    assert (body["title"], body["visibility"]) == ("Kept", "unlisted")


async def test_an_empty_change_changes_nothing(owner: AsyncClient) -> None:
    playlist_id = await create(owner)
    before = (await owner.get(f"/api/playlists/{playlist_id}")).json()

    response = await change(owner, playlist_id)

    assert response.status_code == 200
    assert response.json()["updated_at"] == before["updated_at"]


@pytest.mark.parametrize(
    "body",
    [
        {"title": ""},
        {"title": "   "},
        {"title": "x" * 151},
        {"title": "two\nlines"},
        {"description": "x" * 5001},
        {"visibility": "friends"},
    ],
)
async def test_invalid_changes_are_refused(owner: AsyncClient, body: dict[str, str]) -> None:
    playlist_id = await create(owner, "Kept")

    assert (await change(owner, playlist_id, **body)).status_code == 422
    assert (await owner.get(f"/api/playlists/{playlist_id}")).json()["title"] == "Kept"


async def test_only_the_owner_changes(
    owner: AsyncClient, viewer: AsyncClient, guest: AsyncClient
) -> None:
    playlist_id = await create(owner, "Kept", visibility="public")

    response = await change(viewer, playlist_id, title="Mine now")
    assert response.status_code == 404  # a write to someone else's: as if it didn't exist
    assert response.json() == {"detail": "Playlist not found"}
    assert (await change(guest, playlist_id, title="Mine now")).status_code == 401
    assert (await change(owner, str(UUID(int=1)), title="x")).status_code == 404
    assert (await guest.get(f"/api/playlists/{playlist_id}")).json()["title"] == "Kept"


async def test_watch_later_cant_be_changed_or_deleted(owner: AsyncClient) -> None:
    playlist_id = await watch_later_id(owner)

    for response in (
        await change(owner, playlist_id, visibility="public"),
        await change(owner, playlist_id, title="Later"),
        await drop(owner, playlist_id),
    ):
        assert response.status_code == 400
    assert (await change(owner, playlist_id)).json() == {"detail": "Watch later can't be changed"}
    assert (await drop(owner, playlist_id)).json() == {"detail": "Watch later can't be deleted"}
    playlist = (await owner.get(f"/api/playlists/{playlist_id}")).json()
    assert (playlist["title"], playlist["visibility"]) == ("Watch later", "private")


# --- Delete ---


async def test_delete_a_playlist(owner: AsyncClient, db: AsyncSession, anna: User) -> None:
    playlist_id, kept_id = await create(owner), await create(owner, "Kept")
    video = await make_video(db, anna)
    await add(owner, playlist_id, video)
    await add(owner, kept_id, video)

    assert (await drop(owner, playlist_id)).status_code == 204

    assert (await owner.get(f"/api/playlists/{playlist_id}")).status_code == 404
    assert await items_in(db, playlist_id) == 0
    assert await db.get(Video, video.id) is not None  # the video stays
    assert await stored(db, kept_id) == (1, [0])  # and so do other playlists
    mine = (await owner.get("/api/me/playlists")).json()["items"]
    assert [p["title"] for p in mine] == ["Watch later", "Kept"]
    assert (await drop(owner, playlist_id)).status_code == 404  # gone


async def test_only_the_owner_deletes(
    owner: AsyncClient, viewer: AsyncClient, guest: AsyncClient
) -> None:
    playlist_id = await create(owner, visibility="public")

    assert (await drop(viewer, playlist_id)).status_code == 404
    assert (await drop(guest, playlist_id)).status_code == 401
    assert (await guest.get(f"/api/playlists/{playlist_id}")).status_code == 200


async def test_changes_and_deletes_are_rate_limited(
    owner: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    playlist_id = await create(owner)
    monkeypatch.setattr(service, "PLAYLIST_WRITES", RateLimit("playlist_write", 1, 60))
    await change(owner, playlist_id, title="Once")

    assert (await change(owner, playlist_id, title="Twice")).status_code == 429
    assert (await drop(owner, playlist_id)).status_code == 429


# --- Races ---


async def test_adds_racing_a_delete_finish_first_or_find_no_playlist(
    owner: AsyncClient, db: AsyncSession, anna: User, at_the_lock: Callable[[int], None]
) -> None:
    playlist_id = await create(owner)
    videos = [await make_video(db, anna) for _ in range(4)]

    at_the_lock(len(videos) + 1)
    deleted, *adds = await asyncio.gather(
        drop(owner, playlist_id), *(add(owner, playlist_id, video) for video in videos)
    )

    assert deleted.status_code == 204
    assert {r.status_code for r in adds} <= {204, 404}  # before the delete, or after it
    assert await items_in(db, playlist_id) == 0  # nothing added to a deleted playlist
