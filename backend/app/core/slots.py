"""Counted slots in Redis: at most `limit` holders at once, a semaphore shared by all processes.

A holder renews its slot while it works and releases it when done. A holder that dies (crash,
kill) frees its slot when the slot expires, so a slot is never lost for good.
"""

import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

import anyio
from redis.asyncio import Redis

from app.core.errors import TooManyRequests

# One atomic step: drop expired holders, check the count, take a slot. Redis server time, so the
# api processes' clocks don't matter. Members are holder tokens, scores their expiry in ms.
_ACQUIRE = """
local t = redis.call('TIME')
local now = t[1] * 1000 + math.floor(t[2] / 1000)
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', now)
if redis.call('ZCARD', KEYS[1]) >= tonumber(ARGV[1]) then
  return 0
end
redis.call('ZADD', KEYS[1], now + tonumber(ARGV[2]), ARGV[3])
redis.call('PEXPIRE', KEYS[1], ARGV[2])
return 1
"""

_RENEW = """
local t = redis.call('TIME')
local now = t[1] * 1000 + math.floor(t[2] / 1000)
redis.call('ZADD', KEYS[1], 'XX', now + tonumber(ARGV[1]), ARGV[2])
redis.call('PEXPIRE', KEYS[1], ARGV[1])
return 1
"""


@dataclass(frozen=True)
class Slots:
    name: str
    limit: int
    ttl: int  # seconds a slot lives without a renewal

    def _key(self, subject: str) -> str:
        return f"slots:{self.name}:{subject}"

    async def acquire(self, redis: Redis, subject: str, token: str) -> bool:
        taken = await redis.eval(
            _ACQUIRE, 1, self._key(subject), self.limit, self.ttl * 1000, token
        )
        return taken == 1

    async def renew(self, redis: Redis, subject: str, token: str) -> None:
        await redis.eval(_RENEW, 1, self._key(subject), self.ttl * 1000, token)

    async def release(self, redis: Redis, subject: str, token: str) -> None:
        await redis.zrem(self._key(subject), token)


@dataclass(frozen=True)
class Held:
    """Slots one holder took; renew them together while working."""

    redis: Redis
    token: str
    taken: tuple[tuple[Slots, str], ...]

    async def renew(self) -> None:
        for slots, subject in self.taken:
            await slots.renew(self.redis, subject, self.token)


@asynccontextmanager
async def hold(redis: Redis, *wanted: tuple[Slots, str], busy: str) -> AsyncIterator[Held]:
    """Take a slot in each pool, or none: TooManyRequests with `busy` if any pool is full.

    Released on the way out, however the block ends (error, cancellation, a cut-off client).
    """
    token = secrets.token_hex(16)
    taken: list[tuple[Slots, str]] = []
    try:
        for slots, subject in wanted:
            if not await slots.acquire(redis, subject, token):
                raise TooManyRequests(retry_after=30, detail=busy)
            taken.append((slots, subject))
        yield Held(redis, token, tuple(taken))
    finally:
        with anyio.CancelScope(shield=True):  # a cancelled request still gives its slots back
            for slots, subject in taken:
                await slots.release(redis, subject, token)
