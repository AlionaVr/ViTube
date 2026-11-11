"""Playlist rules. The service commits, like @Transactional.

Access: the owner sees and changes their playlists; others see public and unlisted ones, and
get 404 for private ones and for any write, as if they didn't exist.
"""

from typing import Annotated
from uuid import UUID

from pydantic import Field
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import Conflict, DomainError, NotFound
from app.core.pagination import Page, decode_cursor, split_page
from app.core.rate_limit import RateLimit
from app.modules.playlists import repository as playlists
from app.modules.playlists.models import MAX_VIDEOS, Playlist, PlaylistKind
from app.modules.playlists.schemas import (
    MyPlaylist,
    PlaylistCreate,
    PlaylistItemOut,
    PlaylistOut,
    PlaylistUpdate,
    SavedOut,
)
from app.modules.users.models import User
from app.modules.videos import repository as videos
from app.modules.videos.interactions import get_ready
from app.modules.videos.models import Video, Visibility
from app.modules.videos.schemas import MEDIA_PREFIX, VideoSummary

# Per account. Creating is rare; other writes come one per click.
PLAYLISTS_CREATED = RateLimit("playlist_create", limit=20, window=3600)
PLAYLIST_WRITES = RateLimit("playlist_write", limit=120, window=60)
ITEMS_PAGE_SIZE = 100  # as YouTube loads a playlist
MINE_PAGE_SIZE = 50
# A cursor is client input: a number the column can't hold must give 400, not a DB error.
_PositionKey = tuple[Annotated[int, Field(ge=0, le=2**31 - 1)]]


async def create(db: AsyncSession, redis: Redis, user: User, data: PlaylistCreate) -> PlaylistOut:
    await PLAYLISTS_CREATED.hit(redis, str(user.id))
    playlist = await playlists.insert_playlist(
        db,
        owner_id=user.id,
        title=data.title,
        description=data.description,
        visibility=data.visibility,
    )
    await db.commit()
    return PlaylistOut.build(playlist, user, thumbnail_url=None)


async def update_playlist(
    db: AsyncSession, redis: Redis, user: User, playlist_id: UUID, changes: PlaylistUpdate
) -> PlaylistOut:
    await PLAYLIST_WRITES.hit(redis, str(user.id))
    playlist = await _lock_own(db, user, playlist_id)
    if playlist.kind is PlaylistKind.WATCH_LATER:
        raise DomainError("Watch later can't be changed")
    values = changes.model_dump(exclude_none=True)
    if values:
        playlist = await playlists.update_playlist(db, playlist.id, values)
    await db.commit()
    covers = await playlists.first_videos(db, [playlist.id], user)
    return PlaylistOut.build(playlist, user, _thumbnail(covers.get(playlist.id)))


async def delete_playlist(db: AsyncSession, redis: Redis, user: User, playlist_id: UUID) -> None:
    """The lock makes item writes running meanwhile finish first or find no playlist (404)."""
    await PLAYLIST_WRITES.hit(redis, str(user.id))
    playlist = await _lock_own(db, user, playlist_id)
    if playlist.kind is PlaylistKind.WATCH_LATER:
        raise DomainError("Watch later can't be deleted")
    await playlists.delete_playlist(db, playlist.id)
    await db.commit()


async def get_playlist(db: AsyncSession, viewer: User | None, playlist_id: UUID) -> PlaylistOut:
    playlist = await _get_visible(db, viewer, playlist_id)
    owner = await db.get_one(User, playlist.owner_id)
    covers = await playlists.first_videos(db, [playlist.id], viewer)
    return PlaylistOut.build(playlist, owner, _thumbnail(covers.get(playlist.id)))


async def list_items(
    db: AsyncSession, viewer: User | None, playlist_id: UUID, cursor: str | None
) -> Page[PlaylistItemOut]:
    playlist = await _get_visible(db, viewer, playlist_id)
    after = decode_cursor(cursor, _PositionKey)[0] if cursor else None
    rows = await playlists.list_items(
        db, playlist.id, viewer, after=after, limit=ITEMS_PAGE_SIZE + 1
    )
    page, next_cursor = split_page(rows, ITEMS_PAGE_SIZE, lambda row: (row[0].position,))
    items = [
        PlaylistItemOut(video=VideoSummary.of(video, owner), added_at=item.added_at)
        for item, video, owner in page
    ]
    return Page(items=items, next_cursor=next_cursor)


async def add_video(
    db: AsyncSession, redis: Redis, user: User, playlist_id: UUID, public_id: str
) -> None:
    """Append a video the user may watch. Idempotent: adding it again changes nothing."""
    await PLAYLIST_WRITES.hit(redis, str(user.id))
    video = await get_ready(db, user, public_id)
    playlist = await _lock_own(db, user, playlist_id)
    if playlist.video_count >= MAX_VIDEOS:
        if await playlists.position_of(db, playlist.id, video.id) is not None:
            return
        raise Conflict(f"A playlist holds at most {MAX_VIDEOS} videos")
    if await playlists.add_item(db, playlist.id, video.id):
        await playlists.touch(db, playlist.id, count_delta=1)
    await db.commit()


