"""Reports: a signed-in user flags a video for moderators (ADR 0009)."""

from fastapi import APIRouter, status

from app.core.redis import RedisClient
from app.db.session import DbSession
from app.modules.auth.deps import CurrentUser
from app.modules.reports import service
from app.modules.reports.schemas import ReportIn
from app.modules.videos.schemas import PublicId

router = APIRouter(prefix="/api", tags=["reports"])


@router.post(
    "/videos/{public_id}/report",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Report a video to moderators",
    description="One open report per user and video: reporting it again changes nothing.",
)
async def report_video(
    public_id: PublicId, body: ReportIn, user: CurrentUser, db: DbSession, redis: RedisClient
) -> None:
    await service.report_video(db, redis, user, public_id, body)
