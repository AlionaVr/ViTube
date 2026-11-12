"""Playlists. Anyone reads public and unlisted ones; the owner reads and writes their own."""

from fastapi import APIRouter, status

from app.core.pagination import Cursor, Page
from app.core.redis import RedisClient
from app.db.session import DbSession
from app.modules.auth.deps import CurrentUser, OptionalUser
from app.modules.channels.schemas import Handle
from app.modules.playlists import service
from app.modules.playlists.schemas import (
    ItemMove,
    MyPlaylist,
    PlaylistCreate,
    PlaylistId,
    PlaylistItemOut,
    PlaylistOut,
    PlaylistUpdate,
    SavedOut,
    VideoQuery,
)
from app.modules.videos.schemas import PublicId

router = APIRouter(prefix="/api", tags=["playlists"])


@router.post(
    "/playlists",
    status_code=status.HTTP_201_CREATED,
    response_model=PlaylistOut,
    summary="Create a playlist",
)
async def create_playlist(
    body: PlaylistCreate, user: CurrentUser, db: DbSession, redis: RedisClient
) -> PlaylistOut:
    return await service.create(db, redis, user, body)


@router.get("/playlists/{playlist_id}", response_model=PlaylistOut, summary="A playlist")
async def get_playlist(playlist_id: PlaylistId, user: OptionalUser, db: DbSession) -> PlaylistOut:
    return await service.get_playlist(db, user, playlist_id)


@router.patch(
    "/playlists/{playlist_id}",
    response_model=PlaylistOut,
    summary="Change your playlist",
    description="Only the given fields change. Watch later can't be changed (400).",
)
async def update_playlist(
    playlist_id: PlaylistId,
    body: PlaylistUpdate,
    user: CurrentUser,
    db: DbSession,
    redis: RedisClient,
) -> PlaylistOut:
    return await service.update_playlist(db, redis, user, playlist_id, body)


@router.delete(
    "/playlists/{playlist_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete your playlist",
    description="The videos stay; only the list goes. Watch later can't be deleted (400).",
)
async def delete_playlist(
    playlist_id: PlaylistId, user: CurrentUser, db: DbSession, redis: RedisClient
) -> None:
    await service.delete_playlist(db, redis, user, playlist_id)


@router.get(
    "/playlists/{playlist_id}/items",
    response_model=Page[PlaylistItemOut],
    summary="A playlist's videos, in order",
    description="Only the videos this viewer may watch.",
)
async def list_items(
    playlist_id: PlaylistId, user: OptionalUser, db: DbSession, cursor: Cursor = None
) -> Page[PlaylistItemOut]:
    return await service.list_items(db, user, playlist_id, cursor)


@router.put(
    "/playlists/{playlist_id}/items/{public_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Add a video to the end of your playlist",
    description="Adding it again changes nothing.",
)
async def add_video(
    playlist_id: PlaylistId,
    public_id: PublicId,
    user: CurrentUser,
    db: DbSession,
    redis: RedisClient,
) -> None:
    await service.add_video(db, redis, user, playlist_id, public_id)


@router.delete(
    "/playlists/{playlist_id}/items/{public_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a video from your playlist",
    description="Removing it again, or a video that isn't there, changes nothing.",
)
async def remove_video(
    playlist_id: PlaylistId,
    public_id: PublicId,
    user: CurrentUser,
    db: DbSession,
    redis: RedisClient,
) -> None:
    await service.remove_video(db, redis, user, playlist_id, public_id)


@router.patch(
    "/playlists/{playlist_id}/items/{public_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Move a video in your playlist",
    description="Just before another video of the playlist, or to the end with `before: null`.",
)
async def move_video(
    playlist_id: PlaylistId,
    public_id: PublicId,
    body: ItemMove,
    user: CurrentUser,
    db: DbSession,
    redis: RedisClient,
) -> None:
    await service.move_video(db, redis, user, playlist_id, public_id, body.before)


@router.get(
    "/channels/{handle}/playlists",
    response_model=Page[PlaylistOut],
    summary="A channel's public playlists, newest first",
    description=(
        "The same list for every viewer, the owner too; covers are per viewer. "
        "The owner's view is `/api/me/channel/playlists`."
    ),
)
async def list_channel_playlists(
    handle: Handle, user: OptionalUser, db: DbSession, cursor: Cursor = None
) -> Page[PlaylistOut]:
    return await service.list_channel_playlists(db, user, handle, cursor)


@router.get(
    "/me/channel/playlists",
    response_model=Page[PlaylistOut],
    summary="Your channel's playlists, whatever their visibility",
    description="Every playlist you made, newest first: your own channel's Playlists tab.",
)
async def list_my_channel_playlists(
    user: CurrentUser, db: DbSession, cursor: Cursor = None
) -> Page[PlaylistOut]:
    return await service.list_my_channel_playlists(db, user, cursor)


@router.get(
    "/me/playlists",
    response_model=Page[MyPlaylist],
    summary="Your playlists, newest first",
)
async def list_mine(
    user: CurrentUser, db: DbSession, video: VideoQuery = None, cursor: Cursor = None
) -> Page[MyPlaylist]:
    return await service.list_mine(db, user, video, cursor)


@router.get(
    "/me/watch-later",
    response_model=PlaylistOut,
    summary="Your Watch later playlist",
    description="Every user has one; its id opens it like any other playlist.",
)
async def get_watch_later(user: CurrentUser, db: DbSession) -> PlaylistOut:
    return await service.get_watch_later(db, user)


@router.get(
    "/videos/{public_id}/saved",
    response_model=SavedOut,
    summary="Whether a video is in any of your playlists",
)
async def is_saved(public_id: PublicId, user: CurrentUser, db: DbSession) -> SavedOut:
    return await service.is_saved(db, user, public_id)
