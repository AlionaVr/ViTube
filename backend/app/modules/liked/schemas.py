from datetime import datetime

from pydantic import BaseModel, Field

from app.modules.users.schemas import ChannelSummary
from app.modules.videos.schemas import VideoSummary


class LikedOut(BaseModel):
    """Liked videos (list=LL) as a playlist header or card shows it."""

    video_count: int = Field(description="Liked videos you may watch now, as the list shows")
    thumbnail_url: str | None = Field(description="The newest liked video's; null: none")
    updated_at: datetime | None = Field(description="When it was liked; null: no videos")
    owner: ChannelSummary


class LikedItem(BaseModel):
    video: VideoSummary
    liked_at: datetime
