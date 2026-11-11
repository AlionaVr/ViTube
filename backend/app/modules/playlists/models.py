"""Playlists: a user's ordered lists of videos."""

import enum
from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import str_enum
from app.modules.videos.models import Visibility

TITLE_MAX = 150  # YouTube's limits
DESCRIPTION_MAX = 5000
MAX_VIDEOS = 5000
WATCH_LATER_TITLE = "Watch later"


class PlaylistKind(enum.StrEnum):
    USER = "user"
    # Every user has exactly one, from the start: a DB trigger makes it when the user row is
    # inserted (migration "add watch later"), so no way of creating users can forget it.
    WATCH_LATER = "watch_later"


class Playlist(Base):
    __tablename__ = "playlists"
    __table_args__ = (
        CheckConstraint(
            f"char_length(btrim(title)) >= 1 AND char_length(title) <= {TITLE_MAX}",
            name="title_length",
        ),
        CheckConstraint(
            f"char_length(description) <= {DESCRIPTION_MAX}", name="description_length"
        ),
        CheckConstraint(f"video_count BETWEEN 0 AND {MAX_VIDEOS}", name="video_count_range"),
        # A user's playlists, newest first; also the cascade from users.
        Index("ix_playlists_owner_id_id", "owner_id", "id"),
        # One Watch later per user, and it stays private.
        Index(
            "uq_playlists_owner_id_watch_later",
            "owner_id",
            unique=True,
            postgresql_where=text("kind = 'watch_later'"),
        ),
        CheckConstraint(
            "kind <> 'watch_later' OR visibility = 'private'", name="watch_later_private"
        ),
    )

    # uuidv7: ordered by time, so "newest first" is id order. Also the id in /playlist?list=.
    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("uuidv7()"))
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text, server_default="")
    # Same meaning as for videos: public lists on the channel, unlisted by link, private owner only.
    visibility: Mapped[Visibility] = mapped_column(
        str_enum(Visibility, "visibility"), server_default=Visibility.PRIVATE.value
    )
    kind: Mapped[PlaylistKind] = mapped_column(
        str_enum(PlaylistKind, "kind"), server_default=PlaylistKind.USER.value
    )
    # Items, kept by the writes to them, which all lock this row first.
    video_count: Mapped[int] = mapped_column(Integer, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PlaylistItem(Base):
    """A video in a playlist, once. Positions order the items and may have gaps."""

    __tablename__ = "playlist_items"
    __table_args__ = (
        # Deferrable: checked at the end of each statement, so one UPDATE can shift a range
        # of positions by one. Not an ON CONFLICT target: those name the primary key.
        UniqueConstraint("playlist_id", "position", deferrable=True, initially="IMMEDIATE"),
        CheckConstraint("position >= 0", name="position_not_negative"),
    )

    playlist_id: Mapped[UUID] = mapped_column(
        ForeignKey("playlists.id", ondelete="CASCADE"), primary_key=True
    )
    # Indexed: cascades when a video is deleted.
    video_id: Mapped[UUID] = mapped_column(
        ForeignKey("videos.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    position: Mapped[int] = mapped_column(Integer)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
