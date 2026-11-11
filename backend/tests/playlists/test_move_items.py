"""Reorder a playlist: move a video before another one, or to the end; in parallel too."""

import asyncio
import itertools
import random
from collections.abc import Callable, Sequence
from uuid import UUID

import pytest
from httpx2 import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limit import RateLimit
from app.modules.playlists import service
from app.modules.users.models import User
from app.modules.videos.models import Video, Visibility
from tests.interactions.conftest import OWNER_EMAIL, VIEWER_EMAIL, csrf, user_by_email
from tests.playlists.conftest import add, create, item_ids, move, remove, stored
from tests.videos.factories import make_video


@pytest.fixture
async def anna(db: AsyncSession, owner: AsyncClient) -> User:
    return await user_by_email(db, OWNER_EMAIL)


async def filled(
    owner: AsyncClient, db: AsyncSession, anna: User, count: int
) -> tuple[str, list[Video]]:
    playlist_id = await create(owner)
    videos = [await make_video(db, anna) for _ in range(count)]
    for video in videos:
        assert (await add(owner, playlist_id, video)).status_code == 204
    return playlist_id, videos


def ids(videos: Sequence[Video]) -> list[str]:
    return [video.public_id for video in videos]


def moved(order: Sequence[Video], video: Video, before: Video | None) -> list[Video]:
    """The model: the same move on a Python list."""
    rest = [v for v in order if v is not video]
    at = rest.index(before) if before else len(rest)
    return [*rest[:at], video, *rest[at:]]


# --- One move ---


@pytest.mark.parametrize(
    ("which", "before", "expected"),
    [
        (0, 3, [1, 2, 0, 3]),  # later
        (3, 1, [0, 3, 1, 2]),  # earlier
        (2, 0, [2, 0, 1, 3]),  # to the top
        (1, None, [0, 2, 3, 1]),  # to the end
        (1, 2, [0, 1, 2, 3]),  # before the next one: same order
        (3, None, [0, 1, 2, 3]),  # the last to the end: same order
    ],
)
async def test_move_a_video(
    owner: AsyncClient,
    db: AsyncSession,
    anna: User,
    which: int,
    before: int | None,
    expected: list[int],
) -> None:
    playlist_id, videos = await filled(owner, db, anna, 4)

    response = await move(
        owner, playlist_id, videos[which], None if before is None else videos[before]
    )

    assert response.status_code == 204, response.text
    assert await item_ids(owner, playlist_id) == ids([videos[n] for n in expected])
    count, _ = await stored(db, playlist_id)
    assert count == 4


async def test_moves_work_across_gaps(owner: AsyncClient, db: AsyncSession, anna: User) -> None:
    playlist_id, videos = await filled(owner, db, anna, 6)
    for gone in (videos[1], videos[3]):
        await remove(owner, playlist_id, gone)
    order = [videos[0], videos[2], videos[4], videos[5]]  # positions 0, 2, 4, 5

    for video, before in ((videos[0], videos[5]), (videos[5], videos[2]), (videos[2], None)):
        assert (await move(owner, playlist_id, video, before)).status_code == 204
        order = moved(order, video, before)
        assert await item_ids(owner, playlist_id) == ids(order)


async def test_a_move_refreshes_updated_at(
    owner: AsyncClient, db: AsyncSession, anna: User
) -> None:
    playlist_id, videos = await filled(owner, db, anna, 2)
    before = (await owner.get(f"/api/playlists/{playlist_id}")).json()["updated_at"]

    await move(owner, playlist_id, videos[1], videos[0])

    assert (await owner.get(f"/api/playlists/{playlist_id}")).json()["updated_at"] > before


async def test_a_video_that_turned_private_can_still_be_moved(
    owner: AsyncClient, viewer: AsyncClient, db: AsyncSession
) -> None:
    """Moved by its place among all items, also those the owner can no longer watch."""
    bob = await user_by_email(db, VIEWER_EMAIL)
    playlist_id = await create(owner)
    hidden, shown = await make_video(db, bob), await make_video(db, bob)
    for video in (hidden, shown):
        await add(owner, playlist_id, video)
    await db.execute(
        update(Video).where(Video.id == hidden.id).values(visibility=Visibility.PRIVATE)
    )
    await db.commit()

    assert (await move(owner, playlist_id, hidden, None)).status_code == 204
    assert (await move(owner, playlist_id, hidden, shown)).status_code == 204
    assert await item_ids(owner, playlist_id) == [shown.public_id]  # it stays hidden


# --- Refused ---


async def test_a_video_cant_move_before_itself(
    owner: AsyncClient, db: AsyncSession, anna: User
) -> None:
    playlist_id, videos = await filled(owner, db, anna, 2)

    response = await move(owner, playlist_id, videos[0], videos[0])

    assert response.status_code == 400
    assert response.json() == {"detail": "A video can't move before itself"}


