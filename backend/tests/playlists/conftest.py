"""Signed-in clients and helpers for playlist tests."""

import asyncio
from collections.abc import Callable
from typing import Any
from uuid import UUID

import pytest
from httpx2 import AsyncClient, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.playlists import repository
from app.modules.playlists.models import Playlist, PlaylistItem
from app.modules.videos.models import Video
from tests.interactions.conftest import csrf, guest, make_viewers, owner, viewer

__all__ = ["guest", "make_viewers", "owner", "viewer"]


async def create(
    client: AsyncClient, title: str = "Watch list", visibility: str = "private"
) -> str:
    response = await client.post(
        "/api/playlists", json={"title": title, "visibility": visibility}, headers=csrf(client)
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def add(client: AsyncClient, playlist_id: str, video: Video) -> Response:
    return await client.put(
        f"/api/playlists/{playlist_id}/items/{video.public_id}", headers=csrf(client)
    )


async def remove(client: AsyncClient, playlist_id: str, video: Video) -> Response:
    return await client.delete(
        f"/api/playlists/{playlist_id}/items/{video.public_id}", headers=csrf(client)
    )


async def move(
    client: AsyncClient, playlist_id: str, video: Video, before: Video | None
) -> Response:
    return await client.patch(
        f"/api/playlists/{playlist_id}/items/{video.public_id}",
        json={"before": before.public_id if before else None},
        headers=csrf(client),
    )


async def item_ids(client: AsyncClient, playlist_id: str) -> list[str]:
    response = await client.get(f"/api/playlists/{playlist_id}/items")
    assert response.status_code == 200, response.text
    return [item["video"]["id"] for item in response.json()["items"]]


async def stored(db: AsyncSession, playlist_id: str) -> tuple[int, list[int]]:
    """(video_count, positions in order) as committed now."""
    pid = UUID(playlist_id)
    count = await db.scalar(select(Playlist.video_count).where(Playlist.id == pid))
    positions = await db.scalars(
        select(PlaylistItem.position)
        .where(PlaylistItem.playlist_id == pid)
        .order_by(PlaylistItem.position)
    )
    rows = await db.scalar(
        select(func.count()).select_from(PlaylistItem).where(PlaylistItem.playlist_id == pid)
    )
    assert count is not None
    result = list(positions)
    assert rows == len(result)
    return count, result


@pytest.fixture
def at_the_lock(monkeypatch: pytest.MonkeyPatch) -> Callable[[int], None]:
    """`at_the_lock(n)`: the next n playlist writes wait for each other, then all ask for the
    playlist lock at once. Like a CyclicBarrier just before SELECT ... FOR NO KEY UPDATE."""

    def arm(parties: int) -> None:
        original = repository.lock_own
        barrier = asyncio.Barrier(parties)

        async def wrapped(*args: Any, **kwargs: Any) -> Any:
            async with asyncio.timeout(10):  # a request that never comes fails the test
                await barrier.wait()
            return await original(*args, **kwargs)

        monkeypatch.setattr(repository, "lock_own", wrapped)

    return arm
