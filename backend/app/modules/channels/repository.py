"""Channel and subscription queries. No commits: the service decides when a transaction ends."""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import (
    ColumnElement,
    delete,
    exists,
    func,
    literal_column,
    select,
    true,
    tuple_,
    update,
)
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.modules.channels.models import Subscription
from app.modules.channels.schemas import VideoSort
from app.modules.users.models import User, UserStatus
from app.modules.videos.models import Video, VideoStatus
from app.modules.videos.repository import LISTED, VideoRow


def _shown(*, own: bool) -> tuple[ColumnElement[bool], ...]:
    """What the Videos tab lists. `own`: the owner's view of their channel, every ready video
    whatever its visibility. Hidden ones stay out, as of every list; Studio shows them with the
    reason."""
    return (Video.status == VideoStatus.READY, ~Video.is_hidden) if own else LISTED


async def count_videos(db: AsyncSession, owner_id: UUID, *, own: bool) -> int:
    query = select(func.count()).where(Video.owner_id == owner_id, *_shown(own=own))
    return await db.scalar(query) or 0


async def list_videos(
    db: AsyncSession,
    owner_id: UUID,
    sort: VideoSort,
    *,
    own: bool = False,
    after: tuple[object, ...] | None,
    limit: int,
) -> Sequence[Video]:
    """The channel's videos (see `_shown`) in the sort's order, after the cursor (its sort key).
    ix_videos_owner_id, then a sort."""
    query = select(Video).where(Video.owner_id == owner_id, *_shown(own=own))
    match sort:
        case VideoSort.LATEST:  # ids are uuidv7: ordered by time
            order, key = (Video.id.desc(),), (Video.id,)
        case VideoSort.OLDEST:
            order, key = (Video.id,), (Video.id,)
        case VideoSort.POPULAR:
            # A sort of the channel's listed videos: fine at a channel's size, no extra index.
            order, key = (Video.view_count.desc(), Video.id.desc()), (Video.view_count, Video.id)
    if after is not None:
        position = tuple_(*key)
        query = query.where(
            position > tuple_(*after) if sort is VideoSort.OLDEST else position < tuple_(*after)
        )
    return (await db.scalars(query.order_by(*order).limit(limit))).all()


async def list_feed(
    db: AsyncSession, subscriber_id: UUID, *, before: UUID | None, limit: int
) -> Sequence[VideoRow]:
    """Listed videos of the channels the user subscribed to, newest first, after the cursor.

    Per channel its newest `limit` (an index-only walk of ix_videos_listed_owner_id_id), then the
    newest of those: the cost is subscriptions x page size, whatever the site or a channel holds.
    """
    newest = select(Video.id).where(Video.owner_id == Subscription.channel_id, *LISTED)
    if before is not None:
        newest = newest.where(Video.id < before)
    per_channel = newest.order_by(Video.id.desc()).limit(limit).lateral("newest")
    shown = aliased(Video)  # not Video: the subquery would correlate to it
    query = (
        select(shown, User)
        .select_from(Subscription)
        .join(per_channel, true())
        .join(shown, shown.id == per_channel.c.id)
        .join(User, User.id == shown.owner_id)
        .where(Subscription.subscriber_id == subscriber_id)
    )
    return (await db.execute(query.order_by(shown.id.desc()).limit(limit))).all()


async def list_subscribed(
    db: AsyncSession, subscriber_id: UUID, *, after: str | None, limit: int
) -> Sequence[User]:
    """The channels the user subscribed to, A to Z by handle, after the cursor. A terminated
    one is left out but kept: a reinstate brings it back (ADR 0009).

    No index gives this order across the two tables: it sorts one user's subscriptions.
    """
    query = (
        select(User)
        .join(Subscription, Subscription.channel_id == User.id)
        .where(Subscription.subscriber_id == subscriber_id, User.status != UserStatus.TERMINATED)
    )
    if after is not None:
        query = query.where(User.handle > after)
    return (await db.scalars(query.order_by(User.handle).limit(limit))).all()


async def is_subscribed(db: AsyncSession, subscriber_id: UUID, channel_id: UUID) -> bool:
    query = select(
        exists().where(
            Subscription.subscriber_id == subscriber_id, Subscription.channel_id == channel_id
        )
    )
    return bool(await db.scalar(query))


async def insert_subscription(db: AsyncSession, subscriber_id: UUID, channel_id: UUID) -> bool:
    """True if this statement added the row. A parallel insert waits for ours, then does nothing."""
    statement = (
        insert(Subscription)
        .values(subscriber_id=subscriber_id, channel_id=channel_id)
        .on_conflict_do_nothing(
            index_elements=[Subscription.subscriber_id, Subscription.channel_id]
        )
        .returning(literal_column("1"))
    )
    return await db.scalar(statement) is not None


async def delete_subscription(db: AsyncSession, subscriber_id: UUID, channel_id: UUID) -> bool:
    """True if this statement removed the row. A parallel delete finds it gone and does nothing."""
    statement = (
        delete(Subscription)
        .where(Subscription.subscriber_id == subscriber_id, Subscription.channel_id == channel_id)
        .returning(literal_column("1"))
    )
    return await db.scalar(statement) is not None


async def add_subscribers(db: AsyncSession, channel_id: UUID, delta: int) -> int:
    """subscriber_count + delta in the DB itself, so parallel updates don't overwrite each other."""
    statement = (
        update(User)
        .where(User.id == channel_id)
        .values(subscriber_count=User.subscriber_count + delta)
        .returning(User.subscriber_count)
    )
    return (await db.execute(statement)).scalar_one()


async def get_subscriber_count(db: AsyncSession, channel_id: UUID) -> int:
    # A column query, not the cached User: the count as committed now.
    return (
        await db.execute(select(User.subscriber_count).where(User.id == channel_id))
    ).scalar_one()
