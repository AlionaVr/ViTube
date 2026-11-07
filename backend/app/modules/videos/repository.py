"""Video queries. No commits: the service decides when a transaction ends."""

from datetime import timedelta
from uuid import UUID

from sqlalchemy import exists, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.models import User
from app.modules.videos.models import Video, VideoAccess, VideoStatus, Visibility


async def get_by_public_id(db: AsyncSession, public_id: str) -> Video | None:
    return await db.scalar(select(Video).where(Video.public_id == public_id))


async def get_by_id(db: AsyncSession, video_id: UUID) -> Video | None:
    return await db.get(Video, video_id)


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


async def claim(db: AsyncSession, video_id: UUID) -> int | None:
    """Take an uploaded video for processing. Returns this run's attempt number, None if taken.

    One conditional UPDATE, like an optimistic lock: of two workers only one gets the row.
    """
    statement = (
        update(Video)
        .where(Video.id == video_id, Video.status == VideoStatus.UPLOADED)
        .values(status=VideoStatus.PROCESSING, processing_attempts=Video.processing_attempts + 1)
        .returning(Video.processing_attempts)
    )
    return await db.scalar(statement)


async def finish(
    db: AsyncSession,
    video_id: UUID,
    attempt: int,
    *,
    status: VideoStatus,
    duration_sec: int | None = None,
    error_message: str | None = None,
) -> bool:
    """Leave `processing`, if this run still holds the claim.

    The attempt number fences off a run the sweeper took back: a newer claim has a newer number.
    """
    statement = (
        update(Video)
        .where(
            Video.id == video_id,
            Video.status == VideoStatus.PROCESSING,
            Video.processing_attempts == attempt,
        )
        .values(status=status, duration_sec=duration_sec, error_message=error_message)
        .returning(Video.id)
    )
    return await db.scalar(statement) is not None


async def take_back_stale(
    db: AsyncSession, *, older_than: timedelta, max_attempts: int
) -> list[UUID]:
    """Jobs whose worker is gone: back to `uploaded`, or `failed` after the last attempt.

    Returns the ids that are back in `uploaded`.
    """
    stale = (
        Video.status == VideoStatus.PROCESSING,
        Video.status_changed_at < func.now() - older_than,
    )
    await db.execute(
        update(Video)
        .where(*stale, Video.processing_attempts >= max_attempts)
        .values(status=VideoStatus.FAILED, error_message="Processing failed")
    )
    rows = await db.scalars(
        update(Video).where(*stale).values(status=VideoStatus.UPLOADED).returning(Video.id)
    )
    return list(rows)


async def touch_stale_uploaded(db: AsyncSession, *, older_than: timedelta) -> list[UUID]:
    """Uploaded videos nobody took for a while (lost queue message). Bumps their time, so each is
    queued again at most once per `older_than`."""
    rows = await db.scalars(
        update(Video)
        .where(
            Video.status == VideoStatus.UPLOADED,
            Video.status_changed_at < func.now() - older_than,
        )
        .values(status_changed_at=func.now())
        .returning(Video.id)
    )
    return list(rows)
