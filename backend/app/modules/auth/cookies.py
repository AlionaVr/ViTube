"""Session cookies (ADR 0005)."""

from fastapi import Response

from app.modules.auth.config import get_auth_settings
from app.modules.auth.sessions import ABSOLUTE_SECONDS, UserSession

SESSION_COOKIE = "sid"
CSRF_COOKIE = "csrf_token"  # readable by JS: the web app sends it back in X-CSRF-Token


def set_session_cookies(response: Response, session: UserSession) -> None:
    secure = get_auth_settings().cookie_secure
    response.set_cookie(
        SESSION_COOKIE,
        session.id,
        max_age=ABSOLUTE_SECONDS,
        httponly=True,
        secure=secure,
        samesite="lax",
    )
    response.set_cookie(
        CSRF_COOKIE, session.csrf, max_age=ABSOLUTE_SECONDS, secure=secure, samesite="lax"
    )


def clear_session_cookies(response: Response) -> None:
    secure = get_auth_settings().cookie_secure
    response.delete_cookie(SESSION_COOKIE, httponly=True, secure=secure, samesite="lax")
    response.delete_cookie(CSRF_COOKIE, secure=secure, samesite="lax")
