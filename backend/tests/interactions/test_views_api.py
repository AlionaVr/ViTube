"""POST /api/videos/{id}/views/start and /views: what counts as a view, over HTTP (ADR 0011).

The tracker's own tests cover the rules in detail; these check the endpoints wire them right.
"""

import asyncio

import pytest
from fastapi import FastAPI
from httpx2 import AsyncClient, Response
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.videos.models import Video, VideoStatus, Visibility
from app.modules.views import service, tracker
from tests.interactions.conftest import (
    OWNER_EMAIL,
    VIEWER_EMAIL,
    MakeViewers,
    browser,
    csrf,
    meet_after,
    user_by_email,
)
from tests.videos.factories import get_video, grant, make_video

NOT_READY = [status for status in VideoStatus if status is not VideoStatus.READY]
WAIT = 10 / tracker.MAX_SPEED  # the factory's videos last 10 s: under the 30 s threshold
PARALLEL = 10


class Clock:
    """The tracker's wall clock, moved by hand."""

    def __init__(self) -> None:
        self.time = 1_000_000.0

    def __call__(self) -> float:
        return self.time

    def advance(self, seconds: float) -> None:
        self.time += seconds


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> Clock:
    clock = Clock()
    monkeypatch.setattr(tracker, "now", clock)
    return clock


async def start(client: AsyncClient, video: Video) -> Response:
    return await client.post(f"/api/videos/{video.public_id}/views/start", headers=csrf(client))


async def finish(client: AsyncClient, video: Video) -> Response:
    return await client.post(f"/api/videos/{video.public_id}/views", headers=csrf(client))


async def watch(client: AsyncClient, video: Video, clock: Clock) -> None:
    """Play the video through the threshold, as the player reports it."""
    assert (await start(client, video)).status_code == 204
    clock.advance(WAIT)
    assert (await finish(client, video)).status_code == 204


async def views(db: AsyncSession, video: Video) -> int:
    return (await get_video(db, video.public_id)).view_count


# --- What counts ---


async def test_playback_past_the_threshold_counts(
    viewer: AsyncClient, video: Video, db: AsyncSession, clock: Clock
) -> None:
    await watch(viewer, video, clock)

    assert await views(db, video) == 1
    assert (await viewer.get(f"/api/videos/{video.public_id}")).json()["view_count"] == 1


async def test_a_finish_alone_counts_nothing(
    viewer: AsyncClient, video: Video, db: AsyncSession, clock: Clock
) -> None:
    assert (await finish(viewer, video)).status_code == 204

    assert await views(db, video) == 0


async def test_a_finish_too_soon_counts_nothing(
    viewer: AsyncClient, video: Video, db: AsyncSession, clock: Clock
) -> None:
    await start(viewer, video)
    clock.advance(WAIT - 0.1)
    await finish(viewer, video)
    assert await views(db, video) == 0

    clock.advance(0.1)  # the same playback, now long enough
    await finish(viewer, video)
    assert await views(db, video) == 1


async def test_guests_count_too(
    guest: AsyncClient, video: Video, db: AsyncSession, clock: Clock
) -> None:
    await watch(guest, video, clock)

    assert await views(db, video) == 1


# --- Once per viewer a day ---


async def test_watching_again_the_same_day_counts_once(
    viewer: AsyncClient, video: Video, db: AsyncSession, clock: Clock
) -> None:
    for _ in range(3):
        await watch(viewer, video, clock)
        clock.advance(60 * 60)

    assert await views(db, video) == 1


