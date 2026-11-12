"""Sign-in with Google (ADR 0014), against a fake Google: its token and keys endpoints."""

import asyncio
import base64
import hashlib
import time
from collections.abc import Iterator
from typing import Any
from urllib.parse import parse_qs, urlsplit

import httpx2
import pytest
from fastapi import FastAPI
from httpx2 import AsyncClient, Response
from joserfc import jwt
from joserfc.jwk import RSAKey
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.config import AuthSettings
from app.modules.auth.google import AUTHORIZE_URL, JWKS_URL, TOKEN_URL, create_google
from app.modules.auth.service import BLOCKED, GOOGLE_EMAIL_TAKEN
from app.modules.users import repository as users
from app.modules.users.models import User, UserStatus
from tests.auth.test_auth_api import HANDLE, client_from, csrf, login, signup
from tests.playlists.test_watch_later import watch_laters

CLIENT_ID = "test-client.apps.googleusercontent.com"
CLIENT_SECRET = "test-client-secret"
CLIENT_AUTH = "Basic " + base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
REDIRECT_URI = "http://localhost/auth/google/callback"
SUB = "104834567890123456789"
OTHER_SUB = "117712345678901234567"
EMAIL = "anna@gmail.com"


def new_key(kid: str) -> RSAKey:
    return RSAKey.generate_key(2048, parameters={"kid": kid})


def code_for(state: str) -> str:
    """The code the fake Google sends back with a state."""
    return f"code-{state}"


class FakeGoogle:
    """Answers as Google does; the ID token is signed with a test key it publishes as JWKS."""

    def __init__(self) -> None:
        self.key = new_key("key-1")  # published as JWKS
        self.signing_key = self.key  # another one forges a token
        self.claims: dict[str, Any] = {"sub": SUB, "email": EMAIL, "email_verified": True}
        self.outage: Exception | Response | None = None  # how every request fails, if set
        self.flows: dict[str, dict[str, str]] = {}  # code -> the query of its sign-in page

    def authorize(self, url: str) -> str:
        """The user signs in on Google's page; returns the state Google sends back."""
        query = {name: values[0] for name, values in parse_qs(urlsplit(url).query).items()}
        self.flows[code_for(query["state"])] = query
        return query["state"]

    def id_token(self, nonce: str) -> str:
        now = int(time.time())
        claims = {
            "iss": "https://accounts.google.com",
            "aud": CLIENT_ID,
            "iat": now,
            "exp": now + 3600,
            "nonce": nonce,
            **self.claims,
        }
        header = {"alg": "RS256", "kid": self.signing_key.kid}
        return jwt.encode(header, claims, self.signing_key)

    def handle(self, request: httpx2.Request) -> Response:
        if isinstance(self.outage, Exception):
            raise self.outage
        if self.outage is not None:
            return self.outage
        if str(request.url) == JWKS_URL:
            return Response(200, json={"keys": [self.key.as_dict(private=False)]})
        assert str(request.url) == TOKEN_URL
        assert request.headers["authorization"] == CLIENT_AUTH
        form = {name: values[0] for name, values in parse_qs(request.content.decode()).items()}
        flow = self.flows.pop(form["code"], None)  # a code works once
        if flow is None:
            return Response(400, json={"error": "invalid_grant"})
        # PKCE: the verifier must hash to the challenge sent at the start.
        digest = hashlib.sha256(form["code_verifier"].encode()).digest()
        assert base64.urlsafe_b64encode(digest).rstrip(b"=").decode() == flow["code_challenge"]
        assert form["redirect_uri"] == flow["redirect_uri"] == REDIRECT_URI
        body = {
            "access_token": "test-access-token",
            "token_type": "Bearer",
            "expires_in": 3599,
            "id_token": self.id_token(flow["nonce"]),
        }
        return Response(200, json=body)


@pytest.fixture
def google(app: FastAPI) -> Iterator[FakeGoogle]:
    """Sign-in with Google turned on, against the fake Google."""
    fake = FakeGoogle()
    settings = AuthSettings(google_client_id=CLIENT_ID, google_client_secret=CLIENT_SECRET)  # pyright: ignore[reportCallIssue]
    previous = app.state.google
    app.state.google = create_google(settings, transport=httpx2.MockTransport(fake.handle))
    yield fake
    app.state.google = previous


async def start(client: AsyncClient, google: FakeGoogle) -> str:
    """Go to Google as the button does and sign in there; returns the state Google sends back."""
    response = await client.get("/api/auth/google/start")
    assert response.status_code == 302
    return google.authorize(response.headers["location"])


