"""Liked videos: the user's own, private as on YouTube. Read only: a like is changed by rating."""

from uuid import UUID

from pydantic import AwareDatetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import Page, decode_cursor, split_page
from app.modules.liked import repository as liked
from app.modules.liked.schemas import LikedItem, LikedOut
from app.modules.users.models import User
from app.modules.users.schemas import ChannelSummary
from app.modules.videos.schemas import MEDIA_PREFIX, VideoSummary

PAGE_SIZE = 100  # as YouTube loads a playlist


async def get_liked(db: AsyncSession, user: User) -> LikedOut:
    """The cover and the last change come from the newest like, as on a playlist's first video."""
    newest = await liked.newest_liked(db, user)
    if newest is None:
        return LikedOut(
            video_count=0, thumbnail_url=None, updated_at=None, owner=ChannelSummary.of(user)
        )
    liked_at, video, count = newest
    return LikedOut(
        video_count=count,
        thumbnail_url=MEDIA_PREFIX + video.thumbnail_key,
        updated_at=liked_at,
        owner=ChannelSummary.of(user),
    )


async def list_liked(db: AsyncSession, user: User, cursor: str | None) -> Page[LikedItem]:
    before = decode_cursor(cursor, tuple[AwareDatetime, UUID]) if cursor else None
    rows = await liked.list_liked(db, user, before=before, limit=PAGE_SIZE + 1)
    page, next_cursor = split_page(rows, PAGE_SIZE, lambda row: (row[0].rated_at, row[0].target_id))
    items = [
        LikedItem(video=VideoSummary.of(video, owner), liked_at=reaction.rated_at)
        for reaction, video, owner in page
    ]
    return Page(items=items, next_cursor=next_cursor)
