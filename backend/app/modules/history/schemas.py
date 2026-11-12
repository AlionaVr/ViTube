from datetime import datetime

from pydantic import BaseModel, Field

from app.modules.videos.schemas import VideoSummary


class PositionIn(BaseModel):
    position_sec: int = Field(
        ge=0, le=2**31 - 1, description="Where playback is, in whole seconds; past the end: the end"
    )


class HistoryItem(BaseModel):
    video: VideoSummary
    watched_at: datetime = Field(description="When this viewer last watched it")
