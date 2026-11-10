"""Views: the player reports playback; the server decides what counts (ADR 0011)."""

from fastapi import APIRouter, Request, status

from app.core.rate_limit import client_ip
from app.core.redis import RedisClient
from app.db.session import DbSession
from app.modules.auth.deps import OptionalUser
from app.modules.videos.schemas import PublicId
from app.modules.views import service

router = APIRouter(prefix="/api/videos", tags=["views"])


@router.post(
    "/{public_id}/views/start",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Playback started",
    description="Send when playback begins. A later `views` call counts only after enough time.",
)
async def start_view(
    public_id: PublicId, request: Request, user: OptionalUser, db: DbSession, redis: RedisClient
) -> None:
    await service.start(db, redis, user, client_ip(request), public_id)


@router.post(
    "/{public_id}/views",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Playback reached the view threshold",
    description=(
        "Send after min(30 s, video length) of playback. Counts once per viewer and video a day;"
        " the server checks the time since `views/start` itself."
    ),
)
async def count_view(
    public_id: PublicId, request: Request, user: OptionalUser, db: DbSession, redis: RedisClient
) -> None:
    await service.finish(db, redis, user, client_ip(request), public_id)