async def test_both_videos_must_be_in_the_playlist(
    owner: AsyncClient, db: AsyncSession, anna: User
) -> None:
    playlist_id, videos = await filled(owner, db, anna, 2)
    outside = await make_video(db, anna)

    for video, before in ((outside, videos[0]), (videos[0], outside), (outside, None)):
        response = await move(owner, playlist_id, video, before)
        assert response.status_code == 404
        assert response.json() == {"detail": "Video not in this playlist"}
    unknown = await owner.patch(
        f"/api/playlists/{playlist_id}/items/nosuchvide0",
        json={"before": None},
        headers=csrf(owner),
    )
    assert unknown.status_code == 404
    assert await item_ids(owner, playlist_id) == ids(videos)


@pytest.mark.parametrize("body", [{}, {"before": "short"}, {"before": 5}])
async def test_a_malformed_move_is_refused(
    owner: AsyncClient, db: AsyncSession, anna: User, body: dict[str, object]
) -> None:
    playlist_id, videos = await filled(owner, db, anna, 1)
    url = f"/api/playlists/{playlist_id}/items/{videos[0].public_id}"

    assert (await owner.patch(url, json=body, headers=csrf(owner))).status_code == 422


async def test_only_the_owner_moves(
    owner: AsyncClient, viewer: AsyncClient, guest: AsyncClient, db: AsyncSession, anna: User
) -> None:
    playlist_id, videos = await filled(owner, db, anna, 2)
    await owner.patch(
        f"/api/playlists/{playlist_id}", json={"visibility": "public"}, headers=csrf(owner)
    )

    response = await move(viewer, playlist_id, videos[1], videos[0])
    assert response.status_code == 404
    assert response.json() == {"detail": "Playlist not found"}
    assert (await move(guest, playlist_id, videos[1], videos[0])).status_code == 401
    assert (await move(owner, str(UUID(int=1)), videos[1], videos[0])).status_code == 404
    assert await item_ids(owner, playlist_id) == ids(videos)


async def test_moves_are_rate_limited(
    owner: AsyncClient, db: AsyncSession, anna: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    playlist_id, videos = await filled(owner, db, anna, 2)
    monkeypatch.setattr(service, "PLAYLIST_WRITES", RateLimit("playlist_write", 1, 60))
    await move(owner, playlist_id, videos[1], videos[0])

    assert (await move(owner, playlist_id, videos[0], videos[1])).status_code == 429


# --- Against a model ---


async def test_random_adds_removes_and_moves_match_a_list(
    owner: AsyncClient, db: AsyncSession, anna: User
) -> None:
    """Each step through the API and on a Python list: the orders never differ."""
    rng = random.Random(6)  # noqa: S311 - a fixed seed: a failure replays
    playlist_id = await create(owner)
    pool = [await make_video(db, anna) for _ in range(6)]
    order: list[Video] = []

    for _ in range(60):
        step = rng.choice(["add", "remove", "move", "move"]) if order else "add"
        if step == "add":
            video = rng.choice(pool)
            response = await add(owner, playlist_id, video)
            order = order if video in order else [*order, video]
        elif step == "remove":
            video = rng.choice(pool)
            response = await remove(owner, playlist_id, video)
            order = [v for v in order if v is not video]
        else:
            video = rng.choice(order)
            before = rng.choice([*(v for v in order if v is not video), None])
            response = await move(owner, playlist_id, video, before)
            order = moved(order, video, before)
        assert response.status_code == 204, (step, response.text)
        assert await item_ids(owner, playlist_id) == ids(order), step

    count, positions = await stored(db, playlist_id)
    assert count == len(order) == len(positions)


# --- Races ---


async def test_parallel_moves_end_in_one_of_their_serial_orders(
    owner: AsyncClient, db: AsyncSession, anna: User, at_the_lock: Callable[[int], None]
) -> None:
    playlist_id, videos = await filled(owner, db, anna, 5)
    a, b, c, d, e = videos
    moves = [(a, None), (e, b), (c, a)]
    serial = {tuple(ids(_apply(videos, list(order)))) for order in itertools.permutations(moves)}

    at_the_lock(len(moves))
    responses = await asyncio.gather(
        *(move(owner, playlist_id, video, before) for video, before in moves)
    )

    assert [r.status_code for r in responses] == [204] * len(moves)
    assert tuple(await item_ids(owner, playlist_id)) in serial
    count, positions = await stored(db, playlist_id)
    assert count == len(positions) == 5


def _apply(order: list[Video], moves: list[tuple[Video, Video | None]]) -> list[Video]:
    for video, before in moves:
        order = moved(order, video, before)
    return order


async def test_add_remove_and_move_of_one_video_in_parallel_stay_consistent(
    owner: AsyncClient, db: AsyncSession, anna: User, at_the_lock: Callable[[int], None]
) -> None:
    playlist_id, (first, video, last) = await filled(owner, db, anna, 3)

    for _ in range(3):  # rounds: the order of arrival at the lock varies
        at_the_lock(4)
        responses = await asyncio.gather(
            remove(owner, playlist_id, video),
            move(owner, playlist_id, video, first),
            add(owner, playlist_id, video),
            move(owner, playlist_id, last, video),
        )
        assert {r.status_code for r in responses} <= {204, 404}  # 404: moved a removed video
        count, positions = await stored(db, playlist_id)
        assert count == len(positions)
        assert set(await item_ids(owner, playlist_id)) <= set(ids([first, video, last]))
