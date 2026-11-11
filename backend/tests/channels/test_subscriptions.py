"""PUT/DELETE /api/channels/{handle}/subscription: repeated and parallel requests.

Invariant: users.subscriber_count = COUNT(*) of the channel's subscriptions after every commit.
"""

import asyncio
from collections.abc import Awaitable, Callable
from uuid import UUID

import pytest
from httpx2 import AsyncClient, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limit import RateLimit
from app.modules.channels import service
from app.modules.channels.models import Subscription
from app.modules.users import repository as users
from app.modules.users.models import User
from tests.interactions.conftest import OWNER_EMAIL, VIEWER_EMAIL, MakeViewers, csrf, meet_after
from tests.interactions.conftest import user_by_email as user_of
from tests.videos.factories import make_user

PARALLEL = 8  # below the DB pool size (15): each request holds a connection at the barrier

type Send = Callable[[AsyncClient, str], Awaitable[Response]]


async def subscribe(client: AsyncClient, handle: str) -> Response:
    return await client.put(f"/api/channels/{handle}/subscription", headers=csrf(client))


async def unsubscribe(client: AsyncClient, handle: str) -> Response:
    return await client.delete(f"/api/channels/{handle}/subscription", headers=csrf(client))


async def stored(db: AsyncSession, channel_id: UUID) -> tuple[int, int]:
    """(subscriber_count, rows) as committed now."""
    count = await db.scalar(select(User.subscriber_count).where(User.id == channel_id))
    rows = await db.scalar(
        select(func.count()).select_from(Subscription).where(Subscription.channel_id == channel_id)
    )
    assert count is not None and rows is not None
    return count, rows


@pytest.fixture
async def channel(db: AsyncSession) -> User:
    return await make_user(db, "anna")


@pytest.fixture
def together(monkeypatch: pytest.MonkeyPatch) -> Callable[[], None]:
    """Parallel requests wait for each other after the channel lookup, so all of them reach the
    INSERT or DELETE at once: the race happens every run."""
    return lambda: meet_after(monkeypatch, users, "get_by_handle", PARALLEL)


async def test_subscribe_and_unsubscribe(
    viewer: AsyncClient, channel: User, db: AsyncSession
) -> None:
    response = await subscribe(viewer, "anna")

    assert response.status_code == 200
    assert response.json() == {"subscriber_count": 1, "is_subscribed": True}
    assert await stored(db, channel.id) == (1, 1)

    response = await unsubscribe(viewer, "anna")

    assert response.status_code == 200
    assert response.json() == {"subscriber_count": 0, "is_subscribed": False}
    assert await stored(db, channel.id) == (0, 0)


async def test_repeated_subscribe_counts_once(
    viewer: AsyncClient, channel: User, db: AsyncSession
) -> None:
    responses = [await subscribe(viewer, "anna") for _ in range(3)]

    assert [r.json() for r in responses] == [{"subscriber_count": 1, "is_subscribed": True}] * 3
    assert await stored(db, channel.id) == (1, 1)


async def test_repeated_unsubscribe_takes_one_off(
    viewer: AsyncClient, channel: User, db: AsyncSession
) -> None:
    await subscribe(viewer, "anna")

    responses = [await unsubscribe(viewer, "anna") for _ in range(3)]

    assert [r.json() for r in responses] == [{"subscriber_count": 0, "is_subscribed": False}] * 3
    assert await stored(db, channel.id) == (0, 0)


async def test_unsubscribe_without_a_subscription_changes_nothing(
    viewer: AsyncClient, channel: User, db: AsyncSession
) -> None:
    other = (await make_user(db, "carl")).id
    await subscribe(viewer, "carl")

    response = await unsubscribe(viewer, "anna")

    assert response.json() == {"subscriber_count": 0, "is_subscribed": False}
    assert await stored(db, channel.id) == (0, 0)
    assert await stored(db, other) == (1, 1)


async def test_handle_ignores_case(viewer: AsyncClient, channel: User, db: AsyncSession) -> None:
    await subscribe(viewer, "ANNA")

    assert await stored(db, channel.id) == (1, 1)


@pytest.mark.parametrize("send", [subscribe, unsubscribe])
async def test_own_channel_is_refused(owner: AsyncClient, db: AsyncSession, send: Send) -> None:
    anna = await user_of(db, OWNER_EMAIL)

    response = await send(owner, anna.handle)

    assert response.status_code == 400
    assert response.json() == {"detail": "You can't subscribe to your own channel"}
    assert await stored(db, anna.id) == (0, 0)


