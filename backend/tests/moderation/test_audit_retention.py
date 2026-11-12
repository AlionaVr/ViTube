"""The audit log outlives what it names: deleting a video, a comment or a user keeps every
entry about them (no foreign keys), and the log still reads."""

from httpx2 import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.modules.videos.models import Video
from tests.interactions.conftest import csrf, posted, user_by_email
from tests.moderation.conftest import (
    MODERATOR_EMAIL,
    VIEWER_EMAIL,
    audit_entries,
    hide,
    set_status,
)


async def test_deleting_rows_keeps_their_audit_entries(
    admin_engine: AsyncEngine,
    owner: AsyncClient,
    viewer: AsyncClient,
    moderator: AsyncClient,
    admin: AsyncClient,
    db: AsyncSession,
    video: Video,
) -> None:
    comment = await posted(viewer, video, "Rude")
    await moderator.delete(f"/api/moderation/comments/{comment['id']}", headers=csrf(moderator))
    await hide(moderator, video)
    await set_status(admin, (await user_by_email(db, VIEWER_EMAIL)).handle, "banned")
    before = await audit_entries(db)
    moderator_id = (await user_by_email(db, MODERATOR_EMAIL)).id

    # No API deletes these: as an operator (or a later feature) would, with the superuser.
    async with admin_engine.begin() as conn:
        await conn.execute(text("DELETE FROM comments WHERE id = :id"), {"id": comment["id"]})
        await conn.execute(text("DELETE FROM videos WHERE id = :id"), {"id": video.id})
        for email in ("viewer@example.com", "moderator@example.com"):  # a target, an actor
            await conn.execute(text("DELETE FROM users WHERE email = :e"), {"e": email})

    after = await audit_entries(db)
    assert [entry.id for entry in after] == [entry.id for entry in before]
    assert {entry.actor_id for entry in after} >= {moderator_id}
    items = (await admin.get("/api/moderation/audit-log")).json()["items"]
    assert [(item["action"], item["target"]["label"]) for item in items] == [
        ("set_user_status", ""),
        ("hide_video", ""),
        ("delete_comment", ""),
    ]
    assert items[1]["source"] == "api"
    assert items[1]["actor"] is None  # the moderator is gone; the entry and its actor id stay
    # "About an account" still finds the hide: the entry keeps whose video it was.
    owner_handle = (await owner.get("/api/auth/me")).json()["handle"]
    about = await admin.get("/api/moderation/audit-log", params={"account": owner_handle})
    assert [item["action"] for item in about.json()["items"]] == ["hide_video"]


async def test_the_app_cant_delete_audit_entries_even_by_cascade(db: AsyncSession) -> None:
    """No foreign key points from audit_log anywhere, so no ON DELETE can reach it."""
    references = await db.scalar(
        text(
            "SELECT count(*) FROM pg_constraint"
            " WHERE contype = 'f' AND conrelid = 'audit_log'::regclass"
        )
    )
    assert references == 0
