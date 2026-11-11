"""DB rules for playlists: they hold whatever the app does."""

import pytest
from sqlalchemy import delete, func, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.modules.playlists.models import MAX_VIDEOS, Playlist, PlaylistItem, PlaylistKind
from app.modules.users.models import User
from app.modules.videos.models import Video
from tests.videos.factories import make_user, make_video


async def make_playlist(db: AsyncSession, owner: User, **values: object) -> Playlist:
    playlist = Playlist(owner_id=owner.id, title="Watch list", **values)
    db.add(playlist)
    await db.commit()
    return playlist


async def items(db: AsyncSession, playlist: Playlist, count: int) -> list[Video]:
    owner = await db.get_one(User, playlist.owner_id)
    videos = [await make_video(db, owner) for _ in range(count)]
    db.add_all(
        PlaylistItem(playlist_id=playlist.id, video_id=video.id, position=number)
        for number, video in enumerate(videos)
    )
    await db.commit()
    return videos


async def test_defaults(db: AsyncSession) -> None:
    playlist = await make_playlist(db, await make_user(db, "anna"))

    assert playlist.id.version == 7
    assert (playlist.visibility.value, playlist.video_count, playlist.description) == (
        "private",
        0,
        "",
    )


@pytest.mark.parametrize("title", ["", "   ", "x" * 151])
async def test_title_length_is_checked(db: AsyncSession, title: str) -> None:
    db.add(Playlist(owner_id=(await make_user(db, "anna")).id, title=title))

    with pytest.raises(IntegrityError, match="ck_playlists_title_length"):
        await db.commit()


async def test_video_count_stays_in_range(db: AsyncSession) -> None:
    playlist = await make_playlist(db, await make_user(db, "anna"))

    with pytest.raises(IntegrityError, match="ck_playlists_video_count_range"):
        await db.execute(
            update(Playlist).where(Playlist.id == playlist.id).values(video_count=MAX_VIDEOS + 1)
        )


async def test_unknown_visibility_is_refused(db: AsyncSession) -> None:
    anna = await make_user(db, "anna")
    insert = text(
        "INSERT INTO playlists (owner_id, title, visibility) VALUES (:owner, 'x', 'friends')"
    )

    with pytest.raises(IntegrityError, match="ck_playlists_visibility"):
        await db.execute(insert, {"owner": anna.id})


async def test_a_video_is_in_a_playlist_once(db: AsyncSession) -> None:
    playlist = await make_playlist(db, await make_user(db, "anna"))
    [video] = await items(db, playlist, 1)
    db.add(PlaylistItem(playlist_id=playlist.id, video_id=video.id, position=5))

    with pytest.raises(IntegrityError, match="pk_playlist_items"):
        await db.commit()


async def test_two_items_cant_share_a_position(db: AsyncSession) -> None:
    playlist = await make_playlist(db, await make_user(db, "anna"))
    first, _ = await items(db, playlist, 2)

    with pytest.raises(IntegrityError, match="uq_playlist_items_playlist_id_position"):
        await db.execute(
            update(PlaylistItem)
            .where(PlaylistItem.playlist_id == playlist.id, PlaylistItem.video_id == first.id)
            .values(position=1)
        )


async def test_one_statement_can_shift_a_range_of_positions(db: AsyncSession) -> None:
    """The deferrable constraint is checked at the end of the statement, not row by row:
    shifting 0, 1, 2 to 1, 2, 3 passes whatever order the rows are updated in."""
    playlist = await make_playlist(db, await make_user(db, "anna"))
    await items(db, playlist, 3)

    await db.execute(
        update(PlaylistItem)
        .where(PlaylistItem.playlist_id == playlist.id)
        .values(position=PlaylistItem.position + 1)
    )
    await db.commit()

    positions = await db.scalars(
        select(PlaylistItem.position).where(PlaylistItem.playlist_id == playlist.id)
    )
    assert sorted(positions) == [1, 2, 3]


async def test_position_is_never_negative(db: AsyncSession) -> None:
    playlist = await make_playlist(db, await make_user(db, "anna"))
    video = await make_video(db, await make_user(db, "bob"))
    db.add(PlaylistItem(playlist_id=playlist.id, video_id=video.id, position=-1))

    with pytest.raises(IntegrityError, match="ck_playlist_items_position_not_negative"):
        await db.commit()


async def test_deletes_cascade(db: AsyncSession, admin_engine: AsyncEngine) -> None:
    anna = await make_user(db, "anna")
    kept, gone = await make_playlist(db, anna), await make_playlist(db, anna)
    videos = await items(db, kept, 2)
    await items(db, gone, 1)

    # The superuser: no feature deletes videos yet.
    async with admin_engine.begin() as conn:
        await conn.execute(delete(Playlist).where(Playlist.id == gone.id))
        await conn.execute(delete(Video).where(Video.id == videos[0].id))

    rows = (await db.execute(select(PlaylistItem.playlist_id, PlaylistItem.video_id))).all()
    assert rows == [(kept.id, videos[1].id)]
    users = select(func.count()).select_from(Playlist).where(Playlist.kind == PlaylistKind.USER)
    assert await db.scalar(users) == 1
