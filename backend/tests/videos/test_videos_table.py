import pytest
from sqlalchemy import delete, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.models import User
from app.modules.videos.models import Video, VideoAccess, VideoStatus, Visibility
from tests.videos.factories import make_user, make_video


async def test_db_fills_defaults(db: AsyncSession) -> None:
    owner = await make_user(db, "anna")
    video = Video(public_id="abcdefghijk", owner_id=owner.id, title="Hello")
    db.add(video)
    await db.commit()

    assert video.id.version == 7
    assert video.visibility is Visibility.PRIVATE  # safe default for API clients
    assert video.status is VideoStatus.UPLOADING
    assert video.description == ""
    assert (video.view_count, video.like_count, video.comment_count) == (0, 0, 0)
    assert video.processing_attempts == 0
    assert video.duration_sec is None
    assert video.created_at is not None
    assert video.status_changed_at is not None


async def test_object_keys_come_from_the_id(db: AsyncSession) -> None:
    video = await make_video(db, await make_user(db, "anna"))

    assert video.original_key == f"originals/{video.id}"
    assert video.media_key == f"videos/{video.id}/720p.mp4"
    assert video.thumbnail_key == f"thumbs/{video.id}.jpg"


async def test_public_id_is_unique(db: AsyncSession) -> None:
    owner = await make_user(db, "anna")
    db.add(Video(public_id="abcdefghijk", owner_id=owner.id, title="One"))
    await db.commit()
    db.add(Video(public_id="abcdefghijk", owner_id=owner.id, title="Two"))

    with pytest.raises(IntegrityError, match="uq_videos_public_id"):
        await db.commit()


# Longer ids are refused by varchar(11) itself.
@pytest.mark.parametrize("public_id", ["short", "abc defghij", "abcdefghij!", "abcdefghij/"])
async def test_public_id_format_is_checked(db: AsyncSession, public_id: str) -> None:
    owner = await make_user(db, "anna")
    db.add(Video(public_id=public_id, owner_id=owner.id, title="Hello"))

    with pytest.raises(IntegrityError, match="ck_videos_public_id_format"):
        await db.commit()


@pytest.mark.parametrize(
    ("column", "value", "constraint"),
    [
        ("title", "", "ck_videos_title_length"),
        ("title", "   ", "ck_videos_title_length"),
        ("title", "x" * 101, "ck_videos_title_length"),
        ("description", "x" * 5001, "ck_videos_description_length"),
        ("duration_sec", -1, "ck_videos_duration_sec_not_negative"),
        ("processing_attempts", -1, "ck_videos_processing_attempts_not_negative"),
        ("view_count", -1, "ck_videos_counters_not_negative"),
        ("like_count", -1, "ck_videos_counters_not_negative"),
        ("comment_count", -1, "ck_videos_counters_not_negative"),
    ],
)
async def test_column_limits_are_checked(
    db: AsyncSession, column: str, value: object, constraint: str
) -> None:
    video = await make_video(db, await make_user(db, "anna"))

    with pytest.raises(IntegrityError, match=constraint):
        await db.execute(update(Video).where(Video.id == video.id).values({column: value}))


async def test_a_ready_video_needs_a_duration(db: AsyncSession) -> None:
    video = await make_video(db, await make_user(db, "anna"), status=VideoStatus.PROCESSING)

    with pytest.raises(IntegrityError, match="ck_videos_ready_has_duration"):
        await db.execute(update(Video).where(Video.id == video.id).values(status=VideoStatus.READY))


@pytest.mark.parametrize(
    ("status", "error_message"),
    [(VideoStatus.FAILED, None), (VideoStatus.UPLOADED, "Not a video")],
)
async def test_exactly_failed_videos_have_an_error_message(
    db: AsyncSession, status: VideoStatus, error_message: str | None
) -> None:
    video = await make_video(db, await make_user(db, "anna"), status=VideoStatus.PROCESSING)
    values = {"status": status, "error_message": error_message}

    with pytest.raises(IntegrityError, match="ck_videos_error_message_iff_failed"):
        await db.execute(update(Video).where(Video.id == video.id).values(values))


async def test_error_message_length_is_checked(db: AsyncSession) -> None:
    video = await make_video(db, await make_user(db, "anna"), status=VideoStatus.FAILED)

    with pytest.raises(IntegrityError, match="ck_videos_error_message_length"):
        await db.execute(update(Video).where(Video.id == video.id).values(error_message="x" * 1001))


async def test_a_status_change_stamps_status_changed_at(db: AsyncSession) -> None:
    video = await make_video(db, await make_user(db, "anna"), status=VideoStatus.UPLOADED)
    stamped = video.status_changed_at

    video.status = VideoStatus.PROCESSING  # a new transaction: now() is later
    await db.commit()
    await db.refresh(video)

    assert video.status_changed_at > stamped


async def test_other_changes_keep_status_changed_at(db: AsyncSession) -> None:
    video = await make_video(db, await make_user(db, "anna"), status=VideoStatus.UPLOADED)
    stamped = video.status_changed_at

    # A title edit, and a write of the same status.
    await db.execute(
        update(Video)
        .where(Video.id == video.id)
        .values(title="New title", status=VideoStatus.UPLOADED)
    )
    await db.commit()
    await db.refresh(video)

    assert video.status_changed_at == stamped


# alembic check doesn't compare CHECK constraints: these catch a new value without a migration.
@pytest.mark.parametrize("status", list(VideoStatus))
async def test_db_accepts_every_status(db: AsyncSession, status: VideoStatus) -> None:
    await make_video(db, await make_user(db, "anna"), status=status)


@pytest.mark.parametrize("visibility", list(Visibility))
async def test_db_accepts_every_visibility(db: AsyncSession, visibility: Visibility) -> None:
    await make_video(db, await make_user(db, "anna"), visibility=visibility)


@pytest.mark.parametrize(
    ("column", "constraint"),
    [("status", "ck_videos_status"), ("visibility", "ck_videos_visibility")],
)
async def test_unknown_enum_values_are_rejected(
    db: AsyncSession, column: str, constraint: str
) -> None:
    video = await make_video(db, await make_user(db, "anna"))
    # Raw SQL: the Python enum would reject the value before it reaches the DB.
    statement = text(f"UPDATE videos SET {column} = 'deleted' WHERE id = :id")  # noqa: S608 fixed names

    with pytest.raises(IntegrityError, match=constraint):
        await db.execute(statement, {"id": video.id})


async def test_access_is_granted_once_per_user(db: AsyncSession) -> None:
    video = await make_video(db, await make_user(db, "anna"))
    bob = await make_user(db, "bob")
    db.add(VideoAccess(video_id=video.id, user_id=bob.id))
    await db.commit()
    db.add(VideoAccess(video_id=video.id, user_id=bob.id))

    with pytest.raises(IntegrityError, match="pk_video_access"):
        await db.commit()


async def test_deleting_a_user_deletes_their_videos_and_grants(db: AsyncSession) -> None:
    anna, bob = await make_user(db, "anna"), await make_user(db, "bob")
    video = await make_video(db, anna)
    db.add(VideoAccess(video_id=video.id, user_id=bob.id))
    await db.commit()

    await db.execute(delete(User).where(User.id == anna.id))
    await db.commit()

    assert await db.scalar(select(Video).where(Video.id == video.id)) is None
    assert await db.scalar(select(VideoAccess)) is None
