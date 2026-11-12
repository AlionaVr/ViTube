"""Liked videos (/playlist?list=LL): the signed-in user's likes as a playlist."""

from fastapi import APIRouter

from app.core.pagination import Cursor, Page
from app.db.session import DbSession
from app.modules.auth.deps import CurrentUser
from app.modules.liked import service
from app.modules.liked.schemas import LikedItem, LikedOut

router = APIRouter(prefix="/api/me/liked", tags=["liked videos"])


@router.get(
    "",
    response_model=LikedOut,
    summary="Your Liked videos: count, cover and last change",
    description="Counts only the liked videos you may watch now, as the list shows them.",
)
async def get_liked(user: CurrentUser, db: DbSession) -> LikedOut:
    return await service.get_liked(db, user)


@router.get(
    "/items",
    response_model=Page[LikedItem],
    summary="Your liked videos, newest like first",
    description="Only the videos you may watch now: one that turns private or hidden leaves the"
    " list and comes back with access.",
)
async def list_liked(user: CurrentUser, db: DbSession, cursor: Cursor = None) -> Page[LikedItem]:
    return await service.list_liked(db, user, cursor)
