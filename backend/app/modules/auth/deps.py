"""Auth dependencies: the session from the cookie, CSRF checks, the signed-in user."""

import hmac
from collections.abc import Awaitable, Callable
from typing import Annotated
from urllib.parse import urlsplit

from fastapi import Depends, Request

from app.core.errors import Forbidden, Unauthorized
from app.db.session import DbSession
from app.modules.auth.cookies import SESSION_COOKIE
from app.modules.auth.sessions import SessionStore, UserSession
from app.modules.users import repository as users
from app.modules.users.models import Role, User, UserStatus

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def get_sessions(request: Request) -> SessionStore:
    return request.app.state.sessions


Sessions = Annotated[SessionStore, Depends(get_sessions)]


async def load_session(request: Request, sessions: Sessions) -> UserSession | None:
    """The session from the cookie. FastAPI runs it once per request, however many deps use it."""
    session_id = request.cookies.get(SESSION_COOKIE)
    return await sessions.read(session_id) if session_id else None


CurrentSession = Annotated[UserSession | None, Depends(load_session)]


async def verify_csrf(request: Request, session: CurrentSession) -> None:
    """App-wide (ADR 0005): an unsafe request must come from our own pages."""
    if request.method in SAFE_METHODS:
        return
    # Browsers set Origin and pages can't fake it. No Origin (old browser, script): refused too.
    origin = request.headers.get("origin")
    if origin is None or urlsplit(origin).netloc != request.headers.get("host"):
        raise Forbidden("Cross-site request refused")
    if session is not None:
        token = request.headers.get("x-csrf-token", "")
        # Bytes: compare_digest refuses non-ASCII str, and headers can hold any byte.
        if not hmac.compare_digest(token.encode(), session.csrf.encode()):
            raise Forbidden("Missing or wrong CSRF token")


async def optional_user(
    request: Request, session: CurrentSession, sessions: Sessions, db: DbSession
) -> User | None:
    """The signed-in user or None. Read from the DB each time: a role or status change applies
    to the next request.

    An unsafe request holds the user's write lock until it commits: a ban waits for writes under
    way, and no write commits after it (ADR 0005).
    """
    if session is None:
        return None
    if request.method in SAFE_METHODS:
        user = await users.get_by_id(db, session.user_id)
    else:
        user = await users.get_for_write(db, session.user_id)
    if (
        user is None
        or user.status is not UserStatus.ACTIVE
        or _from_before_restriction(session, user)
    ):
        # Banned, gone, or a session from before a ban: it ends here, whether or not the ban's
        # revoke reached it, and a reinstated account doesn't bring it back.
        await sessions.delete(session.id)
        return None
    return user


def _from_before_restriction(session: UserSession, user: User) -> bool:
    cutoff = user.sessions_valid_after
    return cutoff is not None and session.created_at < cutoff.timestamp()


OptionalUser = Annotated[User | None, Depends(optional_user)]


async def current_user(user: OptionalUser) -> User:
    """The signed-in user; guests get 401."""
    if user is None:
        raise Unauthorized()
    return user


CurrentUser = Annotated[User, Depends(current_user)]


def require_role(minimum: Role) -> Callable[..., Awaitable[User]]:
    """A dependency: the signed-in user with at least this role (ADR 0009), else 403."""

    async def check(user: CurrentUser) -> User:
        if not user.role.at_least(minimum):
            raise Forbidden()
        return user

    return check
