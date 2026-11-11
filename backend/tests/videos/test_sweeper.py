"""Claiming jobs, the sweeper and the worker's own limits (ADR 0003): no ffmpeg needed."""

import asyncio
import signal
from collections.abc import Callable
from datetime import timedelta
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

import anyio
import pytest
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core.storage import Storage
from app.modules.videos import pipeline, tasks
from app.modules.videos import repository as videos
from app.modules.videos.config import get_video_settings
from app.modules.videos.models import GAVE_UP_REASON, Video, VideoStatus
from app.modules.videos.service import PROCESS_TASK
from app.worker.celery_app import celery_app
from tests.videos.factories import make_user, make_video


async def test_a_taken_back_run_cannot_overwrite_the_new_one(db: AsyncSession) -> None:
    video = await make_video(db, await make_user(db, "anna"), status=VideoStatus.UPLOADED)

    first = await videos.claim(db, video.id)
    await db.execute(update(Video).where(Video.id == video.id).values(status=VideoStatus.UPLOADED))
    second = await videos.claim(db, video.id)  # the sweeper gave it to another worker

    assert (first, second) == (1, 2)
    assert not await videos.finish(db, video.id, 1, status=VideoStatus.FAILED, error_message="x")
    assert await videos.finish(db, video.id, 2, status=VideoStatus.READY, duration_sec=3)


async def age(db: AsyncSession, video: Video, by: timedelta) -> None:
    # Set the time directly: the trigger only stamps it when the status changes.
    await db.execute(
        update(Video).where(Video.id == video.id).values(status_changed_at=func.now() - by)
    )
    await db.commit()


async def test_sweeper_queues_videos_left_waiting(db: AsyncSession) -> None:
    owner = await make_user(db, "anna")
    waiting = await make_video(db, owner, status=VideoStatus.UPLOADED)
    await make_video(db, owner, status=VideoStatus.UPLOADED)  # just uploaded: its task is queued
    await age(db, waiting, pipeline.UPLOADED_GRACE + timedelta(minutes=1))

    assert await pipeline.take_back_stuck() == [waiting.id]
    assert await pipeline.take_back_stuck() == []  # not again right away


async def test_sweeper_takes_back_jobs_of_a_lost_worker(db: AsyncSession) -> None:
    owner = await make_user(db, "anna")
    lost = await make_video(db, owner, status=VideoStatus.PROCESSING)
    hopeless = await make_video(db, owner, status=VideoStatus.PROCESSING)
    running = await make_video(db, owner, status=VideoStatus.PROCESSING)
    await db.execute(
        update(Video)
        .where(Video.id == hopeless.id)
        .values(processing_attempts=pipeline.MAX_ATTEMPTS)
    )
    for video in (lost, hopeless):
        await age(db, video, pipeline.PROCESSING_LEASE + timedelta(minutes=1))

    assert await pipeline.take_back_stuck() == [lost.id]

    statuses = dict((await db.execute(select(Video.id, Video.status))).all())
    assert statuses == {
        lost.id: VideoStatus.UPLOADED,
        hopeless.id: VideoStatus.FAILED,
        running.id: VideoStatus.PROCESSING,
    }
    reason = await db.scalar(select(Video.error_message).where(Video.id == hopeless.id))
    assert reason == GAVE_UP_REASON


def test_the_worker_knows_the_task_the_api_sends() -> None:
    assert tasks.__name__ in celery_app.conf.include  # the worker imports it at start
    assert PROCESS_TASK in celery_app.tasks


@pytest.fixture
def no_transcoding(monkeypatch: pytest.MonkeyPatch) -> Callable[[float], None]:
    """Stand-in for ffmpeg: a job that takes `seconds` and makes a 5 s video."""

    def take(seconds: float) -> None:
        async def transcode(*_: object) -> int:
            await asyncio.sleep(seconds)
            return 5

        monkeypatch.setattr(pipeline, "_transcode", transcode)

    return take


async def test_a_long_job_holds_no_db_transaction(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch, no_transcoding: Callable[[float], None]
) -> None:
    # The app role ends transactions idle for 60 s; here 1 s, and the job takes 2 s.
    real_engine = pipeline.create_async_engine

    def strict_engine(url: str, **kwargs: Any) -> AsyncEngine:
        settings = {"idle_in_transaction_session_timeout": "1000"}
        return real_engine(url, connect_args={"server_settings": settings}, **kwargs)

    monkeypatch.setattr(pipeline, "create_async_engine", strict_engine)
    no_transcoding(2)
    video = await make_video(db, await make_user(db, "anna"), status=VideoStatus.UPLOADED)

    await pipeline.process(video.id)

    await db.refresh(video)
    assert (video.status, video.duration_sec) == (VideoStatus.READY, 5)


async def test_a_job_over_its_deadline_fails(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch, no_transcoding: Callable[[float], None]
) -> None:
    monkeypatch.setattr(pipeline, "JOB_TIMEOUT", timedelta(seconds=0.2))
    no_transcoding(5)
    video = await make_video(db, await make_user(db, "anna"), status=VideoStatus.UPLOADED)

    await pipeline.process(video.id)

    await db.refresh(video)
    assert (video.status, video.error_message) == (VideoStatus.FAILED, "Processing took too long")


async def test_a_tool_cut_off_by_the_deadline_is_killed(monkeypatch: pytest.MonkeyPatch) -> None:
    started: list[asyncio.subprocess.Process] = []
    real_exec = asyncio.create_subprocess_exec

    async def recording_exec(*args: Any, **kwargs: Any) -> asyncio.subprocess.Process:
        started.append(await real_exec(*args, **kwargs))
        return started[-1]

    monkeypatch.setattr(asyncio, "create_subprocess_exec", recording_exec)

    with pytest.raises(TimeoutError):
        async with asyncio.timeout(0.3):
            await pipeline._run_tool("sleep", "30")  # pyright: ignore[reportPrivateUsage]

    assert started[0].returncode == -signal.SIGKILL  # killed, not waited out or left running


async def test_tools_get_none_of_the_workers_secrets() -> None:
    out = await pipeline._run_tool("env")  # pyright: ignore[reportPrivateUsage]

    assert [line.split("=")[0] for line in out.splitlines()] == ["PATH"]


async def test_odd_bytes_from_a_tool_are_read_not_a_crash() -> None:
    out = await pipeline._run_tool("printf", "\\377ok")  # pyright: ignore[reportPrivateUsage]

    assert out == "\ufffdok"


async def test_worker_start_removes_work_dirs_a_killed_job_left(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SCRATCH_DIR", str(tmp_path))
    get_video_settings.cache_clear()
    other = tmp_path / "not-ours"
    other.mkdir()
    removed: list[bool] = []

    class Halt(Exception):
        """The job stops with its work file on disk, as when its worker is killed."""

    class Download:
        async def download(self, _key: str, path: Path) -> None:
            await anyio.Path(path).write_bytes(b"x")
            tasks.clear_scratch()  # what the next worker start does
            removed.append(not await anyio.Path(path).exists())
            raise Halt

    try:
        with pytest.raises(Halt):
            await pipeline._transcode(cast(Storage, Download()), Video(id=uuid4()))  # pyright: ignore[reportPrivateUsage]
    finally:
        get_video_settings.cache_clear()

    assert removed == [True]
    assert other.exists()


def test_celery_kills_a_stuck_job_before_the_sweeper_takes_it_back() -> None:
    limit = celery_app.conf.task_time_limit

    assert pipeline.JOB_TIMEOUT.total_seconds() < limit < pipeline.PROCESSING_LEASE.total_seconds()
