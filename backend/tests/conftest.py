"""Shared fixtures: real Postgres and Redis in Docker (testcontainers), the app, an HTTP client."""

import subprocess
import sys
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx2 import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from testcontainers.community.postgres import PostgresContainer
from testcontainers.community.redis import RedisContainer

from app.core.config import get_settings
from app.db.models import Base
from app.main import app as vitube_app

BACKEND_DIR = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def services() -> Iterator[None]:
    """Start Postgres and Redis once per run (same images as compose.yaml) and migrate the DB."""
    with (
        PostgresContainer("postgres:18-alpine", driver="asyncpg") as postgres,
        RedisContainer("redis:8-alpine") as redis,
        pytest.MonkeyPatch.context() as env,
    ):
        host, port = redis.get_container_host_ip(), redis.get_exposed_port(6379)
        env.setenv("DATABASE_URL", postgres.get_connection_url())
        env.setenv("REDIS_URL", f"redis://{host}:{port}/0")
        get_settings.cache_clear()  # settings are cached; rebuild them from the new env
        # A subprocess: alembic's env.py calls asyncio.run() and resets logging.
        subprocess.run(  # noqa: S603 fixed command, no user input
            [sys.executable, "-m", "alembic", "upgrade", "head"], cwd=BACKEND_DIR, check=True
        )
        yield


@pytest.fixture(scope="session")
async def app(services: None) -> AsyncIterator[FastAPI]:
    """The app with its lifespan running: the DB pool and Redis client are open."""
    async with vitube_app.router.lifespan_context(vitube_app):
        yield vitube_app


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    """An HTTP client on empty tables and an empty Redis."""
    await reset_state(app)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
async def db(app: FastAPI) -> AsyncIterator[AsyncSession]:
    """A DB session on empty tables and an empty Redis."""
    await reset_state(app)
    async with app.state.sessionmaker() as session:
        yield session


async def reset_state(app: FastAPI) -> None:
    tables = ", ".join(table.name for table in Base.metadata.sorted_tables)
    if tables:
        async with app.state.sessionmaker() as session:
            await session.execute(text(f"TRUNCATE {tables} CASCADE"))  # noqa: S608 names from models
            await session.commit()
    await app.state.redis.flushdb()
