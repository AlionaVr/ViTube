"""PUT /api/me/history/{id} and GET /api/me/history: where a user stopped, last watched first."""

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from httpx2 import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import encode_cursor
from app.core.rate_limit import RateLimit
from app.modules.history import service
from app.modules.history.models import HistoryEntry
from app.modules.videos.models import Video, VideoStatus, Visibility
from tests.history.conftest import listed, make_private, position, row_count, save
from tests.interactions.conftest import OWNER_EMAIL, VIEWER_EMAIL, csrf, meet_after, user_by_email
from tests.videos.factories import grant, make_user, make_video, set_status

NOT_READY = [status for status in VideoStatus if status is not VideoStatus.READY]
PARALLEL = 10


async def owners_private_video(db: AsyncSession) -> Video:
    return await make_video(db, await user_by_email(db, OWNER_EMAIL), visibility=Visibility.PRIVATE)


# --- Saving ---


async def test_saved_video_shows_in_history(
    viewer: AsyncClient, video: Video, db: AsyncSession
) -> None:
    assert await listed(viewer) == []

    response = await save(viewer, video, 5)

    assert response.status_code == 204
    assert await position(db, VIEWER_EMAIL, video) == 5
    body = (await viewer.get("/api/me/history")).json()
    [item] = body["items"]
    channel = await user_by_email(db, OWNER_EMAIL)
    assert (item["video"]["id"], item["video"]["channel"]["handle"]) == (
        video.public_id,
        channel.handle,
    )
    assert datetime.fromisoformat(item["watched_at"]).tzinfo is not None
    assert body["next_cursor"] is None


async def test_guest_gets_401(guest: AsyncClient, video: Video) -> None:
    assert (await save(guest, video)).status_code == 401
    assert (await guest.get("/api/me/history")).status_code == 401


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"position_sec": None},
        {"position_sec": -1},
        {"position_sec": 2**31},
        {"position_sec": 1.5},
        {"position_sec": "abc"},
    ],
)
async def test_bad_position_gets_422(
    owner: AsyncClient, video: Video, db: AsyncSession, body: dict[str, object]
) -> None:
    response = await owner.put(f"/api/me/history/{video.public_id}", json=body, headers=csrf(owner))

    assert response.status_code == 422
    assert await row_count(db) == 0


@pytest.mark.parametrize(("sent", "stored"), [(0, 0), (10, 10), (11, 10), (2**31 - 1, 10)])
async def test_position_past_the_end_is_saved_as_the_end(
    owner: AsyncClient, video: Video, db: AsyncSession, sent: int, stored: int
) -> None:
    assert (await save(owner, video, sent)).status_code == 204  # the factory's video lasts 10 s

    assert await position(db, OWNER_EMAIL, video) == stored


async def test_saving_again_keeps_one_row_and_moves_the_video_to_the_top(
    owner: AsyncClient, db: AsyncSession
) -> None:
    channel = await make_user(db, "anna")
    first, second = await make_video(db, channel), await make_video(db, channel)
    await save(owner, first, 3)
    await save(owner, second)
    assert await listed(owner) == [second.public_id, first.public_id]

    assert (await save(owner, first, 7)).status_code == 204

    assert await listed(owner) == [first.public_id, second.public_id]
    assert await position(db, OWNER_EMAIL, first) == 7
    assert await row_count(db) == 2


