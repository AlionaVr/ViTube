"""Audit log writes. No commits: the entry joins the action's own transaction."""

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditAction, AuditEntry, AuditSource, TargetType
from app.modules.users.models import User


@dataclass(frozen=True)
class Actor:
    """Who performs an action: a signed-in user (API) or someone with a shell (CLI)."""

    source: AuditSource
    user_id: UUID | None = None
    notes: dict[str, Any] = field(default_factory=dict)  # the admin a CLI command names

    @classmethod
    def of(cls, user: User) -> "Actor":
        return cls(AuditSource.API, user.id)

    @classmethod
    def cli(cls, by: str | None) -> "Actor":
        """The admin named with --by: claimed, not checked by a login. Shell access is the trust
        boundary; who ran `docker compose exec` is in the host's logs, not here (the container's
        user is always the same)."""
        return cls(AuditSource.CLI, notes={"by": by} if by else {})


async def record(
    db: AsyncSession,
    actor: Actor,
    action: AuditAction,
    target_type: TargetType,
    target_id: UUID,
    *,
    subject: UUID,
    **details: Any,
) -> None:
    """`subject`: the account acted on (see AuditEntry.subject_user_id)."""
    await db.execute(
        insert(AuditEntry).values(
            source=actor.source,
            actor_id=actor.user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            subject_user_id=subject,
            details=actor.notes | details,
        )
    )
