"""GET /api/me/subscriptions: the channels the viewer subscribed to, A to Z."""

import pytest
from httpx2 import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import encode_cursor
from app.modules.channels.models import Subscription
from app.modules.channels.service import SUBSCRIPTIONS_PAGE_SIZE
from tests.interactions.conftest import VIEWER_EMAIL, csrf, user_by_email
from tests.videos.factories import make_user

URL = "/api/me/subscriptions"


async def handles(client: AsyncClient, cursor: str | None = None) -> tuple[list[str], str | None]:
    response = await client.get(URL, params={"cursor": cursor} if cursor else {})
    assert response.status_code == 200
    body = response.json()
    return [item["handle"] for item in body["items"]], body["next_cursor"]


async def test_guest_must_sign_in(guest: AsyncClient) -> None:
    response = await guest.get(URL)

    assert response.status_code == 401


async def test_no_subscriptions(viewer: AsyncClient) -> None:
    assert await handles(viewer) == ([], None)


async def test_lists_subscribed_channels_a_to_z_with_their_counts(
    viewer: AsyncClient, db: AsyncSession
) -> None:
    for name in ("carl", "anna", "bob", "dora"):
        await make_user(db, name)
    for name in ("carl", "anna", "bob"):
        await viewer.put(f"/api/channels/{name}/subscription", headers=csrf(viewer))
    await viewer.delete("/api/channels/bob/subscription", headers=csrf(viewer))

    response = await viewer.get(URL)

    assert response.json() == {
        "items": [
            {"handle": "anna", "name": "anna", "avatar_url": None, "subscriber_count": 1},
            {"handle": "carl", "name": "carl", "avatar_url": None, "subscriber_count": 1},
        ],
        "next_cursor": None,
    }


async def test_only_the_viewers_own_subscriptions(
    viewer: AsyncClient, owner: AsyncClient, db: AsyncSession
) -> None:
    await make_user(db, "anna")
    await owner.put("/api/channels/anna/subscription", headers=csrf(owner))

    assert await handles(viewer) == ([], None)


async def test_pages_have_no_gaps_or_repeats(viewer: AsyncClient, db: AsyncSession) -> None:
    me = await user_by_email(db, VIEWER_EMAIL)
    names = [f"channel{number:03}" for number in range(SUBSCRIPTIONS_PAGE_SIZE + 3)]
    for name in names:
        # Straight to the DB: subscribing by API this often hits the rate limit.
        db.add(Subscription(subscriber_id=me.id, channel_id=(await make_user(db, name)).id))
    await db.commit()

    first, cursor = await handles(viewer)
    rest, last = await handles(viewer, cursor)

    assert len(first) == SUBSCRIPTIONS_PAGE_SIZE
    assert first + rest == names
    assert last is None


@pytest.mark.parametrize(
    "cursor", [encode_cursor(("bad handle",)), encode_cursor(("a\x00b",)), encode_cursor((1,))]
)
async def test_bad_cursor_is_refused(viewer: AsyncClient, cursor: str) -> None:
    response = await viewer.get(URL, params={"cursor": cursor})

    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid cursor"}
