"""Channel and subscription rules. The service commits, like @Transactional."""

from typing import Annotated
from uuid import UUID

from pydantic import Field, StringConstraints
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import DomainError, NotFound
from app.core.pagination import Page, decode_cursor, split_page
from app.core.rate_limit import RateLimit
from app.modules.channels import repository as channels
from app.modules.channels.schemas import (
    ChannelOut,
    SubscribedChannel,
    SubscriptionOut,
    VideoSort,
)
from app.modules.users import repository as users
from app.modules.users.models import User
from app.modules.videos.models import Video
from app.modules.videos.schemas import HANDLE_PATTERN, VideoSummary
from app.modules.videos.service import FEED_PAGE_SIZE

# People subscribe by hand; a script flipping one would churn the channel's row. Per account.
SUBSCRIPTIONS_PER_USER = RateLimit("subscription", limit=60, window=60)

# A cursor is client input: a number the column can't hold must give 400, not a DB error.
_PopularKey = tuple[Annotated[int, Field(ge=0, le=2**63 - 1)], UUID]  # (view_count, id)
_HandleKey = tuple[Annotated[str, StringConstraints(pattern=HANDLE_PATTERN)]]
SUBSCRIPTIONS_PAGE_SIZE = 50


async def get_channel(db: AsyncSession, viewer: User | None, handle: str) -> ChannelOut:
    channel = await get_by_handle(db, handle)
    subscribed = viewer is not None and await channels.is_subscribed(db, viewer.id, channel.id)
    return ChannelOut.build(
        channel,
        video_count=await channels.count_listed_videos(db, channel.id),
        is_subscribed=subscribed,
    )


async def list_videos(
    db: AsyncSession, handle: str, sort: VideoSort, cursor: str | None
) -> Page[VideoSummary]:
    """The Videos tab: the same for every viewer, the owner too (public, ready videos only)."""
    channel = await get_by_handle(db, handle)
    shape = _PopularKey if sort is VideoSort.POPULAR else tuple[UUID]
    after = decode_cursor(cursor, shape) if cursor else None
    rows = await channels.list_videos(db, channel.id, sort, after=after, limit=FEED_PAGE_SIZE + 1)
    page, next_cursor = split_page(rows, FEED_PAGE_SIZE, lambda video: _sort_key(video, sort))
    return Page(items=[VideoSummary.of(video, channel) for video in page], next_cursor=next_cursor)


async def list_subscriptions(
    db: AsyncSession, user: User, cursor: str | None
) -> Page[SubscribedChannel]:
    after = decode_cursor(cursor, _HandleKey)[0] if cursor else None
    rows = await channels.list_subscribed(
        db, user.id, after=after, limit=SUBSCRIPTIONS_PAGE_SIZE + 1
    )
    page, next_cursor = split_page(rows, SUBSCRIPTIONS_PAGE_SIZE, lambda channel: (channel.handle,))
    return Page(
        items=[SubscribedChannel.build(channel) for channel in page], next_cursor=next_cursor
    )


async def list_feed(db: AsyncSession, user: User, cursor: str | None) -> Page[VideoSummary]:
    """The subscriptions feed: new public videos of the channels the user subscribed to."""
    before = decode_cursor(cursor, tuple[UUID])[0] if cursor else None
    rows = await channels.list_feed(db, user.id, before=before, limit=FEED_PAGE_SIZE + 1)
    page, next_cursor = split_page(rows, FEED_PAGE_SIZE, lambda row: (row[0].id,))
    return Page(
        items=[VideoSummary.of(video, owner) for video, owner in page], next_cursor=next_cursor
    )


async def subscribe(db: AsyncSession, redis: Redis, user: User, handle: str) -> SubscriptionOut:
    """Idempotent: the count moves only if this request really added the subscription."""
    await SUBSCRIPTIONS_PER_USER.hit(redis, str(user.id))
    channel = await _other_channel(db, user, handle)
    if await channels.insert_subscription(db, user.id, channel.id):
        count = await channels.add_subscribers(db, channel.id, 1)
    else:
        count = await channels.get_subscriber_count(db, channel.id)
    await db.commit()
    return SubscriptionOut(subscriber_count=count, is_subscribed=True)


async def unsubscribe(db: AsyncSession, redis: Redis, user: User, handle: str) -> SubscriptionOut:
    """Idempotent: the count moves only if this request really removed the subscription."""
    await SUBSCRIPTIONS_PER_USER.hit(redis, str(user.id))
    channel = await _other_channel(db, user, handle)
    if await channels.delete_subscription(db, user.id, channel.id):
        count = await channels.add_subscribers(db, channel.id, -1)
    else:
        count = await channels.get_subscriber_count(db, channel.id)
    await db.commit()
    return SubscriptionOut(subscriber_count=count, is_subscribed=False)


async def get_by_handle(db: AsyncSession, handle: str) -> User:
    channel = await users.get_by_handle(db, handle)
    if channel is None:
        raise NotFound("Channel not found")
    return channel


def _sort_key(video: Video, sort: VideoSort) -> tuple[object, ...]:
    return (video.view_count, video.id) if sort is VideoSort.POPULAR else (video.id,)


async def _other_channel(db: AsyncSession, user: User, handle: str) -> User:
    channel = await get_by_handle(db, handle)
    # Checked here: the not_self CHECK would turn it into a 500.
    if channel.id == user.id:
        raise DomainError("You can't subscribe to your own channel")
    return channel
