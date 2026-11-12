"""Watch history: the player saves where it is; the user reads their history."""

from fastapi import APIRouter, status

from app.core.pagination import Cursor, Page
from app.core.redis import RedisClient
from app.db.session import DbSession
from app.modules.auth.deps import CurrentUser
from app.modules.history import service
from app.modules.history.schemas import HistoryItem, PositionIn, VideoIds
from app.modules.videos.schemas import PublicId

router = APIRouter(prefix="/api/me/history", tags=["history"])


@router.get(
    "",
    response_model=Page[HistoryItem],
    summary="Your watch history, last watched first",
    description="Only the videos you may still watch.",
)
async def list_history(
    user: CurrentUser, db: DbSession, cursor: Cursor = None
) -> Page[HistoryItem]:
    return await service.list_history(db, user, cursor)


@router.get(
    "/progress",
    response_model=dict[str, int],
    summary="Where you stopped in these videos",
    description="Saved positions by public id, for the progress bars on thumbnails. Videos you"
    " haven't watched are left out.",
)
async def get_progress(user: CurrentUser, db: DbSession, v: VideoIds) -> dict[str, int]:
    return await service.progress(db, user, v)


@router.put(
    "/{public_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Save where playback is",
    description="Puts the video on top of your history. Send on start, pause and end, and every"
    " 10 s while playing.",
)
async def save_position(
    public_id: PublicId, body: PositionIn, user: CurrentUser, db: DbSession, redis: RedisClient
) -> None:
    await service.save_position(db, redis, user, public_id, body.position_sec)
