"""Signed-in clients and helpers for playlist tests."""

from uuid import UUID

from httpx2 import AsyncClient, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

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
