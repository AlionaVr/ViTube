"""Rating queries, the same for videos and comments. No commits: the service decides."""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import case, delete, func, literal_column, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.reactions.models import CommentReaction, VideoReaction
from app.modules.videos.models import Video

type Table = type[VideoReaction] | type[CommentReaction]


async def get_value(db: AsyncSession, table: Table, target_id: UUID, user_id: UUID) -> int | None:
    query = select(table.value).where(table.target_id == target_id, table.user_id == user_id)
    return await db.scalar(query)


async def get_values(
    db: AsyncSession, table: Table, target_ids: Sequence[UUID], user_id: UUID
) -> dict[UUID, int]:
    """The user's ratings of these targets, in one query: a page needs no query per item."""
    query = select(table.target_id, table.value).where(
        table.target_id.in_(target_ids), table.user_id == user_id
    )
    return {target_id: value for target_id, value in await db.execute(query)}


async def put_value(
    db: AsyncSession, table: Table, target_id: UUID, user_id: UUID, value: int
) -> int | None:
    """Set the user's rating; returns the one it replaced, None if there was none.

    One statement, so no check-then-insert race: a parallel request waits for the row lock,
    then sees this one's result.
    """
    statement = insert(table).values(target_id=target_id, user_id=user_id, value=value)
    same = table.value == statement.excluded.value
    statement = statement.on_conflict_do_update(
        index_elements=[table.target_id, table.user_id],
        # Not `WHERE value <> new value`: that would return no row, and the old value is needed.
        set_={
            "value": statement.excluded.value,
            "rated_at": case((same, table.rated_at), else_=func.now()),
        },
    ).returning(literal_column("old.value"))  # Postgres 18: the row before this statement
    return await db.scalar(statement)


async def delete_value(
    db: AsyncSession, table: Table, target_id: UUID, user_id: UUID
) -> int | None:
    """Remove the user's rating; returns it, None if there was none."""
    statement = (
        delete(table)
        .where(table.target_id == target_id, table.user_id == user_id)
        .returning(table.value)
    )
    return await db.scalar(statement)


async def add_likes(db: AsyncSession, table: Table, target_id: UUID, delta: int) -> int | None:
    """like_count + delta of the rated video or comment, in the DB itself: parallel updates
    don't overwrite each other. None: the video is hidden (checked again after a hide under
    way, as comments.repository.add_comment)."""
    rated = table.rated
    statement = update(rated).where(rated.id == target_id)
    if rated is Video:
        statement = statement.where(~Video.is_hidden)
    statement = statement.values(like_count=rated.like_count + delta).returning(rated.like_count)
    return await db.scalar(statement)
