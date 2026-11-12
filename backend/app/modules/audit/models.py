"""Who did what to whom, and when (ADR 0009). Rows are only added: the app role may not change them.

Written in the same transaction as the action itself, so both happen or neither does.
"""

import enum
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, Index, Uuid, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import str_enum


class AuditSource(enum.StrEnum):
    API = "api"  # a signed-in moderator or admin
    CLI = "cli"  # python -m app.cli: whoever has a shell on the server


class AuditAction(enum.StrEnum):
    HIDE_VIDEO = "hide_video"
    RESTORE_VIDEO = "restore_video"
    DISMISS_VIDEO = "dismiss_video"  # its open reports, not the video
    DELETE_COMMENT = "delete_comment"
    DISMISS_COMMENT = "dismiss_comment"
    SET_USER_STATUS = "set_user_status"
    SET_USER_ROLE = "set_user_role"


class TargetType(enum.StrEnum):
    VIDEO = "video"
    COMMENT = "comment"
    USER = "user"


class AuditEntry(Base):
    __tablename__ = "audit_log"
    __table_args__ = (
        # An API action always has a signed-in actor; the CLI has none (details say who ran it).
        CheckConstraint("(source = 'api') = (actor_id IS NOT NULL)", name="actor_iff_api"),
        # The admins' filters, each newest first (ids are uuidv7).
        Index("ix_audit_log_action_id", "action", "id"),
        Index("ix_audit_log_actor_id_id", "actor_id", "id"),
        Index("ix_audit_log_subject_user_id_id", "subject_user_id", "id"),
        Index("ix_audit_log_cli_id", "id", postgresql_where=text("source = 'cli'")),
    )

    # uuidv7: ordered by time, so "newest first" is id order.
    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("uuidv7()"))
    source: Mapped[AuditSource] = mapped_column(str_enum(AuditSource, "source"))
    # No foreign keys here: the log outlives the rows it names.
    actor_id: Mapped[UUID | None] = mapped_column(Uuid)
    action: Mapped[AuditAction] = mapped_column(str_enum(AuditAction, "action"))
    target_type: Mapped[TargetType] = mapped_column(str_enum(TargetType, "target_type"))
    target_id: Mapped[UUID] = mapped_column(Uuid)
    # The account acted on: the user itself, or the video's owner, or the comment's author. Kept
    # here, so the "about an account" filter finds entries whose video or comment is gone.
    subject_user_id: Mapped[UUID | None] = mapped_column(Uuid)
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
