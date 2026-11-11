"""Accounts in every role, a ready video, and helpers to read reports and the audit log."""

from collections.abc import AsyncIterator
from typing import Any

import pytest
from fastapi import FastAPI
from httpx2 import AsyncClient, Response
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditEntry
from app.modules.reports.models import Report
from app.modules.users.models import Role
from app.modules.videos.models import Video
from tests.interactions.conftest import browser, csrf, signup, user_by_email
from tests.videos.factories import make_video, set_role

OWNER_EMAIL = "owner@example.com"
VIEWER_EMAIL = "viewer@example.com"
MODERATOR_EMAIL = "moderator@example.com"
ADMIN_EMAIL = "admin@example.com"


@pytest.fixture
async def owner(db: AsyncSession, client: AsyncClient) -> AsyncClient:
    """`client`, signed in. After `db`: its reset would wipe the account."""
    await signup(client, OWNER_EMAIL)
    return client


async def _member(
    app: FastAPI, db: AsyncSession, ip: str, email: str, role: Role = Role.USER
) -> AsyncIterator[AsyncClient]:
    async with browser(app, ip) as other:
        await signup(other, email)
        await set_role(db, email, role)
        yield other


@pytest.fixture
async def viewer(app: FastAPI, db: AsyncSession, client: AsyncClient) -> AsyncIterator[AsyncClient]:
    async for other in _member(app, db, "10.0.0.2", VIEWER_EMAIL):
        yield other


@pytest.fixture
async def moderator(
    app: FastAPI, db: AsyncSession, client: AsyncClient
) -> AsyncIterator[AsyncClient]:
    async for other in _member(app, db, "10.0.0.4", MODERATOR_EMAIL, Role.MODERATOR):
        yield other


@pytest.fixture
async def admin(app: FastAPI, db: AsyncSession, client: AsyncClient) -> AsyncIterator[AsyncClient]:
    async for other in _member(app, db, "10.0.0.5", ADMIN_EMAIL, Role.ADMIN):
        yield other


@pytest.fixture
async def guest(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with browser(app, "10.0.0.3") as other:
        yield other


@pytest.fixture
async def video(db: AsyncSession, owner: AsyncClient) -> Video:
    """The owner's public, ready video."""
    return await make_video(db, await user_by_email(db, OWNER_EMAIL))


async def report(
    client: AsyncClient, video: Video, reason: str = "spam", details: str = ""
) -> Response:
    return await client.post(
        f"/api/videos/{video.public_id}/report",
        json={"reason": reason, "details": details},
        headers=csrf(client),
    )


async def hide(client: AsyncClient, video: Video, reason: str = "spam") -> Response:
    return await client.post(
        f"/api/moderation/videos/{video.public_id}/hide",
        json={"reason": reason},
        headers=csrf(client),
    )


async def reports_of(db: AsyncSession, video: Video) -> list[Report]:
    query = select(Report).where(Report.video_id == video.id).order_by(Report.id)
    return list(await db.scalars(query.execution_options(populate_existing=True)))


async def audit_entries(db: AsyncSession) -> list[AuditEntry]:
    query = select(AuditEntry).order_by(AuditEntry.id)
    return list(await db.scalars(query.execution_options(populate_existing=True)))


def as_dict(entry: AuditEntry) -> dict[str, Any]:
    return {
        "source": entry.source,
        "actor_id": entry.actor_id,
        "action": entry.action,
        "target_type": entry.target_type,
        "target_id": entry.target_id,
        "details": entry.details,
    }


async def act(client: AsyncClient, video: Video, action: str) -> Response:
    """restore or dismiss: moderator actions without a body."""
    return await client.post(
        f"/api/moderation/videos/{video.public_id}/{action}", headers=csrf(client)
    )


async def hide_directly(db: AsyncSession, video: Video) -> None:
    """Hide as a moderator would, without the audit entry: for tests of the effects."""
    await db.execute(update(Video).where(Video.id == video.id).values(is_hidden=True))
    await db.commit()
