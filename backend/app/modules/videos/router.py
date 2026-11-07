"""/api/videos: drafts, metadata, the file upload and the watch page data."""

from fastapi import APIRouter, Request, status
from starlette.requests import ClientDisconnect

from app.core.errors import DomainError
from app.core.redis import RedisClient
from app.core.storage import StorageClient
from app.db.session import DbSession
from app.modules.auth.deps import CurrentUser, OptionalUser
from app.modules.videos import service
from app.modules.videos.schemas import PublicId, UploadLimits, VideoCreate, VideoOut, VideoUpdate

router = APIRouter(prefix="/api/videos", tags=["videos"])

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


@router.post(
    "", status_code=status.HTTP_201_CREATED, response_model=VideoOut, summary="Create a draft"
)
async def create_draft(
    body: VideoCreate, user: CurrentUser, db: DbSession, redis: RedisClient
) -> VideoOut:
    return await service.create_draft(db, redis, user, body)


@router.get("/{public_id}", response_model=VideoOut, summary="A video the viewer may watch")
async def get_video(public_id: PublicId, user: OptionalUser, db: DbSession) -> VideoOut:
    return await service.get_video(db, user, public_id)


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
