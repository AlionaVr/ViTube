"""/api/auth: sign up, sign in, sign out, the signed-in user. CSRF checks are app-wide (deps)."""

from fastapi import APIRouter, Depends, Request, Response, status

from app.core.rate_limit import RateLimit
from app.core.redis import RedisClient
from app.db.session import DbSession
from app.modules.auth import service
from app.modules.auth.cookies import SESSION_COOKIE, clear_session_cookies, set_session_cookies
from app.modules.auth.deps import CurrentUser, Sessions
from app.modules.auth.schemas import Credentials, UserOut
from app.modules.auth.sessions import SessionStore
from app.modules.users.models import User

router = APIRouter(prefix="/api/auth", tags=["auth"])

SIGNUP_PER_IP = RateLimit("signup_ip", limit=5, window=60 * 60)
LOGIN_PER_IP = RateLimit("login_ip", limit=10, window=60)


async def start_session(
    request: Request, response: Response, sessions: SessionStore, user: User
) -> None:
    # A new id on every sign-in (no session fixation); the session from the old cookie ends.
    if old_id := request.cookies.get(SESSION_COOKIE):
        await sessions.delete(old_id)
    set_session_cookies(response, await sessions.create(user.id))


@router.post(
    "/signup",
    status_code=status.HTTP_201_CREATED,
    response_model=UserOut,
    summary="Create an account and sign in",
    dependencies=[Depends(SIGNUP_PER_IP.per_ip)],
)
async def signup(
    body: Credentials, request: Request, response: Response, db: DbSession, sessions: Sessions
) -> User:
    user = await service.signup(db, body.email, body.password)
    await start_session(request, response, sessions, user)
    return user


@router.post(
    "/login",
    response_model=UserOut,
    summary="Sign in",
    dependencies=[Depends(LOGIN_PER_IP.per_ip)],
)
async def login(
    body: Credentials,
    request: Request,
    response: Response,
    db: DbSession,
    redis: RedisClient,
    sessions: Sessions,
) -> User:
    user = await service.login(db, redis, body.email, body.password)
    await start_session(request, response, sessions, user)
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, summary="Sign out")
async def logout(request: Request, response: Response, sessions: Sessions) -> None:
    if session_id := request.cookies.get(SESSION_COOKIE):
        await sessions.delete(session_id)
    clear_session_cookies(response)


@router.get("/me", response_model=UserOut, summary="The signed-in user")
async def me(user: CurrentUser) -> User:
    return user
