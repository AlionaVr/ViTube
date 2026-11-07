"""The one access policy for videos (ADR 0004): the API, the watch page and /media all use it."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFound
from app.modules.users.models import Role, User
from app.modules.videos import repository as videos
from app.modules.videos.models import Video, VideoStatus, Visibility


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