async def remove_video(
    db: AsyncSession, redis: Redis, user: User, playlist_id: UUID, public_id: str
) -> None:
    """Idempotent. No access check on the video: one that turned private must still go."""
    await PLAYLIST_WRITES.hit(redis, str(user.id))
    video = await videos.get_by_public_id(db, public_id)
    playlist = await _lock_own(db, user, playlist_id)
    if video is not None and await playlists.delete_item(db, playlist.id, video.id):
        await playlists.touch(db, playlist.id, count_delta=-1)
    await db.commit()


async def move_video(
    db: AsyncSession,
    redis: Redis,
    user: User,
    playlist_id: UUID,
    public_id: str,
    before: str | None,
) -> None:
    """Put a video just before another one of the playlist, or at the end (before=None).

    "Before a video", not "at index k": the owner may not see every item (some turned private),
    so an index on their screen isn't a position. No access check on the videos, as in remove.
    """
    await PLAYLIST_WRITES.hit(redis, str(user.id))
    if before == public_id:
        raise DomainError("A video can't move before itself")
    playlist = await _lock_own(db, user, playlist_id)
    # Positions are read under the lock: what the previous write to this playlist left.
    video_id, start = await _item(db, playlist, public_id)
    if before is None:
        await playlists.move_to_end(db, playlist.id, video_id)
    else:
        _, target = await _item(db, playlist, before)
        await playlists.move_before(db, playlist.id, video_id, start=start, target=target)
    await playlists.touch(db, playlist.id)
    await db.commit()


async def list_mine(
    db: AsyncSession, user: User, video_public_id: str | None, cursor: str | None
) -> Page[MyPlaylist]:
    """Watch later, then the newest; with a video, each says whether it holds it."""
    after = decode_cursor(cursor, tuple[bool, UUID]) if cursor else None
    rows = await playlists.list_owned(db, user.id, after=after, limit=MINE_PAGE_SIZE + 1)
    page, next_cursor = split_page(rows, MINE_PAGE_SIZE, _mine_key)
    ids = [playlist.id for playlist in page]
    covers = await playlists.first_videos(db, ids, user) if ids else {}
    holding: set[UUID] | None = None
    if video_public_id is not None:
        video = await videos.get_by_public_id(db, video_public_id)
        holding = await playlists.containing(db, ids, video.id) if video and ids else set()
    items = [
        MyPlaylist(
            **PlaylistOut.build(playlist, user, _thumbnail(covers.get(playlist.id))).model_dump(),
            contains_video=None if holding is None else playlist.id in holding,
        )
        for playlist in page
    ]
    return Page(items=items, next_cursor=next_cursor)


async def is_saved(db: AsyncSession, user: User, public_id: str) -> SavedOut:
    """No access check: the answer is only about the user's own playlists."""
    video = await videos.get_by_public_id(db, public_id)
    return SavedOut(saved=video is not None and await playlists.is_saved(db, user.id, video.id))


async def get_watch_later(db: AsyncSession, user: User) -> PlaylistOut:
    playlist = await playlists.get_watch_later(db, user.id)
    if playlist is None:  # the users trigger makes one with every user
        raise NotFound("Playlist not found")
    covers = await playlists.first_videos(db, [playlist.id], user)
    return PlaylistOut.build(playlist, user, _thumbnail(covers.get(playlist.id)))


def _mine_key(playlist: Playlist) -> tuple[bool, UUID]:
    return playlist.kind is PlaylistKind.WATCH_LATER, playlist.id


async def _get_visible(db: AsyncSession, viewer: User | None, playlist_id: UUID) -> Playlist:
    playlist = await playlists.get(db, playlist_id)
    own = playlist is not None and viewer is not None and playlist.owner_id == viewer.id
    if playlist is None or (playlist.visibility is Visibility.PRIVATE and not own):
        raise NotFound("Playlist not found")
    return playlist


async def _lock_own(db: AsyncSession, user: User, playlist_id: UUID) -> Playlist:
    playlist = await playlists.lock_own(db, playlist_id, user.id)
    if playlist is None:
        raise NotFound("Playlist not found")
    return playlist


async def _item(db: AsyncSession, playlist: Playlist, public_id: str) -> tuple[UUID, int]:
    """The video's id and its position in the playlist, else NotFound."""
    video = await videos.get_by_public_id(db, public_id)
    position = await playlists.position_of(db, playlist.id, video.id) if video else None
    if video is None or position is None:
        raise NotFound("Video not in this playlist")
    return video.id, position


def _thumbnail(video: Video | None) -> str | None:
    return MEDIA_PREFIX + video.thumbnail_key if video else None
