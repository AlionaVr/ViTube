"""Playlist queries. No commits: the service decides when a transaction ends.

Every write to a playlist locks its row first (lock_own), so writes to one playlist run one at
a time and each reads the positions the previous one left.
"""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import (
    ColumnElement,
    Row,
    delete,
    func,
    insert,
    literal_column,
    select,
    tuple_,
    update,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.playlists.models import Playlist, PlaylistItem, PlaylistKind
from app.modules.users.models import User
from app.modules.videos.access import viewable
from app.modules.videos.models import Video, VideoStatus, Visibility

ItemRow = Row[PlaylistItem, Video, User]


def _watchable(viewer: User | None) -> tuple[ColumnElement[bool], ColumnElement[bool]]:
    """Items a viewer sees: ready videos they may watch (videos never leave ready)."""
    return Video.status == VideoStatus.READY, viewable(viewer)


async def insert_playlist(
    db: AsyncSession, *, owner_id: UUID, title: str, description: str, visibility: Visibility
) -> Playlist:
    statement = (
        insert(Playlist)
        .values(owner_id=owner_id, title=title, description=description, visibility=visibility)
        .returning(Playlist)
    )
    return (await db.execute(statement)).scalar_one()


async def get(db: AsyncSession, playlist_id: UUID) -> Playlist | None:
    return await db.get(Playlist, playlist_id)


async def lock_own(db: AsyncSession, playlist_id: UUID, owner_id: UUID) -> Playlist | None:
    """SELECT ... FOR NO KEY UPDATE of the owner's playlist; None if it isn't theirs.

    Others never take the lock. NO KEY UPDATE, not UPDATE: item inserts check their foreign key
    with KEY SHARE, which this allows.
    """
    query = (
        select(Playlist)
        .where(Playlist.id == playlist_id, Playlist.owner_id == owner_id)
        .with_for_update(key_share=True)
        .execution_options(populate_existing=True)  # the row as locked, not as cached
    )
    return await db.scalar(query)


async def add_item(db: AsyncSession, playlist_id: UUID, video_id: UUID) -> bool:
    """Append the video after the last item. True if added, False if it was there already."""
    last = select(func.max(PlaylistItem.position)).where(PlaylistItem.playlist_id == playlist_id)
    statement = (
        pg_insert(PlaylistItem)
        .values(
            playlist_id=playlist_id,
            video_id=video_id,
            position=func.coalesce(last.scalar_subquery() + 1, 0),
        )
        # The primary key, named: the deferrable position constraint can't be an arbiter.
        .on_conflict_do_nothing(index_elements=[PlaylistItem.playlist_id, PlaylistItem.video_id])
        .returning(literal_column("1"))
    )
    return await db.scalar(statement) is not None


async def delete_item(db: AsyncSession, playlist_id: UUID, video_id: UUID) -> bool:
    """True if this removed the item. The others keep their positions: a gap is fine."""
    statement = (
        delete(PlaylistItem)
        .where(PlaylistItem.playlist_id == playlist_id, PlaylistItem.video_id == video_id)
        .returning(literal_column("1"))
    )
    return await db.scalar(statement) is not None


async def has_item(db: AsyncSession, playlist_id: UUID, video_id: UUID) -> bool:
    query = select(literal_column("1")).where(
        PlaylistItem.playlist_id == playlist_id, PlaylistItem.video_id == video_id
    )
    return await db.scalar(query) is not None


async def count_changed(db: AsyncSession, playlist_id: UUID, delta: int) -> None:
    """video_count + delta and a new updated_at, on the row the caller has locked."""
    await db.execute(
        update(Playlist)
        .where(Playlist.id == playlist_id)
        .values(video_count=Playlist.video_count + delta, updated_at=func.now())
    )


async def list_items(
    db: AsyncSession, playlist_id: UUID, viewer: User | None, *, after: int | None, limit: int
) -> Sequence[ItemRow]:
    """The items this viewer may watch, in order, after the cursor (a position)."""
    query = (
        select(PlaylistItem, Video, User)
        .join(Video, Video.id == PlaylistItem.video_id)
        .join(User, User.id == Video.owner_id)
        .where(PlaylistItem.playlist_id == playlist_id, *_watchable(viewer))
    )
    if after is not None:
        query = query.where(PlaylistItem.position > after)
    return (await db.execute(query.order_by(PlaylistItem.position).limit(limit))).all()


IS_WATCH_LATER = Playlist.kind == PlaylistKind.WATCH_LATER


async def list_owned(
    db: AsyncSession, owner_id: UUID, *, after: tuple[bool, UUID] | None, limit: int
) -> Sequence[Playlist]:
    """A user's playlists: Watch later first, then the newest; after the cursor.

    A sort of one user's playlists: few enough that the (owner_id, id) index needn't give the order.
    """
    query = select(Playlist).where(Playlist.owner_id == owner_id)
    if after is not None:
        query = query.where(tuple_(IS_WATCH_LATER, Playlist.id) < tuple_(*after))
    order = (IS_WATCH_LATER.desc(), Playlist.id.desc())
    return (await db.scalars(query.order_by(*order).limit(limit))).all()


async def get_watch_later(db: AsyncSession, owner_id: UUID) -> Playlist | None:
    query = select(Playlist).where(Playlist.owner_id == owner_id, IS_WATCH_LATER)
    return await db.scalar(query)


async def first_videos(
    db: AsyncSession, playlist_ids: Sequence[UUID], viewer: User | None
) -> dict[UUID, Video]:
    """Each playlist's first video this viewer may watch: its thumbnail is the cover.

    Per playlist, an index walk of its items in order that stops at the first match.
    """
    first = (
        select(PlaylistItem.video_id)
        .join(Video, Video.id == PlaylistItem.video_id)
        .where(PlaylistItem.playlist_id == Playlist.id, *_watchable(viewer))
        .order_by(PlaylistItem.position)
        .limit(1)
        .correlate(Playlist)
        .scalar_subquery()
    )
    pairs = (
        await db.execute(select(Playlist.id, first).where(Playlist.id.in_(playlist_ids)))
    ).all()
    covers = {playlist_id: video_id for playlist_id, video_id in pairs if video_id is not None}
    videos = await db.scalars(select(Video).where(Video.id.in_(covers.values())))
    by_id = {video.id: video for video in videos}
    return {playlist_id: by_id[video_id] for playlist_id, video_id in covers.items()}


async def containing(db: AsyncSession, playlist_ids: Sequence[UUID], video_id: UUID) -> set[UUID]:
    """Which of these playlists hold the video: a primary key probe each."""
    query = select(PlaylistItem.playlist_id).where(
        PlaylistItem.playlist_id.in_(playlist_ids), PlaylistItem.video_id == video_id
    )
    return set(await db.scalars(query))
