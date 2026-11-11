"""Videos and who may watch private ones. Bytes live in MinIO; keys come from the id (ADR 0002)."""

import enum
from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Computed,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

TITLE_MAX = 100  # YouTube's limits
DESCRIPTION_MAX = 5000
ERROR_MESSAGE_MAX = 1000  # a sentence for the owner, never raw ffmpeg output
# The reason after the last attempt failed for something that's not the file's fault.
GAVE_UP_REASON = "The video could not be processed. Upload it again."


class Visibility(enum.StrEnum):
    PUBLIC = "public"  # everyone, in feed and search
    UNLISTED = "unlisted"  # anyone with the link
    PRIVATE = "private"  # owner, users in video_access, moderators


class VideoStatus(enum.StrEnum):
    """uploading → uploaded → processing → ready | failed (ADR 0003)."""

    UPLOADING = "uploading"  # draft: no file yet, or an upload was cut off
    UPLOADED = "uploaded"  # the original is stored and waits for the worker
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class Category(enum.StrEnum):
    """YouTube's upload categories, in its order."""

    FILM = "film"
    AUTOS = "autos"
    MUSIC = "music"
    PETS = "pets"
    SPORTS = "sports"
    TRAVEL = "travel"
    GAMING = "gaming"
    PEOPLE = "people"  # People & Blogs: YouTube's default
    COMEDY = "comedy"
    ENTERTAINMENT = "entertainment"
    NEWS = "news"
    HOWTO = "howto"
    EDUCATION = "education"
    SCIENCE = "science"
    NONPROFITS = "nonprofits"


# repository.LISTED in SQL, for partial indexes; keep the two in sync.
LISTED_SQL = "visibility = 'public' AND status = 'ready'"

# Word stems for search (ADR 0007): "trailers" finds "trailer". Queries must use the same config.
SEARCH_CONFIG = "english"


def _str_enum(enum_class: type[enum.StrEnum], name: str) -> Enum:
    # varchar + CHECK, not a Postgres enum: adding a value is a plain migration.
    return Enum(
        enum_class,
        name=name,
        native_enum=False,
        create_constraint=True,
        length=16,
        values_callable=lambda members: [member.value for member in members],
    )


class Video(Base):
    __tablename__ = "videos"
    __table_args__ = (
        CheckConstraint(r"public_id ~ '^[A-Za-z0-9_-]{11}$'", name="public_id_format"),
        CheckConstraint(
            f"char_length(btrim(title)) >= 1 AND char_length(title) <= {TITLE_MAX}",
            name="title_length",
        ),
        CheckConstraint(
            f"char_length(description) <= {DESCRIPTION_MAX}", name="description_length"
        ),
        CheckConstraint(
            f"char_length(error_message) <= {ERROR_MESSAGE_MAX}", name="error_message_length"
        ),
        CheckConstraint("duration_sec >= 0", name="duration_sec_not_negative"),
        # State rules: a ready video has a duration; exactly the failed ones say why.
        CheckConstraint("status <> 'ready' OR duration_sec IS NOT NULL", name="ready_has_duration"),
        CheckConstraint(
            "(status = 'failed') = (error_message IS NOT NULL)", name="error_message_iff_failed"
        ),
        CheckConstraint("processing_attempts >= 0", name="processing_attempts_not_negative"),
        CheckConstraint(
            "view_count >= 0 AND like_count >= 0 AND comment_count >= 0",
            name="counters_not_negative",
        ),
        # The home feed, newest first: all listed videos, and by category.
        Index("ix_videos_listed_id", "id", postgresql_where=text(LISTED_SQL)),
        Index("ix_videos_listed_category_id", "category", "id", postgresql_where=text(LISTED_SQL)),
        # Search (ADR 0007): full text, and title trigrams for typos and suggestions.
        Index(
            "ix_videos_listed_search_vector",
            "search_vector",
            postgresql_using="gin",
            postgresql_where=text(LISTED_SQL),
        ),
        Index(
            "ix_videos_listed_title_trgm",
            "title",
            postgresql_using="gin",
            postgresql_ops={"title": "gin_trgm_ops"},
            postgresql_where=text(LISTED_SQL),
        ),
    )

    # Internal id: object keys and foreign keys. Never in API paths.
    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("uuidv7()"))
    # Public id, as in /watch?v=<public_id>: random, so ids can't be enumerated.
    public_id: Mapped[str] = mapped_column(String(11), unique=True)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text, server_default="")
    visibility: Mapped[Visibility] = mapped_column(
        _str_enum(Visibility, "visibility"), server_default=Visibility.PRIVATE.value
    )
    status: Mapped[VideoStatus] = mapped_column(
        _str_enum(VideoStatus, "status"), server_default=VideoStatus.UPLOADING.value
    )
    category: Mapped[Category] = mapped_column(
        _str_enum(Category, "category"), server_default=Category.PEOPLE.value
    )
    # Set by a DB trigger on every status change; the sweeper finds stuck jobs by it (ADR 0003).
    status_changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    processing_attempts: Mapped[int] = mapped_column(SmallInteger, server_default="0")
    error_message: Mapped[str | None] = mapped_column(Text)
    # Whole seconds, rounded down; set by the worker.
    duration_sec: Mapped[int | None] = mapped_column(Integer)
    # Counters are updated in place (x = x + n) by the features that own them.
    view_count: Mapped[int] = mapped_column(BigInteger, server_default="0")
    like_count: Mapped[int] = mapped_column(Integer, server_default="0")
    comment_count: Mapped[int] = mapped_column(Integer, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Postgres builds it from the title (weight A) and description (B). Only search reads it.
    search_vector: Mapped[str] = mapped_column(
        TSVECTOR,
        Computed(
            f"setweight(to_tsvector('{SEARCH_CONFIG}', title), 'A')"
            f" || setweight(to_tsvector('{SEARCH_CONFIG}', description), 'B')",
            persisted=True,
        ),
        deferred=True,
    )

    @property
    def original_key(self) -> str:
        return f"originals/{self.id}"

    @property
    def media_key(self) -> str:
        return f"videos/{self.id}/720p.mp4"

    @property
    def thumbnail_key(self) -> str:
        return f"thumbs/{self.id}.jpg"


class VideoAccess(Base):
    """Users the owner let watch a private video. Only the owner grants, so no granted_by."""

    __tablename__ = "video_access"

    video_id: Mapped[UUID] = mapped_column(
        ForeignKey("videos.id", ondelete="CASCADE"), primary_key=True
    )
    # Indexed: "shared with me" lists and cascades when a user is deleted.
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
