"""/api/moderation: the report queue and moderator actions (ADR 0009). Moderators and admins."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query, status

from app.core.errors import NotFound
from app.core.pagination import Cursor, Page
from app.db.session import DbSession
from app.modules.audit.models import AuditAction, AuditSource
from app.modules.audit.repository import Actor
from app.modules.auth.deps import Sessions, require_role
from app.modules.moderation import service
from app.modules.moderation.schemas import (
    AuditEntryOut,
    HideIn,
    ModeratedVideo,
    ReportCase,
    RestrictedAccount,
    StatusIn,
)
from app.modules.users import repository as users
from app.modules.users.models import Role, User, UserStatus
from app.modules.videos.schemas import HANDLE_PATTERN, PublicId

router = APIRouter(prefix="/api/moderation", tags=["moderation"])

Moderator = Annotated[User, Depends(require_role(Role.MODERATOR))]
Admin = Annotated[User, Depends(require_role(Role.ADMIN))]
Handle = Annotated[str, Path(pattern=HANDLE_PATTERN, description="Without the @")]


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


@router.get(
    "/users",
    response_model=Page[RestrictedAccount],
    summary="Banned and terminated accounts (admins)",
)
async def list_restricted(
    _: Admin, db: DbSession, status: UserStatus | None = None, cursor: Cursor = None
) -> Page[RestrictedAccount]:
    return await service.list_restricted(db, status, cursor)


@router.put(
    "/users/{handle}/status",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Ban, terminate or reinstate an account (admins)",
    description=(
        "banned: no sign-in, its sessions end, its content stays. terminated: the same, and"
        " its videos are unavailable to all but moderators. active: reinstated."
    ),
)
async def set_status(
    handle: Handle, body: StatusIn, admin: Admin, db: DbSession, sessions: Sessions
) -> None:
    user = await users.get_by_handle(db, handle)
    if user is None:
        raise NotFound("No such user")
    await service.set_status(db, sessions, Actor.of(admin), user.id, body.status, body.reason)


@router.get(
    "/audit-log",
    response_model=Page[AuditEntryOut],
    summary="Who did what, newest first (admins)",
)
async def list_audit(
    _: Admin,
    db: DbSession,
    action: Annotated[list[AuditAction] | None, Query(description="Any of these actions")] = None,
    source: Annotated[AuditSource | None, Query(description="cli: the command line")] = None,
    actor: Annotated[
        str | None, Query(pattern=HANDLE_PATTERN, description="Who acted, without the @")
    ] = None,
    account: Annotated[
        str | None,
        Query(
            pattern=HANDLE_PATTERN,
            description="The account acted on, its videos and its comments; without the @",
        ),
    ] = None,
    cursor: Cursor = None,
) -> Page[AuditEntryOut]:
    return await service.list_audit(
        db, cursor, actions=action or (), source=source, actor=actor, account=account
    )
