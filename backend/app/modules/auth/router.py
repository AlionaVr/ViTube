"""/api/auth: sign up, sign in, sign out, the signed-in user. CSRF checks are app-wide (deps)."""

from typing import Annotated

import httpx2
from authlib.integrations.base_client import OAuthError
from authlib.integrations.starlette_client import StarletteOAuth2App
from fastapi import APIRouter, Depends, Form, Request, Response, status
from fastapi.responses import RedirectResponse
from joserfc.errors import JoseError

from app.core.errors import BadGateway, DomainError, NotFound
from app.core.rate_limit import RateLimit, client_ip
from app.core.redis import RedisClient
from app.db.session import DbSession
from app.modules.auth import service
from app.modules.auth.config import get_auth_settings
from app.modules.auth.cookies import SESSION_COOKIE, clear_session_cookies, set_session_cookies
from app.modules.auth.deps import CurrentUser, Sessions
from app.modules.auth.google import account_from, id_token_rules
from app.modules.auth.schemas import Credentials, NewAccount, Providers, UserOut
from app.modules.auth.sessions import SessionStore
from app.modules.users.models import User

router = APIRouter(prefix="/api/auth", tags=["auth"])

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
    dependencies=[Depends(service.SIGNUP_PER_IP.per_ip)],
)
async def signup(
    body: NewAccount, request: Request, response: Response, db: DbSession, sessions: Sessions
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
    user = await service.login(db, redis, body.email, body.password, client_ip(request))
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


def get_google(request: Request) -> StarletteOAuth2App | None:
    return request.app.state.google


OptionalGoogle = Annotated[StarletteOAuth2App | None, Depends(get_google)]


def require_google(google: OptionalGoogle) -> StarletteOAuth2App:
    if google is None:
        raise NotFound("Sign-in with Google is off")
    return google


Google = Annotated[StarletteOAuth2App, Depends(require_google)]


@router.get("/providers", response_model=Providers, summary="Ways to sign in besides a password")
async def providers(google: OptionalGoogle) -> Providers:
    return Providers(google=google is not None)


@router.get(
    "/google/start",
    status_code=status.HTTP_302_FOUND,
    response_class=RedirectResponse,
    summary="Go to Google to sign in",
    description="Keeps the sign-in's state in a short-lived cookie (ADR 0014). 404 when it's off.",
)
async def google_start(request: Request, google: Google) -> RedirectResponse:
    return await google.authorize_redirect(request, get_auth_settings().google_redirect_uri)


@router.post(
    "/google/finish",
    response_model=UserOut,
    summary="Finish signing in with Google",
    description=(
        "The web app's callback page sends what Google gave it. 409 when the email belongs to "
        "another account: accounts are never linked by email (ADR 0014)."
    ),
    dependencies=[Depends(LOGIN_PER_IP.per_ip)],
)
async def google_finish(
    # Declared for validation and the API docs; Authlib reads them from the form itself.
    code: Annotated[str, Form()],
    state: Annotated[str, Form()],
    request: Request,
    response: Response,
    db: DbSession,
    redis: RedisClient,
    sessions: Sessions,
    google: Google,
) -> User:
    try:
        # Checks the state against the cookie, swaps the code (with the PKCE verifier) for
        # tokens, and verifies the ID token: Google's signature, issuer, audience, expiry, nonce.
        token = await google.authorize_access_token(
            request, claims_options=id_token_rules(google.client_id)
        )
    except (OAuthError, JoseError) as error:
        raise DomainError("Signing in with Google failed or took too long. Try again.") from error
    except httpx2.HTTPError as error:
        raise BadGateway("Google can't be reached. Try again later.") from error
    if "userinfo" not in token:  # no ID token: never from Google with the openid scope
        raise DomainError("Google didn't confirm who you are. Try again.")
    account = account_from(token["userinfo"])
    user = await service.google_sign_in(db, redis, account, client_ip(request))
    await start_session(request, response, sessions, user)
    return user
