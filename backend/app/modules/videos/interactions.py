"""Likes, comments, views and reports need a ready video: before that there is nothing to watch.

A video hidden by a moderator is frozen for everyone, its owner and moderators too (ADR 0009).
Only these features. The video API itself still shows the owner an unfinished video and its error.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFound
from app.modules.users.models import User
from app.modules.videos.access import can_view, get_viewable
from app.modules.videos.models import Video, VideoStatus


def _open(video: Video) -> bool:
    return video.status is VideoStatus.READY and not video.is_hidden


async def is_ready(db: AsyncSession, user: User | None, video: Video) -> bool:
    """Ready, not hidden, and the viewer may watch it. False for the owner too, until then."""
    return _open(video) and await can_view(db, user, video)


async def get_ready(db: AsyncSession, user: User | None, public_id: str) -> Video:
    """A ready, not hidden video the viewer may watch, else NotFound."""
    video = await get_viewable(db, user, public_id)
    if not _open(video):
        raise NotFound("Video not found")
    return video
