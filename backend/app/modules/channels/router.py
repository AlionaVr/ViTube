"""Channels (/@handle) and subscriptions. Guests read; signed-in users subscribe."""

from fastapi import APIRouter

from app.core.pagination import Cursor, Page
from app.core.redis import RedisClient
from app.db.session import DbSession
from app.modules.auth.deps import CurrentUser, OptionalUser
from app.modules.channels import service
from app.modules.channels.schemas import (
    ChannelOut,
    Handle,
    SubscribedChannel,
    SubscriptionOut,
    VideoSort,
)
from app.modules.videos.schemas import VideoSummary

router = APIRouter(prefix="/api", tags=["channels"])


@router.get("/channels/{handle}", response_model=ChannelOut, summary="A channel's page header")
async def get_channel(handle: Handle, user: OptionalUser, db: DbSession) -> ChannelOut:
    return await service.get_channel(db, user, handle)


@router.get(
    "/channels/{handle}/videos",
    response_model=Page[VideoSummary],
    summary="A channel's public videos",
    description="Only public, ready videos: the same for every viewer, the owner too.",
)
async def list_videos(
    handle: Handle, db: DbSession, sort: VideoSort = VideoSort.LATEST, cursor: Cursor = None
) -> Page[VideoSummary]:
    return await service.list_videos(db, handle, sort, cursor)


@router.put(
    "/channels/{handle}/subscription",
    response_model=SubscriptionOut,
    summary="Subscribe to a channel",
    description="Subscribing again changes nothing.",
)
async def subscribe(
    handle: Handle, user: CurrentUser, db: DbSession, redis: RedisClient
) -> SubscriptionOut:
    return await service.subscribe(db, redis, user, handle)


@router.delete(
    "/channels/{handle}/subscription",
    response_model=SubscriptionOut,
    summary="Unsubscribe from a channel",
    description="Unsubscribing again changes nothing.",
)
async def unsubscribe(
    handle: Handle, user: CurrentUser, db: DbSession, redis: RedisClient
) -> SubscriptionOut:
    return await service.unsubscribe(db, redis, user, handle)


@router.get(
    "/me/subscriptions",
    response_model=Page[SubscribedChannel],
    summary="Channels you subscribed to, A to Z",
)
async def list_subscriptions(
    user: CurrentUser, db: DbSession, cursor: Cursor = None
) -> Page[SubscribedChannel]:
    return await service.list_subscriptions(db, user, cursor)


@router.get(
    "/feed/subscriptions",
    response_model=Page[VideoSummary],
    summary="New public videos of the channels you subscribed to",
)
async def list_feed(user: CurrentUser, db: DbSession, cursor: Cursor = None) -> Page[VideoSummary]:
    return await service.list_feed(db, user, cursor)
