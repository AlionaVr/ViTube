"""GET /api/channels/{handle}: the channel page header."""

from datetime import datetime

import pytest
from httpx2 import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.models import User
from app.modules.videos.models import VideoStatus, Visibility
from tests.interactions.conftest import OWNER_EMAIL, VIEWER_EMAIL, csrf, user_by_email
from tests.videos.factories import make_user, make_video


async def test_guest_sees_the_channel(client: AsyncClient, db: AsyncSession) -> None:
    anna = await make_user(db, "anna")

    response = await client.get("/api/channels/anna")

    assert response.status_code == 200
    body = response.json()
    assert datetime.fromisoformat(body.pop("joined_at")) == anna.created_at
    assert body == {
        "handle": "anna",
        "name": "anna",
        "avatar_url": None,
        "subscriber_count": 0,
        "video_count": 0,
        "is_subscribed": False,
        "is_terminated": False,
    }


async def test_handle_ignores_case(client: AsyncClient, db: AsyncSession) -> None:
    await make_user(db, "anna")

    response = await client.get("/api/channels/AnNa")

    assert response.status_code == 200
    assert response.json()["handle"] == "anna"


async def test_unknown_channel_is_not_found(client: AsyncClient, db: AsyncSession) -> None:
    response = await client.get("/api/channels/nobody")

    assert response.status_code == 404
    assert response.json() == {"detail": "Channel not found"}


@pytest.mark.parametrize("handle", ["ab", "x" * 31, "@anna", "an na"])
async def test_malformed_handle_is_refused(client: AsyncClient, handle: str) -> None:
    response = await client.get(f"/api/channels/{handle}")

    assert response.status_code == 422


async def test_video_count_is_what_everyone_may_see_in_lists(
    owner: AsyncClient, guest: AsyncClient, db: AsyncSession
) -> None:
    anna = await user_by_email(db, OWNER_EMAIL)
    for _ in range(2):
        await make_video(db, anna)
    for visibility in (Visibility.UNLISTED, Visibility.PRIVATE):
        await make_video(db, anna, visibility=visibility)
    for status in (VideoStatus.PROCESSING, VideoStatus.FAILED):
        await make_video(db, anna, status=status)
    await make_video(db, await make_user(db, "bob"))  # another channel's
    url = f"/api/channels/{anna.handle}"

    # The owner sees the same count: the channel page shows the channel's public face.
    assert (await guest.get(url)).json()["video_count"] == 2
    assert (await owner.get(url)).json()["video_count"] == 2


async def test_is_subscribed_for_a_subscriber_but_not_on_your_own_channel(
    owner: AsyncClient, viewer: AsyncClient, db: AsyncSession
) -> None:
    anna = await user_by_email(db, OWNER_EMAIL)
    bob = await user_by_email(db, VIEWER_EMAIL)
    url = f"/api/channels/{anna.handle}"
    assert (await viewer.put(f"{url}/subscription", headers=csrf(viewer))).status_code == 200

    assert (await viewer.get(url)).json()["is_subscribed"] is True
    assert (await owner.get(url)).json()["is_subscribed"] is False
    assert (await owner.get(f"/api/channels/{bob.handle}")).json()["is_subscribed"] is False


async def test_counts_come_from_the_db_each_time(
    client: AsyncClient, viewer: AsyncClient, db: AsyncSession
) -> None:
    anna: User = await make_user(db, "anna")
    await viewer.put("/api/channels/anna/subscription", headers=csrf(viewer))
    await make_video(db, anna)

    body = (await client.get("/api/channels/anna")).json()

    assert (body["subscriber_count"], body["video_count"]) == (1, 1)
