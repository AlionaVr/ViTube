from fastapi import FastAPI
from httpx2 import AsyncClient
from sqlalchemy import text


async def test_migrations_enable_extensions(app: FastAPI) -> None:
    async with app.state.sessionmaker() as session:
        result = await session.execute(text("SELECT extname FROM pg_extension"))
        extensions = set(result.scalars())

    assert {"citext", "pg_trgm"} <= extensions


async def test_redis_is_reachable(app: FastAPI) -> None:
    assert await app.state.redis.ping()


async def test_client_reaches_the_app(client: AsyncClient) -> None:
    response = await client.get("/api/health")

    assert response.status_code == 200
