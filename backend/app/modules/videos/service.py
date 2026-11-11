"""Video rules: drafts, metadata, uploads (ADR 0006). The service commits, like @Transactional."""

import contextlib
import logging
import secrets
import time
from collections.abc import AsyncIterable, AsyncIterator, Awaitable, Callable
from datetime import timedelta
from functools import partial
from uuid import UUID

import anyio
from redis.asyncio import Redis
from redis.asyncio.lock import Lock
from redis.exceptions import LockError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import Conflict, DomainError, NotFound, PayloadTooLarge, RequestTimeout
from app.core.pagination import Page, decode_cursor, split_page
from app.core.rate_limit import RateLimit
from app.core.slots import Slots, hold
from app.core.storage import Storage
from app.modules.reactions import service as reactions
from app.modules.users import repository as users
from app.modules.users.models import User
from app.modules.videos import repository as videos
from app.modules.videos.access import get_viewable
from app.modules.videos.config import get_video_settings
from app.modules.videos.models import Category, Video, VideoStatus
from app.modules.videos.repository import VideoRow
from app.modules.videos.schemas import (
    UploadLimits,
    VideoCreate,
    VideoDetail,
    VideoOut,
    VideoSummary,
    VideoUpdate,
)
from app.worker.celery_app import celery_app

log = logging.getLogger(__name__)

PUBLIC_ID_TRIES = 5
DRAFTS_PER_USER = RateLimit("video_draft", limit=20, window=60 * 60)
# Drafts still waiting for a file. Counted over a day: abandoned ones stop counting by themselves.
OPEN_DRAFTS_MAX = 10
OPEN_DRAFTS_WINDOW = timedelta(days=1)
# Held for the whole upload; renewed while bytes keep coming, so a crashed upload frees it soon.
UPLOAD_LOCK_SECONDS = 5 * 60
UPLOAD_LOCK_RENEW_SECONDS = 60
# Uploads at once (ADR 0006). Per account, not per IP: people behind one NAT don't share a limit.
# Each holds up to 2 parts in memory (16 MiB), so 32 uploads stay within ~512 MiB of the api.
UPLOADS_PER_USER = Slots("uploads_user", limit=3, ttl=UPLOAD_LOCK_SECONDS)
UPLOADS_TOTAL = Slots("uploads_total", limit=32, ttl=UPLOAD_LOCK_SECONDS)
# 1 GiB fits even at ~1.2 Mbit/s; a client trickling bytes can't hold a slot longer.
UPLOAD_DEADLINE_SEC = 2 * 3600
PROCESS_TASK = "videos.process"  # by name: the api doesn't import worker code
FEED_PAGE_SIZE = 24  # full rows in a grid of 2, 3, 4 or 6 columns
UP_NEXT_PAGE_SIZE = 20


def upload_limits() -> UploadLimits:
    settings = get_video_settings()
    return UploadLimits(
        max_size_bytes=settings.max_upload_bytes, max_duration_sec=settings.max_video_duration_sec
    )


async def create_draft(db: AsyncSession, redis: Redis, user: User, data: VideoCreate) -> VideoOut:
    await DRAFTS_PER_USER.hit(redis, str(user.id))
    # The user's row lock makes their drafts count one request at a time: two parallel requests
    # can't both see 9 and make 11 (like @Lock(PESSIMISTIC_WRITE)).
    await users.lock(db, user.id)
    if await videos.count_open_drafts(db, user.id, within=OPEN_DRAFTS_WINDOW) >= OPEN_DRAFTS_MAX:
        raise Conflict(f"You have {OPEN_DRAFTS_MAX} unfinished uploads. Finish one first.")
    for _ in range(PUBLIC_ID_TRIES):
        video = await videos.insert_unless_taken(
            db,
            public_id=secrets.token_urlsafe(8),  # 64 random bits, 11 URL-safe chars
            owner_id=user.id,
            title=data.title,
            description=data.description,
            visibility=data.visibility,
            category=data.category,
        )
        if video is not None:
            await db.commit()
            return VideoOut.of(video, user)
    raise RuntimeError("No free public id found")  # 2^64 ids: practically never


