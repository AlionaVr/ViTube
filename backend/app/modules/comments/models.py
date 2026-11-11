"""Comments and replies. One level, as on YouTube: a reply to a reply joins the root's thread."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    false,
    func,
)
from sqlalchemy import text as sql  # the model has a `text` column
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

TEXT_MAX = 10_000  # YouTube's limit


class Comment(Base):
    __tablename__ = "comments"
    __table_args__ = (
        CheckConstraint(
            f"char_length(btrim(text)) >= 1 AND char_length(text) <= {TEXT_MAX}",
            name="text_length",
        ),
        CheckConstraint("like_count >= 0 AND reply_count >= 0", name="counters_not_negative"),
        CheckConstraint("parent_id IS NULL OR reply_count = 0", name="only_roots_have_replies"),
        # Newest first (the query orders by parent_id too, see the repository); also the cascade
        # from videos.
        Index("ix_comments_video_id_parent_id_id", "video_id", "parent_id", "id"),
        # Top first.
        Index(
            "ix_comments_video_id_like_count_id",
            "video_id",
            "like_count",
            "id",
            postgresql_where=sql("parent_id IS NULL"),
        ),
        # A thread's replies, oldest first; also the cascade from the root. Partial: likes of
        # top-level comments don't rewrite it.
        Index(
            "ix_comments_parent_id_id",
            "parent_id",
            "id",
            postgresql_where=sql("parent_id IS NOT NULL"),
        ),
    )

    # uuidv7: ordered by time, so "newest first" is id order.
    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=sql("uuidv7()"))
    video_id: Mapped[UUID] = mapped_column(ForeignKey("videos.id", ondelete="CASCADE"))
    # Indexed: cascades when a user is deleted.
    author_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    # The thread root, never a reply. Null for a top-level comment.
    parent_id: Mapped[UUID | None] = mapped_column(ForeignKey("comments.id", ondelete="CASCADE"))
    text: Mapped[str] = mapped_column(Text)
    # Updated in place (x = x + n) by ratings and replies.
    like_count: Mapped[int] = mapped_column(Integer, server_default="0")
    reply_count: Mapped[int] = mapped_column(Integer, server_default="0")
    # Deleted by a moderator (ADR 0009): gone from every list, the row stays as evidence. Deleting
    # a thread's root deletes its replies too. Counters count only the comments not deleted.
    is_deleted: Mapped[bool] = mapped_column(Boolean, server_default=false())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
