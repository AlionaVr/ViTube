"""The one access policy for videos (ADR 0004): the API, the watch page and /media all use it."""

import re
from uuid import UUID

from sqlalchemy import ColumnElement, and_, exists, or_, true
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFound
from app.modules.users import repository as users
from app.modules.users.models import Role, User, UserStatus
from app.modules.videos import repository as videos
from app.modules.videos.models import Video, VideoAccess, VideoStatus, Visibility

_UUID = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
# The only files /media serves: a ready video and its thumbnail. Never originals (ADR 0002).
MEDIA_PATH = re.compile(
    rf"/media/(?:videos/(?P<video>{_UUID})/720p\.mp4|thumbs/(?P<thumb>{_UUID})\.jpg)"
)


async def is_restricted(db: AsyncSession, video: Video) -> bool:
    """Hidden by a moderator, or its channel terminated (ADR 0009). The SQL twin for lists is
    repository.NOT_RESTRICTED. One query at most: callers check it once per decision."""
    if video.is_hidden:
        return True
    return await users.get_status(db, video.owner_id) is UserStatus.TERMINATED


async def can_view(db: AsyncSession, user: User | None, video: Video) -> bool:
    """Owner and moderators: always, restricted videos too (to review them). Others: ready
    videos that are not restricted (ADR 0009); private ones need a grant."""
    if _owner_or_staff(user, video):
        return True
    if video.status is not VideoStatus.READY or await is_restricted(db, video):
        return False
    return await _visibility_allows(db, user, video)


async def can_interact(db: AsyncSession, user: User | None, video: Video) -> bool:
    """Likes, comments, views and reports: a ready video that is not restricted, for everyone,
    its owner and moderators too; and the viewer may watch it."""
    if video.status is not VideoStatus.READY or await is_restricted(db, video):
        return False
    return _owner_or_staff(user, video) or await _visibility_allows(db, user, video)


def _owner_or_staff(user: User | None, video: Video) -> bool:
    return user is not None and (user.id == video.owner_id or user.role.at_least(Role.MODERATOR))


async def _visibility_allows(db: AsyncSession, user: User | None, video: Video) -> bool:
    if video.visibility is not Visibility.PRIVATE:
        return True
    return user is not None and await videos.has_access(db, video.id, user.id)


def viewable(user: User | None) -> ColumnElement[bool]:
    """can_view as a SQL condition, for lists that may hold more than public videos (playlists).

    The same rule: tests/videos/test_visibility_rules.py checks the two agree on every case.
    """
    if user is not None and user.role.at_least(Role.MODERATOR):
        return true()
    ready = Video.status == VideoStatus.READY
    open_to_all = and_(ready, Video.visibility != Visibility.PRIVATE)
    if user is None:
        return open_to_all
    granted = exists().where(VideoAccess.video_id == Video.id, VideoAccess.user_id == user.id)
    return or_(Video.owner_id == user.id, open_to_all, and_(ready, granted))


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
