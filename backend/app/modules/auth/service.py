"""Sign-up and sign-in rules (ADR 0005). The service commits, like a @Transactional method."""

import secrets

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import Conflict, Forbidden, NotFound, Unauthorized
from app.core.rate_limit import RateLimit
from app.modules.audit import repository as audit
from app.modules.audit.models import AuditAction, TargetType
from app.modules.audit.repository import Actor
from app.modules.auth.passwords import hash_password, verify_password
from app.modules.users import repository as users
from app.modules.users.models import Role, User, UserStatus

HANDLE_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"  # no look-alikes: i, l, o, 0, 1
HANDLE_TRIES = 5
# Login limits per account (unknown emails too), on top of the per-IP one in the router.
# Per account and IP: one IP stops after 5 guesses, and can't lock the owner out elsewhere.
LOGIN_PER_EMAIL_AND_IP = RateLimit("login_email_ip", limit=5, window=15 * 60)
# Per account from all IPs: caps guessing spread over many IPs. Each IP adds at most 5,
# so locking an account out takes 20+ IPs (ADR 0005).
LOGIN_PER_EMAIL = RateLimit("login_email", limit=100, window=15 * 60)


BLOCKED = {
    UserStatus.BANNED: "This account is banned",
    UserStatus.TERMINATED: "This channel was terminated for breaking the rules",
}


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


async def login(db: AsyncSession, redis: Redis, email: str, password: str, ip: str) -> User:
    email_key = email.lower()  # emails are ASCII (schemas.Email): lowercased like citext does
    ip_key = f"{ip} {email_key}"
    # Before the check, so every guess counts. Per IP first: a blocked IP adds nothing below.
    await LOGIN_PER_EMAIL_AND_IP.hit(redis, ip_key)
    await LOGIN_PER_EMAIL.hit(redis, email_key)
    user = await users.get_by_email(db, email)
    # Unknown email and wrong password: same work, same error. No probing for accounts.
    valid = await verify_password(user.password_hash if user else None, password)
    if user is None or not valid:
        raise Unauthorized("Wrong email or password")
    # The owner's typos from this IP are forgiven; the account-wide count stays for guessers.
    await LOGIN_PER_EMAIL_AND_IP.reset(redis, ip_key)
    # Only after the password: others can't learn that an account is banned.
    if user.status is not UserStatus.ACTIVE:
        raise Forbidden(BLOCKED[user.status])
    return user


async def set_role(db: AsyncSession, actor: Actor, email: str, role: Role) -> User:
    """Open sessions get the new role on the next request: it is read from the DB each time.
    A real change is written to the audit log in the same transaction."""
    found = await users.get_by_email(db, email)
    # Locked like a status change, so a ban can't check the old role while it changes.
    user = await users.lock_for_status(db, found.id) if found else None
    if user is None:
        raise NotFound("No user with this email")
    previous = user.role
    if previous is not role:
        user.role = role
        await audit.record(
            db,
            actor,
            AuditAction.SET_USER_ROLE,
            TargetType.USER,
            user.id,
            **{"from": previous.value, "to": role.value},
        )
    await db.commit()
    return user
