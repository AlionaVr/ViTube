"""Counted slots in Redis: a shared semaphore whose dead holders time out."""

import anyio
import pytest
from redis.asyncio import Redis

from app.core.errors import TooManyRequests
from app.core.slots import Slots, hold

UPLOADS = Slots("test", limit=2, ttl=60)


async def test_slots_up_to_the_limit(redis: Redis) -> None:
    assert await UPLOADS.acquire(redis, "anna", "a")
    assert await UPLOADS.acquire(redis, "anna", "b")
    assert not await UPLOADS.acquire(redis, "anna", "c")
    assert await UPLOADS.acquire(redis, "bob", "c")  # per subject

    await UPLOADS.release(redis, "anna", "a")

    assert await UPLOADS.acquire(redis, "anna", "c")


async def test_parallel_takers_never_pass_the_limit(redis: Redis) -> None:
    results: list[bool] = []

    async def take(token: str) -> None:
        results.append(await UPLOADS.acquire(redis, "anna", token))

    async with anyio.create_task_group() as tasks:
        for number in range(10):
            tasks.start_soon(take, str(number))

    assert sorted(results) == [False] * 8 + [True] * 2


async def test_a_dead_holders_slot_expires(redis: Redis) -> None:
    short = Slots("test", limit=1, ttl=1)
    assert await short.acquire(redis, "anna", "crashed")  # never released

    await anyio.sleep(1.1)

    assert await short.acquire(redis, "anna", "next")


async def test_renewal_keeps_a_slot(redis: Redis) -> None:
    short = Slots("test", limit=1, ttl=1)
    assert await short.acquire(redis, "anna", "working")

    for _ in range(3):
        await anyio.sleep(0.5)
        await short.renew(redis, "anna", "working")

    assert not await short.acquire(redis, "anna", "other")


async def test_hold_takes_all_or_none_and_gives_back(redis: Redis) -> None:
    user, total = Slots("user", limit=1, ttl=60), Slots("total", limit=1, ttl=60)
    assert await total.acquire(redis, "all", "someone else")

    with pytest.raises(TooManyRequests):
        async with hold(redis, (user, "anna"), (total, "all"), busy="busy"):
            pass  # pragma: no cover

    # The user slot taken before the full pool was given back.
    assert await user.acquire(redis, "anna", "x")


async def test_hold_gives_back_on_cancellation(redis: Redis) -> None:
    user, total = Slots("user", limit=1, ttl=60), Slots("total", limit=1, ttl=60)

    with anyio.move_on_after(0.2):  # cancels every await inside, the clean-up's too unless shielded
        async with hold(redis, (user, "anna"), (total, "all"), busy="busy"):
            await anyio.sleep_forever()

    assert await user.acquire(redis, "anna", "next")
    assert await total.acquire(redis, "all", "next")
