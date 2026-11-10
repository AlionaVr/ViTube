"""Comment queries. No commits: the service decides when a transaction ends."""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import Row, insert, select, tuple_, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.comments.models import Comment
from app.modules.users.models import User
from app.modules.videos.models import Video

CommentRow = Row[Comment, User]

_WITH_AUTHOR = select(Comment, User).join(User, User.id == Comment.author_id)


async def get(db: AsyncSession, comment_id: UUID) -> Comment | None:
    return await db.get(Comment, comment_id)


async def list_newest(
    db: AsyncSession, video_id: UUID, *, before: UUID | None, limit: int
) -> Sequence[CommentRow]:
    """Top-level comments, newest first, after the cursor."""
    query = _WITH_AUTHOR.where(Comment.video_id == video_id, Comment.parent_id.is_(None))
    if before is not None:
        query = query.where(Comment.id < before)
    # parent_id is NULL in every row here, but keep it: it makes (video_id, parent_id, id) the
    # only index that gives this order. With `id` alone the planner may walk the primary key
    # through every newer comment of other videos (seen on Postgres 18).
    order = (Comment.parent_id.desc(), Comment.id.desc())
    return (await db.execute(query.order_by(*order).limit(limit))).all()


async def list_top(
    db: AsyncSession, video_id: UUID, *, after: tuple[int, UUID] | None, limit: int
) -> Sequence[CommentRow]:
    """Top-level comments, most liked first; newer first among equals."""
    query = _WITH_AUTHOR.where(Comment.video_id == video_id, Comment.parent_id.is_(None))
    if after is not None:
        query = query.where(tuple_(Comment.like_count, Comment.id) < tuple_(*after))
    order = (Comment.like_count.desc(), Comment.id.desc())
    return (await db.execute(query.order_by(*order).limit(limit))).all()


async def list_replies(
    db: AsyncSession, parent_id: UUID, *, after: UUID | None, limit: int
) -> Sequence[CommentRow]:
    """A thread's replies, oldest first, after the cursor."""
    query = _WITH_AUTHOR.where(Comment.parent_id == parent_id)
    if after is not None:
        query = query.where(Comment.id > after)
    return (await db.execute(query.order_by(Comment.id).limit(limit))).all()


async def insert_comment(
    db: AsyncSession, *, video_id: UUID, author_id: UUID, parent_id: UUID | None, text: str
) -> Comment:
    statement = (
        insert(Comment)
        .values(video_id=video_id, author_id=author_id, parent_id=parent_id, text=text)
        .returning(Comment)
    )
    return (await db.execute(statement)).scalar_one()


async def add_reply(db: AsyncSession, root_id: UUID) -> None:
    """reply_count + 1 in the DB itself, so parallel replies don't overwrite each other."""
    await db.execute(
        update(Comment).where(Comment.id == root_id).values(reply_count=Comment.reply_count + 1)
    )


async def add_comment(db: AsyncSession, video_id: UUID) -> None:
    await db.execute(
        update(Video).where(Video.id == video_id).values(comment_count=Video.comment_count + 1)
    )
