"""Roles (ADR 0009): nested checks and the set-role command."""

import asyncio
import sys
from pathlib import Path

import pytest
from fastapi import Depends, FastAPI
from httpx2 import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import register_error_handlers
from app.modules.audit.repository import Actor
from app.modules.auth import service
from app.modules.auth.deps import require_role
from app.modules.users.models import Role

BACKEND_DIR = Path(__file__).resolve().parents[2]
EMAIL = "anna@example.com"
CREDENTIALS = {"email": EMAIL, "password": "correct horse battery"}


@pytest.mark.parametrize(
    ("role", "minimum", "allowed"),
    [
        (Role.USER, Role.USER, True),
        (Role.USER, Role.MODERATOR, False),
        (Role.USER, Role.ADMIN, False),
        (Role.MODERATOR, Role.USER, True),
        (Role.MODERATOR, Role.MODERATOR, True),
        (Role.MODERATOR, Role.ADMIN, False),
        (Role.ADMIN, Role.USER, True),
        (Role.ADMIN, Role.MODERATOR, True),
        (Role.ADMIN, Role.ADMIN, True),
    ],
)
def test_roles_are_nested(role: Role, minimum: Role, allowed: bool) -> None:
    assert role.at_least(minimum) is allowed


@pytest.fixture
def probe(app: FastAPI) -> FastAPI:
    """An app with one moderators-only route, on the real app's DB and sessions."""
    probe = FastAPI()
    register_error_handlers(probe)
    probe.state.sessionmaker = app.state.sessionmaker
    probe.state.sessions = app.state.sessions

    @probe.get("/moderation", dependencies=[Depends(require_role(Role.MODERATOR))])
    async def moderation() -> None:
        pass

    return probe


async def test_require_role_lets_in_only_that_role_and_above(
    client: AsyncClient, db: AsyncSession, probe: FastAPI
) -> None:
    async def status(session_id: str | None) -> int:
        headers = {"Cookie": f"sid={session_id}"} if session_id else {}
        transport = ASGITransport(app=probe)
        async with AsyncClient(transport=transport, base_url="http://test") as probe_client:
            return (await probe_client.get("/moderation", headers=headers)).status_code

    assert await status(None) == 401
    await client.post("/api/auth/signup", json=CREDENTIALS)
    session_id = client.cookies["sid"]
    assert await status(session_id) == 403

    for role in (Role.MODERATOR, Role.ADMIN):
        await service.set_role(db, Actor.cli(None), EMAIL, role)
        assert await status(session_id) == 200


async def run_cli(*args: str) -> tuple[int | None, str]:
    # A real process, as in the container; it connects as the app role, like the api.
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "app.cli",
        *args,
        cwd=BACKEND_DIR,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    output, _ = await process.communicate()
    return process.returncode, output.decode()


async def test_set_role_applies_to_an_open_session_at_once(client: AsyncClient) -> None:
    await client.post("/api/auth/signup", json=CREDENTIALS)
    assert (await client.get("/api/auth/me")).json()["role"] == "user"

    code, output = await run_cli("set-role", EMAIL, "admin")

    assert (code, output) == (0, f"{EMAIL}: admin\n")
    assert (await client.get("/api/auth/me")).json()["role"] == "admin"  # same session


async def test_set_role_for_an_unknown_email_fails(client: AsyncClient) -> None:
    code, output = await run_cli("set-role", "nobody@example.com", "admin")

    assert code == 1
    assert "No user with this email" in output


async def test_set_role_refuses_an_unknown_role(client: AsyncClient) -> None:
    code, output = await run_cli("set-role", EMAIL, "superuser")

    assert code == 2
    assert "invalid choice" in output
