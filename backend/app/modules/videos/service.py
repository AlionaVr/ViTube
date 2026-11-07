"""Video rules: drafts, metadata, uploads (ADR 0006). The service commits, like @Transactional."""

import contextlib
import logging
import secrets
import time
from collections.abc import AsyncIterable, AsyncIterator
from functools import partial
from uuid import UUID

import anyio
from redis.asyncio import Redis
from redis.asyncio.lock import Lock
from redis.exceptions import LockError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import Conflict, DomainError, NotFound, PayloadTooLarge
from app.core.rate_limit import RateLimit
from app.core.storage import Storage
from app.modules.users import repository as users
from app.modules.users.models import User
from app.modules.videos import repository as videos
from app.modules.videos.access import get_viewable
from app.modules.videos.config import get_video_settings
from app.modules.videos.models import Video, VideoStatus
from app.modules.videos.schemas import UploadLimits, VideoCreate, VideoOut, VideoUpdate
from app.worker.celery_app import celery_app

log = logging.getLogger(__name__)

PUBLIC_ID_TRIES = 5
DRAFTS_PER_USER = RateLimit("video_draft", limit=20, window=60 * 60)
# Held for the whole upload; renewed while bytes keep coming, so a crashed upload frees it soon.
UPLOAD_LOCK_SECONDS = 5 * 60
UPLOAD_LOCK_RENEW_SECONDS = 60
PROCESS_TASK = "videos.process"  # by name: the api doesn't import worker code


def upload_limits() -> UploadLimits:
    settings = get_video_settings()
    return UploadLimits(
        max_size_bytes=settings.max_upload_bytes, max_duration_sec=settings.max_video_duration_sec
    )


async def create_draft(db: AsyncSession, redis: Redis, user: User, data: VideoCreate) -> VideoOut:
    await DRAFTS_PER_USER.hit(redis, str(user.id))
    for _ in range(PUBLIC_ID_TRIES):
        video = await videos.insert_unless_taken(
            db,
            public_id=secrets.token_urlsafe(8),  # 64 random bits, 11 URL-safe chars
            owner_id=user.id,
            title=data.title,
            description=data.description,
            visibility=data.visibility,
        )
        if video is not None:
            await db.commit()
            return VideoOut.of(video, user)
    raise RuntimeError("No free public id found")  # 2^64 ids: practically never


async def get_video(db: AsyncSession, user: User | None, public_id: str) -> VideoOut:
    video = await get_viewable(db, user, public_id)
    return VideoOut.of(video, await videos.get_owner(db, video))


async def update_video(
    db: AsyncSession, user: User, public_id: str, changes: VideoUpdate
) -> VideoOut:
    """Metadata edits work in any status: while uploading and processing too (ADR 0006)."""
    video = await get_owned(db, user, public_id)
    for field, value in changes.model_dump(exclude_none=True).items():
        setattr(video, field, value)
    await db.commit()
    await db.refresh(video)  # the worker may have moved the status meanwhile
    return VideoOut.of(video, user)


async def upload_file(
    db: AsyncSession,
    redis: Redis,
    storage: Storage,
    user: User,
    public_id: str,
    body: AsyncIterable[bytes],
    declared_size: int | None,
) -> VideoOut:
    """Stream the file to MinIO, then mark it uploaded and queue processing.

    A cut-off upload stores nothing and leaves the video in `uploading`: the client may retry.
    """
    limit = get_video_settings().max_upload_bytes
    video = await get_owned(db, user, public_id)
    # Content-Length only refuses early; the real bytes are counted below (ADR 0006).
    if declared_size is not None and declared_size > limit:
        raise PayloadTooLarge(_too_large())
    lock = redis.lock(f"upload:{video.id}", timeout=UPLOAD_LOCK_SECONDS, blocking=False)
    if not await lock.acquire():
        raise Conflict("This video is already being uploaded")
    try:
        await db.refresh(video)  # the status as it is now that no other upload can run
        if video.status is not VideoStatus.UPLOADING:
            raise Conflict("This video already has a file")
        # No transaction stays open while the file streams: the DB ends idle ones after 60 s.
        await db.commit()
        await storage.upload(
            video.original_key,
            _checked(body, limit, lock),
            content_type="application/octet-stream",  # the client's type is not trusted
        )
        moved = await videos.move_status(
            db, video.id, current=VideoStatus.UPLOADING, new=VideoStatus.UPLOADED
        )
        if not moved:  # only if the lock expired and another upload won
            raise Conflict("This video already has a file")
        await db.commit()
    finally:
        await _release(lock)
    await enqueue_processing(video.id)  # only after the commit: the worker must see `uploaded`
    await db.refresh(video)
    return VideoOut.of(video, user)


async def grant_access(db: AsyncSession, user: User, public_id: str, handle: str) -> None:
    """Let a user watch the owner's private video. Takes effect on their next request."""
    video = await get_owned(db, user, public_id)
    grantee = await users.get_by_handle(db, handle)
    if grantee is None:
        raise NotFound("No user with this handle")
    if grantee.id == user.id:
        raise DomainError("You can always watch your own video")
    await videos.grant_access(db, video.id, grantee.id)
    await db.commit()


async def revoke_access(db: AsyncSession, user: User, public_id: str, handle: str) -> None:
    """Applies to the user's next request, media too (ADR 0004: no cache)."""
    video = await get_owned(db, user, public_id)
    grantee = await users.get_by_handle(db, handle)
    if grantee is not None:  # an unknown handle has nothing to revoke
        await videos.revoke_access(db, video.id, grantee.id)
        await db.commit()


async def enqueue_processing(video_id: UUID) -> None:
    """Best effort. If the broker is down, the sweeper queues the video later (ADR 0003)."""
    send = partial(celery_app.send_task, PROCESS_TASK, args=[str(video_id)])
    try:
        await anyio.to_thread.run_sync(send)  # kombu blocks; keep it off the event loop
    except Exception:
        log.exception("Could not queue video %s; the sweeper will", video_id)


async def get_owned(db: AsyncSession, user: User, public_id: str) -> Video:
    """The user's own video. Others get 404, as if it didn't exist."""
    video = await videos.get_by_public_id(db, public_id)
    if video is None or video.owner_id != user.id:
        raise NotFound("Video not found")
    return video


async def _checked(body: AsyncIterable[bytes], limit: int, lock: Lock) -> AsyncIterator[bytes]:
    """The body as it comes, with the size limit and the upload lock kept alive."""
    size = 0
    renewed_at = time.monotonic()
    async for chunk in body:
        size += len(chunk)
        if size > limit:
            raise PayloadTooLarge(_too_large())
        if time.monotonic() - renewed_at > UPLOAD_LOCK_RENEW_SECONDS:
            try:
                await lock.reacquire()
            except LockError:
                raise Conflict("The upload was interrupted. Try again.") from None
            renewed_at = time.monotonic()
        yield chunk
    if size == 0:
        raise DomainError("The file is empty")


async def _release(lock: Lock) -> None:
    with contextlib.suppress(LockError):  # it expired: nothing to release
        await lock.release()


def _too_large() -> str:
    return f"The file is larger than {get_video_settings().max_upload_size_mb} MB"
