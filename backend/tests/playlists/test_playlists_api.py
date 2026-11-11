"""Playlists: create, read, add videos; who sees what; repeated and parallel adds."""

import asyncio
from collections.abc import Callable
from uuid import UUID

import pytest
from httpx2 import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import encode_cursor
from app.core.rate_limit import RateLimit
from app.modules.playlists import service
from app.modules.playlists.models import MAX_VIDEOS, Playlist
from app.modules.users.models import User
from app.modules.videos.models import Video, VideoStatus, Visibility
from tests.interactions.conftest import (
    OWNER_EMAIL,
    VIEWER_EMAIL,
    csrf,
    meet_after,
    user_by_email,
)
from tests.playlists.conftest import add, create, item_ids, remove, stored
from tests.videos.factories import grant, make_user, make_video

PARALLEL = 8


@pytest.fixture
async def anna(db: AsyncSession, owner: AsyncClient) -> User:
    """The owner client's account."""
    return await user_by_email(db, OWNER_EMAIL)


async def set_visibility(db: AsyncSession, video: Video, visibility: Visibility) -> None:
    await db.execute(update(Video).where(Video.id == video.id).values(visibility=visibility))
    await db.commit()


# --- Create ---


async def test_create_a_playlist(owner: AsyncClient, anna: User) -> None:
    response = await owner.post(
        "/api/playlists",
        json={"title": "  Trailers  ", "description": "Line one\nline two"},
        headers=csrf(owner),
    )

    assert response.status_code == 201
    body = response.json()
    assert UUID(body["id"]).version == 7
    assert {key: body[key] for key in ("title", "description", "visibility", "video_count")} == {
        "title": "Trailers",
        "description": "Line one\nline two",
        "visibility": "private",
        "video_count": 0,
    }
    assert body["thumbnail_url"] is None
    assert body["owner"] == {"handle": anna.handle, "name": anna.handle, "avatar_url": None}


@pytest.mark.parametrize(
    "body",
    [
        {"title": ""},
        {"title": "   "},
        {"title": "x" * 151},
        {"title": "two\nlines"},
        {"title": "nul\x00"},
        {"title": "ok", "description": "nul\x00"},
        {"title": "ok", "description": "x" * 5001},
        {"title": "ok", "visibility": "friends"},
    ],
)
async def test_invalid_playlist_is_refused(owner: AsyncClient, body: dict[str, str]) -> None:
    response = await owner.post("/api/playlists", json=body, headers=csrf(owner))

    assert response.status_code == 422


async def test_guest_cant_create(guest: AsyncClient) -> None:
    assert (await guest.post("/api/playlists", json={"title": "x"})).status_code == 401


