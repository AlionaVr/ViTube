"""/api/videos/{id}/access: who the owner shared a video with, and the cap on that list."""

import asyncio
from collections.abc import AsyncIterator
from datetime import datetime
from uuid import UUID

import pytest
from fastapi import FastAPI
from httpx2 import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users import repository as users
from app.modules.users.models import User
from app.modules.videos import service
from app.modules.videos.models import Video, VideoAccess, VideoStatus
from tests.interactions.conftest import meet_after
from tests.videos.factories import grant, make_user
from tests.videos.test_videos_api import (
    browser,
    edit,
    guest,
    handle_of,
    moderator,
    owner,
    share,
    signup,
    stranger,
    unshare,
    video_in,
)

__all__ = ["guest", "moderator", "owner", "stranger"]

LIMIT = 2  # SHARED_MAX in the `small_limit` tests: the rule is the same, with fewer rows
PARALLEL = 8  # below the DB pool size (15): each request holds a connection at the barrier


@pytest.fixture
async def friend(app: FastAPI, db: AsyncSession, client: AsyncClient) -> AsyncIterator[AsyncClient]:
    """A signed-in user to share with. After `db` and `client`: their resets would wipe it."""
    async with browser(app, "10.0.0.5") as other:
        await signup(other, "friend@example.com")
        yield other


@pytest.fixture
async def video(owner: AsyncClient, db: AsyncSession) -> Video:
    """The owner's private video, ready to watch."""
    return await video_in(owner, db, VideoStatus.READY)


@pytest.fixture
def small_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(service, "SHARED_MAX", LIMIT)


async def shared_with(client: AsyncClient, public_id: str) -> Response:
    return await client.get(f"/api/videos/{public_id}/access")


async def handles(client: AsyncClient, public_id: str) -> list[str]:
    response = await shared_with(client, public_id)
    assert response.status_code == 200, response.text
    return [person["handle"] for person in response.json()]


async def people(db: AsyncSession, count: int, prefix: str = "person") -> list[User]:
    return [await make_user(db, f"{prefix}{n:02d}") for n in range(count)]


async def grant_all(db: AsyncSession, video: Video, grantees: list[User]) -> None:
    for grantee in grantees:
        await grant(db, video.public_id, grantee.email)


async def stored(db: AsyncSession, video: Video) -> dict[UUID, datetime]:
    """When each grantee got access, as committed now."""
    query = select(VideoAccess.user_id, VideoAccess.created_at)
    rows = await db.execute(query.where(VideoAccess.video_id == video.id))
    return dict(rows.all())


# --- The list ---


async def test_owner_sees_nobody_before_sharing(owner: AsyncClient, video: Video) -> None:
    assert await handles(owner, video.public_id) == []


async def test_owner_sees_people_first_shared_first(
    owner: AsyncClient, db: AsyncSession, video: Video
) -> None:
    a, b, c = await people(db, 3)
    order = [c, a, b]  # not the signup order: user ids grow with it
    for person in order:
        assert (await share(owner, video.public_id, person.handle)).status_code == 204

    response = await shared_with(owner, video.public_id)

    assert response.status_code == 200
    granted = await stored(db, video)
    body = [
        item | {"shared_at": datetime.fromisoformat(item["shared_at"])} for item in response.json()
    ]
    assert body == [
        {"handle": p.handle, "name": p.handle, "avatar_url": None, "shared_at": granted[p.id]}
        for p in order
    ]


async def test_people_shared_with_at_once_are_listed_by_user_id(
    owner: AsyncClient, db: AsyncSession, video: Video
) -> None:
    people_ = await people(db, 3)
    # One transaction: now() gives all of them the same created_at.
    db.add_all([VideoAccess(video_id=video.id, user_id=p.id) for p in reversed(people_)])
    await db.commit()
    assert len(set((await stored(db, video)).values())) == 1

    by_id = sorted(people_, key=lambda p: p.id)
    assert await handles(owner, video.public_id) == [p.handle for p in by_id]


async def test_unsharing_takes_the_person_off_the_list(
    owner: AsyncClient, db: AsyncSession, video: Video
) -> None:
    a, b = await people(db, 2)
    await grant_all(db, video, [a, b])

    assert (await unshare(owner, video.public_id, a.handle)).status_code == 204

    assert await handles(owner, video.public_id) == [b.handle]


