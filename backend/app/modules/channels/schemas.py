import enum
from datetime import datetime
from typing import Annotated

from fastapi import Path
from pydantic import BaseModel, Field

from app.modules.users.models import User, UserStatus
from app.modules.users.schemas import ChannelSummary
from app.modules.videos.schemas import HANDLE_PATTERN

Handle = Annotated[str, Path(pattern=HANDLE_PATTERN, description="Channel handle, without the @")]


class VideoSort(enum.StrEnum):
    LATEST = "latest"
    POPULAR = "popular"  # most viewed first
    OLDEST = "oldest"


class SubscribedChannel(ChannelSummary):
    """A row of the viewer's subscriptions."""

    subscriber_count: int

    @classmethod
    def build(cls, user: User) -> "SubscribedChannel":
        return cls(**ChannelSummary.of(user).model_dump(), subscriber_count=user.subscriber_count)


class SubscriptionOut(BaseModel):
    subscriber_count: int
    is_subscribed: bool


class ChannelOut(ChannelSummary):
    """The channel page header. The watch page reads it for the subscriber count too."""

    joined_at: datetime
    subscriber_count: int
    video_count: int = Field(description="Public, ready videos: what the Videos tab lists")
    is_subscribed: bool = Field(description="False for guests and on your own channel")
    is_terminated: bool = Field(
        description="Terminated by an admin: only moderators see it, and it is frozen"
    )

    @classmethod
    def build(cls, user: User, *, video_count: int, is_subscribed: bool) -> "ChannelOut":
        return cls(
            **ChannelSummary.of(user).model_dump(),
            joined_at=user.created_at,
            subscriber_count=user.subscriber_count,
            video_count=video_count,
            is_subscribed=is_subscribed,
            is_terminated=user.status is UserStatus.TERMINATED,
        )