async def test_creating_is_rate_limited(
    owner: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(service, "PLAYLISTS_CREATED", RateLimit("playlist_create", 1, 60))
    await create(owner)

    response = await owner.post("/api/playlists", json={"title": "x"}, headers=csrf(owner))

    assert response.status_code == 429


# --- Read ---


@pytest.mark.parametrize("visibility", ["public", "unlisted"])
async def test_anyone_reads_a_public_or_unlisted_playlist(
    owner: AsyncClient, guest: AsyncClient, visibility: str
) -> None:
    playlist_id = await create(owner, visibility=visibility)

    response = await guest.get(f"/api/playlists/{playlist_id}")

    assert response.status_code == 200
    assert response.json()["visibility"] == visibility


async def test_a_private_playlist_is_the_owners_alone(
    owner: AsyncClient, viewer: AsyncClient, guest: AsyncClient
) -> None:
    playlist_id = await create(owner)

    assert (await owner.get(f"/api/playlists/{playlist_id}")).status_code == 200
    for other in (viewer, guest):
        for path in ("", "/items"):
            response = await other.get(f"/api/playlists/{playlist_id}{path}")
            # The same answer as for a playlist that doesn't exist.
            assert response.status_code == 404
            assert response.json() == {"detail": "Playlist not found"}


async def test_unknown_or_malformed_playlist(guest: AsyncClient) -> None:
    assert (await guest.get(f"/api/playlists/{UUID(int=1)}")).status_code == 404
    assert (await guest.get("/api/playlists/not-a-uuid")).status_code == 422


# --- Add ---


async def test_add_videos_in_order(owner: AsyncClient, db: AsyncSession, anna: User) -> None:
    playlist_id = await create(owner)
    videos = [await make_video(db, anna) for _ in range(3)]

    for video in videos:
        assert (await add(owner, playlist_id, video)).status_code == 204

    assert await item_ids(owner, playlist_id) == [video.public_id for video in videos]
    assert await stored(db, playlist_id) == (3, [0, 1, 2])
    item = (await owner.get(f"/api/playlists/{playlist_id}/items")).json()["items"][0]
    assert item["video"]["channel"]["handle"] == anna.handle
    assert item["added_at"]


async def test_adding_again_changes_nothing(
    owner: AsyncClient, db: AsyncSession, anna: User
) -> None:
    playlist_id = await create(owner)
    video = await make_video(db, anna)
    playlist = (await owner.get(f"/api/playlists/{playlist_id}")).json()

    for _ in range(3):
        assert (await add(owner, playlist_id, video)).status_code == 204

    assert await stored(db, playlist_id) == (1, [0])
    after = (await owner.get(f"/api/playlists/{playlist_id}")).json()
    assert after["updated_at"] > playlist["updated_at"]


async def test_videos_of_other_channels_can_be_added(owner: AsyncClient, db: AsyncSession) -> None:
    playlist_id = await create(owner)
    video = await make_video(db, await make_user(db, "bob"))

    assert (await add(owner, playlist_id, video)).status_code == 204


@pytest.mark.parametrize(
    ("visibility", "status"),
    [
        (Visibility.PRIVATE, VideoStatus.READY),  # someone else's private video
        (Visibility.PUBLIC, VideoStatus.PROCESSING),
        (Visibility.PUBLIC, VideoStatus.FAILED),
    ],
)
async def test_only_videos_you_may_watch_can_be_added(
    owner: AsyncClient, db: AsyncSession, visibility: Visibility, status: VideoStatus
) -> None:
    playlist_id = await create(owner)
    video = await make_video(db, await make_user(db, "bob"), visibility=visibility, status=status)

    response = await add(owner, playlist_id, video)

    assert response.status_code == 404
    assert response.json() == {"detail": "Video not found"}
    assert await stored(db, playlist_id) == (0, [])


async def test_own_and_shared_private_videos_can_be_added(
    owner: AsyncClient, db: AsyncSession, anna: User
) -> None:
    playlist_id = await create(owner)
    mine = await make_video(db, anna, visibility=Visibility.PRIVATE)
    shared = await make_video(db, await make_user(db, "bob"), visibility=Visibility.PRIVATE)
    await grant(db, shared.public_id, OWNER_EMAIL)

    assert (await add(owner, playlist_id, mine)).status_code == 204
    assert (await add(owner, playlist_id, shared)).status_code == 204


async def test_only_the_owner_adds(
    owner: AsyncClient, viewer: AsyncClient, guest: AsyncClient, db: AsyncSession, anna: User
) -> None:
    playlist_id = await create(owner, visibility="public")
    video = await make_video(db, anna)

    response = await add(viewer, playlist_id, video)
    assert response.status_code == 404
    assert response.json() == {"detail": "Playlist not found"}
    assert (await add(guest, playlist_id, video)).status_code == 401
    assert (await add(owner, str(UUID(int=1)), video)).status_code == 404
    assert await stored(db, playlist_id) == (0, [])


async def test_a_full_playlist_takes_no_new_video(
    owner: AsyncClient, db: AsyncSession, anna: User
) -> None:
    playlist_id = await create(owner)
    inside, new = await make_video(db, anna), await make_video(db, anna)
    await add(owner, playlist_id, inside)
    await db.execute(
        update(Playlist).where(Playlist.id == UUID(playlist_id)).values(video_count=MAX_VIDEOS)
    )
    await db.commit()

    response = await add(owner, playlist_id, new)

    assert response.status_code == 409
    assert response.json() == {"detail": f"A playlist holds at most {MAX_VIDEOS} videos"}
    assert (await add(owner, playlist_id, inside)).status_code == 204  # already there: fine


async def test_item_writes_are_rate_limited(
    owner: AsyncClient, db: AsyncSession, anna: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(service, "PLAYLIST_WRITES", RateLimit("playlist_write", 1, 60))
    playlist_id = await create(owner)
    await add(owner, playlist_id, await make_video(db, anna))

    assert (await add(owner, playlist_id, await make_video(db, anna))).status_code == 429


# --- Remove ---


async def test_remove_leaves_the_others_in_place(
    owner: AsyncClient, db: AsyncSession, anna: User
) -> None:
    playlist_id = await create(owner)
    videos = [await make_video(db, anna) for _ in range(3)]
    for video in videos:
        await add(owner, playlist_id, video)

    for _ in range(2):  # again: nothing changes
        assert (await remove(owner, playlist_id, videos[1])).status_code == 204

    assert await stored(db, playlist_id) == (2, [0, 2])  # a gap, no shift
    assert await item_ids(owner, playlist_id) == [videos[0].public_id, videos[2].public_id]
    await add(owner, playlist_id, videos[1])
    assert await stored(db, playlist_id) == (3, [0, 2, 3])  # back at the end


async def test_a_video_that_turned_private_can_still_be_removed(
    owner: AsyncClient, db: AsyncSession
) -> None:
    playlist_id = await create(owner)
    video = await make_video(db, await make_user(db, "bob"))
    await add(owner, playlist_id, video)
    await set_visibility(db, video, Visibility.PRIVATE)

    assert (await remove(owner, playlist_id, video)).status_code == 204
    assert await stored(db, playlist_id) == (0, [])


async def test_removing_an_unknown_video_changes_nothing(
    owner: AsyncClient, db: AsyncSession
) -> None:
    playlist_id = await create(owner)

    response = await owner.delete(
        f"/api/playlists/{playlist_id}/items/nosuchvide0", headers=csrf(owner)
    )

    assert response.status_code == 204
    assert await stored(db, playlist_id) == (0, [])


async def test_only_the_owner_removes(
    owner: AsyncClient, viewer: AsyncClient, guest: AsyncClient, db: AsyncSession, anna: User
) -> None:
    playlist_id = await create(owner, visibility="public")
    video = await make_video(db, anna)
    await add(owner, playlist_id, video)

    assert (await remove(viewer, playlist_id, video)).status_code == 404
    assert (await remove(guest, playlist_id, video)).status_code == 401
    assert await stored(db, playlist_id) == (1, [0])


# --- Who sees which items ---


async def test_items_are_the_videos_this_viewer_may_watch(
    owner: AsyncClient, viewer: AsyncClient, guest: AsyncClient, db: AsyncSession, anna: User
) -> None:
    playlist_id = await create(owner, visibility="public")
    bob = await make_user(db, "bob")
    first, second, third = [await make_video(db, bob) for _ in range(3)]
    for video in (first, second, third):
        await add(owner, playlist_id, video)
    # After they were added: one turns private, shared with the viewer only.
    await set_visibility(db, second, Visibility.PRIVATE)
    await grant(db, second.public_id, VIEWER_EMAIL)

    assert await item_ids(guest, playlist_id) == [first.public_id, third.public_id]
    assert await item_ids(owner, playlist_id) == [first.public_id, third.public_id]
    assert await item_ids(viewer, playlist_id) == [v.public_id for v in (first, second, third)]
    # The count is every item: it tells the owner some are hidden.
    assert (await guest.get(f"/api/playlists/{playlist_id}")).json()["video_count"] == 3


async def test_the_cover_is_the_first_video_this_viewer_may_watch(
    owner: AsyncClient, viewer: AsyncClient, guest: AsyncClient, db: AsyncSession, anna: User
) -> None:
    playlist_id = await create(owner, visibility="public")
    bob = await make_user(db, "bob")
    first, second = await make_video(db, bob), await make_video(db, bob)
    await add(owner, playlist_id, first)
    await add(owner, playlist_id, second)
    await set_visibility(db, first, Visibility.PRIVATE)
    await grant(db, first.public_id, VIEWER_EMAIL)

    def cover(body: dict[str, object]) -> object:
        return body["thumbnail_url"]

    url = f"/api/playlists/{playlist_id}"
    assert cover((await guest.get(url)).json()) == f"/media/thumbs/{second.id}.jpg"
    assert cover((await viewer.get(url)).json()) == f"/media/thumbs/{first.id}.jpg"
    await set_visibility(db, second, Visibility.PRIVATE)
    assert cover((await guest.get(url)).json()) is None


async def test_a_grant_on_another_video_shows_neither_item_nor_cover(
    owner: AsyncClient, viewer: AsyncClient, db: AsyncSession, anna: User
) -> None:
    playlist_id = await create(owner, visibility="public")
    bob = await make_user(db, "bob")
    inside, elsewhere = await make_video(db, bob), await make_video(db, bob)
    await add(owner, playlist_id, inside)
    for video in (inside, elsewhere):
        await set_visibility(db, video, Visibility.PRIVATE)
    await grant(db, elsewhere.public_id, VIEWER_EMAIL)

    assert await item_ids(viewer, playlist_id) == []
    assert (await viewer.get(f"/api/playlists/{playlist_id}")).json()["thumbnail_url"] is None


async def test_items_come_in_pages(owner: AsyncClient, db: AsyncSession, anna: User) -> None:
    playlist_id = await create(owner)
    videos = [await make_video(db, anna) for _ in range(service.ITEMS_PAGE_SIZE + 2)]
    for video in videos:
        await add(owner, playlist_id, video)
    url = f"/api/playlists/{playlist_id}/items"

    first = (await owner.get(url)).json()
    rest = (await owner.get(url, params={"cursor": first["next_cursor"]})).json()

    ids = [item["video"]["id"] for item in first["items"] + rest["items"]]
    assert len(first["items"]) == service.ITEMS_PAGE_SIZE
    assert ids == [video.public_id for video in videos]
    assert rest["next_cursor"] is None


@pytest.mark.parametrize("key", [(-1,), (2**31,), ("x",), (1, 2)])
async def test_bad_items_cursor_is_refused(owner: AsyncClient, key: tuple[object, ...]) -> None:
    playlist_id = await create(owner)

    response = await owner.get(
        f"/api/playlists/{playlist_id}/items", params={"cursor": encode_cursor(key)}
    )

    assert response.status_code == 400


# --- My playlists ---


async def test_my_playlists_newest_first_and_mine_only(
    owner: AsyncClient, viewer: AsyncClient, db: AsyncSession, anna: User
) -> None:
    older = await create(owner, "Older")
    newer = await create(owner, "Newer", visibility="public")
    await create(viewer, "Someone else's")
    video = await make_video(db, anna)
    await add(owner, older, video)

    body = (await owner.get("/api/me/playlists")).json()

    watch_later, *rest = body["items"]
    assert watch_later["kind"] == "watch_later"  # always first
    assert [item["id"] for item in rest] == [newer, older]
    assert {item["contains_video"] for item in body["items"]} == {None}
    assert rest[1]["thumbnail_url"] == f"/media/thumbs/{video.id}.jpg"
    assert body["next_cursor"] is None


async def test_my_playlists_say_which_hold_a_video(
    owner: AsyncClient, db: AsyncSession, anna: User
) -> None:
    with_it, without = await create(owner), await create(owner)
    video = await make_video(db, anna)
    await add(owner, with_it, video)

    body = (await owner.get("/api/me/playlists", params={"video": video.public_id})).json()
    unknown = (await owner.get("/api/me/playlists", params={"video": "nosuchvide0"})).json()

    holds = {item["id"]: item["contains_video"] for item in body["items"]}
    watch_later = body["items"][0]["id"]
    assert holds == {watch_later: False, with_it: True, without: False}
    assert {item["contains_video"] for item in unknown["items"]} == {False}


async def test_my_playlists_need_a_user_and_a_valid_video_id(
    guest: AsyncClient, owner: AsyncClient
) -> None:
    assert (await guest.get("/api/me/playlists")).status_code == 401
    assert (await owner.get("/api/me/playlists", params={"video": "short"})).status_code == 422


# --- Parallel adds ---


@pytest.fixture
def together(monkeypatch: pytest.MonkeyPatch) -> Callable[[], None]:
    """Parallel requests wait for each other before the playlist lock, then race for it."""
    return lambda: meet_after(monkeypatch, service, "get_ready", PARALLEL)


async def test_parallel_adds_of_different_videos_all_land_in_distinct_places(
    owner: AsyncClient, db: AsyncSession, anna: User, together: Callable[[], None]
) -> None:
    playlist_id = await create(owner)
    videos = [await make_video(db, anna) for _ in range(PARALLEL)]

    together()
    responses = await asyncio.gather(*(add(owner, playlist_id, video) for video in videos))

    assert [r.status_code for r in responses] == [204] * PARALLEL
    assert await stored(db, playlist_id) == (PARALLEL, list(range(PARALLEL)))
    assert sorted(await item_ids(owner, playlist_id)) == sorted(v.public_id for v in videos)


async def test_parallel_adds_of_one_video_count_once(
    owner: AsyncClient, db: AsyncSession, anna: User, together: Callable[[], None]
) -> None:
    playlist_id = await create(owner)
    video = await make_video(db, anna)

    together()
    responses = await asyncio.gather(*(add(owner, playlist_id, video) for _ in range(PARALLEL)))

    assert [r.status_code for r in responses] == [204] * PARALLEL
    assert await stored(db, playlist_id) == (1, [0])
