"""View rules (ADR 0011). The service commits, like @Transactional."""

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.models import User
from app.modules.videos.interactions import get_ready
from app.modules.views import repository as views
from app.modules.views import tracker


async def start(db: AsyncSession, redis: Redis, user: User | None, ip: str, public_id: str) -> None:
    video = await get_ready(db, user, public_id)
    await tracker.start(redis, video.id, tracker.viewer_id(user.id if user else None, ip))


async def finish(
    db: AsyncSession, redis: Redis, user: User | None, ip: str, public_id: str
) -> None:
    """Counts a view if playback really reached the threshold and it is the first in the window."""
    video = await get_ready(db, user, public_id)
    viewer = tracker.viewer_id(user.id if user else None, ip)
    # Redis first: if the update then fails, a view is lost, never counted twice.
    if await tracker.finish(redis, video.id, viewer, video.duration_sec):
        await views.add_view(db, video.id)  # the only lock: it can't be part of a deadlock
        await db.commit()
