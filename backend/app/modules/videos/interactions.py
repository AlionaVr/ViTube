"""Likes, comments, views and reports need a ready video: before that there is nothing to watch.

A restricted video (hidden, or its channel terminated) is frozen for everyone, its owner and
moderators too (ADR 0009).
Only these features. The video API itself still shows the owner an unfinished video and its error.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFound
from app.modules.users.models import User
from app.modules.videos import repository as videos
from app.modules.videos.access import can_interact
from app.modules.videos.models import Video


async def get_ready(db: AsyncSession, user: User | None, public_id: str) -> Video:
    """A ready, not restricted video the viewer may watch, else NotFound."""
    video = await videos.get_by_public_id(db, public_id)
    if video is None or not await can_interact(db, user, video):
        raise NotFound("Video not found")
    return video
