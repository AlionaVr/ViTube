from datetime import datetime
from typing import Annotated

from fastapi import Path
from pydantic import BaseModel, Field, StringConstraints

from app.modules.reactions.schemas import Rating
from app.modules.users.models import User
from app.modules.users.schemas import ChannelSummary
from app.modules.videos.models import (
    DESCRIPTION_MAX,
    TITLE_MAX,
    Category,
    Video,
    VideoStatus,
    Visibility,
)

MEDIA_PREFIX = "/media/"  # nginx serves objects here after an access check (ADR 0004)

PublicId = Annotated[str, Path(pattern=r"^[A-Za-z0-9_-]{11}$", description="Public video id")]
HANDLE_PATTERN = r"^[A-Za-z0-9._-]{3,30}$"  # the users.handle rule; case doesn't matter
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=TITLE_MAX)]
Description = Annotated[str, StringConstraints(max_length=DESCRIPTION_MAX)]


class VideoCreate(BaseModel):
    """A draft: metadata first, the file comes next with PUT /api/videos/{id}/file."""

    title: Title
    description: Description = ""
    visibility: Visibility = Visibility.PRIVATE
    category: Category = Category.PEOPLE


class VideoUpdate(BaseModel):
    """Changes only the given fields; null leaves a field as it is. Works in any status."""

    title: Title | None = None
    description: Description | None = None
    visibility: Visibility | None = None
    category: Category | None = None


class VideoOut(BaseModel):
    id: str = Field(description="Public id, as in /watch?v=<id>")
    title: str
    description: str
    visibility: Visibility
    category: Category
    status: VideoStatus
    error_message: str | None = Field(description="Why processing failed")
    duration_sec: int | None
    thumbnail_url: str | None = Field(description="Set once the video is ready")
    media_url: str | None = Field(description="MP4 with Range support; set once ready")
    view_count: int
    like_count: int
    comment_count: int
    created_at: datetime
    channel: ChannelSummary

    @classmethod
    def of(cls, video: Video, owner: User) -> "VideoOut":
        ready = video.status is VideoStatus.READY
        return cls(
            id=video.public_id,
            title=video.title,
            description=video.description,
            visibility=video.visibility,
            category=video.category,
            status=video.status,
            error_message=video.error_message,
            duration_sec=video.duration_sec,
            thumbnail_url=MEDIA_PREFIX + video.thumbnail_key if ready else None,
            media_url=MEDIA_PREFIX + video.media_key if ready else None,
            view_count=video.view_count,
            like_count=video.like_count,
            comment_count=video.comment_count,
            created_at=video.created_at,
            channel=ChannelSummary.of(owner),
        )


class VideoSummary(BaseModel):
    """A video in a public list: home feed, Up next, search. Only ready videos are listed."""

    id: str = Field(description="Public id, as in /watch?v=<id>")
    title: str
    thumbnail_url: str
    duration_sec: int
    view_count: int
    created_at: datetime
    channel: ChannelSummary

    @classmethod
    def of(cls, video: Video, owner: User) -> "VideoSummary":
        if video.duration_sec is None:  # the ready_has_duration CHECK rules this out
            raise ValueError(f"Video {video.id} is listed but has no duration")
        return cls(
            id=video.public_id,
            title=video.title,
            thumbnail_url=MEDIA_PREFIX + video.thumbnail_key,
            duration_sec=video.duration_sec,
            view_count=video.view_count,
            created_at=video.created_at,
            channel=ChannelSummary.of(owner),
        )


class VideoDetail(VideoOut):
    """The watch page: the video and what this viewer did with it."""

    my_rating: Rating


class AccessGrant(BaseModel):
    handle: str = Field(pattern=HANDLE_PATTERN, description="Who may watch, without the @")


class UploadLimits(BaseModel):
    max_size_bytes: int
    max_duration_sec: int
