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
    notes: dict[str, Any] = field(default_factory=dict)  # what the CLI knows about who ran it

    @classmethod
    def of(cls, user: User) -> "Actor":
        return cls(AuditSource.API, user.id)


async def record(
    db: AsyncSession,
    actor: Actor,
    action: AuditAction,
    target_type: TargetType,
    target_id: UUID,
    **details: Any,
) -> None:
    await db.execute(
        insert(AuditEntry).values(
            source=actor.source,
            actor_id=actor.user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            details=actor.notes | details,
        )
    )
