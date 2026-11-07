"""Video processing in the worker (ADR 0003): probe, transcode to MP4, thumbnail, store, ready.

Each step trusts nothing about the upload: ffmpeg reads it with a fixed list of formats and only
local files, so a playlist posing as a video can't make it fetch URLs or read other files.
"""

import asyncio
import json
import logging
import math
import tempfile
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.core.storage import Storage, get_storage_settings, open_storage
from app.modules.videos import repository as videos
from app.modules.videos.config import get_video_settings
from app.modules.videos.models import Video, VideoStatus

log = logging.getLogger(__name__)

MAX_ATTEMPTS = 3  # then FAILED: a file that kills the worker can't loop forever
FFMPEG_TIMEOUT_SEC = 2 * 3600
# The sweeper (ADR 0003): a lost queue message, and a job whose worker is gone.
UPLOADED_GRACE = timedelta(minutes=5)
PROCESSING_LEASE = timedelta(hours=3)  # longer than any run: ffmpeg's timeout plus transfers
# Demuxers for real video containers. No playlists (hls, concat), images or raw streams.
INPUT_FORMATS = "mov,matroska,avi,flv,mpegts,mpeg,asf,ogg"
SAFE_INPUT = ["-protocol_whitelist", "file", "-format_whitelist", INPUT_FORMATS]
MAX_PIXELS = 7680 * 4320  # 8K
THUMBNAIL_HEIGHT = 360


class BadVideo(Exception):
    """The file itself is the problem. The message is shown to the owner."""


@dataclass(frozen=True)
class Probe:
    duration: float
    width: int
    height: int


@asynccontextmanager
async def _session() -> AsyncIterator[AsyncSession]:
    """A DB session for one task. NullPool: each task runs in its own event loop."""
    engine = create_async_engine(str(get_settings().database_url), poolclass=NullPool)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as db:
            yield db
    finally:
        await engine.dispose()


async def process(video_id: UUID) -> None:
    """Process one uploaded video. Safe to run twice: only the run that claims it works."""
    async with _session() as db, open_storage(get_storage_settings()) as storage:
        attempt = await videos.claim(db, video_id)
        await db.commit()
        if attempt is None:
            log.info("Video %s is not waiting for processing; skipped", video_id)
            return
        await _run(db, storage, await db.get_one(Video, video_id), attempt)


async def take_back_stuck() -> list[UUID]:
    """The sweeper's DB side: ids of videos to queue again."""
    async with _session() as db:
        back = await videos.take_back_stale(
            db, older_than=PROCESSING_LEASE, max_attempts=MAX_ATTEMPTS
        )
        waiting = await videos.touch_stale_uploaded(db, older_than=UPLOADED_GRACE)
        await db.commit()
    return back + waiting


async def _run(db: AsyncSession, storage: Storage, video: Video, attempt: int) -> None:
    video_id = video.id
    try:
        duration = await _transcode(storage, video)
    except BadVideo as error:
        log.info("Video %s failed: %s", video_id, error)
        await videos.finish(
            db, video_id, attempt, status=VideoStatus.FAILED, error_message=str(error)
        )
    except Exception:
        # Not the file's fault (storage, disk, a bug): keep the original and try again later.
        log.exception("Processing video %s failed (attempt %d)", video_id, attempt)
        await db.rollback()
        if attempt >= MAX_ATTEMPTS:
            await videos.finish(
                db, video_id, attempt, status=VideoStatus.FAILED, error_message="Processing failed"
            )
        else:
            await videos.finish(db, video_id, attempt, status=VideoStatus.UPLOADED)
    else:
        await videos.finish(db, video_id, attempt, status=VideoStatus.READY, duration_sec=duration)
    await db.commit()


async def _transcode(storage: Storage, video: Video) -> int:
    """Original → MP4 + thumbnail in MinIO. Returns the duration in whole seconds."""
    settings = get_video_settings()
    with tempfile.TemporaryDirectory(dir=settings.scratch_dir) as work:
        original, output, thumbnail = (Path(work) / f for f in ("original", "out.mp4", "thumb.jpg"))
        await storage.download(video.original_key, original)
        probe = await _probe(original)
        if probe.duration > settings.max_video_duration_sec:
            raise BadVideo(f"The video is longer than {_minutes(settings.max_video_duration_sec)}")
        if probe.width * probe.height > MAX_PIXELS:
            raise BadVideo("The video resolution is above 8K")
        # Flag-value pairs on one line each.
        # fmt: off
        await _ffmpeg(
            *SAFE_INPUT,
            "-i", str(original),
            "-map", "0:v:0", "-map", "0:a:0?",  # the first video and audio streams, if any
            # Height ≤ the limit, never upscaled; even sizes for H.264 4:2:0.
            "-vf", f"scale=-2:'min({settings.max_video_height},trunc(ih/2)*2)'",
            "-fpsmax", "60",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "128k", "-ac", "2",
            "-map_metadata", "-1", "-map_chapters", "-1",  # drops GPS and other private tags
            "-t", str(settings.max_video_duration_sec),  # never longer than allowed
            "-movflags", "+faststart",  # index first: playback starts before the download ends
            str(output),
        )
        # fmt: on
        result = await _probe(output)
        # fmt: off
        await _ffmpeg(
            "-ss", f"{result.duration / 4:.3f}",  # a frame a quarter in: past any intro
            "-i", str(output),
            "-frames:v", "1", "-update", "1",
            "-vf", f"scale=-2:{THUMBNAIL_HEIGHT}", "-q:v", "3",
            str(thumbnail),
        )
        # fmt: on
        await storage.upload_file(video.media_key, output, content_type="video/mp4")
        await storage.upload_file(video.thumbnail_key, thumbnail, content_type="image/jpeg")
        return math.floor(result.duration)


async def _probe(path: Path) -> Probe:
    entries = "format=duration:stream=codec_type,width,height:stream_disposition=attached_pic"
    # fmt: off
    out = await _run_tool(
        "ffprobe", "-v", "error", *SAFE_INPUT,
        "-show_entries", entries,
        "-of", "json", str(path),
    )
    # fmt: on
    info = json.loads(out)
    video = next(
        (
            s
            for s in info.get("streams", [])
            if s.get("codec_type") == "video" and not s.get("disposition", {}).get("attached_pic")
        ),
        None,
    )
    try:
        duration = float(info["format"]["duration"])
    except (KeyError, ValueError):
        duration = 0.0
    if video is None or duration <= 0 or not video.get("width"):
        raise BadVideo("The file is not a video")
    return Probe(duration, int(video["width"]), int(video["height"]))


async def _ffmpeg(*args: str) -> None:
    await _run_tool("ffmpeg", "-nostdin", "-hide_banner", "-v", "error", "-y", *args)


async def _run_tool(*command: str) -> str:
    process = await asyncio.create_subprocess_exec(
        *command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    try:
        out, err = await asyncio.wait_for(process.communicate(), FFMPEG_TIMEOUT_SEC)
    except TimeoutError:
        process.kill()
        await process.wait()
        raise BadVideo("Processing took too long") from None
    if process.returncode != 0:
        # The details go to the log only: they may name paths and internals.
        log.warning("%s exited with %s: %s", command[0], process.returncode, err.decode()[-2000:])
        raise BadVideo("The file is not a video or is damaged")
    return out.decode()


def _minutes(seconds: int) -> str:
    return f"{seconds // 60} minutes" if seconds % 60 == 0 else f"{seconds} seconds"
