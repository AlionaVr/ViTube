"""Likes, comments, views and reports need a ready video: before that there is nothing to watch.

A restricted video (hidden, or its channel terminated) is frozen for everyone, its owner and
moderators too (ADR 0009).
Only these features. The video API itself still shows the owner an unfinished video and its error.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFound
from app.modules.users.models import User
from app.modules.videos.access import can_view, get_viewable, is_restricted
from app.modules.videos.models import Video, VideoStatus


async def _open(db: AsyncSession, video: Video) -> bool:
    return video.status is VideoStatus.READY and not await is_restricted(db, video)


async def is_ready(db: AsyncSession, user: User | None, video: Video) -> bool:
    """Ready, not restricted, and the viewer may watch it. False for the owner too, until then."""
    return await _open(db, video) and await can_view(db, user, video)


async def get_ready(db: AsyncSession, user: User | None, public_id: str) -> Video:
    """A ready, not restricted video the viewer may watch, else NotFound."""
    video = await get_viewable(db, user, public_id)
    if not await _open(db, video):
        raise NotFound("Video not found")
    return video
