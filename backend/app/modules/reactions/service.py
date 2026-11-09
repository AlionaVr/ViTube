"""Rating rules. The service commits, like @Transactional."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.reactions import repository as reactions
from app.modules.reactions.models import DISLIKE, LIKE
from app.modules.reactions.schemas import Rating, RatingOut
from app.modules.users.models import User
from app.modules.videos.interactions import get_ready

_VALUES = {Rating.LIKE: LIKE, Rating.DISLIKE: DISLIKE}
_RATINGS = {value: rating for rating, value in _VALUES.items()}


async def my_rating(db: AsyncSession, user: User | None, video_id: UUID) -> Rating:
    value = await reactions.get_value(db, video_id, user.id) if user else None
    return Rating.NONE if value is None else _RATINGS[value]


async def rate_video(db: AsyncSession, user: User, public_id: str, rating: Rating) -> RatingOut:
    """Idempotent: sending the same rating again changes nothing."""
    video = await get_ready(db, user, public_id)
    value = _VALUES.get(rating)
    if value is None:
        old = await reactions.delete_value(db, video.id, user.id)
    else:
        old = await reactions.put_value(db, video.id, user.id, value)
    # Counted from what the statement really replaced, so parallel requests add up exactly.
    delta = (value == LIKE) - (old == LIKE)
    like_count = await reactions.add_likes(db, video.id, delta) if delta else video.like_count
    await db.commit()
    return RatingOut(like_count=like_count, my_rating=rating)
