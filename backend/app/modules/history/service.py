"""Watch history rules. Only the user reads and changes their own. The service commits, like
@Transactional."""

from uuid import UUID

from pydantic import AwareDatetime
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import Page, decode_cursor, split_page
from app.core.rate_limit import RateLimit
from app.modules.history import repository as history
from app.modules.history.schemas import HistoryItem, HistorySettings
from app.modules.search.schemas import SearchResult
from app.modules.users.models import User
from app.modules.videos.interactions import get_ready

# Per account. The player saves every 10 s while playing and on start, pause and end; seeking
# while playing adds saves. Clicks on the history's controls have their own budget, so the
# player can't use it up: "Pause" must work.
HISTORY_WRITES = RateLimit("history_write", limit=120, window=60)
HISTORY_CHANGES = RateLimit("history_change", limit=60, window=60)
# A search reads the user's history row by row (its videos may be private, so the search index
# doesn't serve it), as many rows as the history holds: a budget, as /api/search has. Pages count.
HISTORY_SEARCHES = RateLimit("history_search", limit=60, window=60)
PAGE_SIZE = 20


async def save_position(
    db: AsyncSession, redis: Redis, user: User, public_id: str, position_sec: int
) -> None:
    """Puts the video on top of the user's history, at this position. Paused: no change."""
    if user.history_paused:
        return
    await HISTORY_WRITES.hit(redis, str(user.id))
    video = await get_ready(db, user, public_id)
    if video.duration_sec is not None:  # always set once ready (CHECK ready_has_duration)
        position_sec = min(position_sec, video.duration_sec)
    await history.save_position(db, user.id, video.id, position_sec)
    await db.commit()


async def progress(db: AsyncSession, user: User, public_ids: list[str]) -> dict[str, int]:
    """Only videos the user may still watch, as in the list."""
    return await history.positions(db, user, public_ids)


async def list_history(
    db: AsyncSession, redis: Redis, user: User, words: str | None, cursor: str | None
) -> Page[HistoryItem]:
    if words is not None:
        await HISTORY_SEARCHES.hit(redis, str(user.id))
    before = decode_cursor(cursor, tuple[AwareDatetime, UUID]) if cursor else None
    rows = await history.list_entries(db, user, words, before=before, limit=PAGE_SIZE + 1)
    page, next_cursor = split_page(
        rows, PAGE_SIZE, lambda row: (row[0].watched_at, row[0].video_id)
    )
    items = [
        HistoryItem(video=SearchResult.of(video, owner), watched_at=entry.watched_at)
        for entry, video, owner in page
    ]
    return Page(items=items, next_cursor=next_cursor)


async def remove(db: AsyncSession, redis: Redis, user: User, public_id: str) -> None:
    """Idempotent: a video that isn't there changes nothing."""
    await HISTORY_CHANGES.hit(redis, str(user.id))
    await history.delete_entry(db, user.id, public_id)
    await db.commit()


async def clear(db: AsyncSession, redis: Redis, user: User) -> None:
    await HISTORY_CHANGES.hit(redis, str(user.id))
    await history.delete_all(db, user.id)
    await db.commit()


def get_settings(user: User) -> HistorySettings:
    return HistorySettings(paused=user.history_paused)


async def set_paused(db: AsyncSession, redis: Redis, user: User, paused: bool) -> HistorySettings:
    """The history stays as it is either way; only new saves stop or start."""
    await HISTORY_CHANGES.hit(redis, str(user.id))
    await history.set_paused(db, user.id, paused)
    await db.commit()
    return HistorySettings(paused=paused)
