"""The demo seed on real Postgres, Redis, MinIO and the worker pipeline (ffmpeg)."""

import asyncio
import shutil
import subprocess
from collections.abc import AsyncIterator, Awaitable, Callable
from pathlib import Path
from typing import Any
from uuid import UUID

import anyio
import pytest
from fastapi import FastAPI
from pydantic import SecretStr
from redis.asyncio import Redis
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlalchemy.orm import aliased

from app import seed
from app.db.models import Base
from app.modules.auth.passwords import verify_password
from app.modules.channels.models import Subscription
from app.modules.comments.models import Comment
from app.modules.moderation import service as moderation
from app.modules.playlists.models import Playlist, PlaylistItem
from app.modules.reactions.models import CommentReaction, VideoReaction
from app.modules.reactions.schemas import Rating
from app.modules.reports.models import Report, ReportReason, ReportStatus
from app.modules.users.models import Role, User
from app.modules.videos import pipeline
from app.modules.videos import service as video_service
from app.modules.videos.models import Video, VideoStatus, Visibility
from app.worker.celery_app import celery_app
from tests.videos.factories import make_user

DEMO_DATA = Path(__file__).resolve().parents[3] / "demo-data"
PASSWORD = "demo-password-for-tests"
LIKE = Rating.LIKE.stored
RunSeed = Callable[[], Awaitable[None]]


@pytest.fixture(autouse=True, scope="module")
def ffmpeg_installed() -> None:
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        pytest.fail("These tests need ffmpeg and ffprobe: sudo apt install ffmpeg", pytrace=False)


