"""Video queries. No commits: the service decides when a transaction ends."""

from uuid import UUID

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.videos.models import Video, VideoAccess


async def get_by_public_id(db: AsyncSession, public_id: str) -> Video | None:
    return await db.scalar(select(Video).where(Video.public_id == public_id))


async def has_access(db: AsyncSession, video_id: UUID, user_id: UUID) -> bool:
    query = select(exists().where(VideoAccess.video_id == video_id, VideoAccess.user_id == user_id))
    return bool(await db.scalar(query))