async def finish(client: AsyncClient, state: str, code: str | None = None) -> Response:
    """What the web app's callback page sends."""
    data = {"code": code or code_for(state), "state": state}
    return await client.post("/api/auth/google/finish", data=data, headers=csrf(client))


async def sign_in(client: AsyncClient, google: FakeGoogle) -> Response:
    return await finish(client, await start(client, google))


async def user_count(db: AsyncSession) -> int:
    return (await db.execute(select(func.count()).select_from(User))).scalar_one()


async def only_user(db: AsyncSession) -> User:
    [user] = (await db.scalars(select(User))).all()
    return user


# --- Signing in ---


async def test_start_sends_the_browser_to_google_with_pkce_and_a_nonce(
    client: AsyncClient, google: FakeGoogle
) -> None:
    response = await client.get("/api/auth/google/start")

    assert response.status_code == 302
    url = urlsplit(response.headers["location"])
    assert f"{url.scheme}://{url.netloc}{url.path}" == AUTHORIZE_URL
    query = {name: values[0] for name, values in parse_qs(url.query).items()}
    assert query["client_id"] == CLIENT_ID
    assert query["redirect_uri"] == REDIRECT_URI
    assert query["response_type"] == "code"
    assert query["scope"] == "openid email"  # no name or picture (ADR 0014)
    assert query["code_challenge_method"] == "S256"
    assert query["prompt"] == "select_account"
    assert query["state"] and query["nonce"] and query["code_challenge"]


async def test_first_sign_in_creates_an_account_and_signs_in(
    client: AsyncClient, google: FakeGoogle
) -> None:
    response = await sign_in(client, google)

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == EMAIL
    assert HANDLE.fullmatch(body["handle"])
    assert (await client.get("/api/auth/me")).json() == body


async def test_new_account_has_the_google_id_no_password_and_watch_later(
    client: AsyncClient, db: AsyncSession, google: FakeGoogle
) -> None:
    await sign_in(client, google)

    user = await only_user(db)
    assert user.google_sub == SUB
    assert user.password_hash is None
    assert len(await watch_laters(db, user)) == 1


async def test_repeated_sign_in_finds_the_account_with_a_new_session(
    app: FastAPI, client: AsyncClient, db: AsyncSession, google: FakeGoogle
) -> None:
    first = (await sign_in(client, google)).json()
    old_id = client.cookies["sid"]

    response = await sign_in(client, google)

    assert response.status_code == 200
    assert response.json() == first
    assert await user_count(db) == 1
    assert client.cookies["sid"] != old_id
    assert await app.state.sessions.read(old_id) is None


async def test_changed_google_email_still_finds_the_account_by_its_id(
    client: AsyncClient, google: FakeGoogle
) -> None:
    first = (await sign_in(client, google)).json()
    google.claims["email"] = "anna.new@gmail.com"

    response = await sign_in(client, google)

    assert response.json() == first  # the stored email isn't updated (ADR 0014)


