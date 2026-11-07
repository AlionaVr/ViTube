"""Shared fixtures: real Postgres and Redis in Docker (testcontainers), the app, an HTTP client.

Like production: the superuser runs the migrate job (migrations, then the app role), and the app
itself runs as vitube_app. So every test also checks that the app role has the grants it needs.
"""

import os
import subprocess
import sys
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx2 import ASGITransport, AsyncClient
from redis.asyncio import Redis
from sqlalchemy import make_url, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from testcontainers.community.postgres import PostgresContainer
from testcontainers.community.redis import RedisContainer

from app.core.config import get_settings
from app.db.models import Base
from app.db.roles import APP_ROLE
from app.main import app as vitube_app

BACKEND_DIR = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Services:
    admin_url: str  # the superuser: migrations, role setup, test cleanup
    app_url: str  # vitube_app: what the app uses


@pytest.fixture(scope="session")
def services() -> Iterator[Services]:
    """Start Postgres and Redis once per run (same images as compose.yaml); run the migrate job."""
    with (
        PostgresContainer("postgres:18-alpine", driver="asyncpg") as postgres,
        RedisContainer("redis:8-alpine") as redis,
        pytest.MonkeyPatch.context() as env,
    ):
        admin_url = postgres.get_connection_url()
        app_password = "app-test-password"
        app_url = (
            make_url(admin_url)
            .set(username=APP_ROLE, password=app_password)
            .render_as_string(hide_password=False)
        )
        host, port = redis.get_container_host_ip(), redis.get_exposed_port(6379)
        env.setenv("REDIS_URL", f"redis://{host}:{port}/0")
        env.setenv("SESSION_SECRET", "test-session-secret-0123456789abcdef")
        # Same steps as the migrate job. Subprocesses: alembic's env.py calls asyncio.run().
        job_env = {**os.environ, "DATABASE_URL": admin_url, "POSTGRES_APP_PASSWORD": app_password}
        for args in (["alembic", "upgrade", "head"], ["app.db.roles"]):
            subprocess.run(  # noqa: S603 fixed commands, no user input
                [sys.executable, "-m", *args], cwd=BACKEND_DIR, env=job_env, check=True
            )
        env.setenv("DATABASE_URL", app_url)
        get_settings.cache_clear()  # settings are cached; rebuild them from the new env
        yield Services(admin_url, app_url)


@pytest.fixture(scope="session")
async def admin_engine(services: Services) -> AsyncIterator[AsyncEngine]:
    """The superuser: for cleanup and for tests that act like a migration."""
    engine = create_async_engine(services.admin_url)
    yield engine
    await engine.dispose()


@pytest.fixture(scope="session")
async def app(services: Services) -> AsyncIterator[FastAPI]:
    """The app with its lifespan running: the DB pool (as vitube_app) and Redis client are open."""
    async with vitube_app.router.lifespan_context(vitube_app):
        yield vitube_app


@pytest.fixture
async def client(app: FastAPI, admin_engine: AsyncEngine) -> AsyncIterator[AsyncClient]:
    """An HTTP client on empty tables and an empty Redis."""
    await reset_state(app, admin_engine)
    transport = ASGITransport(app=app)
    # Origin as a browser sends it from our own pages: the CSRF check wants it on unsafe methods.
    headers = {"Origin": "http://test"}
    async with AsyncClient(transport=transport, base_url="http://test", headers=headers) as client:
        yield client


@pytest.fixture
async def db(app: FastAPI, admin_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """A DB session as the app role, on empty tables and an empty Redis."""
    await reset_state(app, admin_engine)
    async with app.state.sessionmaker() as session:
        yield session


@pytest.fixture
async def redis(app: FastAPI) -> Redis:
    """The app's Redis client, on an empty Redis."""
    await app.state.redis.flushdb()
    return app.state.redis


async def reset_state(app: FastAPI, admin_engine: AsyncEngine) -> None:
    tables = ", ".join(table.name for table in Base.metadata.sorted_tables)
    if tables:
        # The superuser: the app role may not TRUNCATE.
        async with admin_engine.begin() as conn:
            await conn.execute(text(f"TRUNCATE {tables} CASCADE"))  # noqa: S608 names from models
    await app.state.redis.flushdb()
