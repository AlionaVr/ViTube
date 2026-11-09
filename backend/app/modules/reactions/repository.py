"""Rating queries. No commits: the service decides when a transaction ends."""

from uuid import UUID

from sqlalchemy import case, delete, func, literal_column, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.reactions.models import VideoReaction
from app.modules.videos.models import Video


async def get_value(db: AsyncSession, video_id: UUID, user_id: UUID) -> int | None:
    query = select(VideoReaction.value).where(
        VideoReaction.video_id == video_id, VideoReaction.user_id == user_id
    )
    return await db.scalar(query)


async def put_value(db: AsyncSession, video_id: UUID, user_id: UUID, value: int) -> int | None:
    """Set the user's rating; returns the one it replaced, None if there was none.

    One statement, so no check-then-insert race: a parallel request waits for the row lock,
    then sees this one's result.
    """
    statement = insert(VideoReaction).values(video_id=video_id, user_id=user_id, value=value)
    same = VideoReaction.value == statement.excluded.value
    statement = statement.on_conflict_do_update(
        index_elements=[VideoReaction.video_id, VideoReaction.user_id],
        # Not `WHERE value <> new value`: that would return no row, and the old value is needed.
        set_={
            "value": statement.excluded.value,
            "rated_at": case((same, VideoReaction.rated_at), else_=func.now()),
        },
    ).returning(literal_column("old.value"))  # Postgres 18: the row before this statement
    return await db.scalar(statement)


async def delete_value(db: AsyncSession, video_id: UUID, user_id: UUID) -> int | None:
    """Remove the user's rating; returns it, None if there was none."""
    statement = (
        delete(VideoReaction)
        .where(VideoReaction.video_id == video_id, VideoReaction.user_id == user_id)
        .returning(VideoReaction.value)
    )
    return await db.scalar(statement)


async def add_likes(db: AsyncSession, video_id: UUID, delta: int) -> int:
    """like_count + delta in the DB itself, so parallel updates don't overwrite each other."""
    statement = (
        update(Video)
        .where(Video.id == video_id)
        .values(like_count=Video.like_count + delta)
        .returning(Video.like_count)
    )
    return (await db.execute(statement)).scalar_one()
