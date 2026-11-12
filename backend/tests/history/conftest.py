"""Signed-in clients and helpers for watch history tests."""

from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx2 import AsyncClient, Response
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.history.models import HistoryEntry
from app.modules.users.models import Role, User
from app.modules.videos.models import Video, Visibility
from tests.interactions.conftest import browser, csrf, guest, owner, signup, video, viewer
from tests.videos.factories import set_role

__all__ = ["guest", "owner", "video", "viewer"]

MODERATOR_EMAIL = "mod@example.com"


async def save(client: AsyncClient, video: Video, position_sec: int = 5) -> Response:
    return await client.put(
        f"/api/me/history/{video.public_id}",
        json={"position_sec": position_sec},
        headers=csrf(client),
    )


async def listed(client: AsyncClient) -> list[str]:
    """Public ids on the first page of the client's history."""
    response = await client.get("/api/me/history")
    assert response.status_code == 200, response.text
    return [item["video"]["id"] for item in response.json()["items"]]


async def position(db: AsyncSession, email: str, video: Video) -> int | None:
    """The saved position as committed now; None without a row."""
    query = (
        select(HistoryEntry.position_sec)
        .join(User, User.id == HistoryEntry.user_id)
        .where(User.email == email, HistoryEntry.video_id == video.id)
    )
    return await db.scalar(query)


async def row_count(db: AsyncSession) -> int:
    return await db.scalar(select(func.count()).select_from(HistoryEntry)) or 0


async def make_private(db: AsyncSession, video: Video) -> None:
    """The owner turns a video private after people watched it."""
    await db.execute(
        update(Video).where(Video.id == video.id).values(visibility=Visibility.PRIVATE)
    )
    await db.commit()


@pytest.fixture
async def moderator(
    app: FastAPI, db: AsyncSession, client: AsyncClient
) -> AsyncIterator[AsyncClient]:
    """A signed-in moderator. After `db` and `client`: their resets would wipe the account."""
    async with browser(app, "10.0.0.4") as other:
        await signup(other, MODERATOR_EMAIL)
        await set_role(db, MODERATOR_EMAIL, Role.MODERATOR)
        yield other
