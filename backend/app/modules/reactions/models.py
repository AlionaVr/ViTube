"""Likes and dislikes of videos and comments. One row per user and target; no row: no rating."""

from datetime import datetime
from typing import ClassVar
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, SmallInteger, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.modules.comments.models import Comment
from app.modules.videos.models import Video

LIKE = 1
DISLIKE = -1


def _value_check() -> CheckConstraint:
    return CheckConstraint(f"value IN ({LIKE}, {DISLIKE})", name="value")


class _Reaction:
    """Columns every reaction table has, like a JPA @MappedSuperclass. A subclass adds target_id:
    with (target_id, user_id) as the key, a second like is impossible, whatever the requests do.
    Each table indexes user_id itself: the cascade when a user is deleted needs it."""

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    value: Mapped[int] = mapped_column(SmallInteger)
    # When the current value was set; a repeated identical rating keeps it.
    rated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class VideoReaction(_Reaction, Base):
    __tablename__ = "video_reactions"
    __table_args__ = (
        _value_check(),
        # Liked videos, newest first; also the cascade from users.
        Index("ix_video_reactions_user_id_rated_at_video_id", "user_id", "rated_at", "video_id"),
    )
    rated: ClassVar[type[Video]] = Video  # whose like_count a rating moves; not a column

    target_id: Mapped[UUID] = mapped_column(
        "video_id", ForeignKey("videos.id", ondelete="CASCADE"), primary_key=True, sort_order=-1
    )


class CommentReaction(_Reaction, Base):
    __tablename__ = "comment_reactions"
    __table_args__ = (_value_check(), Index("ix_comment_reactions_user_id", "user_id"))
    rated: ClassVar[type[Comment]] = Comment

    target_id: Mapped[UUID] = mapped_column(
        "comment_id", ForeignKey("comments.id", ondelete="CASCADE"), primary_key=True, sort_order=-1
    )