async def test_parallel_first_sign_ins_make_one_account(
    app: FastAPI,
    client: AsyncClient,
    db: AsyncSession,
    google: FakeGoogle,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Both requests find no user before either inserts: one insert wins, the other uses it.
    lookup = users.get_by_google_sub
    barrier = asyncio.Barrier(2)
    calls = 0

    async def look_up_together(session: AsyncSession, sub: str) -> User | None:
        nonlocal calls
        calls += 1
        first_round = calls <= 2  # each request's first lookup
        found = await lookup(session, sub)
        if first_round:
            async with asyncio.timeout(10):
                await barrier.wait()
        return found

    monkeypatch.setattr(users, "get_by_google_sub", look_up_together)
    async with client_from(app, "10.0.13.1") as laptop, client_from(app, "10.0.13.2") as phone:
        states = [await start(laptop, google), await start(phone, google)]
        responses = await asyncio.gather(finish(laptop, states[0]), finish(phone, states[1]))

    assert [response.status_code for response in responses] == [200, 200]
    assert responses[0].json() == responses[1].json()
    assert await user_count(db) == 1


async def test_rotated_google_key_is_fetched_again(client: AsyncClient, google: FakeGoogle) -> None:
    assert (await sign_in(client, google)).status_code == 200  # the keys are cached now
    google.key = google.signing_key = new_key("key-2")

    assert (await sign_in(client, google)).status_code == 200


# --- Emails that belong to another account ---


@pytest.mark.parametrize("taken", [EMAIL, "Anna@Gmail.COM"], ids=["same case", "other case"])
async def test_email_of_a_password_account_is_refused_and_not_linked(
    app: FastAPI, client: AsyncClient, db: AsyncSession, google: FakeGoogle, taken: str
) -> None:
    async with client_from(app, "10.0.5.1") as owner:
        assert (await signup(owner, email=taken)).status_code == 201

    response = await sign_in(client, google)

    assert response.status_code == 409
    assert response.json() == {"detail": GOOGLE_EMAIL_TAKEN}
    assert "sid" not in client.cookies
    assert (await only_user(db)).google_sub is None


async def test_pre_hijacked_email_gives_the_attacker_nothing(
    app: FastAPI, client: AsyncClient, db: AsyncSession, google: FakeGoogle
) -> None:
    # The attacker signs up the victim's Gmail with a password before the victim comes.
    async with client_from(app, "10.0.6.1") as attacker:
        own = (await signup(attacker, email=EMAIL)).json()

        response = await sign_in(client, google)  # the victim

        assert response.status_code == 409
        assert (await client.get("/api/auth/me")).status_code == 401
        assert (await attacker.get("/api/auth/me")).json() == own
    user = await only_user(db)
    assert user.google_sub is None
    assert user.password_hash is not None


async def test_another_google_account_with_a_taken_email_is_refused(
    app: FastAPI, client: AsyncClient, db: AsyncSession, google: FakeGoogle
) -> None:
    await sign_in(client, google)
    google.claims["sub"] = OTHER_SUB  # e.g. a work address moved to a new Google account

    async with client_from(app, "10.0.7.1") as other:
        response = await sign_in(other, google)
        assert "sid" not in other.cookies

    assert response.status_code == 409
    assert (await only_user(db)).google_sub == SUB


async def test_password_login_to_a_google_account_fails(
    client: AsyncClient, google: FakeGoogle
) -> None:
    await sign_in(client, google)

    response = await login(client, email=EMAIL)

    assert response.status_code == 401


async def test_password_signup_with_a_google_accounts_email_is_refused(
    client: AsyncClient, google: FakeGoogle
) -> None:
    await sign_in(client, google)

    response = await signup(client, email=EMAIL)

    assert response.status_code == 409


# --- Blocked accounts ---


@pytest.mark.parametrize("status", [UserStatus.BANNED, UserStatus.TERMINATED])
async def test_blocked_account_cant_sign_in_with_google(
    client: AsyncClient, db: AsyncSession, google: FakeGoogle, status: UserStatus
) -> None:
    await sign_in(client, google)
    await db.execute(update(User).where(User.google_sub == SUB).values(status=status))
    await db.commit()

    response = await sign_in(client, google)

    assert response.status_code == 403
    assert response.json() == {"detail": BLOCKED[status]}
    assert "sid" not in response.cookies


# --- What Google says ---


@pytest.mark.parametrize(
    "claims",
    [
        {"sub": SUB, "email": EMAIL, "email_verified": False},
        {"sub": SUB, "email": EMAIL},
        {"sub": SUB, "email_verified": True},
        {"sub": SUB, "email": "annaé@gmail.com", "email_verified": True},
    ],
    ids=["unverified email", "no email_verified", "no email", "non-ASCII email"],
)
async def test_account_without_a_usable_email_is_refused(
    client: AsyncClient, db: AsyncSession, google: FakeGoogle, claims: dict[str, Any]
) -> None:
    google.claims = claims

    response = await sign_in(client, google)

    assert response.status_code == 400
    assert await user_count(db) == 0


async def test_code_google_refuses_is_a_400(
    client: AsyncClient, db: AsyncSession, google: FakeGoogle
) -> None:
    state = await start(client, google)

    response = await finish(client, state, code="expired-code")  # Google: invalid_grant

    assert response.status_code == 400
    assert await user_count(db) == 0


@pytest.mark.parametrize(
    "claims",
    [
        {"aud": "someone-else.apps.googleusercontent.com"},
        # Another client's token that names ours as the authorized party: still not for us.
        {"aud": "someone-else.apps.googleusercontent.com", "azp": CLIENT_ID},
        {"nonce": "nonce-of-another-sign-in"},
        {"iss": "https://accounts.example.com"},
        {"exp": int(time.time()) - 600},
    ],
    ids=["other audience", "other audience, our azp", "wrong nonce", "other issuer", "expired"],
)
async def test_id_token_with_wrong_claims_is_refused(
    client: AsyncClient, db: AsyncSession, google: FakeGoogle, claims: dict[str, Any]
) -> None:
    google.claims |= claims

    response = await sign_in(client, google)

    assert response.status_code == 400
    assert await user_count(db) == 0


@pytest.mark.parametrize("kid", ["key-unknown", "key-1"], ids=["unknown kid", "known kid"])
async def test_id_token_signed_by_another_key_is_refused(
    client: AsyncClient, db: AsyncSession, google: FakeGoogle, kid: str
) -> None:
    google.signing_key = new_key(kid)

    response = await sign_in(client, google)

    assert response.status_code == 400
    assert await user_count(db) == 0


@pytest.mark.parametrize(
    "outage",
    [
        httpx2.ConnectError("no route to host"),
        httpx2.ReadTimeout("timed out"),
        Response(503, text="Service Unavailable"),
    ],
    ids=["unreachable", "timeout", "server error"],
)
async def test_google_outage_is_a_502(
    client: AsyncClient,
    db: AsyncSession,
    google: FakeGoogle,
    outage: Exception | Response,
) -> None:
    state = await start(client, google)
    google.outage = outage

    response = await finish(client, state)

    assert response.status_code == 502
    assert await user_count(db) == 0


# --- The state ---


async def test_finish_without_start_is_refused(client: AsyncClient, google: FakeGoogle) -> None:
    response = await finish(client, "state-from-nowhere")

    assert response.status_code == 400


async def test_state_from_another_browser_is_refused(
    app: FastAPI, client: AsyncClient, db: AsyncSession, google: FakeGoogle
) -> None:
    # Login CSRF: the attacker's code and state, sent from the victim's browser.
    async with client_from(app, "10.0.8.1") as attacker:
        state = await start(attacker, google)
    await start(client, google)  # the victim's own sign-in is under way

    response = await finish(client, state)

    assert response.status_code == 400
    assert await user_count(db) == 0


async def test_state_works_once(client: AsyncClient, google: FakeGoogle) -> None:
    state = await start(client, google)
    assert (await finish(client, state)).status_code == 200

    response = await finish(client, state)

    assert response.status_code == 400


async def test_state_cookie_has_safe_flags(client: AsyncClient, google: FakeGoogle) -> None:
    response = await client.get("/api/auth/google/start")

    cookie = response.headers["set-cookie"].lower()
    assert cookie.startswith("google_oauth=")
    assert "httponly" in cookie
    assert "samesite=lax" in cookie
    assert "path=/api/auth/google;" in cookie
    assert "max-age=600" in cookie  # 10 minutes for one sign-in


# --- Requests ---


@pytest.mark.parametrize("data", [{"state": "s"}, {"code": "c"}], ids=["no code", "no state"])
async def test_finish_checks_its_form(
    client: AsyncClient, google: FakeGoogle, data: dict[str, str]
) -> None:
    response = await client.post("/api/auth/google/finish", data=data)

    assert response.status_code == 422


@pytest.mark.parametrize("origin", [None, "http://evil.example"], ids=["no origin", "other site"])
async def test_finish_from_another_origin_is_refused(
    app: FastAPI, db: AsyncSession, google: FakeGoogle, origin: str | None
) -> None:
    async with client_from(app, "10.0.9.1", origin=origin) as browser:
        response = await sign_in(browser, google)

    assert response.status_code == 403
    assert await user_count(db) == 0


async def test_finish_is_limited_per_ip(
    app: FastAPI, client: AsyncClient, google: FakeGoogle
) -> None:
    async with client_from(app, "10.0.10.1") as browser:
        for _ in range(10):
            assert (await finish(browser, "state-from-nowhere")).status_code == 400

        assert (await finish(browser, "state-from-nowhere")).status_code == 429


async def test_new_google_accounts_count_as_sign_ups_per_ip(
    app: FastAPI, db: AsyncSession, google: FakeGoogle
) -> None:
    async with client_from(app, "10.0.11.1") as browser:
        for n in range(4):  # password sign-ups and Google sign-ups share the limit of 5
            assert (await signup(browser, f"user{n}@example.com")).status_code == 201
        google.claims = {"sub": SUB, "email": EMAIL, "email_verified": True}
        assert (await sign_in(browser, google)).status_code == 200
        # Signing in again to that account makes nothing new: not counted.
        assert (await sign_in(browser, google)).status_code == 200

        google.claims = {"sub": OTHER_SUB, "email": "ben@gmail.com", "email_verified": True}
        response = await sign_in(browser, google)

    assert response.status_code == 429
    assert await user_count(db) == 5


# --- On and off ---


async def test_google_sign_in_is_off_without_a_client_id(client: AsyncClient) -> None:
    assert (await client.get("/api/auth/providers")).json() == {"google": False}
    assert (await client.get("/api/auth/google/start")).status_code == 404
    response = await client.post("/api/auth/google/finish", data={"code": "c", "state": "s"})
    assert response.status_code == 404


async def test_providers_list_google_when_it_is_on(client: AsyncClient, google: FakeGoogle) -> None:
    response = await client.get("/api/auth/providers")

    assert response.json() == {"google": True}
