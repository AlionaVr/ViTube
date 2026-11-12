"""Each user's sessions are indexed, so a ban can end them all (ADR 0005)."""

from uuid import uuid4

import pytest
from pydantic import SecretStr
from redis.asyncio import Redis

from app.modules.auth.sessions import ABSOLUTE_SECONDS, SessionStore

SECRET = SecretStr("test-session-secret-0123456789abcdef")


async def test_revoke_all_ends_every_session_of_the_user_only(redis: Redis) -> None:
    store = SessionStore(redis, SECRET)
    anna, bob = uuid4(), uuid4()
    annas = [await store.create(anna) for _ in range(3)]
    bobs = await store.create(bob)

    await store.revoke_all(anna)

    assert [await store.read(session.id) for session in annas] == [None, None, None]
    assert await store.read(bobs.id) is not None
    assert await redis.zcard(f"user_sessions:{anna}") == 0


async def test_a_session_made_during_a_revoke_stays_indexed(
    redis: Redis, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = SessionStore(redis, SECRET)
    anna = uuid4()
    old = await store.create(anna)
    made: list = []
    read_index = redis.zrange

    async def read_then_sign_in(*args, **kwargs):
        members = await read_index(*args, **kwargs)
        made.append(await store.create(anna))  # a login right after the revoke read the index
        return members

    monkeypatch.setattr(redis, "zrange", read_then_sign_in)
    await store.revoke_all(anna)
    monkeypatch.undo()

    assert await store.read(old.id) is None
    assert await store.read(made[0].id) is not None
    await store.revoke_all(anna)  # the next revoke still finds it
    assert await store.read(made[0].id) is None


async def test_the_index_drops_sessions_past_the_absolute_timeout(redis: Redis) -> None:
    clock = [1_000_000.0]
    store = SessionStore(redis, SECRET, now=lambda: clock[0])
    anna = uuid4()
    await store.create(anna)
    clock[0] += ABSOLUTE_SECONDS + 1

    await store.create(anna)

    assert await redis.zcard(f"user_sessions:{anna}") == 1
    assert 0 < await redis.ttl(f"user_sessions:{anna}") <= ABSOLUTE_SECONDS
