from datetime import datetime
from typing import Annotated

from fastapi import Query
from pydantic import BaseModel, Field, StringConstraints

from app.modules.search.schemas import SearchResult
from app.modules.videos.schemas import PUBLIC_ID_PATTERN

MAX_PROGRESS_IDS = 100  # a page of the longest list, a playlist

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
