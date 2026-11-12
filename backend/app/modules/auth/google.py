"""Sign-in with Google (ADR 0014): the OpenID Connect code flow with PKCE, through Authlib."""

import hashlib
from dataclasses import dataclass
from typing import Any

import httpx2
from authlib.integrations.starlette_client import OAuth, StarletteOAuth2App
from starlette.middleware.sessions import SessionMiddleware
from starlette.types import ASGIApp

from app.core.errors import DomainError
from app.modules.auth.config import AuthSettings, get_auth_settings
from app.modules.auth.schemas import ascii_email

# Fixed endpoints, no discovery document: the api calls only the token and keys endpoints.
AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"  # noqa: S105 - a URL, not a secret
JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
ISSUERS = ["https://accounts.google.com", "accounts.google.com"]  # Google uses both forms
TIMEOUT_SECONDS = 10

STATE_COOKIE = "google_oauth"
STATE_SECONDS = 10 * 60


def create_google(
    settings: AuthSettings, transport: httpx2.AsyncBaseTransport | None = None
) -> StarletteOAuth2App | None:
    """The Google client, or None while GOOGLE_CLIENT_ID is empty. Tests pass a fake Google
    as the transport."""
    if not settings.google_client_id:
        return None
    client_kwargs: dict[str, Any] = {
        "scope": "openid email",
        "code_challenge_method": "S256",  # PKCE
        "timeout": TIMEOUT_SECONDS,
    }
    if transport is not None:
        client_kwargs["transport"] = transport
    return OAuth().register(
        "google",
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret.get_secret_value(),
        authorize_url=AUTHORIZE_URL,
        authorize_params={"prompt": "select_account"},  # pick an account, like YouTube does
        access_token_url=TOKEN_URL,
        jwks_uri=JWKS_URL,
        client_kwargs=client_kwargs,
    )


def id_token_rules(client_id: str) -> dict[str, Any]:
    """Claims checked besides the signature, expiry and nonce. The audience is named: Authlib
    alone would also take a token for another client that lists ours as `azp`."""
    return {"iss": {"values": ISSUERS}, "aud": {"essential": True, "value": client_id}}


@dataclass(frozen=True)
class GoogleAccount:
    sub: str  # the Google account's id, never reused
    email: str


def account_from(claims: dict[str, Any]) -> GoogleAccount:
    """The account from a verified ID token. Only an email Google has verified is used."""
    email = claims.get("email")
    if not email or claims.get("email_verified") is not True:
        raise DomainError("Google hasn't verified this account's email")
    try:
        return GoogleAccount(sub=claims["sub"], email=ascii_email(email))
    except ValueError:
        raise DomainError("This Google account's email can't be used on ViTube") from None


class GoogleStateMiddleware(SessionMiddleware):
    """A signed cookie where Authlib keeps a sign-in's state, PKCE verifier and nonce: only for
    the Google routes, for 10 minutes. Not the user's session (ADR 0005)."""

    def __init__(self, app: ASGIApp) -> None:
        # Read when the app starts, not on import: the OpenAPI export imports the app without env.
        settings = get_auth_settings()
        # A key of its own, derived from the session secret: no new secret to set. Not an HMAC
        # under that secret: those name sessions in Redis, and a cookie picks their message.
        secret = settings.session_secret.get_secret_value().encode()
        key = hashlib.sha256(b"vitube google-oauth-state\0" + secret).hexdigest()
        super().__init__(
            app,
            secret_key=key,
            session_cookie=STATE_COOKIE,
            max_age=STATE_SECONDS,
            path="/api/auth/google",
            same_site="lax",
            https_only=settings.cookie_secure,
        )
