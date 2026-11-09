"""Likes, comments and views need a ready video: before that there is nothing to watch.

Only these features. The video API itself still shows the owner an unfinished video and its error.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFound
from app.modules.users.models import User
from app.modules.videos.access import get_viewable
from app.modules.videos.models import Video, VideoStatus


async def get_ready(db: AsyncSession, user: User | None, public_id: str) -> Video:
    """A ready video the viewer may watch, else NotFound: the owner too, until it is ready."""
    video = await get_viewable(db, user, public_id)
    if video.status is not VideoStatus.READY:
        raise NotFound("Video not found")
    return video
