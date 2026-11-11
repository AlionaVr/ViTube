from datetime import datetime

from pydantic import BaseModel, Field

from app.modules.reports.models import ReportReason
from app.modules.reports.repository import OpenCase
from app.modules.users.models import User
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


class ReportCase(BaseModel):
    """The open reports of one video."""

    video: ModeratedVideo
    report_count: int
    reasons: list[ReportReason]
    notes: list[str] = Field(description="The newest report texts")
    last_reported_at: datetime

    @classmethod
    def of(cls, case: OpenCase, video: ModeratedVideo) -> "ReportCase":
        return cls(
            video=video,
            report_count=case.report_count,
            reasons=case.reasons,
            notes=case.notes,
            last_reported_at=case.last_reported_at,
        )


class HideIn(BaseModel):
    reason: ReportReason = Field(description="The rule the video breaks")
