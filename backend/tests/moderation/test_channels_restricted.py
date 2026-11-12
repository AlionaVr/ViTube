"""Channels, subscriptions and playlists under moderation (ADR 0009): a terminated channel is gone
for all but moderators and frozen for everyone; a restricted video drops out of playlists."""

import pytest
from httpx2 import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.videos.models import Video
from tests.interactions.conftest import csrf
from tests.moderation.conftest import OWNER_EMAIL, hide_directly, set_status
from tests.moderation.test_accounts import handle_of
from tests.playlists.conftest import add, create, item_ids


async def subscribe(client: AsyncClient, handle: str, method: str = "PUT") -> int:
    response = await client.request(
        method, f"/api/channels/{handle}/subscription", headers=csrf(client)
    )
    return response.status_code


async def subscriptions(client: AsyncClient) -> list[str]:
    items = (await client.get("/api/me/subscriptions")).json()["items"]
    return [item["handle"] for item in items]


async def test_a_terminated_channel_opens_only_for_staff(
    admin: AsyncClient,
    owner: AsyncClient,
    viewer: AsyncClient,
    guest: AsyncClient,
    moderator: AsyncClient,
    db: AsyncSession,
    video: Video,
) -> None:
    handle = await handle_of(db, OWNER_EMAIL)
    playlist = await create(owner, "Mix", visibility="public")
    assert (await add(owner, playlist, video)).status_code == 204
    paths = [
        f"/api/channels/{handle}",
        f"/api/channels/{handle}/videos",
        f"/api/channels/{handle}/playlists",
        f"/api/playlists/{playlist}",
        f"/api/playlists/{playlist}/items",
    ]

    assert (await set_status(admin, handle, "terminated")).status_code == 204

    for outsider in (viewer, guest):
        assert [(await outsider.get(path)).status_code for path in paths] == [404] * len(paths)
    for staff in (moderator, admin):
        assert [(await staff.get(path)).status_code for path in paths] == [200] * len(paths)
    # Staff open it to review it, but public lists leave its videos out for everyone.
    assert (await moderator.get(f"/api/channels/{handle}/videos")).json()["items"] == []
    assert (await moderator.get(f"/api/channels/{handle}")).json()["is_terminated"] is True

    assert (await set_status(admin, handle, "active")).status_code == 204
    assert [(await viewer.get(path)).status_code for path in paths] == [200] * len(paths)
    assert (await moderator.get(f"/api/channels/{handle}")).json()["is_terminated"] is False


async def test_a_banned_channel_stays_open(
    admin: AsyncClient, owner: AsyncClient, guest: AsyncClient, db: AsyncSession, video: Video
) -> None:
    handle = await handle_of(db, OWNER_EMAIL)

    assert (await set_status(admin, handle, "banned")).status_code == 204

    channel = await guest.get(f"/api/channels/{handle}")
    assert channel.status_code == 200
    assert channel.json()["is_terminated"] is False  # the API doesn't tell a ban
    videos = (await guest.get(f"/api/channels/{handle}/videos")).json()["items"]
    assert [item["id"] for item in videos] == [video.public_id]


async def test_subscriptions_to_a_terminated_channel_are_kept_and_frozen(
    admin: AsyncClient,
    owner: AsyncClient,
    viewer: AsyncClient,
    moderator: AsyncClient,
    db: AsyncSession,
) -> None:
    handle = await handle_of(db, OWNER_EMAIL)
    assert await subscribe(viewer, handle) == 200

    assert (await set_status(admin, handle, "terminated")).status_code == 204

    assert await subscriptions(viewer) == []
    assert await subscribe(viewer, handle, "DELETE") == 404
    assert await subscribe(moderator, handle) == 404  # frozen for staff too, as its videos

    assert (await set_status(admin, handle, "active")).status_code == 204
    assert await subscriptions(viewer) == [handle]
    channel = (await viewer.get(f"/api/channels/{handle}")).json()
    assert (channel["subscriber_count"], channel["is_subscribed"]) == (1, True)


@pytest.mark.parametrize("restriction", ["hidden", "terminated"])
async def test_a_playlist_leaves_out_a_restricted_video_for_all_but_staff(
    restriction: str,
    admin: AsyncClient,
    owner: AsyncClient,
    viewer: AsyncClient,
    guest: AsyncClient,
    moderator: AsyncClient,
    db: AsyncSession,
    video: Video,
) -> None:
    """The viewer's playlist holds the owner's video: only the owner's channel is restricted."""
    playlist = await create(viewer, "Saved", visibility="public")
    assert (await add(viewer, playlist, video)).status_code == 204

    if restriction == "hidden":
        await hide_directly(db, video)
    else:
        await set_status(admin, await handle_of(db, OWNER_EMAIL), "terminated")

    assert await item_ids(viewer, playlist) == []  # its own playlist, someone else's video
    assert await item_ids(guest, playlist) == []
    assert await item_ids(moderator, playlist) == [video.public_id]
