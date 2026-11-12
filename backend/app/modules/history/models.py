"""Watch history: the videos a user watched and where they stopped."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class HistoryEntry(Base):
    """One row per user and video: watching it again moves the row up, not adds one."""

    __tablename__ = "watch_history"
    __table_args__ = (
        CheckConstraint("position_sec >= 0", name="position_not_negative"),
        # A user's history, newest first, paged by (watched_at, video_id).
        Index("ix_watch_history_user_id_watched_at", "user_id", "watched_at", "video_id"),
    )

    # The key's first column also serves the cascade when a user is deleted.
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    # Indexed: cascades when a video is deleted.
    video_id: Mapped[UUID] = mapped_column(
        ForeignKey("videos.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    # Where playback stopped; the video's length once it played to the end.
    position_sec: Mapped[int] = mapped_column(Integer)
    watched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
