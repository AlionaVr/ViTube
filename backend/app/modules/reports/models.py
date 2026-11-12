"""Reports of videos and comments (ADR 0009). Moderators work through the open ones."""

import enum
from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import str_enum

DETAILS_MAX = 500  # YouTube's limit for the report text


class ReportReason(enum.StrEnum):
    """YouTube's reasons, for videos and comments alike. Also why a moderator hid a video."""

    SEXUAL = "sexual"
    VIOLENT = "violent"
    HATEFUL = "hateful"
    HARASSMENT = "harassment"
    HARMFUL = "harmful"
    MISINFORMATION = "misinformation"
    CHILD_ABUSE = "child_abuse"
    TERRORISM = "terrorism"
    SPAM = "spam"
    LEGAL = "legal"


class ReportStatus(enum.StrEnum):
    OPEN = "open"
    ACTIONED = "actioned"  # the target was hidden or deleted
    DISMISSED = "dismissed"  # a moderator found nothing wrong


class Report(Base):
    __tablename__ = "reports"
    __table_args__ = (
        CheckConstraint("num_nonnulls(video_id, comment_id) = 1", name="one_target"),
        CheckConstraint(f"char_length(details) <= {DETAILS_MAX}", name="details_length"),
        CheckConstraint("(status = 'open') = (resolved_at IS NULL)", name="resolved_iff_closed"),
        # One open report per user and target. The target comes first: the same index finds a
        # target's open reports when a moderator acts on it.
        Index(
            "ix_reports_video_id_reporter_id_open",
            "video_id",
            "reporter_id",
            unique=True,
            postgresql_where=text("status = 'open' AND video_id IS NOT NULL"),
        ),
        Index(
            "ix_reports_comment_id_reporter_id_open",
            "comment_id",
            "reporter_id",
            unique=True,
            postgresql_where=text("status = 'open' AND comment_id IS NOT NULL"),
        ),
        # The queue: open reports, oldest first.
        Index("ix_reports_open_id", "id", postgresql_where=text("status = 'open'")),
    )

    # uuidv7: ordered by time, so "oldest first" is id order.
    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("uuidv7()"))
    # Indexed: cascades when a user is deleted.
    reporter_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    # Indexed (all rows, not only open ones): cascades when a video or comment is deleted.
    video_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("videos.id", ondelete="CASCADE"), index=True
    )
    comment_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("comments.id", ondelete="CASCADE"), index=True
    )
    reason: Mapped[ReportReason] = mapped_column(str_enum(ReportReason, "reason"))
    details: Mapped[str] = mapped_column(Text, server_default="")
    status: Mapped[ReportStatus] = mapped_column(
        str_enum(ReportStatus, "status"), server_default=ReportStatus.OPEN.value
    )
    # Who closed it. The audit log keeps the full record; this is for the queue.
    resolved_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
