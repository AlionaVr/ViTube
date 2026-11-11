"""Watch later: every user has exactly one, private, from the moment their row exists."""

import pytest
from httpx2 import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import encode_cursor
from app.modules.playlists import service
from app.modules.playlists.models import WATCH_LATER_TITLE, Playlist, PlaylistKind
from app.modules.users.models import User
from app.modules.videos.models import Visibility
from tests.interactions.conftest import OWNER_EMAIL, user_by_email
from tests.playlists.conftest import add, create, item_ids, remove
from tests.videos.factories import make_user, make_video


async def watch_laters(db: AsyncSession, user: User) -> list[Playlist]:
    query = select(Playlist).where(
        Playlist.owner_id == user.id, Playlist.kind == PlaylistKind.WATCH_LATER
    )
    return list(await db.scalars(query))


async def test_every_new_user_gets_one(db: AsyncSession) -> None:
    anna = await make_user(db, "anna")  # straight to the DB, not through sign-up

    [watch_later] = await watch_laters(db, anna)

    assert watch_later.title == WATCH_LATER_TITLE
    assert watch_later.visibility is Visibility.PRIVATE
    assert watch_later.video_count == 0


async def test_signing_up_gives_one(owner: AsyncClient, db: AsyncSession) -> None:
    assert len(await watch_laters(db, await user_by_email(db, OWNER_EMAIL))) == 1


async def test_a_second_one_is_refused(db: AsyncSession) -> None:
    anna = await make_user(db, "anna")
    db.add(Playlist(owner_id=anna.id, title="Later", kind=PlaylistKind.WATCH_LATER))

    with pytest.raises(IntegrityError, match="uq_playlists_owner_id_watch_later"):
        await db.commit()


async def test_it_stays_private(db: AsyncSession) -> None:
    [watch_later] = await watch_laters(db, await make_user(db, "anna"))
    watch_later.visibility = Visibility.PUBLIC

    with pytest.raises(IntegrityError, match="ck_playlists_watch_later_private"):
        await db.commit()


async def test_unknown_kind_is_refused(db: AsyncSession) -> None:
    db.add(Playlist(owner_id=(await make_user(db, "anna")).id, title="x"))
    await db.commit()

    # Raw SQL: the Python enum would refuse the value before it reaches the DB.
    with pytest.raises(IntegrityError, match="ck_playlists_kind"):
        await db.execute(text("UPDATE playlists SET kind = 'favorites'"))


async def test_the_api_returns_your_own(owner: AsyncClient, guest: AsyncClient) -> None:
    response = await owner.get("/api/me/watch-later")

    assert response.status_code == 200
    body = response.json()
    assert (body["title"], body["kind"], body["visibility"]) == (
        "Watch later",
        "watch_later",
        "private",
    )
    assert (await guest.get("/api/me/watch-later")).status_code == 401
    # Opened by its id like any playlist, and private like any private one.
    assert (await owner.get(f"/api/playlists/{body['id']}")).status_code == 200
    assert (await guest.get(f"/api/playlists/{body['id']}")).status_code == 404


async def test_videos_are_saved_to_it_like_to_any_playlist(
    owner: AsyncClient, db: AsyncSession
) -> None:
    watch_later = (await owner.get("/api/me/watch-later")).json()["id"]
    video = await make_video(db, await make_user(db, "bob"))

    assert (await add(owner, watch_later, video)).status_code == 204

    assert await item_ids(owner, watch_later) == [video.public_id]
    assert (await owner.get("/api/me/watch-later")).json()["video_count"] == 1


async def test_it_comes_first_on_every_page_order(
    owner: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(service, "MINE_PAGE_SIZE", 2)
    newest = [await create(owner, f"List {n}") for n in range(3)][::-1]
    watch_later = (await owner.get("/api/me/watch-later")).json()["id"]

    first = (await owner.get("/api/me/playlists")).json()
    second = (await owner.get("/api/me/playlists", params={"cursor": first["next_cursor"]})).json()

    ids = [item["id"] for item in first["items"] + second["items"]]
    assert ids == [watch_later, *newest]
    assert second["next_cursor"] is None


async def test_bad_cursor_is_refused(owner: AsyncClient) -> None:
    response = await owner.get(
        "/api/me/playlists", params={"cursor": encode_cursor(("not a uuid",))}
    )

    assert response.status_code == 400


# --- Saved anywhere ---


async def saved(client: AsyncClient, public_id: str) -> object:
    response = await client.get(f"/api/videos/{public_id}/saved")
    assert response.status_code == 200, response.text
    return response.json()["saved"]


async def test_saved_is_true_while_the_video_is_in_any_own_playlist(
    owner: AsyncClient, viewer: AsyncClient, db: AsyncSession
) -> None:
    video = await make_video(db, await make_user(db, "bob"))
    watch_later = (await owner.get("/api/me/watch-later")).json()["id"]
    mine = await create(owner)
    assert await saved(owner, video.public_id) is False

    await add(owner, watch_later, video)
    await add(owner, mine, video)
    assert await saved(owner, video.public_id) is True
    assert await saved(viewer, video.public_id) is False  # someone else's playlists don't count

    await remove(owner, watch_later, video)
    assert await saved(owner, video.public_id) is True
    await remove(owner, mine, video)
    assert await saved(owner, video.public_id) is False


async def test_saved_needs_a_user_and_a_valid_id(owner: AsyncClient, guest: AsyncClient) -> None:
    assert await saved(owner, "nosuchvide0") is False
    assert (await guest.get("/api/videos/nosuchvide0/saved")).status_code == 401
    assert (await owner.get("/api/videos/bad/saved")).status_code == 422
