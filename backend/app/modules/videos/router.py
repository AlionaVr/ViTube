"""/api/videos: the feed, drafts, metadata, the file upload, the watch page data and sharing.
/api/me/videos: the owner's list for Studio."""

from typing import Annotated

from fastapi import APIRouter, Path, Request, status
from starlette.requests import ClientDisconnect

from app.core.errors import DomainError
from app.core.pagination import Cursor, Page
from app.core.redis import RedisClient
from app.core.storage import StorageClient
from app.db.session import DbSession
from app.modules.auth.deps import CurrentUser, OptionalUser
from app.modules.videos import service
from app.modules.videos.models import Category
from app.modules.videos.schemas import (
    HANDLE_PATTERN,
    AccessGrant,
    PublicId,
    UploadLimits,
    VideoCreate,
    VideoDetail,
    VideoOut,
    VideoSummary,
    VideoUpdate,
)

router = APIRouter(prefix="/api/videos", tags=["videos"])
categories_router = APIRouter(prefix="/api/categories", tags=["videos"])
me_router = APIRouter(prefix="/api/me", tags=["videos"])

# The body is the file itself, any Content-Type (ADR 0006).
FILE_BODY = {
    "requestBody": {
        "required": True,
        "content": {"application/octet-stream": {"schema": {"type": "string", "format": "binary"}}},
    }
}


# Before /{public_id}: routes match in order.
@router.get("/upload-limits", response_model=UploadLimits, summary="Upload limits")
async def upload_limits() -> UploadLimits:
    return service.upload_limits()


@router.get("", response_model=Page[VideoSummary], summary="Home feed: public videos, newest first")
async def list_feed(
    db: DbSession, category: Category | None = None, cursor: Cursor = None
) -> Page[VideoSummary]:
    return await service.list_feed(db, category, cursor)


@categories_router.get(
    "", response_model=list[Category], summary="Categories that have public videos"
)
async def list_categories(db: DbSession) -> list[Category]:
    return await service.list_categories(db)


@me_router.get(
    "/videos",
    response_model=Page[VideoOut],
    summary="Your videos, newest first: drafts, processing, failed and private ones too",
)
async def list_my_videos(user: CurrentUser, db: DbSession, cursor: Cursor = None) -> Page[VideoOut]:
    return await service.list_mine(db, user, cursor)


@router.post(
    "", status_code=status.HTTP_201_CREATED, response_model=VideoOut, summary="Create a draft"
)
async def create_draft(
    body: VideoCreate, user: CurrentUser, db: DbSession, redis: RedisClient
) -> VideoOut:
    return await service.create_draft(db, redis, user, body)


@router.get("/{public_id}", response_model=VideoDetail, summary="A video the viewer may watch")
async def get_video(public_id: PublicId, user: OptionalUser, db: DbSession) -> VideoDetail:
    return await service.get_video(db, user, public_id)


@router.get(
    "/{public_id}/related",
    response_model=Page[VideoSummary],
    summary="Up next: the channel's other videos first, then the newest",
)
async def list_up_next(
    public_id: PublicId, user: OptionalUser, db: DbSession, cursor: Cursor = None
) -> Page[VideoSummary]:
    return await service.list_up_next(db, user, public_id, cursor)


@router.patch("/{public_id}", response_model=VideoOut, summary="Edit your video's details")
async def update_video(
    public_id: PublicId, body: VideoUpdate, user: CurrentUser, db: DbSession
) -> VideoOut:
    return await service.update_video(db, user, public_id, body)


@router.put(
    "/{public_id}/file",
    response_model=VideoOut,
    summary="Upload the file of your draft",
    description="The request body is the file. Processing starts once it is stored.",
    openapi_extra=FILE_BODY,
)
async def upload_file(
    public_id: PublicId,
    request: Request,
    user: CurrentUser,
    db: DbSession,
    redis: RedisClient,
    storage: StorageClient,
) -> VideoOut:
    length = request.headers.get("content-length", "")
    try:
        return await service.upload_file(
            db,
            redis,
            storage,
            user,
            public_id,
            request.stream(),
            int(length) if length.isdecimal() else None,
        )
    except ClientDisconnect:
        raise DomainError("The upload was interrupted") from None  # nothing was stored


@router.post(
    "/{public_id}/access",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Let a user watch your private video",
)
async def grant_access(
    public_id: PublicId, body: AccessGrant, user: CurrentUser, db: DbSession
) -> None:
    await service.grant_access(db, user, public_id, body.handle)


@router.delete(
    "/{public_id}/access/{handle}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Take back a user's access to your video",
)
async def revoke_access(
    public_id: PublicId,
    handle: Annotated[str, Path(pattern=HANDLE_PATTERN)],
    user: CurrentUser,
    db: DbSession,
) -> None:
    await service.revoke_access(db, user, public_id, handle)
