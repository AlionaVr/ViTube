"""Password hashing with Argon2id (ADR 0005). Runs in threads: a hash is CPU-heavy, 64 MiB."""

import functools
import secrets

import anyio
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

_hasher = PasswordHasher()  # argon2id with RFC 9106 defaults: 64 MiB, 3 passes, 4 lanes
_limiter = anyio.CapacityLimiter(4)  # at most 4 hashes at once: a login burst can't eat all RAM


@functools.cache
def _dummy_hash() -> str:
    return _hasher.hash(secrets.token_urlsafe())


def _verify(password_hash: str | None, password: str) -> bool:
    try:
        _hasher.verify(password_hash or _dummy_hash(), password)
    except (VerificationError, InvalidHashError):
        return False
    return password_hash is not None


async def hash_password(password: str) -> str:
    return await anyio.to_thread.run_sync(_hasher.hash, password, limiter=_limiter)


async def verify_password(password_hash: str | None, password: str) -> bool:
    """No hash (unknown email) still runs a full check: both cases take the same time."""
    return await anyio.to_thread.run_sync(_verify, password_hash, password, limiter=_limiter)
