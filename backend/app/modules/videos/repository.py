"""Video queries. No commits: the service decides when a transaction ends."""

from uuid import UUID

from sqlalchemy import exists, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.models import User
from app.modules.videos.models import Video, VideoAccess, VideoStatus, Visibility


async def get_by_public_id(db: AsyncSession, public_id: str) -> Video | None:
    return await db.scalar(select(Video).where(Video.public_id == public_id))


async def get_owner(db: AsyncSession, video: Video) -> User:
    # No query when the owner is the signed-in user: the session's identity map has them.
    return await db.get_one(User, video.owner_id)


async def has_access(db: AsyncSession, video_id: UUID, user_id: UUID) -> bool:
    query = select(exists().where(VideoAccess.video_id == video_id, VideoAccess.user_id == user_id))
    return bool(await db.scalar(query))


async def insert_unless_taken(
    db: AsyncSession,
    *,
    public_id: str,
    owner_id: UUID,
    title: str,
    description: str,
    visibility: Visibility,
) -> Video | None:
    """Insert a draft. None if the public id is taken: no exception, no savepoint needed."""
    statement = (
        insert(Video)
        .values(
            public_id=public_id,
            owner_id=owner_id,
            title=title,
            description=description,
            visibility=visibility,
        )
        .on_conflict_do_nothing(index_elements=[Video.public_id])
        .returning(Video)
    )
    return await db.scalar(statement)


async def move_status(
    db: AsyncSession, video_id: UUID, *, current: VideoStatus, new: VideoStatus
) -> bool:
    """Change the status only if it is still `current`. False if someone changed it first."""
    statement = (
        update(Video)
        .where(Video.id == video_id, Video.status == current)
        .values(status=new)
        .returning(Video.id)
    )
    return await db.scalar(statement) is not None
