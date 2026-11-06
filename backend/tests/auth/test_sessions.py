"""Server-side sessions in Redis (ADR 0005)."""

import base64
import uuid

import pytest
from pydantic import SecretStr, ValidationError
from redis.asyncio import Redis

from app.modules.auth.config import AuthSettings
from app.modules.auth.sessions import SessionStore

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


def test_short_session_secret_is_refused() -> None:
    with pytest.raises(ValidationError):
        AuthSettings(session_secret=SecretStr("change-me"))
