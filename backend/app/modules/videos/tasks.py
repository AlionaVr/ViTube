"""Celery tasks: thin sync wrappers around the async pipeline."""

import asyncio
from uuid import UUID

from celery.signals import worker_init

from app.modules.videos import pipeline
from app.modules.videos.service import PROCESS_TASK
from app.worker.celery_app import celery_app


@worker_init.connect
def clear_scratch(**_: object) -> None:
    """Before any job runs: a killed worker leaves its work files on the volume."""
    pipeline.clear_scratch()


@celery_app.task(name=PROCESS_TASK)
def process_video(video_id: str) -> None:
    asyncio.run(pipeline.process(UUID(video_id)))


@celery_app.task(name="videos.requeue")
def requeue_stuck_videos() -> None:
    """The sweeper (ADR 0003). Beat runs it every minute."""
    for video_id in asyncio.run(pipeline.take_back_stuck()):
        celery_app.send_task(PROCESS_TASK, args=[str(video_id)])  # as the api does
