"""Fixed-window rate limits in Redis."""

import asyncio

import pytest
from fastapi import Depends, FastAPI
from httpx2 import ASGITransport, AsyncClient, Response
from redis.asyncio import Redis

from app.core.errors import TooManyRequests, register_error_handlers
from app.core.rate_limit import RateLimit

LIMIT = RateLimit("test", limit=3, window=60)


async def only_key(redis: Redis) -> str:
    keys = await redis.keys("ratelimit:*")
    assert len(keys) == 1
    assert isinstance(keys[0], str)  # the app's client decodes responses
    return keys[0]


async def test_allows_the_limit_then_refuses(redis: Redis) -> None:
    for _ in range(LIMIT.limit):
        await LIMIT.hit(redis, "a")

    with pytest.raises(TooManyRequests) as error:
        await LIMIT.hit(redis, "a")

    assert 0 < error.value.retry_after <= LIMIT.window


async def test_subjects_are_counted_apart(redis: Redis) -> None:
    for _ in range(LIMIT.limit):
        await LIMIT.hit(redis, "a")

    await LIMIT.hit(redis, "b")


async def test_window_starts_at_the_first_attempt(redis: Redis) -> None:
    await LIMIT.hit(redis, "a")
    key = await only_key(redis)
    assert 0 < await redis.ttl(key) <= LIMIT.window
    await redis.expire(key, 5)  # as if most of the window has passed

    await LIMIT.hit(redis, "a")

    assert await redis.ttl(key) <= 5  # later attempts don't extend the window


async def test_reset_clears_the_count(redis: Redis) -> None:
    for _ in range(LIMIT.limit):
        await LIMIT.hit(redis, "a")

    await LIMIT.reset(redis, "a")

    await LIMIT.hit(redis, "a")


async def test_parallel_attempts_never_pass_the_limit(redis: Redis) -> None:
    results = await asyncio.gather(
        *(LIMIT.hit(redis, "a") for _ in range(20)), return_exceptions=True
    )

    assert results.count(None) == LIMIT.limit
    assert all(isinstance(r, TooManyRequests) for r in results if r is not None)
    assert await redis.ttl(await only_key(redis)) > 0  # the counter always expires


async def test_keys_hold_no_subject_in_plain_text(redis: Redis) -> None:
    await LIMIT.hit(redis, "anna@example.com")

    assert "anna" not in await only_key(redis)


async def test_per_ip_dependency_counts_each_client_ip(redis: Redis) -> None:
    probe = FastAPI()
    register_error_handlers(probe)
    probe.state.redis = redis

    @probe.post("/probe", dependencies=[Depends(LIMIT.per_ip)])
    async def probe_route() -> None:
        pass

    async def post_from(ip: str) -> Response:
        transport = ASGITransport(app=probe, client=(ip, 1234))
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post("/probe")

    for _ in range(LIMIT.limit):
        assert (await post_from("10.0.0.1")).status_code == 200
    blocked = await post_from("10.0.0.1")
    assert blocked.status_code == 429
    assert "retry-after" in blocked.headers
    assert (await post_from("10.0.0.2")).status_code == 200
