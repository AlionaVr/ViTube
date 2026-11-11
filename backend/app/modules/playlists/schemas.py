from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import Path, Query
from pydantic import BaseModel, Field, StringConstraints

from app.core.text import MULTILINE, SINGLE_LINE
from app.modules.playlists.models import DESCRIPTION_MAX, TITLE_MAX, Playlist, PlaylistKind
from app.modules.users.models import User
from app.modules.users.schemas import ChannelSummary
from app.modules.videos.models import Visibility
from app.modules.videos.schemas import VideoSummary

PlaylistId = Annotated[UUID, Path(description="Playlist id, as in /playlist?list=<id>")]
VideoQuery = Annotated[
    str | None,
    Query(
        pattern=r"^[A-Za-z0-9_-]{11}$", description="A public video id: mark the playlists with it"
    ),
]
Title = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=1, max_length=TITLE_MAX, pattern=SINGLE_LINE
    ),
]
Description = Annotated[str, StringConstraints(max_length=DESCRIPTION_MAX, pattern=MULTILINE)]


class PlaylistCreate(BaseModel):
    title: Title
    description: Description = ""
    visibility: Visibility = Visibility.PRIVATE


class PlaylistOut(BaseModel):
    id: UUID
    title: str
    description: str
    visibility: Visibility
    kind: PlaylistKind = Field(
        description="watch_later: the owner's own, can't be renamed or deleted"
    )
    video_count: int = Field(description="All items, also those this viewer may not watch")
    thumbnail_url: str | None = Field(description="The first video this viewer may watch")
    owner: ChannelSummary
    created_at: datetime
    updated_at: datetime

    @classmethod
    def build(cls, playlist: Playlist, owner: User, thumbnail_url: str | None) -> "PlaylistOut":
        return cls(
            id=playlist.id,
            title=playlist.title,
            description=playlist.description,
            visibility=playlist.visibility,
            kind=playlist.kind,
            video_count=playlist.video_count,
            thumbnail_url=thumbnail_url,
            owner=ChannelSummary.of(owner),
            created_at=playlist.created_at,
            updated_at=playlist.updated_at,
        )


class MyPlaylist(PlaylistOut):
    contains_video: bool | None = Field(description="With ?video=: whether it is in this playlist")


class PlaylistItemOut(BaseModel):
    video: VideoSummary
    added_at: datetime