async def test_parallel_finishes_count_once(
    viewer: AsyncClient,
    video: Video,
    db: AsyncSession,
    clock: Clock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await start(viewer, video)
    clock.advance(WAIT)

    meet_after(monkeypatch, service, "get_ready", PARALLEL)
    responses = await asyncio.gather(*(finish(viewer, video) for _ in range(PARALLEL)))

    assert [response.status_code for response in responses] == [204] * PARALLEL
    assert await views(db, video) == 1


async def test_parallel_views_of_many_users_all_count(
    make_viewers: MakeViewers,
    video: Video,
    db: AsyncSession,
    clock: Clock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    viewers = await make_viewers(PARALLEL)
    for client in viewers:
        await start(client, video)
    clock.advance(WAIT)

    meet_after(monkeypatch, service, "get_ready", PARALLEL)
    responses = await asyncio.gather(*(finish(client, video) for client in viewers))

    assert [response.status_code for response in responses] == [204] * PARALLEL
    assert await views(db, video) == PARALLEL


async def test_a_view_counts_again_after_the_window(
    viewer: AsyncClient, video: Video, db: AsyncSession, redis: Redis, clock: Clock
) -> None:
    await watch(viewer, video, clock)
    async for key in redis.scan_iter("view:*"):
        await redis.pexpire(key, 1)  # the 24 h window, run out (its length: tracker tests)
    await asyncio.sleep(0.05)

    await watch(viewer, video, clock)

    assert await views(db, video) == 2


# --- Who is the viewer ---


async def test_a_user_counts_once_from_any_network(
    app: FastAPI, viewer: AsyncClient, video: Video, db: AsyncSession, clock: Clock
) -> None:
    await watch(viewer, video, clock)
    async with browser(app, "10.9.9.9", cookies=viewer.cookies) as same_user_elsewhere:
        await watch(same_user_elsewhere, video, clock)

    assert await views(db, video) == 1


async def test_users_behind_one_nat_count_apart(
    app: FastAPI, make_viewers: MakeViewers, video: Video, db: AsyncSession, clock: Clock
) -> None:
    first, second = await make_viewers(2)
    async with (
        browser(app, "10.8.0.1", cookies=first.cookies) as first_at_office,
        browser(app, "10.8.0.1", cookies=second.cookies) as second_at_office,
    ):
        await watch(first_at_office, video, clock)
        await watch(second_at_office, video, clock)

    assert await views(db, video) == 2


async def test_guests_behind_one_ip_count_once(
    app: FastAPI, video: Video, db: AsyncSession, clock: Clock
) -> None:
    async with browser(app, "10.7.0.1") as first, browser(app, "10.7.0.1") as second:
        await watch(first, video, clock)
        await watch(second, video, clock)
    async with browser(app, "10.7.0.2") as elsewhere:
        await watch(elsewhere, video, clock)

    assert await views(db, video) == 2  # the accepted cost, ADR 0011


# --- Access ---


async def test_private_video_is_hidden_from_strangers(
    owner: AsyncClient, viewer: AsyncClient, db: AsyncSession, clock: Clock
) -> None:
    video = await make_video(
        db, await user_by_email(db, OWNER_EMAIL), visibility=Visibility.PRIVATE
    )

    assert (await start(viewer, video)).status_code == 404
    assert (await finish(viewer, video)).status_code == 404

    await grant(db, video.public_id, VIEWER_EMAIL)
    await watch(viewer, video, clock)
    await watch(owner, video, clock)
    assert await views(db, video) == 2


@pytest.mark.parametrize("status", NOT_READY)
async def test_unfinished_video_takes_no_views_even_from_its_owner(
    owner: AsyncClient, db: AsyncSession, status: VideoStatus
) -> None:
    video = await make_video(db, await user_by_email(db, OWNER_EMAIL), status=status)

    assert (await start(owner, video)).status_code == 404
    assert (await finish(owner, video)).status_code == 404


async def test_reports_from_other_sites_are_refused(
    guest: AsyncClient, video: Video, db: AsyncSession
) -> None:
    other_site = {"Origin": "https://evil.example"}
    path = f"/api/videos/{video.public_id}/views"

    assert (await guest.post(f"{path}/start", headers=other_site)).status_code == 403
    assert (await guest.post(path, headers=other_site)).status_code == 403
