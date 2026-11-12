from typing import Annotated

from fastapi import Query
from pydantic import StringConstraints

from app.modules.users.models import User
from app.modules.videos.models import Video
from app.modules.videos.schemas import VideoSummary

# What a search box sends. No control characters: Postgres refuses NUL (a 500, not a 422).
Words = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=200,
        pattern=r"^[^\x00-\x1f\x7f]*$",
    ),
]
SearchQuery = Annotated[Words, Query(description="Words to find in titles and descriptions")]


class SearchResult(VideoSummary):
    """A row that also shows the start of the description: search results, watch history."""

    description: str

    @classmethod
    def of(cls, video: Video, owner: User) -> "SearchResult":
        return cls(**dict(VideoSummary.of(video, owner)), description=video.description)
