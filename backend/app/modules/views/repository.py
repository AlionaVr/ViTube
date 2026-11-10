"""View count queries. No commits: the service decides when a transaction ends."""

from uuid import UUID

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.videos.models import Video


async def add_view(db: AsyncSession, video_id: UUID) -> None:
    """view_count + 1 in the DB itself, so parallel views don't overwrite each other."""
    await db.execute(
        update(Video).where(Video.id == video_id).values(view_count=Video.view_count + 1)
    )
