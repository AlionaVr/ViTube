"""Video queries. No commits: the service decides when a transaction ends."""

from collections.abc import Sequence
from datetime import timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import (
    ColumnElement,
    Row,
    Select,
    String,
    column,
    delete,
    exists,
    func,
    literal,
    or_,
    select,
    tuple_,
    update,
    values,
)
from sqlalchemy.dialects.postgresql import REGCONFIG, insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.models import User, UserStatus
from app.modules.videos.models import (
    GAVE_UP_REASON,
    SEARCH_CONFIG,
    Category,
    Video,
    VideoAccess,
    VideoStatus,
    Visibility,
)

VideoRow = Row[Video, User]
RankedRow = Row[Video, User, float]

# Title typos (ADR 0007): pg_trgm's 0.6 misses a swap of two letters ("sintle"); 0.5 finds it.
TYPO_SIMILARITY = 0.5

# Public lists (feed, search, Up next) show only these. One place: a new rule reaches every list.
# Partial indexes use models.LISTED_SQL: LISTED must imply it (may add rules, never drop one).
# Literals, not bind parameters: a generic plan can't use a partial index for `visibility = $1`.
# Restricted by moderation (ADR 0009): hidden, or the channel terminated. The SQL twin of
# access.is_restricted. Not in LISTED_SQL: such videos are few, so filtering them out on top of
# the partial indexes costs less than rebuilding them.
NOT_RESTRICTED = (
    ~Video.is_hidden,
    Video.owner_id.not_in(
        select(User.id).where(
            User.status == literal(UserStatus.TERMINATED, User.status.type, literal_execute=True)
        )
    ),
)
LISTED = (
    Video.visibility == literal(Visibility.PUBLIC, Video.visibility.type, literal_execute=True),
    Video.status == literal(VideoStatus.READY, Video.status.type, literal_execute=True),
    *NOT_RESTRICTED,
)

_WITH_OWNER = select(Video, User).join(User, User.id == Video.owner_id)


async def get_by_public_id(db: AsyncSession, public_id: str) -> Video | None:
    return await db.scalar(select(Video).where(Video.public_id == public_id))


async def get_by_id(db: AsyncSession, video_id: UUID) -> Video | None:
    return await db.get(Video, video_id)


async def get_owner(db: AsyncSession, video: Video) -> User:
    # No query when the owner is the signed-in user: the session's identity map has them.
    return await db.get_one(User, video.owner_id)


async def _newest(
    db: AsyncSession, query: Select[Video, User], before: UUID | None, limit: int
) -> Sequence[VideoRow]:
    """Newest first (ids are uuidv7: ordered by time), after the cursor."""
    if before is not None:
        query = query.where(Video.id < before)
    return (await db.execute(query.order_by(Video.id.desc()).limit(limit))).all()


async def list_newest(
    db: AsyncSession, *, category: Category | None, before: UUID | None, limit: int
) -> Sequence[VideoRow]:
    query = _WITH_OWNER.where(*LISTED)
    if category is not None:
        query = query.where(Video.category == category)
    return await _newest(db, query, before, limit)


async def list_owned(
    db: AsyncSession, owner_id: UUID, *, before: UUID | None, limit: int
) -> Sequence[VideoRow]:
    """All of the owner's videos, whatever their status or visibility."""
    return await _newest(db, _WITH_OWNER.where(Video.owner_id == owner_id), before, limit)


async def list_up_next(
    db: AsyncSession, video: Video, *, same_channel: bool, before: UUID | None, limit: int
) -> Sequence[VideoRow]:
    """Listed videos but this one: from its channel, or from all the others."""
    channel = Video.owner_id == video.owner_id if same_channel else Video.owner_id != video.owner_id
    return await _newest(
        db, _WITH_OWNER.where(*LISTED, channel, Video.id != video.id), before, limit
    )


async def _allow_title_typos(db: AsyncSession) -> None:
    # SET LOCAL: this transaction only. `%>` reads the threshold from it, so its index still works.
    await db.execute(
        select(func.set_config("pg_trgm.word_similarity_threshold", str(TYPO_SIMILARITY), True))
    )


def text_query(words: str) -> ColumnElement[Any]:
    """The words as a tsquery: "quotes", OR and -word work as on YouTube (ADR 0007)."""
    return func.websearch_to_tsquery(literal(SEARCH_CONFIG, REGCONFIG), words)


def text_matches(query: ColumnElement[Any]) -> tuple[ColumnElement[bool], ColumnElement[bool]]:
    """Filters for videos with the words in the title or description. The first: some word is
    required (querytree 'T': with "-word" only, every video would match)."""
    return func.querytree(query) != "T", Video.search_vector.bool_op("@@")(query)


async def search(
    db: AsyncSession,
    words: str,
    *,
    typos: bool,
    after: tuple[float, UUID] | None,
    limit: int,
) -> Sequence[RankedRow]:
    """Listed videos with the words in the title or description, best first.

    With `typos`, titles close to the words match too. Rank: full-text rank (title over
    description) plus how close the title is to the words.
    """
    query = text_query(words)
    required, matches = text_matches(query)
    if typos:
        await _allow_title_typos(db)
        matches = or_(matches, Video.title.bool_op("%>")(words))
    rank = func.ts_rank(Video.search_vector, query) + func.word_similarity(words, Video.title)
    statement = _WITH_OWNER.add_columns(rank).where(*LISTED, required, matches)
    if after is not None:
        statement = statement.where(tuple_(rank, Video.id) < tuple_(*after))
    return (await db.execute(statement.order_by(rank.desc(), Video.id.desc()).limit(limit))).all()


