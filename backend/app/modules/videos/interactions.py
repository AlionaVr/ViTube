"""Likes, comments and views need a ready video: before that there is nothing to watch.

Only these features. The video API itself still shows the owner an unfinished video and its error.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFound
from app.modules.users.models import User
from app.modules.videos.access import can_view, get_viewable
from app.modules.videos.models import Video, VideoStatus


async def is_ready(db: AsyncSession, user: User | None, video: Video) -> bool:
    """Ready, and the viewer may watch it. False for the owner too, until it is ready."""
    return video.status is VideoStatus.READY and await can_view(db, user, video)


async def get_ready(db: AsyncSession, user: User | None, public_id: str) -> Video:
    """A ready video the viewer may watch, else NotFound."""
    video = await get_viewable(db, user, public_id)
    if video.status is not VideoStatus.READY:
        raise NotFound("Video not found")
    return video
