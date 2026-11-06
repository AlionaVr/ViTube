"""Sign-up and sign-in rules (ADR 0005). The service commits, like a @Transactional method."""

import secrets

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import Conflict, Unauthorized
from app.core.rate_limit import RateLimit
from app.modules.auth.passwords import hash_password, verify_password
from app.modules.users import repository as users
from app.modules.users.models import User

HANDLE_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"  # no look-alikes: i, l, o, 0, 1
HANDLE_TRIES = 5
# Per account: guesses spread over many IPs still hit it. Unknown emails count too.
LOGIN_PER_EMAIL = RateLimit("login_email", limit=5, window=15 * 60)


def random_handle() -> str:
    return "user-" + "".join(secrets.choice(HANDLE_ALPHABET) for _ in range(8))


async def signup(db: AsyncSession, email: str, password: str) -> User:
    password_hash = await hash_password(password)
    for _ in range(HANDLE_TRIES):
        user = await users.insert_unless_taken(
            db, email=email, handle=random_handle(), password_hash=password_hash
        )
        if user is not None:
            await db.commit()
            return user
        if await users.get_by_email(db, email) is not None:
            raise Conflict("This email is already registered")
        # Otherwise the random handle was taken: try another.
    raise RuntimeError("No free handle found")  # 31^8 handles: practically never


async def login(db: AsyncSession, redis: Redis, email: str, password: str) -> User:
    email_key = email.lower()
    await LOGIN_PER_EMAIL.hit(redis, email_key)  # before the check: every guess counts
    user = await users.get_by_email(db, email)
    # Unknown email and wrong password: same work, same error. No probing for accounts.
    valid = await verify_password(user.password_hash if user else None, password)
    if user is None or not valid:
        raise Unauthorized("Wrong email or password")
    await LOGIN_PER_EMAIL.reset(redis, email_key)
    return user
