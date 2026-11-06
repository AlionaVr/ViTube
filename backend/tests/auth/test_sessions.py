"""Server-side sessions in Redis (ADR 0005)."""

import asyncio
import base64
import uuid

import pytest
from pydantic import SecretStr, ValidationError
from redis.asyncio import Redis

from app.modules.auth.config import AuthSettings
from app.modules.auth.sessions import SessionStore, UserSession

IDLE = 100
ABSOLUTE = 1000


class Clock:
    """A clock the test moves by hand."""

    def __init__(self) -> None:
        self.time = 1_800_000_000.0

    def __call__(self) -> float:
        return self.time


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def store(redis: Redis, clock: Clock) -> SessionStore:
    return SessionStore(redis, SecretStr("s" * 32), idle=IDLE, absolute=ABSOLUTE, now=clock)


async def only_session_key(redis: Redis) -> str:
    keys = await redis.keys("session:*")
    assert len(keys) == 1
    assert isinstance(keys[0], str)  # the app's client decodes responses
    return keys[0]


async def test_a_created_session_can_be_read(store: SessionStore) -> None:
    user_id = uuid.uuid4()

    session = await store.create(user_id)

    assert session.user_id == user_id
    assert await store.read(session.id) == session


async def test_redis_keeps_an_hmac_of_the_id_not_the_id(store: SessionStore, redis: Redis) -> None:
    session = await store.create(uuid.uuid4())

    key = await only_session_key(redis)
    assert session.id not in key
    assert session.id not in str(await redis.get(key))
    # Without the secret the key can't be found.
    other = SessionStore(redis, SecretStr("o" * 32))
    assert await other.read(session.id) is None


async def test_each_session_gets_new_random_256_bit_id_and_csrf_token(store: SessionStore) -> None:
    user_id = uuid.uuid4()

    first, second = await store.create(user_id), await store.create(user_id)

    assert first.id != second.id
    assert first.csrf != second.csrf
    assert len(base64.urlsafe_b64decode(first.id + "=")) == 32


async def test_unknown_id_gives_no_session(store: SessionStore) -> None:
    assert await store.read("no-such-session") is None


async def test_deleted_session_is_gone(store: SessionStore) -> None:
    session = await store.create(uuid.uuid4())

    await store.delete(session.id)

    assert await store.read(session.id) is None


async def test_reading_restarts_the_idle_timeout(store: SessionStore, redis: Redis) -> None:
    session = await store.create(uuid.uuid4())
    key = await only_session_key(redis)
    assert IDLE - 2 <= await redis.ttl(key) <= IDLE
    await redis.expire(key, 5)  # as if it sat unused for a while

    await store.read(session.id)

    assert await redis.ttl(key) >= IDLE - 2


async def test_session_ends_at_the_absolute_timeout(
    store: SessionStore, redis: Redis, clock: Clock
) -> None:
    session = await store.create(uuid.uuid4())

    clock.time += ABSOLUTE - 1  # used all along: the idle timeout never hits
    assert await store.read(session.id) is not None

    clock.time += 1
    assert await store.read(session.id) is None
    assert await redis.keys("session:*") == []


async def test_a_read_at_the_ttl_boundary_renews_or_misses_never_half(
    store: SessionStore, redis: Redis
) -> None:
    # GETEX reads and renews in one step. So the first read that finds the session also keeps
    # it alive for the rest: parallel reads all find it or all miss it, and a found one exists.
    for attempt in range(100):
        await redis.flushdb()
        session = await store.create(uuid.uuid4())
        key = await only_session_key(redis)
        await redis.pexpire(key, attempt % 4)  # expires 0-3 ms from now: during the reads

        results = await asyncio.gather(*(store.read(session.id) for _ in range(20)))

        found = [r is not None for r in results]
        assert all(found) or not any(found)
        assert await redis.exists(key) == any(found)


async def test_reads_never_bring_back_a_deleted_session(store: SessionStore, redis: Redis) -> None:
    for _ in range(20):
        session = await store.create(uuid.uuid4())
        reads = [store.read(session.id) for _ in range(20)]

        await asyncio.gather(*reads[:10], store.delete(session.id), *reads[10:])

        assert await redis.keys("session:*") == []
        assert await store.read(session.id) is None


async def test_parallel_reads_after_the_absolute_timeout_all_refuse(
    store: SessionStore, redis: Redis, clock: Clock
) -> None:
    session = await store.create(uuid.uuid4())
    clock.time += ABSOLUTE

    results = await asyncio.gather(*(store.read(session.id) for _ in range(20)))

    assert results == [None] * 20
    assert await redis.keys("session:*") == []


async def test_cancelled_reads_never_mix_up_sessions(store: SessionStore) -> None:
    # A request cancelled mid-read (timeout, client gone) must not leave its reply on a pooled
    # connection for the next request to take: that showed other users' data (CVE-2023-28858).
    sessions = [await store.create(uuid.uuid4()) for _ in range(20)]
    for attempt in range(30):
        tasks = [asyncio.create_task(store.read(s.id)) for s in sessions]
        await asyncio.sleep(attempt / 10_000)  # cancel at different points: 0-3 ms
        for task in tasks[::2]:
            task.cancel()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for session, result in zip(sessions, results, strict=True):
            if isinstance(result, UserSession):
                assert result.user_id == session.user_id

    results = await asyncio.gather(*(store.read(s.id) for s in sessions))
    assert [r and r.user_id for r in results] == [s.user_id for s in sessions]


def test_short_session_secret_is_refused() -> None:
    with pytest.raises(ValidationError):
        AuthSettings(session_secret=SecretStr("change-me"))