async def list_feed(
    db: AsyncSession, category: Category | None, cursor: str | None
) -> Page[VideoSummary]:
    """The home feed: the same for every viewer, so no user is read."""
    before = decode_cursor(cursor, tuple[UUID])[0] if cursor else None
    rows = await videos.list_newest(db, category=category, before=before, limit=FEED_PAGE_SIZE + 1)
    page, next_cursor = split_page(rows, FEED_PAGE_SIZE, lambda row: (row[0].id,))
    return Page(
        items=[VideoSummary.of(video, owner) for video, owner in page], next_cursor=next_cursor
    )


async def list_up_next(
    db: AsyncSession, user: User | None, public_id: str, cursor: str | None
) -> Page[VideoSummary]:
    """The channel's other videos first, then the newest of other channels."""
    # Only for a viewable video: the order would tell who owns a private one.
    video = await get_viewable(db, user, public_id)
    same_channel, before = decode_cursor(cursor, tuple[bool, UUID]) if cursor else (True, None)
    limit = UP_NEXT_PAGE_SIZE + 1
    rows: list[VideoRow] = []
    if same_channel:
        rows += await videos.list_up_next(db, video, same_channel=True, before=before, limit=limit)
        before = None  # the other channels start from their newest
    if len(rows) < limit:
        rows += await videos.list_up_next(
            db, video, same_channel=False, before=before, limit=limit - len(rows)
        )
    page, next_cursor = split_page(
        rows, UP_NEXT_PAGE_SIZE, lambda row: (row[0].owner_id == video.owner_id, row[0].id)
    )
    return Page(
        items=[VideoSummary.of(item, owner) for item, owner in page], next_cursor=next_cursor
    )


async def list_categories(db: AsyncSession) -> list[Category]:
    """Categories with listed videos, in YouTube's order: a chip never leads to an empty feed."""
    present = await videos.listed_categories(db)
    return [category for category in Category if category in present]


async def get_video(db: AsyncSession, user: User | None, public_id: str) -> VideoDetail:
    video = await get_viewable(db, user, public_id)
    out = VideoOut.of(video, await videos.get_owner(db, video))
    return VideoDetail(**dict(out), my_rating=await reactions.my_rating(db, user, video.id))


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
        busy = "Too many uploads at once. Wait for one to finish."
        slots = ((UPLOADS_PER_USER, str(user.id)), (UPLOADS_TOTAL, "all"))
        async with hold(redis, *slots, busy=busy) as held:
            await db.refresh(video)  # the status as it is now that no other upload can run
            if video.status is not VideoStatus.UPLOADING:
                raise Conflict("This video already has a file")
            # No transaction stays open while the file streams: the DB ends idle ones after 60 s.
            await db.commit()

            async def keep_alive() -> None:
                await lock.reacquire()
                await held.renew()

            with anyio.move_on_after(UPLOAD_DEADLINE_SEC) as deadline:
                await storage.upload(
                    video.original_key,
                    _checked(body, limit, keep_alive),
                    content_type="application/octet-stream",  # the client's type is not trusted
                )
            if deadline.cancelled_caught:  # the upload was aborted: nothing stored
                raise RequestTimeout("The upload took too long. Try again on a faster connection.")
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


async def _checked(
    body: AsyncIterable[bytes], limit: int, keep_alive: Callable[[], Awaitable[None]]
) -> AsyncIterator[bytes]:
    """The body as it comes, with the size limit; the upload's lock and slots kept alive."""
    size = 0
    renewed_at = time.monotonic()
    async for chunk in body:
        size += len(chunk)
        if size > limit:
            raise PayloadTooLarge(_too_large())
        if time.monotonic() - renewed_at > UPLOAD_LOCK_RENEW_SECONDS:
            try:
                await keep_alive()
            except LockError:
                raise Conflict("The upload was interrupted. Try again.") from None
            renewed_at = time.monotonic()
        yield chunk
    if size == 0:
        raise DomainError("The file is empty")


async def _release(lock: Lock) -> None:
    # Shielded: a cancelled request still frees the video for a retry.
    with anyio.CancelScope(shield=True), contextlib.suppress(LockError):  # expired: nothing to do
        await lock.release()


def _too_large() -> str:
    return f"The file is larger than {get_video_settings().max_upload_size_mb} MB"
