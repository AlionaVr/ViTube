"""Fixed-window rate limits in Redis: count attempts per subject, refuse past the limit."""

import hashlib
from dataclasses import dataclass

from fastapi import Request
from redis.asyncio import Redis

from app.core.errors import TooManyRequests
from app.core.redis import RedisClient


@dataclass(frozen=True)
class RateLimit:
    name: str
    limit: int  # attempts allowed per window
    window: int  # seconds, counted from the first attempt

    def _key(self, subject: str) -> str:
        # Hashed: Redis holds no emails or IPs in plain text, and keys have a fixed length.
        return f"ratelimit:{self.name}:{hashlib.sha256(subject.encode()).hexdigest()}"

    async def hit(self, redis: Redis, subject: str) -> None:
        """Count one attempt. Raise TooManyRequests once the subject is over the limit."""
        key = self._key(subject)
        # MULTI/EXEC: a crash between INCR and EXPIRE can't leave a counter that never expires.
        async with redis.pipeline(transaction=True) as pipe:
            pipe.incr(key)
            pipe.expire(key, self.window, nx=True)  # NX: later attempts don't extend the window
            pipe.ttl(key)
            count, _, ttl = await pipe.execute()
        if count > self.limit:
            raise TooManyRequests(retry_after=max(ttl, 1))

    async def reset(self, redis: Redis, subject: str) -> None:
        await redis.delete(self._key(subject))

    async def per_ip(self, request: Request, redis: RedisClient) -> None:
        """A dependency: Depends(LIMIT.per_ip) counts requests per client IP."""
        # nginx sends the client IP in X-Forwarded-For; uvicorn puts it in request.client.
        ip = request.client.host if request.client else "unknown"
        await self.hit(redis, ip)
