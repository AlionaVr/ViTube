"""No N+1: a page of 2 rows and a page of 6 rows take the same number of SQL statements."""

from collections.abc import Awaitable, Callable, Iterator
from contextlib import contextmanager

from fastapi import FastAPI
from httpx2 import AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession

from tests.interactions.conftest import browser, csrf, posted, signup, user_by_email
from tests.moderation.conftest import OWNER_EMAIL, hide, report, set_status
from tests.videos.factories import make_video

Seed = Callable[[int], Awaitable[None]]


@contextmanager
def counted(app: FastAPI) -> Iterator[list[str]]:
    """The SQL statements the app sends while inside."""
    statements: list[str] = []
    engine = app.state.sessionmaker.kw["bind"].sync_engine

    def record(conn, cursor, statement, parameters, context, executemany) -> None:  # noqa: ANN001
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", record)
    try:
        yield statements
    finally:
        event.remove(engine, "before_cursor_execute", record)


async def statements_for(app: FastAPI, client: AsyncClient, path: str) -> int:
    with counted(app) as statements:
        response = await client.get(path)
    assert response.status_code == 200
    assert response.json()["items"]
    return len(statements)


async def test_moderation_lists_take_a_fixed_number_of_queries(
    app: FastAPI,
    owner: AsyncClient,
    viewer: AsyncClient,
    moderator: AsyncClient,
    admin: AsyncClient,
    db: AsyncSession,
) -> None:
    anna = await user_by_email(db, OWNER_EMAIL)
    paths = (
        "/api/moderation/reports",
        "/api/moderation/videos/hidden",
        "/api/moderation/users",
        "/api/moderation/audit-log",
        "/api/videos",  # the feed: LISTED's terminated-owner subquery runs once
    )
    made = 0

    async def seed(rows: int) -> None:
        """Up to `rows` of each kind: reported videos and comments, hidden videos, banned users,
        audit entries on all three kinds of target."""
        nonlocal made
        for _ in range(rows - made):
            video = await make_video(db, anna)
            listed = await make_video(db, anna)
            await report(viewer, video)
            comment = await posted(owner, listed, "Rude")
            await viewer.post(
                f"/api/comments/{comment['id']}/report",
                json={"reason": "spam"},
                headers=csrf(viewer),
            )
            hidden = await make_video(db, anna)
            await hide(moderator, hidden)
            await moderator.delete(
                f"/api/moderation/comments/{(await posted(owner, listed))['id']}",
                headers=csrf(moderator),
            )
            async with browser(app, f"10.9.0.{made}") as other:
                email = f"banned{made}@example.com"
                await signup(other, email)
            await set_status(admin, (await user_by_email(db, email)).handle, "banned")
            made += 1

    await seed(2)
    few = [await statements_for(app, admin, path) for path in paths]
    await seed(6)
    many = [await statements_for(app, admin, path) for path in paths]

    assert many == few


async def test_an_interaction_reads_the_owner_once(
    app: FastAPI, owner: AsyncClient, viewer: AsyncClient, db: AsyncSession
) -> None:
    """The restriction is checked once per decision: no second read of the video's owner."""
    video = await make_video(db, await user_by_email(db, OWNER_EMAIL))

    with counted(app) as statements:
        assert (await viewer.get(f"/api/videos/{video.public_id}/comments")).status_code == 200
    user_reads = [s for s in statements if "FROM users" in s and "WHERE users.id =" in s]

    assert len(user_reads) == 2  # the viewer, for the request; the owner's status
