"""Video processing in the worker (ADR 0003): probe, transcode to MP4, thumbnail, store, ready.

Each step trusts nothing about the upload. ffmpeg reads it with fixed lists of formats and decoders,
local files only and a pixel cap, and runs without the worker's secrets in its environment.
"""

import asyncio
import contextlib
import json
import logging
import math
import os
import shutil
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
JOB_TIMEOUT = timedelta(hours=2)  # the whole job: download, ffmpeg runs, upload
# The sweeper (ADR 0003): a lost queue message, and a job whose worker is gone.
UPLOADED_GRACE = timedelta(minutes=5)
PROCESSING_LEASE = timedelta(hours=3)  # longer than a job may run, so its worker is gone
# Demuxers for real video containers. No playlists (hls, concat), images or raw streams.
INPUT_FORMATS = "mov,matroska,avi,flv,mpegts,mpeg,asf,ogg"
# Decoders for what phones, cameras and screen recorders produce: fewer parsers of untrusted bytes.
DECODERS = (
    "h264,hevc,vp8,vp9,av1,libdav1d,mpeg4,msmpeg4v3,mpeg2video,mpeg1video,prores,mjpeg,vc1,wmv3,"
    "theora,aac,mp3float,mp3,opus,vorbis,ac3,eac3,flac,alac,pcm_s16le,pcm_s16be,pcm_s24le,"
    "pcm_f32le,wmav2"
)
MAX_PIXELS = 7680 * 4320  # 8K; the decoder refuses bigger frames, wherever they are in the file
SAFE_INPUT = [
    "-protocol_whitelist", "file",
    "-format_whitelist", INPUT_FORMATS,
    "-codec_whitelist", DECODERS,
    "-max_pixels", str(MAX_PIXELS),
]  # fmt: skip
TOOL_ENV = {"PATH": os.environ.get("PATH", "/usr/bin:/bin")}  # no DB, Redis or S3 secrets
THUMBNAIL_HEIGHT = 360
SCRATCH_PREFIX = "job-"


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
        video = await db.get_one(Video, video_id) if attempt is not None else None
        # Nothing stays open while ffmpeg runs: the DB ends transactions idle for 60 s.
        await db.commit()
        if attempt is None or video is None:
            log.info("Video %s is not waiting for processing; skipped", video_id)
            return
        await _run(db, storage, video, attempt)


async def take_back_stuck() -> list[UUID]:
    """The sweeper's DB side: ids of videos to queue again."""
    async with _session() as db:
        back = await videos.take_back_stale(
            db, older_than=PROCESSING_LEASE, max_attempts=MAX_ATTEMPTS
        )
        waiting = await videos.touch_stale_uploaded(db, older_than=UPLOADED_GRACE)
        await db.commit()
    return back + waiting


def clear_scratch() -> None:
    """Remove work dirs a killed job left behind. Called when the worker starts."""
    for path in get_video_settings().scratch_dir.glob(f"{SCRATCH_PREFIX}*"):
        shutil.rmtree(path, ignore_errors=True)


async def _run(db: AsyncSession, storage: Storage, video: Video, attempt: int) -> None:
    video_id = video.id
    deadline = asyncio.timeout(JOB_TIMEOUT.total_seconds())
    try:
        try:
            async with deadline:
                duration = await _transcode(storage, video)
        except TimeoutError:
            if deadline.expired():  # ours, not a library's own timeout
                raise BadVideo("Processing took too long") from None
            raise
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
    with tempfile.TemporaryDirectory(prefix=SCRATCH_PREFIX, dir=settings.scratch_dir) as work:
        original, output, thumbnail = (Path(work) / f for f in ("original", "out.mp4", "thumb.jpg"))
        await storage.download(video.original_key, original)
        probe = await _probe(original)
        if probe.duration > settings.max_video_duration_sec:
            raise BadVideo(f"The video is longer than {_minutes(settings.max_video_duration_sec)}")
        if probe.width * probe.height > MAX_PIXELS:  # quick answer; -max_pixels covers the rest
            raise BadVideo("The video resolution is above 8K")
        # Flag-value pairs on one line each.
        # fmt: off
        await _ffmpeg(
            *SAFE_INPUT,
            "-i", str(original),
            # The probed stream: "V" skips cover pictures. Audio, if any.
            "-map", "0:V:0", "-map", "0:a:0?",
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
    # fmt: off
    out = await _run_tool(
        "ffprobe", "-v", "error", *SAFE_INPUT,
        "-select_streams", "V:0",  # the first real video stream, not a cover picture
        "-show_entries", "format=duration:stream=width,height",
        "-of", "json", str(path),
    )
    # fmt: on
    info = json.loads(out)
    video = next(iter(info.get("streams", [])), None)
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
        *command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, env=TOOL_ENV
    )
    try:
        out, err = await process.communicate()
    except BaseException:  # the job's deadline: don't leave ffmpeg running
        with contextlib.suppress(ProcessLookupError):  # it may have just exited
            process.kill()
        await process.wait()
        raise
    if process.returncode != 0:
        # The details go to the log only: they may name paths and internals. %r: one line.
        tail = err.decode(errors="replace")[-2000:]
        log.warning("%s exited with %s: %r", command[0], process.returncode, tail)
        raise BadVideo("The file is not a video or is damaged")
    return out.decode(errors="replace")  # odd bytes in tags must not look like a crash


def _minutes(seconds: int) -> str:
    return f"{seconds // 60} minutes" if seconds % 60 == 0 else f"{seconds} seconds"
