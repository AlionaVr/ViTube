"""Watch history queries. No commits: the service decides when a transaction ends."""

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import ColumnElement, Row, delete, func, select, tuple_, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.history.models import HistoryEntry
from app.modules.users.models import User
from app.modules.videos import repository as videos
from app.modules.videos.access import viewable
from app.modules.videos.models import Video, VideoStatus

HistoryRow = Row[HistoryEntry, Video, User]


def _watchable(user: User) -> tuple[ColumnElement[bool], ColumnElement[bool]]:
    """Rows the user sees: ready videos they may still watch. The others are kept, not shown:
    the video may come back, and a lost one must not show that it still exists (ADR 0004)."""
    return Video.status == VideoStatus.READY, viewable(user)


async def save_position(db: AsyncSession, user_id: UUID, video_id: UUID, position_sec: int) -> None:
    """One statement for the first save and the next: parallel saves can't add a second row."""
    statement = pg_insert(HistoryEntry).values(
        user_id=user_id, video_id=video_id, position_sec=position_sec
    )
    statement = statement.on_conflict_do_update(
        index_elements=[HistoryEntry.user_id, HistoryEntry.video_id],
        set_={"position_sec": statement.excluded.position_sec, "watched_at": func.now()},
    )
    await db.execute(statement)


async def positions(db: AsyncSession, user: User, public_ids: Sequence[str]) -> dict[str, int]:
    """Saved positions of the given videos the user watched, by public id."""
    query = (
        select(Video.public_id, HistoryEntry.position_sec)
        .join(Video, Video.id == HistoryEntry.video_id)
        .where(HistoryEntry.user_id == user.id, Video.public_id.in_(public_ids), *_watchable(user))
    )
    return {public_id: position for public_id, position in await db.execute(query)}


async def list_entries(
    db: AsyncSession,
    user: User,
    words: str | None,
    *,
    before: tuple[datetime, UUID] | None,
    limit: int,
) -> Sequence[HistoryRow]:
    """The user's history, last watched first; with `words`, only videos that have them."""
    query = (
        select(HistoryEntry, Video, User)
        .join(Video, Video.id == HistoryEntry.video_id)
        .join(User, User.id == Video.owner_id)
        .where(HistoryEntry.user_id == user.id, *_watchable(user))
    )
    if words is not None:
        query = query.where(*videos.text_matches(videos.text_query(words)))
    if before is not None:
        query = query.where(
            tuple_(HistoryEntry.watched_at, HistoryEntry.video_id) < tuple_(*before)
        )
    order = (HistoryEntry.watched_at.desc(), HistoryEntry.video_id.desc())
    return (await db.execute(query.order_by(*order).limit(limit))).all()


async def delete_entry(db: AsyncSession, user_id: UUID, public_id: str) -> None:
    """Any video of the user's history, one they may no longer watch too: it must still go."""
    video_id = select(Video.id).where(Video.public_id == public_id).scalar_subquery()
    await db.execute(
        delete(HistoryEntry).where(
            HistoryEntry.user_id == user_id, HistoryEntry.video_id == video_id
        )
    )


async def delete_all(db: AsyncSession, user_id: UUID) -> None:
    await db.execute(delete(HistoryEntry).where(HistoryEntry.user_id == user_id))


async def set_paused(db: AsyncSession, user_id: UUID, paused: bool) -> None:
    await db.execute(update(User).where(User.id == user_id).values(history_paused=paused))
