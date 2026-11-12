from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from pydantic import BaseModel, Field, StringConstraints

from app.core.text import MULTILINE
from app.modules.audit.models import AuditAction, AuditEntry, AuditSource, TargetType
from app.modules.comments.models import Comment
from app.modules.reports.models import DETAILS_MAX, ReportReason
from app.modules.reports.repository import OpenCase
from app.modules.users.models import User, UserStatus
from app.modules.users.schemas import ChannelSummary
from app.modules.videos.models import Video, VideoStatus, Visibility
from app.modules.videos.schemas import MEDIA_PREFIX


class ModeratedVideo(BaseModel):
    """A video as a moderator sees it: in any state, hidden or not."""

    id: str = Field(description="Public id, as in /watch?v=<id>")
    title: str
    thumbnail_url: str | None = Field(description="Set once the video is ready")
    duration_sec: int | None
    status: VideoStatus
    visibility: Visibility
    is_hidden: bool
    created_at: datetime
    channel: ChannelSummary

    @classmethod
    def of(cls, video: Video, owner: User) -> "ModeratedVideo":
        ready = video.status is VideoStatus.READY
        return cls(
            id=video.public_id,
            title=video.title,
            thumbnail_url=MEDIA_PREFIX + video.thumbnail_key if ready else None,
            duration_sec=video.duration_sec,
            status=video.status,
            visibility=video.visibility,
            is_hidden=video.is_hidden,
            created_at=video.created_at,
            channel=ChannelSummary.of(owner),
        )


class ModeratedComment(BaseModel):
    """A comment as a moderator sees it, with the video it is on."""

    id: UUID
    text: str
    author: ChannelSummary
    published_at: datetime
    is_reply: bool
    is_deleted: bool
    video: ModeratedVideo

    @classmethod
    def of(cls, comment: Comment, author: User, video: ModeratedVideo) -> "ModeratedComment":
        return cls(
            id=comment.id,
            text=comment.text,
            author=ChannelSummary.of(author),
            published_at=comment.created_at,
            is_reply=comment.parent_id is not None,
            is_deleted=comment.is_deleted,
            video=video,
        )


class ReportCase(BaseModel):
    """The open reports of one video or one comment."""

    video: ModeratedVideo | None = Field(description="The reported video; null for a comment")
    comment: ModeratedComment | None = Field(description="The reported comment; null for a video")
    report_count: int
    reasons: list[ReportReason]
    notes: list[str] = Field(description="The newest report texts")
    last_reported_at: datetime

    @classmethod
    def of(
        cls,
        case: OpenCase,
        *,
        video: ModeratedVideo | None = None,
        comment: ModeratedComment | None = None,
    ) -> "ReportCase":
        return cls(
            video=video,
            comment=comment,
            report_count=case.report_count,
            reasons=case.reasons,
            notes=case.notes,
            last_reported_at=case.last_reported_at,
        )


class HideIn(BaseModel):
    reason: ReportReason = Field(description="The rule the video breaks")


class StatusIn(BaseModel):
    status: UserStatus
    reason: Annotated[
        str, StringConstraints(strip_whitespace=True, max_length=DETAILS_MAX, pattern=MULTILINE)
    ] = Field(default="", description="Why, for the audit log")


class RestrictedAccount(BaseModel):
    """A banned or terminated account."""

    channel: ChannelSummary
    status: UserStatus

    @classmethod
    def of(cls, user: User) -> "RestrictedAccount":
        return cls(channel=ChannelSummary.of(user), status=user.status)


class AuditTarget(BaseModel):
    """What an entry is about, as a person reads it."""

    type: TargetType
    label: str = Field(description="Video title, comment text or @handle; empty if it is gone")
    video_id: str | None = Field(description="Public id of the video, or of the comment's video")
    handle: str | None = Field(description="The user, for a user target")


class AuditEntryOut(BaseModel):
    id: UUID
    created_at: datetime
    source: AuditSource
    actor: ChannelSummary | None = Field(
        description="Who acted through the API; null for the CLI or an account deleted since"
    )
    by: str | None = Field(description="CLI: the admin named with --by (claimed, not proven)")
    action: AuditAction
    target: AuditTarget
    details: dict[str, Any] = Field(description="reason, reports, replies, from, to")

    @classmethod
    def of(cls, entry: AuditEntry, actor: User | None, target: AuditTarget) -> "AuditEntryOut":
        details = dict(entry.details)
        by = details.pop("by", None)
        return cls(
            id=entry.id,
            created_at=entry.created_at,
            source=entry.source,
            actor=ChannelSummary.of(actor) if actor else None,
            by=by,
            action=entry.action,
            target=target,
            details=details,
        )
