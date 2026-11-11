"""Queries of moderator actions. No commits: the service decides when a transaction ends."""

from collections.abc import Collection, Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.models import User
from app.modules.videos.models import Video
from app.modules.videos.repository import VideoRow


async def lock_video(db: AsyncSession, public_id: str) -> Video | None:
    """The video, locked until the transaction ends: actions on it run one at a time.

    FOR NO KEY UPDATE: inserts that reference the video (reports, ratings) don't wait for it.
    """
    query = (
        select(Video)
        .where(Video.public_id == public_id)
        .with_for_update(key_share=True)
        .execution_options(populate_existing=True)  # the row as locked, not as cached
    )
    return await db.scalar(query)


async def list_hidden(db: AsyncSession, *, before: UUID | None, limit: int) -> Sequence[VideoRow]:
    """Hidden videos, newest first (ids are uuidv7), after the cursor."""
    query = select(Video, User).join(User, User.id == Video.owner_id).where(Video.is_hidden)
    if before is not None:
        query = query.where(Video.id < before)
    return (await db.execute(query.order_by(Video.id.desc()).limit(limit))).all()


async def videos_with_owners(
    db: AsyncSession, video_ids: Collection[UUID]
) -> dict[UUID, tuple[Video, User]]:
    rows = await db.execute(
        select(Video, User).join(User, User.id == Video.owner_id).where(Video.id.in_(video_ids))
    )
    return {video.id: (video, owner) for video, owner in rows}