async def suggest_titles(db: AsyncSession, words: str, *, limit: int) -> list[str]:
    """Titles of listed videos close to the words, closest first, in lower case like
    YouTube's suggestions; titles that differ only in case come once."""
    await _allow_title_typos(db)
    title = func.lower(Video.title)
    closeness = func.word_similarity(words, Video.title)  # pg_trgm ignores case
    statement = (
        select(title, closeness)
        .where(*LISTED, Video.title.bool_op("%>")(words))
        .distinct()
        .order_by(closeness.desc(), title)
        .limit(limit)
    )
    return list(await db.scalars(statement))


async def listed_categories(db: AsyncSession) -> set[Category]:
    """One index probe per category (ix_videos_listed_category_id), not a scan of every video."""
    categories = values(column("name", String), name="categories").data(
        [(category.value,) for category in Category]
    )
    statement = select(categories.c.name).where(
        exists().where(*LISTED, Video.category == categories.c.name)
    )
    return {Category(name) for name in await db.scalars(statement)}


async def has_access(db: AsyncSession, video_id: UUID, user_id: UUID) -> bool:
    query = select(exists().where(VideoAccess.video_id == video_id, VideoAccess.user_id == user_id))
    return bool(await db.scalar(query))


async def count_open_drafts(db: AsyncSession, owner_id: UUID, *, within: timedelta) -> int:
    """The owner's drafts still waiting for a file, made in the last `within`."""
    query = select(func.count()).where(
        Video.owner_id == owner_id,
        Video.status == VideoStatus.UPLOADING,
        Video.created_at > func.now() - within,
    )
    return await db.scalar(query) or 0


async def grant_access(db: AsyncSession, video_id: UUID, user_id: UUID) -> None:
    statement = insert(VideoAccess).values(video_id=video_id, user_id=user_id)
    await db.execute(statement.on_conflict_do_nothing())  # granting twice is fine


async def revoke_access(db: AsyncSession, video_id: UUID, user_id: UUID) -> None:
    await db.execute(
        delete(VideoAccess).where(VideoAccess.video_id == video_id, VideoAccess.user_id == user_id)
    )


async def insert_unless_taken(
    db: AsyncSession,
    *,
    public_id: str,
    owner_id: UUID,
    title: str,
    description: str,
    visibility: Visibility,
    category: Category,
) -> Video | None:
    """Insert a draft. None if the public id is taken: no exception, no savepoint needed."""
    statement = (
        insert(Video)
        .values(
            public_id=public_id,
            owner_id=owner_id,
            title=title,
            description=description,
            visibility=visibility,
            category=category,
        )
        .on_conflict_do_nothing(index_elements=[Video.public_id])
        .returning(Video)
    )
    return await db.scalar(statement)


async def get_owned_by_title(db: AsyncSession, owner_id: UUID, title: str) -> Video | None:
    """The owner's oldest video with this title (titles aren't unique). For the seed."""
    query = select(Video).where(Video.owner_id == owner_id, Video.title == title)
    return await db.scalar(query.order_by(Video.id).limit(1))


async def move_status(
    db: AsyncSession, video_id: UUID, *, current: VideoStatus, new: VideoStatus
) -> bool:
    """Change the status only if it is still `current`. False if someone changed it first."""
    statement = (
        update(Video)
        .where(Video.id == video_id, Video.status == current)
        .values(status=new)
        .returning(Video.id)
    )
    return await db.scalar(statement) is not None


async def claim(db: AsyncSession, video_id: UUID) -> int | None:
    """Take an uploaded video for processing. Returns this run's attempt number, None if taken.

    One conditional UPDATE, like an optimistic lock: of two workers only one gets the row.
    """
    statement = (
        update(Video)
        .where(Video.id == video_id, Video.status == VideoStatus.UPLOADED)
        .values(status=VideoStatus.PROCESSING, processing_attempts=Video.processing_attempts + 1)
        .returning(Video.processing_attempts)
    )
    return await db.scalar(statement)


async def finish(
    db: AsyncSession,
    video_id: UUID,
    attempt: int,
    *,
    status: VideoStatus,
    duration_sec: int | None = None,
    error_message: str | None = None,
) -> bool:
    """Leave `processing`, if this run still holds the claim.

    The attempt number fences off a run the sweeper took back: a newer claim has a newer number.
    """
    statement = (
        update(Video)
        .where(
            Video.id == video_id,
            Video.status == VideoStatus.PROCESSING,
            Video.processing_attempts == attempt,
        )
        .values(status=status, duration_sec=duration_sec, error_message=error_message)
        .returning(Video.id)
    )
    return await db.scalar(statement) is not None


async def take_back_stale(
    db: AsyncSession, *, older_than: timedelta, max_attempts: int
) -> list[UUID]:
    """Jobs whose worker is gone: back to `uploaded`, or `failed` after the last attempt.

    Returns the ids that are back in `uploaded`.
    """
    stale = (
        Video.status == VideoStatus.PROCESSING,
        Video.status_changed_at < func.now() - older_than,
    )
    await db.execute(
        update(Video)
        .where(*stale, Video.processing_attempts >= max_attempts)
        .values(status=VideoStatus.FAILED, error_message=GAVE_UP_REASON)
    )
    rows = await db.scalars(
        update(Video).where(*stale).values(status=VideoStatus.UPLOADED).returning(Video.id)
    )
    return list(rows)


async def touch_stale_uploaded(db: AsyncSession, *, older_than: timedelta) -> list[UUID]:
    """Uploaded videos nobody took for a while (lost queue message). Bumps their time, so each is
    queued again at most once per `older_than`."""
    rows = await db.scalars(
        update(Video)
        .where(
            Video.status == VideoStatus.UPLOADED,
            Video.status_changed_at < func.now() - older_than,
        )
        .values(status_changed_at=func.now())
        .returning(Video.id)
    )
    return list(rows)