@pytest.mark.parametrize("send", [subscribe, unsubscribe])
async def test_guest_must_sign_in(
    guest: AsyncClient, channel: User, db: AsyncSession, send: Send
) -> None:
    response = await send(guest, "anna")

    assert response.status_code == 401
    assert await stored(db, channel.id) == (0, 0)


async def test_unknown_channel_is_not_found(viewer: AsyncClient, db: AsyncSession) -> None:
    response = await subscribe(viewer, "nobody")

    assert response.status_code == 404
    assert response.json() == {"detail": "Channel not found"}


async def test_request_without_csrf_token_is_refused(
    viewer: AsyncClient, channel: User, db: AsyncSession
) -> None:
    response = await viewer.put("/api/channels/anna/subscription")

    assert response.status_code == 403
    assert await stored(db, channel.id) == (0, 0)


async def test_subscriptions_are_rate_limited_per_account(
    viewer: AsyncClient,
    channel: User,
    db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(service, "SUBSCRIPTIONS_PER_USER", RateLimit("subscription", 2, 60))
    await subscribe(viewer, "anna")
    await unsubscribe(viewer, "anna")

    response = await subscribe(viewer, "anna")

    assert response.status_code == 429
    assert await stored(db, channel.id) == (0, 0)


# --- Parallel requests ---


async def test_parallel_subscribes_of_one_user_count_once(
    viewer: AsyncClient, channel: User, db: AsyncSession, together: Callable[[], None]
) -> None:
    together()
    responses = await asyncio.gather(*(subscribe(viewer, "anna") for _ in range(PARALLEL)))

    # Each answer waited for the one that inserted, so all of them report the committed count.
    assert [r.json() for r in responses] == [
        {"subscriber_count": 1, "is_subscribed": True}
    ] * PARALLEL
    assert await stored(db, channel.id) == (1, 1)


async def test_parallel_unsubscribes_of_one_user_take_one_off(
    viewer: AsyncClient, channel: User, db: AsyncSession, together: Callable[[], None]
) -> None:
    await subscribe(viewer, "anna")

    together()
    responses = await asyncio.gather(*(unsubscribe(viewer, "anna") for _ in range(PARALLEL)))

    assert [r.status_code for r in responses] == [200] * PARALLEL
    assert await stored(db, channel.id) == (0, 0)


async def test_parallel_subscribes_and_unsubscribes_keep_the_count_exact(
    viewer: AsyncClient, channel: User, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    for start in (subscribe, unsubscribe, subscribe, unsubscribe):
        await start(viewer, "anna")
        meet_after(monkeypatch, users, "get_by_handle", PARALLEL)
        sends = [subscribe, unsubscribe] * (PARALLEL // 2)

        responses = await asyncio.gather(*(send(viewer, "anna") for send in sends))

        assert [r.status_code for r in responses] == [200] * PARALLEL
        count, rows = await stored(db, channel.id)
        assert count == rows  # whichever request came last decides; the count follows it
        assert rows <= 1
        monkeypatch.undo()


async def test_parallel_subscribes_of_many_users_all_count(
    make_viewers: MakeViewers, channel: User, db: AsyncSession, together: Callable[[], None]
) -> None:
    viewers = await make_viewers(PARALLEL)

    together()
    responses = await asyncio.gather(*(subscribe(client, "anna") for client in viewers))

    assert [r.status_code for r in responses] == [200] * PARALLEL
    assert sorted(r.json()["subscriber_count"] for r in responses) == list(range(1, PARALLEL + 1))
    assert await stored(db, channel.id) == (PARALLEL, PARALLEL)


async def test_two_users_subscribing_to_each_other_at_once_do_not_deadlock(
    owner: AsyncClient, viewer: AsyncClient, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    anna, bob = await user_of(db, OWNER_EMAIL), await user_of(db, VIEWER_EMAIL)
    meet_after(monkeypatch, users, "get_by_handle", 2)

    responses = await asyncio.gather(subscribe(owner, bob.handle), subscribe(viewer, anna.handle))

    assert [r.status_code for r in responses] == [200, 200]
    assert await stored(db, anna.id) == (1, 1)
    assert await stored(db, bob.id) == (1, 1)
