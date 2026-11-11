"""/api/moderation: the report queue and moderator actions (ADR 0009). Moderators and admins."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.core.pagination import Cursor, Page
from app.db.session import DbSession
from app.modules.auth.deps import require_role
from app.modules.moderation import service
from app.modules.moderation.schemas import HideIn, ModeratedVideo, ReportCase
from app.modules.users.models import Role, User
from app.modules.videos.schemas import PublicId

router = APIRouter(prefix="/api/moderation", tags=["moderation"])

Moderator = Annotated[User, Depends(require_role(Role.MODERATOR))]


@router.get(
    "/reports",
    response_model=Page[ReportCase],
    summary="Open reports by video or comment, oldest first",
)
async def list_reports(_: Moderator, db: DbSession, cursor: Cursor = None) -> Page[ReportCase]:
    return await service.list_cases(db, cursor)


@router.get(
    "/videos/hidden",
    response_model=Page[ModeratedVideo],
    summary="Hidden videos, newest first",
)
async def list_hidden(_: Moderator, db: DbSession, cursor: Cursor = None) -> Page[ModeratedVideo]:
    return await service.list_hidden(db, cursor)


@router.post(
    "/videos/{public_id}/hide",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Hide a video and close its reports",
    description="Only its owner and moderators can open it then; everyone else gets 404.",
)
async def hide_video(
    public_id: PublicId, body: HideIn, moderator: Moderator, db: DbSession
) -> None:
    await service.hide_video(db, moderator, public_id, body.reason)


@router.post(
    "/videos/{public_id}/restore",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Show a hidden video again",
)
async def restore_video(public_id: PublicId, moderator: Moderator, db: DbSession) -> None:
    await service.restore_video(db, moderator, public_id)


@router.post(
    "/videos/{public_id}/dismiss",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Close a video's reports: nothing wrong with it",
)
async def dismiss_video(public_id: PublicId, moderator: Moderator, db: DbSession) -> None:
    await service.dismiss_video(db, moderator, public_id)


@router.delete(
    "/comments/{comment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a comment and close its reports",
    description="Deleting a thread's first comment deletes its replies too.",
)
async def delete_comment(comment_id: UUID, moderator: Moderator, db: DbSession) -> None:
    await service.delete_comment(db, moderator, comment_id)


@router.post(
    "/comments/{comment_id}/dismiss",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Close a comment's reports: nothing wrong with it",
)
async def dismiss_comment(comment_id: UUID, moderator: Moderator, db: DbSession) -> None:
    await service.dismiss_comment(db, moderator, comment_id)
