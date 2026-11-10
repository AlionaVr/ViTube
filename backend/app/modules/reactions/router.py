"""Likes and dislikes of videos and comments."""

from uuid import UUID

from fastapi import APIRouter

from app.core.redis import RedisClient
from app.db.session import DbSession
from app.modules.auth.deps import CurrentUser
from app.modules.reactions import service
from app.modules.reactions.schemas import RatingIn, RatingOut
from app.modules.videos.schemas import PublicId

router = APIRouter(prefix="/api", tags=["ratings"])


@router.put(
    "/videos/{public_id}/rating",
    response_model=RatingOut,
    summary="Like or dislike a video",
    description='"none" takes the rating back. Sending the same rating again changes nothing.',
)
async def rate_video(
    public_id: PublicId, body: RatingIn, user: CurrentUser, db: DbSession, redis: RedisClient
) -> RatingOut:
    return await service.rate_video(db, redis, user, public_id, body.rating)


@router.put(
    "/comments/{comment_id}/rating",
    response_model=RatingOut,
    summary="Like or dislike a comment",
    description='"none" takes the rating back. Sending the same rating again changes nothing.',
)
async def rate_comment(
    comment_id: UUID, body: RatingIn, user: CurrentUser, db: DbSession, redis: RedisClient
) -> RatingOut:
    return await service.rate_comment(db, redis, user, comment_id, body.rating)
