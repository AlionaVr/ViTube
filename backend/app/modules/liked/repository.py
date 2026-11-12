"""Liked videos queries: a list read from the user's likes, not a stored playlist (ADR 0013)."""

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import ColumnElement, Row, func, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.reactions.models import LIKE, VideoReaction
from app.modules.users.models import User
from app.modules.videos.access import watchable
from app.modules.videos.models import Video

LikedRow = Row[VideoReaction, Video, User]


def _liked_by(user: User) -> tuple[ColumnElement[bool], ...]:
    """The user's likes of videos they may watch now: the list and its count agree."""
    return VideoReaction.user_id == user.id, VideoReaction.value == LIKE, watchable(user)


async def list_liked(
    db: AsyncSession, user: User, *, before: tuple[datetime, UUID] | None, limit: int
) -> Sequence[LikedRow]:
    """Newest like first."""
    query = (
        select(VideoReaction, Video, User)
        .join(Video, Video.id == VideoReaction.target_id)
        .join(User, User.id == Video.owner_id)
        .where(*_liked_by(user))
    )
    if before is not None:
        query = query.where(
            tuple_(VideoReaction.rated_at, VideoReaction.target_id) < tuple_(*before)
        )
    order = (VideoReaction.rated_at.desc(), VideoReaction.target_id.desc())
    return (await db.execute(query.order_by(*order).limit(limit))).all()


async def count_liked(db: AsyncSession, user: User) -> int:
    query = (
        select(func.count())
        .select_from(VideoReaction)
        .join(Video, Video.id == VideoReaction.target_id)
        .where(*_liked_by(user))
    )
    return await db.scalar(query) or 0
