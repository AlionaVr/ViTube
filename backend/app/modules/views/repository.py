"""View count queries. No commits: the service decides when a transaction ends."""

from uuid import UUID

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.videos.models import Video


async def add_view(db: AsyncSession, video_id: UUID) -> bool:
    """view_count + 1 in the DB itself, so parallel views don't overwrite each other. False: the
    video is hidden (checked again after a hide under way, as comments.repository.add_comment)."""
    statement = (
        update(Video)
        .where(Video.id == video_id, ~Video.is_hidden)
        .values(view_count=Video.view_count + 1)
        .returning(Video.id)
    )
    return await db.scalar(statement) is not None
