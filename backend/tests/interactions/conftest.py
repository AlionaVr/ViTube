"""Accounts and a ready video for tests of likes, comments and views."""

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import AsyncExitStack
from types import ModuleType
from typing import Any

import pytest
from fastapi import FastAPI
from httpx2 import ASGITransport, AsyncClient, Cookies, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.models import User
from app.modules.videos.models import Video
from tests.videos.factories import make_video

PASSWORD = "correct horse battery"
OWNER_EMAIL = "owner@example.com"
VIEWER_EMAIL = "viewer@example.com"

MakeViewers = Callable[[int], Awaitable[list[AsyncClient]]]


def browser(app: FastAPI, ip: str, cookies: Cookies | None = None) -> AsyncClient:
    """A client like another browser: its own IP and cookies (or a copy of another's session)."""
    transport = ASGITransport(app=app, client=(ip, 1234))
    headers = {"Origin": "http://test"}  # as a browser sends it from our pages
    return AsyncClient(
        transport=transport, base_url="http://test", headers=headers, cookies=cookies
    )


def csrf(client: AsyncClient) -> dict[str, str]:
    """The header the web app adds to unsafe requests once it has a session."""
    token = client.cookies.get("csrf_token")
    return {"X-CSRF-Token": token} if token else {}


async def signup(client: AsyncClient, email: str) -> None:
    response = await client.post("/api/auth/signup", json={"email": email, "password": PASSWORD})
    assert response.status_code == 201


# --- Comments ---


async def post(
    client: AsyncClient, video: Video, text: str = "Nice video", parent_id: object = None
) -> Response:
    body = {"text": text} | ({"parent_id": str(parent_id)} if parent_id else {})
    return await client.post(
        f"/api/videos/{video.public_id}/comments", json=body, headers=csrf(client)
    )


async def posted(
    client: AsyncClient, video: Video, text: str = "Nice video", parent_id: object = None
) -> dict[str, object]:
    response = await post(client, video, text, parent_id)
    assert response.status_code == 201
    return response.json()


async def comments_of(
    client: AsyncClient, video: Video, sort: str = "top", cursor: str | None = None
) -> Response:
    params = {"sort": sort} | ({"cursor": cursor} if cursor else {})
    return await client.get(f"/api/videos/{video.public_id}/comments", params=params)


async def replies_to(
    client: AsyncClient, comment_id: object, cursor: str | None = None
) -> Response:
    params = {"cursor": cursor} if cursor else {}
    return await client.get(f"/api/comments/{comment_id}/replies", params=params)


def ids(response: Response) -> list[str]:
    assert response.status_code == 200
    return [item["id"] for item in response.json()["items"]]


def meet_after(
    monkeypatch: pytest.MonkeyPatch, module: ModuleType, name: str, parties: int
) -> None:
    """Parallel requests wait for each other after `module.name`, then go on together.

    Like a CyclicBarrier: without it a fast request may finish before the next one starts,
    and a read-then-write race goes unseen. Keep `parties` below the DB pool size (15).
    """
    original = getattr(module, name)
    barrier = asyncio.Barrier(parties)

    async def wrapped(*args: Any, **kwargs: Any) -> Any:
        result = await original(*args, **kwargs)
        async with asyncio.timeout(10):  # a request that never comes fails the test, not hangs it
            await barrier.wait()
        return result

    monkeypatch.setattr(module, name, wrapped)


async def user_by_email(db: AsyncSession, email: str) -> User:
    user = await db.scalar(select(User).where(User.email == email))
    assert user is not None
    return user


@pytest.fixture
async def owner(db: AsyncSession, client: AsyncClient) -> AsyncClient:
    """`client`, signed in. After `db`: its reset would wipe the account."""
    await signup(client, OWNER_EMAIL)
    return client


@pytest.fixture
async def viewer(app: FastAPI, db: AsyncSession, client: AsyncClient) -> AsyncIterator[AsyncClient]:
    """Another signed-in user. After `db` and `client`: their resets would wipe the account."""
    async with browser(app, "10.0.0.2") as other:
        await signup(other, VIEWER_EMAIL)
        yield other


@pytest.fixture
async def guest(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with browser(app, "10.0.0.3") as other:
        yield other


@pytest.fixture
async def make_viewers(
    app: FastAPI, db: AsyncSession, client: AsyncClient
) -> AsyncIterator[MakeViewers]:
    """Signed-in users, each from its own IP: signup is limited per IP."""
    async with AsyncExitStack() as stack:

        async def make(count: int) -> list[AsyncClient]:
            clients = []
            for number in range(count):
                other = await stack.enter_async_context(browser(app, f"10.1.0.{number}"))
                await signup(other, f"user{number}@example.com")
                clients.append(other)
            return clients

        yield make


@pytest.fixture
async def video(db: AsyncSession, owner: AsyncClient) -> Video:
    """The owner's public, ready video."""
    return await make_video(db, await user_by_email(db, OWNER_EMAIL))
