from datetime import datetime
from typing import Annotated

from fastapi import Query
from pydantic import BaseModel, Field, StringConstraints

from app.modules.search.schemas import SearchResult, Words
from app.modules.videos.schemas import PUBLIC_ID_PATTERN

MAX_PROGRESS_IDS = 100  # a page of the longest list, a playlist

HistoryQuery = Annotated[
    Words | None, Query(description="Only videos with these words in the title or description")
]
VideoIds = Annotated[
    list[Annotated[str, StringConstraints(pattern=PUBLIC_ID_PATTERN)]],
    Query(min_length=1, max_length=MAX_PROGRESS_IDS, description="Public video ids"),
]


class PositionIn(BaseModel):
    position_sec: int = Field(
        ge=0, le=2**31 - 1, description="Where playback is, in whole seconds; past the end: the end"
    )


class HistoryItem(BaseModel):
    video: SearchResult = Field(description="With its description, as a search result row")
    watched_at: datetime = Field(description="When this viewer last watched it")


class HistorySettings(BaseModel):
    paused: bool = Field(description="Videos you watch don't go to your history meanwhile")
