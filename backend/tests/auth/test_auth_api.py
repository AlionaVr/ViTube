"""/api/auth: sign up, sign in, sign out, /me, CSRF and rate limits (ADR 0005)."""

import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
from fastapi import FastAPI
from httpx2 import ASGITransport, AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limit import RateLimit
from app.modules.auth import service
from app.modules.users.models import User

EMAIL = "anna@example.com"
PASSWORD = "correct horse battery"
HANDLE = re.compile(r"user-[abcdefghjkmnpqrstuvwxyz23456789]{8}")


def csrf(client: AsyncClient) -> dict[str, str]:
    """The header the web app adds to unsafe requests once it has a session."""
    token = client.cookies.get("csrf_token")
    return {"X-CSRF-Token": token} if token else {}


async def signup(client: AsyncClient, email: str = EMAIL, password: str = PASSWORD) -> Response:
    body = {"email": email, "password": password}
    return await client.post("/api/auth/signup", json=body, headers=csrf(client))


async def login(client: AsyncClient, email: str = EMAIL, password: str = PASSWORD) -> Response:
    body = {"email": email, "password": password}
    return await client.post("/api/auth/login", json=body, headers=csrf(client))


@asynccontextmanager
async def client_from(
    app: FastAPI, ip: str, origin: str | None = "http://test"
) -> AsyncIterator[AsyncClient]:
    """A client with its own IP and cookies. origin=None sends no Origin header."""
    transport = ASGITransport(app=app, client=(ip, 1234))
    headers = {"Origin": origin} if origin else {}
    async with AsyncClient(transport=transport, base_url="http://test", headers=headers) as client:
        yield client


async def test_signup_creates_an_account_and_signs_in(client: AsyncClient) -> None:
    response = await signup(client)

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == EMAIL
    assert body["role"] == "user"
    assert HANDLE.fullmatch(body["handle"])
    assert (await client.get("/api/auth/me")).json() == body


async def test_session_cookies_have_safe_flags(client: AsyncClient) -> None:
    response = await signup(client)

    cookies = {c.split("=")[0]: c.lower() for c in response.headers.get_list("set-cookie")}
    assert "httponly" in cookies["sid"]
    assert "samesite=lax" in cookies["sid"]
    assert "max-age=2592000" in cookies["sid"]  # the absolute timeout: 30 days
    assert "httponly" not in cookies["csrf_token"]  # the web app reads it
    assert "samesite=lax" in cookies["csrf_token"]


async def test_password_is_stored_as_an_argon2id_hash(
    client: AsyncClient, db: AsyncSession
) -> None:
    await signup(client)

    stored = await db.scalar(select(User.password_hash))
    assert stored is not None
    assert stored.startswith("$argon2id$")
    assert PASSWORD not in stored


async def test_signup_with_a_taken_email_is_refused(client: AsyncClient) -> None:
    await signup(client)

    response = await signup(client, email="Anna@Example.COM")  # emails ignore case

    assert response.status_code == 409
    assert response.json() == {"detail": "This email is already registered"}


@pytest.mark.parametrize(
    "body",
    [
        {"email": "not-an-email", "password": PASSWORD},
        {"email": EMAIL, "password": "short"},
        {"email": EMAIL, "password": "x" * 129},
        {"email": EMAIL},
        {"email": "annaé@example.com", "password": PASSWORD},
    ],
    ids=["bad email", "short password", "long password", "no password", "non-ASCII name"],
)
async def test_signup_checks_input(client: AsyncClient, body: dict[str, str]) -> None:
    response = await client.post("/api/auth/signup", json=body)

    assert response.status_code == 422


