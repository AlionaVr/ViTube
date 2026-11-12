"""Server-side sessions in Redis (ADR 0005). The cookie holds a random id; Redis holds its HMAC."""

import hashlib
import hmac
import json
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import cast
from uuid import UUID

from pydantic import SecretStr
from redis.asyncio import Redis

IDLE_SECONDS = 7 * 24 * 3600
ABSOLUTE_SECONDS = 30 * 24 * 3600


@dataclass(frozen=True)
class UserSession:
    id: str  # the cookie value; Redis never stores it
    user_id: UUID  # no role: it is read from the DB on each request, so changes apply at once
    csrf: str
    created_at: float  # unix time; older sessions have whole seconds


class SessionStore:
    def __init__(
        self,
        redis: Redis,
        secret: SecretStr,
        *,
        idle: int = IDLE_SECONDS,
        absolute: int = ABSOLUTE_SECONDS,
        now: Callable[[], float] = time.time,
    ) -> None:
        self._redis = redis
        self._secret = secret.get_secret_value().encode()
        self._idle = idle
        self._absolute = absolute
        self._now = now

    def _key(self, session_id: str) -> str:
        # A Redis dump gives no usable cookies: the key is an HMAC of the id, not the id.
        digest = hmac.new(self._secret, session_id.encode(), hashlib.sha256).hexdigest()
        return f"session:{digest}"

    async def create(self, user_id: UUID) -> UserSession:
        """A new session with a new random id: each login gets one (no session fixation)."""
        session = UserSession(
            id=secrets.token_urlsafe(32),  # 256 bits
            user_id=user_id,
            csrf=secrets.token_urlsafe(32),
            created_at=self._now(),  # fractions too: a ban's cutoff splits one second
        )
        value = {"user_id": str(user_id), "csrf": session.csrf, "created_at": session.created_at}
        key, index = self._key(session.id), self._index_key(user_id)
        # MULTI/EXEC: the session never exists without its TTL or outside the user's index.
        async with self._redis.pipeline(transaction=True) as pipe:
            pipe.set(key, json.dumps(value), ex=min(self._idle, self._absolute))
            # Scored by creation time: sessions past the absolute timeout are gone, so they
            # leave the index here, and it can't grow without end.
            pipe.zadd(index, {key: session.created_at})
            pipe.zremrangebyscore(index, "-inf", session.created_at - self._absolute)
            pipe.expire(index, self._absolute)
            await pipe.execute()
        return session

    async def read(self, session_id: str) -> UserSession | None:
        """The session, or None if unknown or timed out. Each read restarts the idle timeout."""
        key = self._key(session_id)
        raw = await self._redis.getex(key, ex=self._idle)  # read and refresh in one round trip
        if raw is None:
            return None
        value = json.loads(raw)
        if self._now() >= value["created_at"] + self._absolute:
            await self._redis.delete(key)
            return None
        return UserSession(session_id, UUID(value["user_id"]), value["csrf"], value["created_at"])

    async def delete(self, session_id: str) -> None:
        # Its index entry stays until the index is pruned: deleting a missing key is harmless.
        await self._redis.delete(self._key(session_id))

    async def revoke_all(self, user_id: UUID) -> None:
        """End every session of the user (a ban).

        Removes only the entries it read: a session made meanwhile keeps its entry. Not what
        enforces a ban: requests read the user's status from the DB (ADR 0005), so a session
        this misses (made just now, or before the index existed) is refused all the same.
        """
        index = self._index_key(user_id)
        keys = cast(list[str], await self._redis.zrange(index, 0, -1))  # no scores asked
        if keys:
            async with self._redis.pipeline(transaction=True) as pipe:
                pipe.delete(*keys)
                pipe.zrem(index, *keys)
                await pipe.execute()

    @staticmethod
    def _index_key(user_id: UUID) -> str:
        # Holds session keys (HMACs of the ids), never the cookie values.
        return f"user_sessions:{user_id}"
