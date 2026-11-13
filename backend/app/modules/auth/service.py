"""Sign-up and sign-in rules (ADR 0005). The service commits, like a @Transactional method."""

import secrets

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import Conflict, Forbidden, NotFound, Unauthorized
from app.core.rate_limit import RateLimit
from app.modules.audit import repository as audit
from app.modules.audit.models import AuditAction, TargetType
from app.modules.audit.repository import Actor
from app.modules.auth.google import GoogleAccount
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
# New accounts per IP, made with a password or with Google.
SIGNUP_PER_IP = RateLimit("signup_ip", limit=5, window=60 * 60)

# The account that has the email may use a password or another Google account.
GOOGLE_EMAIL_TAKEN = "This email is already registered with another sign-in method."

BLOCKED = {
    UserStatus.BANNED: "This account is banned",
    UserStatus.TERMINATED: "This channel was terminated for breaking the rules",
}


def random_handle() -> str:
    return "user-" + "".join(secrets.choice(HANDLE_ALPHABET) for _ in range(8))


async def _insert_user(
    db: AsyncSession, email: str, *, password_hash: str | None = None, google_sub: str | None = None
) -> User | None:
    """A new user with a random handle. None if the email or the Google account is taken."""
    for _ in range(HANDLE_TRIES):
        user = await users.insert_unless_taken(
            db,
            email=email,
            handle=random_handle(),
            password_hash=password_hash,
            google_sub=google_sub,
        )
        if user is not None:
            return user
        if await users.get_by_email(db, email) is not None:
            return None
        if google_sub is not None and await users.get_by_google_sub(db, google_sub) is not None:
            return None
        # Otherwise the random handle was taken: try another.
    raise RuntimeError("No free handle found")  # 31^8 handles: practically never


async def signup(db: AsyncSession, email: str, password: str) -> User:
    user = await _insert_user(db, email, password_hash=await hash_password(password))
    if user is None:
        raise Conflict("This email is already registered")
    await db.commit()
    return user


async def google_sign_in(db: AsyncSession, redis: Redis, account: GoogleAccount, ip: str) -> User:
    """Sign in with Google; the first time, sign up. The account is found by Google's id, never
    by email: password sign-up doesn't verify emails, so the same email doesn't prove the same
    person (pre-hijacking, ADR 0014). A taken email is refused and nothing is linked."""
    user = await users.get_by_google_sub(db, account.sub)
    if user is None:
        await SIGNUP_PER_IP.hit(redis, ip)  # a new account, as with a password
        user = await _insert_user(db, account.email, google_sub=account.sub)
        # None: the email is taken, or a parallel first sign-in of this account made the user.
        user = user or await users.get_by_google_sub(db, account.sub)
        if user is None:
            raise Conflict(GOOGLE_EMAIL_TAKEN)
        await db.commit()
    if user.status is not UserStatus.ACTIVE:
        raise Forbidden(BLOCKED[user.status])
    return user


async def login(db: AsyncSession, redis: Redis, email: str, password: str, ip: str) -> User:
    email_key = email.lower()  # emails are ASCII (schemas.Email): lowercased like citext does
    ip_key = f"{ip} {email_key}"
    # Before the check, so every guess counts. Per IP first: a blocked IP adds nothing below.
    await LOGIN_PER_EMAIL_AND_IP.hit(redis, ip_key)
    await LOGIN_PER_EMAIL.hit(redis, email_key)
    user = await users.get_by_email(db, email)
    # Ends the read: while the check waits for a hashing slot, its DB connection is back in the
    # pool. A login flood fills the hashing queue only, not the pool the whole site needs.
    await db.commit()
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
    if role is Role.ADMIN and user.status is not UserStatus.ACTIVE:
        # Admins can't be restricted, so they couldn't be reinstated either (a DB check too).
        raise Forbidden("A restricted account can't be made an admin: reinstate it first")
    previous = user.role
    if previous is not role:
        user.role = role
        await audit.record(
            db,
            actor,
            AuditAction.SET_USER_ROLE,
            TargetType.USER,
            user.id,
            subject=user.id,
            **{"from": previous.value, "to": role.value},
        )
    await db.commit()
    return user