async def test_parallel_first_saves_keep_one_row(
    owner: AsyncClient, video: Video, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    meet_after(monkeypatch, service, "get_ready", PARALLEL)

    responses = await asyncio.gather(*(save(owner, video, n) for n in range(PARALLEL)))

    assert [response.status_code for response in responses] == [204] * PARALLEL
    assert await row_count(db) == 1


async def test_saves_are_rate_limited_per_user(
    owner: AsyncClient,
    viewer: AsyncClient,
    video: Video,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(service, "HISTORY_WRITES", RateLimit("history_write", 2, 60))
    for _ in range(2):
        assert (await save(owner, video)).status_code == 204

    too_many = await save(owner, video)

    assert too_many.status_code == 429
    assert int(too_many.headers["Retry-After"]) > 0
    assert (await save(viewer, video)).status_code == 204  # another account has its own budget


# --- Which videos ---


async def test_unknown_or_malformed_id_is_refused(owner: AsyncClient) -> None:
    body = {"position_sec": 1}
    headers = csrf(owner)

    unknown = await owner.put("/api/me/history/nosuchvide0", json=body, headers=headers)
    malformed = await owner.put("/api/me/history/bad", json=body, headers=headers)

    assert (unknown.status_code, malformed.status_code) == (404, 422)


@pytest.mark.parametrize("status", NOT_READY)
async def test_unfinished_video_gets_404_even_for_its_owner(
    owner: AsyncClient, db: AsyncSession, status: VideoStatus
) -> None:
    video = await make_video(db, await user_by_email(db, OWNER_EMAIL), status=status)

    assert (await save(owner, video)).status_code == 404
    assert await row_count(db) == 0


async def test_stranger_gets_404_for_private_video(
    owner: AsyncClient, viewer: AsyncClient, db: AsyncSession
) -> None:
    video = await owners_private_video(db)

    assert (await save(viewer, video)).status_code == 404
    assert await row_count(db) == 0


async def test_owner_can_save_their_private_video(owner: AsyncClient, db: AsyncSession) -> None:
    video = await owners_private_video(db)

    assert (await save(owner, video)).status_code == 204
    assert await listed(owner) == [video.public_id]


async def test_granted_user_can_save_a_private_video(
    owner: AsyncClient, viewer: AsyncClient, db: AsyncSession
) -> None:
    video = await owners_private_video(db)
    await grant(db, video.public_id, VIEWER_EMAIL)

    assert (await save(viewer, video)).status_code == 204
    assert await listed(viewer) == [video.public_id]


async def test_moderator_can_save_a_private_video(
    owner: AsyncClient, moderator: AsyncClient, db: AsyncSession
) -> None:
    video = await owners_private_video(db)

    assert (await save(moderator, video)).status_code == 204
    assert await listed(moderator) == [video.public_id]


# --- Listing ---


async def test_histories_of_two_users_are_apart(
    owner: AsyncClient, viewer: AsyncClient, video: Video, db: AsyncSession
) -> None:
    other = await make_video(db, await make_user(db, "anna"))
    await save(owner, video, 1)
    await save(viewer, video, 8)
    await save(viewer, other)

    assert await listed(owner) == [video.public_id]
    assert await listed(viewer) == [other.public_id, video.public_id]
    assert (await position(db, OWNER_EMAIL, video), await position(db, VIEWER_EMAIL, video)) == (
        1,
        8,
    )


async def test_history_pages_last_watched_first(owner: AsyncClient, db: AsyncSession) -> None:
    me, channel = await user_by_email(db, OWNER_EMAIL), await make_user(db, "anna")
    videos = [await make_video(db, channel) for _ in range(service.PAGE_SIZE + 5)]
    start = datetime.now(UTC)
    # Three rows share each time, so the first page ends inside a tie: video_id breaks it.
    watched = [(start + timedelta(seconds=n // 3), video) for n, video in enumerate(videos)]
    db.add_all(
        HistoryEntry(user_id=me.id, video_id=video.id, position_sec=0, watched_at=at)
        for at, video in watched
    )
    await db.commit()

    first = (await owner.get("/api/me/history")).json()
    rest = (await owner.get("/api/me/history", params={"cursor": first["next_cursor"]})).json()

    expected = sorted(watched, key=lambda pair: (pair[0], pair[1].id), reverse=True)
    ids = [item["video"]["id"] for item in first["items"] + rest["items"]]
    assert len(first["items"]) == service.PAGE_SIZE
    assert ids == [video.public_id for _, video in expected]
    assert rest["next_cursor"] is None


@pytest.mark.parametrize(
    "cursor",
    [
        "not base64!",
        encode_cursor(("x",)),
        encode_cursor(("2026-11-12T10:00:00Z", "not a uuid")),
        encode_cursor(("2026-11-12T10:00:00", str(uuid4()))),  # no time zone
        encode_cursor(("2026-11-12T10:00:00Z", str(uuid4()), 1)),
    ],
)
async def test_bad_cursor_gets_400(owner: AsyncClient, cursor: str) -> None:
    response = await owner.get("/api/me/history", params={"cursor": cursor})

    assert response.status_code == 400


async def test_video_turned_private_leaves_a_strangers_history_until_a_grant(
    owner: AsyncClient, viewer: AsyncClient, video: Video, db: AsyncSession
) -> None:
    await save(viewer, video, 4)

    await make_private(db, video)
    assert await listed(viewer) == []
    assert await position(db, VIEWER_EMAIL, video) == 4  # kept: access may come back

    await grant(db, video.public_id, VIEWER_EMAIL)
    assert await listed(viewer) == [video.public_id]


async def test_owner_and_moderator_keep_a_video_that_turned_private(
    owner: AsyncClient, moderator: AsyncClient, video: Video, db: AsyncSession
) -> None:
    await save(owner, video)
    await save(moderator, video)

    await make_private(db, video)

    assert await listed(owner) == [video.public_id]
    assert await listed(moderator) == [video.public_id]


async def test_video_no_longer_ready_is_not_listed_even_to_owner_or_moderator(
    owner: AsyncClient, moderator: AsyncClient, video: Video, db: AsyncSession
) -> None:
    await save(owner, video)
    await save(moderator, video)

    await set_status(db, video.public_id, VideoStatus.PROCESSING)

    assert await listed(owner) == []
    assert await listed(moderator) == []
    assert await row_count(db) == 2


# --- Progress on thumbnails ---


async def progress(client: AsyncClient, *ids: str) -> dict[str, int]:
    response = await client.get("/api/me/history/progress", params={"v": list(ids)})
    assert response.status_code == 200, response.text
    return response.json()


async def test_progress_gives_saved_positions_of_watched_videos_only(
    owner: AsyncClient, viewer: AsyncClient, video: Video, db: AsyncSession
) -> None:
    watched, unseen = await make_video(db, await make_user(db, "anna")), "unknown0001"
    await save(viewer, video, 4)
    await save(viewer, watched, 10)
    await save(owner, video, 7)

    assert await progress(viewer, video.public_id, watched.public_id, unseen) == {
        video.public_id: 4,
        watched.public_id: 10,
    }
    assert await progress(owner, video.public_id, watched.public_id) == {video.public_id: 7}


async def test_progress_needs_a_signed_in_user(guest: AsyncClient, video: Video) -> None:
    response = await guest.get("/api/me/history/progress", params={"v": video.public_id})
    assert response.status_code == 401


@pytest.mark.parametrize("ids", [[], ["bad"], [f"video{n:06d}" for n in range(101)]])
async def test_progress_refuses_no_bad_or_too_many_ids(owner: AsyncClient, ids: list[str]) -> None:
    response = await owner.get("/api/me/history/progress", params={"v": ids})
    assert response.status_code == 422


# --- Removing ---


async def remove(client: AsyncClient, public_id: str) -> int:
    response = await client.delete(f"/api/me/history/{public_id}", headers=csrf(client))
    return response.status_code


async def test_removing_a_video_drops_it_and_its_progress(
    viewer: AsyncClient, video: Video, db: AsyncSession
) -> None:
    other = await make_video(db, await make_user(db, "anna"))
    await save(viewer, video, 4)
    await save(viewer, other, 2)

    assert await remove(viewer, video.public_id) == 204

    assert await listed(viewer) == [other.public_id]
    assert await progress(viewer, video.public_id, other.public_id) == {other.public_id: 2}
    # Again, or a video never watched or unknown: nothing to do.
    assert await remove(viewer, video.public_id) == 204
    assert await remove(viewer, "unknown0001") == 204


async def test_removing_works_for_a_video_that_turned_private(
    viewer: AsyncClient, video: Video, db: AsyncSession
) -> None:
    await save(viewer, video)
    await make_private(db, video)

    assert await remove(viewer, video.public_id) == 204
    assert await position(db, VIEWER_EMAIL, video) is None


async def test_clearing_empties_only_the_users_history(
    owner: AsyncClient, viewer: AsyncClient, video: Video
) -> None:
    await save(owner, video, 3)
    await save(viewer, video, 4)

    response = await viewer.delete("/api/me/history", headers=csrf(viewer))

    assert response.status_code == 204
    assert await listed(viewer) == []
    assert await progress(viewer, video.public_id) == {}
    assert await progress(owner, video.public_id) == {video.public_id: 3}


async def test_removing_needs_a_signed_in_user(guest: AsyncClient, video: Video) -> None:
    assert await remove(guest, video.public_id) == 401
    response = await guest.delete("/api/me/history", headers=csrf(guest))
    assert response.status_code == 401


async def test_history_rows_carry_the_description(viewer: AsyncClient, video: Video) -> None:
    await save(viewer, video)
    [item] = (await viewer.get("/api/me/history")).json()["items"]
    assert item["video"]["description"] == video.description