async def test_signup_retries_a_taken_handle(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    handles = iter(["user-aaaaaaaa", "user-aaaaaaaa", "user-bbbbbbbb"])
    monkeypatch.setattr(service, "random_handle", lambda: next(handles))

    first = await signup(client, email="first@example.com")
    second = await signup(client, email="second@example.com")

    assert first.json()["handle"] == "user-aaaaaaaa"
    assert second.status_code == 201
    assert second.json()["handle"] == "user-bbbbbbbb"


async def test_signup_is_limited_per_ip(client: AsyncClient) -> None:
    for i in range(5):
        assert (await signup(client, email=f"user{i}@example.com")).status_code == 201

    response = await signup(client, email="one-more@example.com")

    assert response.status_code == 429
    assert int(response.headers["retry-after"]) > 0


async def test_login_starts_a_new_session_and_ends_the_old_one(
    app: FastAPI, client: AsyncClient
) -> None:
    await signup(client)
    old_id = client.cookies["sid"]

    response = await login(client)

    assert response.status_code == 200
    assert response.json()["email"] == EMAIL
    assert client.cookies["sid"] != old_id
    assert await app.state.sessions.read(old_id) is None
    assert (await client.get("/api/auth/me")).status_code == 200


async def test_unknown_email_and_wrong_password_get_the_same_response(
    client: AsyncClient,
) -> None:
    await signup(client)

    wrong_password = await login(client, password="wrong password")
    unknown_email = await login(client, email="nobody@example.com")

    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.content == unknown_email.content
    assert wrong_password.headers == unknown_email.headers
    assert wrong_password.json() == {"detail": "Wrong email or password"}


async def test_short_password_on_sign_in_is_just_wrong(client: AsyncClient) -> None:
    await signup(client)

    response = await login(client, password="short")

    assert response.status_code == 401  # not 422: old accounts keep working if the rule changes


async def test_unknown_email_still_runs_a_password_check(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    checked: list[str | None] = []
    real_check = service.verify_password

    async def spy(password_hash: str | None, password: str) -> bool:
        checked.append(password_hash)
        return await real_check(password_hash, password)

    monkeypatch.setattr(service, "verify_password", spy)

    await login(client, email="nobody@example.com")

    assert checked == [None]  # a check against a dummy hash: the same time as a real one


async def test_login_holds_no_db_connection_while_checking_the_password(
    app: FastAPI, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Logins queue for a hashing slot: holding a connection there would let a flood take the pool.
    await signup(client)
    pool = app.state.sessionmaker.kw["bind"].pool
    held: list[int] = []
    real_check = service.verify_password

    async def spy(password_hash: str | None, password: str) -> bool:
        held.append(pool.checkedout())
        return await real_check(password_hash, password)

    monkeypatch.setattr(service, "verify_password", spy)

    assert (await login(client)).status_code == 200
    assert (await login(client, email="nobody@example.com")).status_code == 401
    assert held == [0, 0]


async def test_login_is_limited_per_ip(app: FastAPI, client: AsyncClient) -> None:
    async with client_from(app, "10.0.0.1") as attacker, client_from(app, "10.0.0.2") as other:
        for i in range(10):  # different emails: only the IP limit applies
            assert (await login(attacker, email=f"user{i}@example.com")).status_code == 401

        assert (await login(attacker, email="user10@example.com")).status_code == 429
        assert (await login(other, email="user10@example.com")).status_code == 401


@pytest.mark.parametrize("registered", [True, False], ids=["known email", "unknown email"])
async def test_login_is_limited_per_email_from_one_ip(
    app: FastAPI, client: AsyncClient, registered: bool
) -> None:
    if registered:
        await signup(client)
    emails = [EMAIL, EMAIL.upper()]  # the same account, whatever the case

    async with client_from(app, "10.0.1.1") as guesser:
        for i in range(5):
            response = await login(guesser, email=emails[i % 2], password="wrong password")
            assert response.status_code == 401

        assert (await login(guesser, password="wrong password")).status_code == 429


async def test_guessing_from_one_ip_does_not_lock_the_owner_out(
    app: FastAPI, client: AsyncClient
) -> None:
    await signup(client)
    async with client_from(app, "10.0.1.1") as guesser:
        for _ in range(5):
            await login(guesser, password="wrong password")
        assert (await login(guesser)).status_code == 429  # blocked there, even with the password

    async with client_from(app, "10.0.1.2") as owner:
        assert (await login(owner)).status_code == 200


async def test_login_is_limited_per_email_across_ips(
    app: FastAPI, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The account-wide cap, made small here: 10 = two IPs at their own limit of 5.
    small_cap = RateLimit("login_email", limit=10, window=15 * 60)
    monkeypatch.setattr(service, "LOGIN_PER_EMAIL", small_cap)
    async with client_from(app, "10.0.2.1") as guesser:
        codes = [(await login(guesser, password="wrong password")).status_code for _ in range(7)]
        assert codes == [401] * 5 + [429] * 2  # blocked tries don't count toward the cap
    async with client_from(app, "10.0.2.2") as guesser:
        for _ in range(5):
            assert (await login(guesser, password="wrong password")).status_code == 401

    async with client_from(app, "10.0.2.99") as guesser:
        assert (await login(guesser, password="wrong password")).status_code == 429


async def test_successful_login_forgives_typos_from_that_ip(
    app: FastAPI, client: AsyncClient
) -> None:
    await signup(client)
    async with client_from(app, "10.0.3.1") as owner:
        for _ in range(4):
            assert (await login(owner, password="wrong password")).status_code == 401
        assert (await login(owner)).status_code == 200
        for _ in range(5):
            assert (await login(owner, password="wrong password")).status_code == 401


async def test_non_ascii_case_variant_of_an_email_is_refused(client: AsyncClient) -> None:
    # Python lowercases "İ" to "i" + a dot, Postgres to "i": such a variant would find the
    # account but get its own rate limit counter.
    await signup(client, email="aliona@example.com")

    response = await login(client, email="alİona@example.com")

    assert response.status_code == 422


async def test_internationalized_domain_is_kept_as_punycode(client: AsyncClient) -> None:
    response = await signup(client, email="anna@пример.рф")

    assert response.status_code == 201
    assert response.json()["email"] == "anna@xn--e1afmkfd.xn--p1ai"
    assert (await login(client, email="anna@пример.рф")).status_code == 200


async def test_logout_needs_the_csrf_token(client: AsyncClient) -> None:
    await signup(client)

    assert (await client.post("/api/auth/logout")).status_code == 403
    wrong = {"X-CSRF-Token": "wrong"}
    assert (await client.post("/api/auth/logout", headers=wrong)).status_code == 403
    assert (await client.get("/api/auth/me")).status_code == 200

    response = await client.post("/api/auth/logout", headers=csrf(client))

    assert response.status_code == 204
    assert "sid" not in client.cookies
    assert (await client.get("/api/auth/me")).status_code == 401


async def test_logout_without_a_session_does_nothing(client: AsyncClient) -> None:
    assert (await client.post("/api/auth/logout")).status_code == 204


async def test_non_ascii_csrf_token_is_refused_not_a_crash(client: AsyncClient) -> None:
    await signup(client)

    headers = {b"X-CSRF-Token": "токен".encode()}  # header bytes beyond ASCII
    response = await client.post("/api/auth/logout", headers=headers)

    assert response.status_code == 403


@pytest.mark.parametrize(
    "origin",
    [None, "http://evil.example", "null", "http://test.evil.example"],
    ids=["no origin", "other site", "opaque origin", "look-alike"],
)
async def test_unsafe_requests_from_other_origins_are_refused(
    app: FastAPI, client: AsyncClient, origin: str | None
) -> None:
    async with client_from(app, "10.0.4.1", origin=origin) as other_site:
        response = await signup(other_site)

    assert response.status_code == 403
    assert (await login(client)).status_code == 401  # no account was created


async def test_me_without_a_session_is_401(client: AsyncClient) -> None:
    response = await client.get("/api/auth/me")

    assert response.status_code == 401
    assert response.json() == {"detail": "Sign in required"}
