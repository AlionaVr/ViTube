"""Likes and dislikes. One row per user and video; no row means no rating."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, SmallInteger, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

LIKE = 1
DISLIKE = -1


class VideoReaction(Base):
    __tablename__ = "video_reactions"
    __table_args__ = (CheckConstraint(f"value IN ({LIKE}, {DISLIKE})", name="value"),)

    # The key makes a second like impossible, whatever the requests do.
    video_id: Mapped[UUID] = mapped_column(
        ForeignKey("videos.id", ondelete="CASCADE"), primary_key=True
    )
    # Indexed: cascades when a user is deleted.
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    value: Mapped[int] = mapped_column(SmallInteger)
    # When the current value was set; a repeated identical rating keeps it.
    rated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