@pytest.fixture(scope="module")
def clips(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """1 s clips under the demo file names: the real videos aren't in git."""
    root = tmp_path_factory.mktemp("clips")
    for upload in seed.UPLOADS:
        subprocess.run(  # noqa: S603 fixed commands, no user input
            ["ffmpeg", "-nostdin", "-v", "error", "-y",  # noqa: S607 ffmpeg from PATH
             "-f", "lavfi", "-i", "testsrc=duration=1:size=320x240:rate=10",
             "-f", "lavfi", "-i", "sine=duration=1",
             "-c:v", "libx264", "-c:a", "aac", "-shortest", str(root / upload.file)],
            check=True,
        )  # fmt: skip
    return root


@pytest.fixture
def demo_dir(tmp_path: Path, clips: Path) -> Path:
    """A demo-data/ as on a server: the real videos.json, the files in videos/."""
    shutil.copy(DEMO_DATA / "videos.json", tmp_path / "videos.json")
    shutil.copytree(clips, tmp_path / "videos")
    return tmp_path


@pytest.fixture
async def queued(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[list[str]]:
    """The worker: each queued video runs through the real pipeline on this event loop."""
    loop = asyncio.get_running_loop()
    jobs: list[asyncio.Task[None]] = []
    ids: list[str] = []

    def start(video_id: str) -> None:
        jobs.append(loop.create_task(pipeline.process(UUID(video_id))))

    def send_task(name: str, args: list[str]) -> None:
        # Runs in a worker thread, like kombu's blocking call.
        ids.append(args[0])
        anyio.from_thread.run_sync(start, args[0])

    monkeypatch.setattr(celery_app, "send_task", send_task)
    monkeypatch.setattr(seed, "POLL_SECONDS", 0.05)
    yield ids
    await asyncio.gather(*jobs)


@pytest.fixture
def run_seed(
    app: FastAPI, db: AsyncSession, redis: Redis, demo_dir: Path, queued: list[str]
) -> RunSeed:
    """Run the seed as `python -m app.seed` would, on empty tables."""
    settings = seed.SeedSettings(demo_password=SecretStr(PASSWORD), demo_data_dir=demo_dir)

    async def run() -> None:
        await seed.run(app.state.sessionmaker, redis, app.state.storage, settings)

    return run


async def snapshot(admin_engine: AsyncEngine) -> dict[str, list[Any]]:
    """Every row of every table."""
    async with admin_engine.connect() as conn:
        return {
            table.name: list(
                (await conn.execute(select(table).order_by(*table.primary_key.columns))).all()
            )
            for table in Base.metadata.sorted_tables
        }


async def video_rows(app: FastAPI) -> list[tuple[str, VideoStatus, int]]:
    async with app.state.sessionmaker() as db:
        query = select(Video.title, Video.status, Video.processing_attempts).order_by(Video.id)
        return [tuple(row) for row in (await db.execute(query)).all()]


def spam_comment() -> seed.DemoComment:
    return next(c for upload in seed.UPLOADS for c in upload.comments if c.reported_by)


def count(model: Any, *where: Any) -> Any:
    return select(func.count()).select_from(model).where(*where).scalar_subquery()


async def test_creates_the_demo_accounts_with_their_roles(app: FastAPI, run_seed: RunSeed) -> None:
    await run_seed()

    async with app.state.sessionmaker() as db:
        for account in seed.ACCOUNTS:
            user = await db.scalar(select(User).where(User.email == account.email))
            assert user is not None
            assert (user.handle, user.role) == (account.handle, account.role)
            assert await verify_password(user.password_hash, PASSWORD)


async def test_uploads_the_demo_videos_and_waits_until_they_are_ready(
    app: FastAPI, run_seed: RunSeed, queued: list[str]
) -> None:
    await run_seed()

    meta = {entry["file"]: entry for entry in seed._read_videos_json(DEMO_DATA)}  # noqa: SLF001
    async with app.state.sessionmaker() as db:
        for upload in seed.UPLOADS:
            row = await db.execute(
                select(Video, User.handle)
                .join(User, User.id == Video.owner_id)
                .where(Video.title == meta[upload.file]["title"])
            )
            video, owner = row.one()
            assert owner == upload.owner
            assert video.description == meta[upload.file]["description"]  # the license credit
            assert (video.visibility, video.category) == (Visibility.PUBLIC, upload.category)
            assert video.status is VideoStatus.READY
    assert len(queued) == len(seed.UPLOADS)


async def test_the_demo_activity_is_as_written(app: FastAPI, run_seed: RunSeed) -> None:
    await run_seed()

    meta = {entry["file"]: entry for entry in seed._read_videos_json(DEMO_DATA)}  # noqa: SLF001
    async with app.state.sessionmaker() as db:
        handles = dict((await db.execute(select(User.id, User.handle))).all())
        for upload in seed.UPLOADS:
            video = await db.scalar(select(Video).where(Video.title == meta[upload.file]["title"]))
            assert video is not None
            assert video.view_count == len(seed.ACCOUNTS) - 1  # everyone but the owner
            likers = await db.scalars(
                select(VideoReaction.user_id).where(
                    VideoReaction.target_id == video.id, VideoReaction.value == LIKE
                )
            )
            assert sorted(handles[user_id] for user_id in likers) == sorted(upload.liked_by)
            written = [(c.author, c.text) for c in upload.comments] + [
                (r.author, r.text) for c in upload.comments for r in c.replies
            ]
            posted = await db.execute(
                select(Comment.author_id, Comment.text).where(Comment.video_id == video.id)
            )
            assert sorted((handles[a], text) for a, text in posted.all()) == sorted(written)

        subscriptions = await db.execute(
            select(Subscription.subscriber_id, Subscription.channel_id)
        )
        pairs = sorted((handles[s], handles[c]) for s, c in subscriptions.all())
        assert pairs == sorted(seed.SUBSCRIPTIONS)

        for demo in seed.PLAYLISTS:
            playlist = await db.scalar(select(Playlist).where(Playlist.title == demo.title))
            assert playlist is not None
            assert (handles[playlist.owner_id], playlist.visibility) == (
                demo.owner,
                Visibility.PUBLIC,
            )
            titles = await db.scalars(
                select(Video.title)
                .join(PlaylistItem, PlaylistItem.video_id == Video.id)
                .where(PlaylistItem.playlist_id == playlist.id)
                .order_by(PlaylistItem.position)
            )
            assert list(titles) == [meta[file]["title"] for file in demo.files]

        report = (await db.execute(select(Report, Comment.text).join(Comment))).one()
        assert report[1] == spam_comment().text
        assert (handles[report[0].reporter_id], report[0].reason, report[0].status) == (
            spam_comment().reported_by[0],
            ReportReason.SPAM,
            ReportStatus.OPEN,
        )


async def test_every_counter_matches_its_rows(app: FastAPI, run_seed: RunSeed) -> None:
    await run_seed()

    reply = aliased(Comment)
    video_likes = (VideoReaction.target_id == Video.id, VideoReaction.value == LIKE)
    comment_likes = (CommentReaction.target_id == Comment.id, CommentReaction.value == LIKE)
    checks = [
        select(Video.like_count, count(VideoReaction, *video_likes)),
        select(Video.comment_count, count(Comment, Comment.video_id == Video.id)),
        select(Comment.like_count, count(CommentReaction, *comment_likes)),
        select(Comment.reply_count, count(reply, reply.parent_id == Comment.id)),
        select(User.subscriber_count, count(Subscription, Subscription.channel_id == User.id)),
        select(Playlist.video_count, count(PlaylistItem, PlaylistItem.playlist_id == Playlist.id)),
    ]
    async with app.state.sessionmaker() as db:
        for check in checks:
            rows = (await db.execute(check)).all()
            assert rows, check
            assert all(counter == actual for counter, actual in rows), (check, rows)
            assert any(counter for counter, _ in rows), check  # the scenario sets each one


async def test_a_second_run_changes_nothing(
    admin_engine: AsyncEngine, run_seed: RunSeed, queued: list[str]
) -> None:
    await run_seed()
    before, sent = await snapshot(admin_engine), len(queued)

    await run_seed()

    assert await snapshot(admin_engine) == before
    assert len(queued) == sent  # nothing uploaded or queued again


async def test_a_comment_a_moderator_deleted_is_not_posted_again(
    app: FastAPI, run_seed: RunSeed
) -> None:
    await run_seed()
    async with app.state.sessionmaker() as db:
        moderator = await db.scalar(select(User).where(User.role == Role.MODERATOR))
        spam = await db.scalar(select(Comment.id).where(Comment.text == spam_comment().text))
        assert moderator is not None and spam is not None
        await moderation.delete_comment(db, moderator, spam)

    await run_seed()

    async with app.state.sessionmaker() as db:
        posts = await db.scalars(
            select(Comment.is_deleted).where(Comment.text == spam_comment().text)
        )
        assert list(posts) == [True]  # still deleted, not posted again
        assert list(await db.scalars(select(Report.status))) == [ReportStatus.ACTIONED]


async def test_a_rerun_skips_what_a_hidden_video_refuses(app: FastAPI, run_seed: RunSeed) -> None:
    first, *rest = seed.UPLOADS
    await run_seed()
    async with app.state.sessionmaker() as db:
        moderator = await db.scalar(select(User).where(User.role == Role.MODERATOR))
        meta = {entry["file"]: entry for entry in seed._read_videos_json(DEMO_DATA)}  # noqa: SLF001
        video = await db.scalar(select(Video).where(Video.title == meta[first.file]["title"]))
        assert moderator is not None and video is not None
        await moderation.hide_video(db, moderator, video.public_id, ReportReason.SPAM)
        await db.execute(delete(VideoReaction))  # so the re-run likes every video again
        await db.commit()

    await run_seed()  # the first video's likes are refused (404) and skipped; the rest goes on

    async with app.state.sessionmaker() as db:
        assert await db.scalar(select(Video.is_hidden).where(Video.id == video.id))
        liked = await db.scalar(select(func.count()).select_from(VideoReaction))
        assert liked == sum(len(upload.liked_by) for upload in rest)
    assert first.liked_by  # the scenario has likes to refuse


async def test_a_dismissed_report_is_not_filed_again(app: FastAPI, run_seed: RunSeed) -> None:
    await run_seed()
    async with app.state.sessionmaker() as db:
        moderator = await db.scalar(select(User).where(User.role == Role.MODERATOR))
        spam = await db.scalar(select(Comment.id).where(Comment.text == spam_comment().text))
        assert moderator is not None and spam is not None
        await moderation.dismiss_comment(db, moderator, spam)

    await run_seed()

    async with app.state.sessionmaker() as db:
        assert list(await db.scalars(select(Report.status))) == [ReportStatus.DISMISSED]


async def test_a_run_that_failed_midway_is_finished_by_the_next(
    app: FastAPI, run_seed: RunSeed, monkeypatch: pytest.MonkeyPatch
) -> None:
    upload_file = video_service.upload_file
    calls = 0

    async def fails_on_the_second_file(*args: Any, **kwargs: Any) -> Any:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("connection lost")
        return await upload_file(*args, **kwargs)

    monkeypatch.setattr(video_service, "upload_file", fails_on_the_second_file)
    with pytest.raises(RuntimeError, match="connection lost"):
        await run_seed()

    await run_seed()

    videos = await video_rows(app)
    assert len(videos) == len(seed.UPLOADS)  # the draft left behind was reused, not doubled
    assert {(status, attempts) for _, status, attempts in videos} == {(VideoStatus.READY, 1)}


async def test_a_missing_file_is_skipped_and_added_by_a_later_run(
    app: FastAPI, run_seed: RunSeed, demo_dir: Path, tmp_path_factory: pytest.TempPathFactory
) -> None:
    missing = demo_dir / "videos" / seed.UPLOADS[-1].file
    kept = tmp_path_factory.mktemp("kept") / missing.name
    missing.rename(kept)

    await run_seed()
    assert len(await video_rows(app)) == len(seed.UPLOADS) - 1

    kept.rename(missing)
    await run_seed()
    assert len(await video_rows(app)) == len(seed.UPLOADS)


async def test_a_video_that_fails_processing_is_not_uploaded_again(
    app: FastAPI, run_seed: RunSeed, demo_dir: Path, queued: list[str]
) -> None:
    (demo_dir / "videos" / seed.UPLOADS[0].file).write_bytes(b"not a video")

    await run_seed()  # the other videos are still seeded, with their activity
    statuses = sorted(status for _, status, _ in await video_rows(app))
    assert statuses == sorted([VideoStatus.FAILED] + [VideoStatus.READY] * (len(statuses) - 1))
    sent = len(queued)

    await run_seed()

    assert len(queued) == sent


async def test_a_demo_email_taken_with_another_password_stops_the_seed(
    app: FastAPI, db: AsyncSession, run_seed: RunSeed
) -> None:
    # Someone signed up as the demo admin before the seed ran: they must not become an admin.
    await make_user(db, "admin")

    with pytest.raises(seed.SeedError, match="admin@example.com"):
        await run_seed()

    async with app.state.sessionmaker() as session:
        user = await session.scalar(select(User).where(User.email == "admin@example.com"))
        assert user is not None
        assert user.role is Role.USER
        assert await session.scalar(select(Video.id)) is None  # stopped before any upload


async def test_a_video_whose_queue_message_was_lost_is_queued_by_the_next_run(
    app: FastAPI, run_seed: RunSeed, monkeypatch: pytest.MonkeyPatch
) -> None:
    worker = celery_app.send_task
    monkeypatch.setattr(celery_app, "send_task", lambda name, args: None)  # the broker lost them
    monkeypatch.setattr(seed, "PROCESSING_TIMEOUT_SEC", 0.3)
    with pytest.raises(seed.SeedError):
        await run_seed()

    monkeypatch.setattr(celery_app, "send_task", worker)
    monkeypatch.setattr(seed, "PROCESSING_TIMEOUT_SEC", 60)
    await run_seed()

    assert {status for _, status, _ in await video_rows(app)} == {VideoStatus.READY}


async def test_gives_up_when_the_worker_does_not_process_in_time(
    run_seed: RunSeed, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(celery_app, "send_task", lambda name, args: None)  # the worker is down
    monkeypatch.setattr(seed, "PROCESSING_TIMEOUT_SEC", 0.3)

    with pytest.raises(seed.SeedError, match="in time"):
        await run_seed()