async def test_sharing_again_keeps_the_first_place(
    owner: AsyncClient, db: AsyncSession, video: Video
) -> None:
    a, b = await people(db, 2)
    await grant_all(db, video, [a, b])
    before = (await shared_with(owner, video.public_id)).json()

    assert (await share(owner, video.public_id, a.handle.upper())).status_code == 204

    assert (await shared_with(owner, video.public_id)).json() == before


async def test_the_list_stays_when_the_video_goes_public_and_back(
    owner: AsyncClient, db: AsyncSession, video: Video
) -> None:
    (a,) = await people(db, 1)
    await grant_all(db, video, [a])

    for visibility in ("public", "unlisted", "private"):
        assert (await edit(owner, video.public_id, {"visibility": visibility})).status_code == 200
        assert await handles(owner, video.public_id) == [a.handle]


async def test_only_the_owner_sees_who_a_video_is_shared_with(
    owner: AsyncClient,
    stranger: AsyncClient,
    friend: AsyncClient,
    moderator: AsyncClient,
    video: Video,
) -> None:
    assert (await share(owner, video.public_id, await handle_of(friend))).status_code == 204
    assert (await friend.get(f"/api/videos/{video.public_id}")).status_code == 200  # may watch

    for other in (stranger, friend, moderator):
        response = await shared_with(other, video.public_id)
        assert response.status_code == 404
        assert response.json() == {"detail": "Video not found"}


async def test_guest_gets_401_for_the_share_list(guest: AsyncClient, video: Video) -> None:
    assert (await shared_with(guest, video.public_id)).status_code == 401


@pytest.mark.parametrize(("public_id", "status"), [("A" * 11, 404), ("short", 422)])
async def test_share_list_of_an_unknown_or_malformed_video_id(
    owner: AsyncClient, public_id: str, status: int
) -> None:
    assert (await shared_with(owner, public_id)).status_code == status


# --- The limit ---


async def test_sharing_past_the_limit_is_refused_and_stores_nothing(
    owner: AsyncClient, db: AsyncSession, video: Video
) -> None:
    *crowd, newcomer = await people(db, service.SHARED_MAX + 1)
    await grant_all(db, video, crowd)

    response = await share(owner, video.public_id, newcomer.handle)

    assert response.status_code == 400
    assert response.json() == {"detail": "A video can be shared with up to 50 people"}
    assert set(await stored(db, video)) == {p.id for p in crowd}


@pytest.mark.usefixtures("small_limit")
async def test_sharing_again_at_the_limit_is_fine(
    owner: AsyncClient, db: AsyncSession, video: Video
) -> None:
    crowd = await people(db, LIMIT)
    await grant_all(db, video, crowd)

    assert (await share(owner, video.public_id, crowd[0].handle)).status_code == 204

    assert set(await stored(db, video)) == {p.id for p in crowd}


@pytest.mark.usefixtures("small_limit")
async def test_unsharing_at_the_limit_makes_room(
    owner: AsyncClient, db: AsyncSession, video: Video
) -> None:
    first, *rest, newcomer = await people(db, LIMIT + 1)
    await grant_all(db, video, [first, *rest])
    assert (await share(owner, video.public_id, newcomer.handle)).status_code == 400

    assert (await unshare(owner, video.public_id, first.handle)).status_code == 204

    assert (await share(owner, video.public_id, newcomer.handle)).status_code == 204
    assert await handles(owner, video.public_id) == [p.handle for p in [*rest, newcomer]]


@pytest.mark.usefixtures("small_limit")
async def test_the_limit_counts_each_video_alone(
    owner: AsyncClient, db: AsyncSession, video: Video
) -> None:
    crowd = await people(db, LIMIT)
    await grant_all(db, video, crowd)
    other = await video_in(owner, db, VideoStatus.READY)

    assert (await share(owner, other.public_id, crowd[0].handle)).status_code == 204


@pytest.mark.usefixtures("small_limit")
async def test_parallel_shares_for_the_last_place_let_one_in(
    owner: AsyncClient, db: AsyncSession, video: Video, monkeypatch: pytest.MonkeyPatch
) -> None:
    await grant_all(db, video, await people(db, LIMIT - 1, "old"))
    newcomers = await people(db, PARALLEL, "new")
    # After the handle lookup comes the video lock: all requests ask for it at once.
    meet_after(monkeypatch, users, "get_by_handle", PARALLEL)

    responses = await asyncio.gather(*(share(owner, video.public_id, p.handle) for p in newcomers))

    assert sorted(r.status_code for r in responses) == [204] + [400] * (PARALLEL - 1)
    assert len(await stored(db, video)) == LIMIT
