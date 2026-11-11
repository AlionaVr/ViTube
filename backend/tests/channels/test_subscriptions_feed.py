"""GET /api/feed/subscriptions: new public videos of the channels the viewer subscribed to."""

from httpx2 import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.channels.models import Subscription
from app.modules.videos.models import VideoStatus, Visibility
from app.modules.videos.service import FEED_PAGE_SIZE
from tests.interactions.conftest import VIEWER_EMAIL, csrf, user_by_email
from tests.videos.factories import make_user, make_video

URL = "/api/feed/subscriptions"


async def feed(client: AsyncClient, cursor: str | None = None) -> tuple[list[str], str | None]:
    response = await client.get(URL, params={"cursor": cursor} if cursor else {})
    assert response.status_code == 200
    body = response.json()
    return [item["id"] for item in body["items"]], body["next_cursor"]


async def test_guest_must_sign_in(guest: AsyncClient) -> None:
    assert (await guest.get(URL)).status_code == 401


async def test_new_public_videos_of_subscribed_channels_newest_first(
    viewer: AsyncClient, db: AsyncSession
) -> None:
    anna, bob, carl = [await make_user(db, name) for name in ("anna", "bob", "carl")]
    for channel in ("anna", "bob"):
        await viewer.put(f"/api/channels/{channel}/subscription", headers=csrf(viewer))
    first = await make_video(db, anna)
    second = await make_video(db, bob)
    third = await make_video(db, anna)
    await make_video(db, carl)  # not subscribed
    for visibility in (Visibility.UNLISTED, Visibility.PRIVATE):
        await make_video(db, anna, visibility=visibility)
    await make_video(db, anna, status=VideoStatus.PROCESSING)

    ids, cursor = await feed(viewer)

    assert ids == [third.public_id, second.public_id, first.public_id]
    assert cursor is None


async def test_unsubscribing_takes_the_channel_out(viewer: AsyncClient, db: AsyncSession) -> None:
    await make_video(db, await make_user(db, "anna"))
    await viewer.put("/api/channels/anna/subscription", headers=csrf(viewer))
    await viewer.delete("/api/channels/anna/subscription", headers=csrf(viewer))

    assert await feed(viewer) == ([], None)


async def test_pages_have_no_gaps_or_repeats(viewer: AsyncClient, db: AsyncSession) -> None:
    me = await user_by_email(db, VIEWER_EMAIL)
    anna = await make_user(db, "anna")
    db.add(Subscription(subscriber_id=me.id, channel_id=anna.id))
    await db.commit()
    videos = [await make_video(db, anna) for _ in range(FEED_PAGE_SIZE + 2)]

    first, cursor = await feed(viewer)
    rest, last = await feed(viewer, cursor)

    assert len(first) == FEED_PAGE_SIZE
    assert first + rest == [video.public_id for video in reversed(videos)]
    assert last is None


async def test_bad_cursor_is_refused(viewer: AsyncClient) -> None:
    response = await viewer.get(URL, params={"cursor": "bm90IGEgY3Vyc29y"})

    assert response.status_code == 400
