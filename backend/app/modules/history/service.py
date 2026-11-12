"""Watch history rules. Only the user reads and changes their own. The service commits, like
@Transactional."""

from uuid import UUID

from pydantic import AwareDatetime
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import Page, decode_cursor, split_page
from app.core.rate_limit import RateLimit
from app.modules.history import repository as history
from app.modules.history.schemas import HistoryItem
from app.modules.users.models import User
from app.modules.videos.interactions import get_ready
from app.modules.videos.schemas import VideoSummary

# The player saves every 10 s while playing and on start, pause and end: far below this.
HISTORY_WRITES = RateLimit("history_write", limit=120, window=60)
PAGE_SIZE = 20


async def save_position(
    db: AsyncSession, redis: Redis, user: User, public_id: str, position_sec: int
) -> None:
    """Puts the video on top of the user's history, at this position."""
    await HISTORY_WRITES.hit(redis, str(user.id))
    video = await get_ready(db, user, public_id)
    if video.duration_sec is not None:  # always set once ready (CHECK ready_has_duration)
        position_sec = min(position_sec, video.duration_sec)
    await history.save_position(db, user.id, video.id, position_sec)
    await db.commit()


async def list_history(db: AsyncSession, user: User, cursor: str | None) -> Page[HistoryItem]:
    before = decode_cursor(cursor, tuple[AwareDatetime, UUID]) if cursor else None
    rows = await history.list_entries(db, user, before=before, limit=PAGE_SIZE + 1)
    page, next_cursor = split_page(
        rows, PAGE_SIZE, lambda row: (row[0].watched_at, row[0].video_id)
    )
    items = [
        HistoryItem(video=VideoSummary.of(video, owner), watched_at=entry.watched_at)
        for entry, video, owner in page
    ]
    return Page(items=items, next_cursor=next_cursor)
