"""View counting in Redis: playback threshold, one view per viewer and video a day."""

import asyncio
from uuid import UUID, uuid4

import pytest
from redis.asyncio import Redis

from app.modules.views import tracker

VIDEO = UUID("01900000-0000-7000-8000-000000000001")
LONG_VIDEO = 600
GUEST = tracker.viewer_id(None, "203.0.113.7")
WAIT = tracker.WATCH_SECONDS / tracker.MAX_SPEED  # wall time for 30 s of playback at 2x


class Clock:
    def __init__(self) -> None:
        self.time = 1_800_000_000.0

    def __call__(self) -> float:
        return self.time

    def advance(self, seconds: float) -> None:
        self.time += seconds


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> Clock:
    clock = Clock()
    monkeypatch.setattr(tracker, "now", clock)
    return clock


async def watch(redis: Redis, clock: Clock, viewer: str = GUEST, video: UUID = VIDEO) -> bool:
    """Start playback, wait out the threshold, report it."""
    await tracker.start(redis, video, viewer)
    clock.advance(WAIT)
    return await tracker.finish(redis, video, viewer, LONG_VIDEO)


async def view_key(redis: Redis) -> str:
    keys = await redis.keys("view:*")
    assert len(keys) == 1
    assert isinstance(keys[0], str)  # the app's client decodes responses
    return keys[0]


async def test_playback_past_the_threshold_counts(redis: Redis, clock: Clock) -> None:
    assert await watch(redis, clock)


async def test_finish_without_start_does_not_count(redis: Redis, clock: Clock) -> None:
    assert not await tracker.finish(redis, VIDEO, GUEST, LONG_VIDEO)


async def test_finish_before_the_threshold_does_not_count(redis: Redis, clock: Clock) -> None:
    await tracker.start(redis, VIDEO, GUEST)
    clock.advance(WAIT - 0.1)

    assert not await tracker.finish(redis, VIDEO, GUEST, LONG_VIDEO)

    clock.advance(0.1)  # the early call spent nothing: the honest report still counts
    assert await tracker.finish(redis, VIDEO, GUEST, LONG_VIDEO)


async def test_a_new_start_restarts_the_wait(redis: Redis, clock: Clock) -> None:
    await tracker.start(redis, VIDEO, GUEST)
    clock.advance(WAIT)
    await tracker.start(redis, VIDEO, GUEST)

    assert not await tracker.finish(redis, VIDEO, GUEST, LONG_VIDEO)


async def test_short_video_threshold_is_its_length(redis: Redis, clock: Clock) -> None:
    await tracker.start(redis, VIDEO, GUEST)
    clock.advance(10 / tracker.MAX_SPEED)

    assert await tracker.finish(redis, VIDEO, GUEST, 10)


async def test_sub_second_video_still_needs_playback(redis: Redis, clock: Clock) -> None:
    await tracker.start(redis, VIDEO, GUEST)

    assert not await tracker.finish(redis, VIDEO, GUEST, 0)  # 0: shorter than a second
    clock.advance(tracker.MIN_WATCH_SECONDS / tracker.MAX_SPEED)
    assert await tracker.finish(redis, VIDEO, GUEST, 0)


async def test_unknown_duration_needs_the_full_threshold(redis: Redis, clock: Clock) -> None:
    await tracker.start(redis, VIDEO, GUEST)
    clock.advance(WAIT - 0.1)

    assert not await tracker.finish(redis, VIDEO, GUEST, None)


async def test_repeat_view_within_a_day_does_not_count(redis: Redis, clock: Clock) -> None:
    assert await watch(redis, clock)

    assert not await tracker.finish(redis, VIDEO, GUEST, LONG_VIDEO)
    clock.advance(23 * 60 * 60)
    assert not await watch(redis, clock)


async def test_parallel_reports_count_once(redis: Redis, clock: Clock) -> None:
    await tracker.start(redis, VIDEO, GUEST)
    clock.advance(WAIT)

    results = await asyncio.gather(
        *(tracker.finish(redis, VIDEO, GUEST, LONG_VIDEO) for _ in range(20))
    )

    assert results.count(True) == 1


async def test_the_window_is_a_day(redis: Redis, clock: Clock) -> None:
    await watch(redis, clock)

    ttl = await redis.ttl(await view_key(redis))
    assert tracker.VIEW_WINDOW - 5 < ttl <= tracker.VIEW_WINDOW == 24 * 60 * 60


async def test_view_counts_again_after_the_window(redis: Redis, clock: Clock) -> None:
    assert await watch(redis, clock)
    await redis.pexpire(await view_key(redis), 20)  # as if the day has passed
    await asyncio.sleep(0.1)  # Redis expires the key itself

    assert await watch(redis, clock)


async def test_users_behind_one_nat_count_apart(redis: Redis, clock: Clock) -> None:
    ip = "198.51.100.1"
    first, second = (tracker.viewer_id(uuid4(), ip) for _ in range(2))

    assert await watch(redis, clock, first)
    assert await watch(redis, clock, second)


async def test_guests_behind_one_nat_count_once(redis: Redis, clock: Clock) -> None:
    assert await watch(redis, clock, tracker.viewer_id(None, "198.51.100.1"))
    assert not await watch(redis, clock, tracker.viewer_id(None, "198.51.100.1"))


async def test_each_video_counts_apart(redis: Redis, clock: Clock) -> None:
    assert await watch(redis, clock, video=VIDEO)
    assert await watch(redis, clock, video=uuid4())


async def test_redis_holds_no_ip(redis: Redis, clock: Clock) -> None:
    await watch(redis, clock)

    for key in await redis.keys("*"):
        assert "203.0.113.7" not in str(key)
        assert "203.0.113.7" not in str(await redis.get(key))
