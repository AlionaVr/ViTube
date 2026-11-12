"""Liked videos queries: a list read from the user's likes, not a stored playlist (ADR 0013)."""

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import ColumnElement, Row, func, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.reactions.models import LIKE, VideoReaction
from app.modules.users.models import User
from app.modules.videos.access import interactable
from app.modules.videos.models import Video

LikedRow = Row[VideoReaction, Video, User]
NEWEST = (VideoReaction.rated_at.desc(), VideoReaction.target_id.desc())


def _liked_by(user: User) -> tuple[ColumnElement[bool], ...]:
    """The user's likes they may still take back: every row's "Remove" works, and the list
    and its count agree."""
    return VideoReaction.user_id == user.id, VideoReaction.value == LIKE, interactable(user)


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
    return (await db.execute(query.order_by(*NEWEST).limit(limit))).all()


async def newest_liked(db: AsyncSession, user: User) -> tuple[datetime, Video, int] | None:
    """The newest like, its video and the count of all: one statement, so they agree."""
    query = (
        select(VideoReaction.rated_at, Video, func.count().over())
        .join(Video, Video.id == VideoReaction.target_id)
        .where(*_liked_by(user))
        .order_by(*NEWEST)
        .limit(1)
    )
    row = (await db.execute(query)).first()
    return (row[0], row[1], row[2]) if row else None
