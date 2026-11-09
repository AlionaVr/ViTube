"""The one access policy for videos (ADR 0004): the API, the watch page and /media all use it."""

import re
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFound
from app.modules.users.models import Role, User
from app.modules.videos import repository as videos
from app.modules.videos.models import Video, VideoStatus, Visibility

_UUID = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
# The only files /media serves: a ready video and its thumbnail. Never originals (ADR 0002).
MEDIA_PATH = re.compile(
    rf"/media/(?:videos/(?P<video>{_UUID})/720p\.mp4|thumbs/(?P<thumb>{_UUID})\.jpg)"
)


async def can_view(db: AsyncSession, user: User | None, video: Video) -> bool:
    """Owner and moderators: always. Others: ready videos only; private ones need a grant."""
    if user is not None and (user.id == video.owner_id or user.role.at_least(Role.MODERATOR)):
        return True
    if video.status is not VideoStatus.READY:
        return False
    if video.visibility is not Visibility.PRIVATE:
        return True
    return user is not None and await videos.has_access(db, video.id, user.id)


async def get_viewable(db: AsyncSession, user: User | None, public_id: str) -> Video:
    """The video, or NotFound: others never learn that a private video exists (no 403)."""
    video = await videos.get_by_public_id(db, public_id)
    if video is None or not await can_view(db, user, video):
        raise NotFound("Video not found")
    return video


async def can_fetch_media(db: AsyncSession, user: User | None, uri: str) -> bool:
    """For nginx's auth_request: may this viewer fetch this /media URI?"""
    match = MEDIA_PATH.fullmatch(uri.split("?", 1)[0])  # nginx drops the query before MinIO
    if match is None:
        return False
    video = await videos.get_by_id(db, UUID(match["video"] or match["thumb"]))
    return video is not None and await can_view(db, user, video)
