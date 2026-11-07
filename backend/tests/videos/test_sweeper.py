"""Claiming jobs and the sweeper (ADR 0003): no ffmpeg needed."""

from datetime import timedelta

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.videos import pipeline, tasks
from app.modules.videos import repository as videos
from app.modules.videos.models import Video, VideoStatus
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


def test_the_worker_knows_the_task_the_api_sends() -> None:
    assert tasks.__name__ in celery_app.conf.include  # the worker imports it at start
    assert PROCESS_TASK in celery_app.tasks
