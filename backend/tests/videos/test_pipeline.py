"""The worker pipeline on real ffmpeg, MinIO and Postgres (ADR 0003)."""

import json
import shutil
import subprocess
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import Any

import anyio
import pytest
from fastapi import FastAPI
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from types_aiobotocore_s3 import S3Client

from app.core.storage import Storage, get_storage_settings, open_s3_client
from app.modules.videos import pipeline
from app.modules.videos.config import get_video_settings
from app.modules.videos.models import Video, VideoStatus
from tests.videos.factories import make_user, make_video


@pytest.fixture(autouse=True, scope="module")
def ffmpeg_installed() -> None:
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        pytest.fail("These tests need ffmpeg and ffprobe: sudo apt install ffmpeg", pytrace=False)


def ffmpeg(*args: str) -> None:
    subprocess.run(  # noqa: S603 fixed commands, no user input
        ["ffmpeg", "-nostdin", "-v", "error", "-y", *args],  # noqa: S607 ffmpeg from PATH
        check=True,
    )


def probe(path: Path) -> dict[str, Any]:
    out = subprocess.run(  # noqa: S603
        ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],  # noqa: S607
        check=True,
        capture_output=True,
    ).stdout
    return json.loads(out)


@pytest.fixture(scope="session")
def samples(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Small generated media files, made once per run."""
    root = tmp_path_factory.mktemp("samples")
    ffmpeg(
        "-f",
        "lavfi",
        "-i",
        "testsrc=duration=2:size=1920x1080:rate=25",
        "-f",
        "lavfi",
        "-i",
        "sine=duration=2",
        "-c:v",
        "libx264",
        "-c:a",
        "aac",
        "-shortest",
        "-metadata",
        "location=+52.37+004.89/",  # phone-style GPS tag
        str(root / "hd.mp4"),
    )
    ffmpeg(  # portrait, no audio, WebM
        "-f",
        "lavfi",
        "-i",
        "testsrc=duration=1:size=360x640:rate=30",
        "-c:v",
        "libvpx-vp9",
        "-b:v",
        "200k",
        str(root / "portrait.webm"),
    )
    ffmpeg("-f", "lavfi", "-i", "sine=duration=1", "-c:a", "aac", str(root / "audio.m4a"))
    (root / "text.mp4").write_text("not a video at all")
    # A playlist posing as a video: without the format allowlist ffmpeg could read local files.
    (root / "playlist.mp4").write_text(
        "#EXTM3U\n#EXT-X-MEDIA-SEQUENCE:0\n#EXTINF:1.0,\nfile:///etc/passwd\n#EXT-X-ENDLIST\n"
    )
    return root


@pytest.fixture
def storage(app: FastAPI) -> Storage:
    return app.state.storage


@pytest.fixture
async def s3(app: FastAPI) -> AsyncIterator[S3Client]:
    async with open_s3_client(get_storage_settings()) as client:
        yield client


@pytest.fixture
def limits(monkeypatch: pytest.MonkeyPatch) -> Iterator[pytest.MonkeyPatch]:
    """Lets a test change the video limits through env; restores the cached settings after."""
    get_video_settings.cache_clear()
    yield monkeypatch
    monkeypatch.undo()
    get_video_settings.cache_clear()


async def uploaded(db: AsyncSession, storage: Storage, source: Path) -> Video:
    video = await make_video(db, await make_user(db, "anna"), status=VideoStatus.UPLOADED)
    await storage.upload_file(video.original_key, source, content_type="application/octet-stream")
    return video


async def reload(db: AsyncSession, video: Video) -> Video:
    await db.refresh(video)
    return video


async def download(s3: S3Client, key: str, path: Path) -> Path:
    response = await s3.get_object(Bucket=get_storage_settings().s3_bucket, Key=key)
    async with response["Body"] as body:
        await anyio.Path(path).write_bytes(await body.read())
    return path


def top_level_boxes(path: Path) -> list[str]:
    """MP4 box types in file order (ISO BMFF: 4-byte size, 4-byte type)."""
    data, boxes, offset = path.read_bytes(), [], 0
    while offset + 8 <= len(data):
        size = int.from_bytes(data[offset : offset + 4], "big")
        boxes.append(data[offset + 4 : offset + 8].decode())
        if size == 1:  # 64-bit size follows
            size = int.from_bytes(data[offset + 8 : offset + 16], "big")
        if size < 8:
            break
        offset += size
    return boxes


async def test_hd_video_becomes_a_720p_mp4_with_thumbnail(
    db: AsyncSession, storage: Storage, s3: S3Client, samples: Path, tmp_path: Path
) -> None:
    video = await uploaded(db, storage, samples / "hd.mp4")

    await pipeline.process(video.id)

    video = await reload(db, video)
    assert video.status is VideoStatus.READY
    assert video.duration_sec == 2
    assert video.error_message is None
    output = await download(s3, video.media_key, tmp_path / "out.mp4")
    info = probe(output)
    streams = {s["codec_type"]: s for s in info["streams"]}
    assert (streams["video"]["codec_name"], streams["video"]["height"]) == ("h264", 720)
    assert streams["video"]["width"] == 1280
    assert streams["audio"]["codec_name"] == "aac"
    assert "location" not in info["format"].get("tags", {})  # metadata stripped
    boxes = top_level_boxes(output)
    assert boxes.index("moov") < boxes.index("mdat")  # faststart: playback starts at once
    thumbnail = await download(s3, video.thumbnail_key, tmp_path / "thumb.jpg")
    assert thumbnail.read_bytes()[:3] == b"\xff\xd8\xff"  # JPEG
    head = await s3.head_object(Bucket=get_storage_settings().s3_bucket, Key=video.media_key)
    assert head["ContentType"] == "video/mp4"


async def test_small_portrait_video_is_not_upscaled(
    db: AsyncSession, storage: Storage, s3: S3Client, samples: Path, tmp_path: Path
) -> None:
    video = await uploaded(db, storage, samples / "portrait.webm")

    await pipeline.process(video.id)

    video = await reload(db, video)
    assert video.status is VideoStatus.READY
    output = probe(await download(s3, video.media_key, tmp_path / "out.mp4"))
    assert [(s["width"], s["height"]) for s in output["streams"]] == [(360, 640)]  # no audio


@pytest.mark.parametrize(
    ("sample", "message"),
    [
        ("audio.m4a", "The file is not a video"),
        ("text.mp4", "The file is not a video or is damaged"),
        ("playlist.mp4", "The file is not a video or is damaged"),
    ],
)
async def test_files_that_are_not_videos_fail_with_a_reason(
    db: AsyncSession, storage: Storage, samples: Path, sample: str, message: str
) -> None:
    video = await uploaded(db, storage, samples / sample)

    await pipeline.process(video.id)

    video = await reload(db, video)
    assert (video.status, video.error_message) == (VideoStatus.FAILED, message)


async def test_a_real_playlist_is_refused(samples: Path) -> None:
    # A proper .m3u8 whose segment is a local file: ffmpeg would read it without the format
    # allowlist, so this is how a playlist could pull in files that aren't the upload.
    playlist = samples / "playlist.m3u8"
    playlist.write_text(
        f"#EXTM3U\n#EXT-X-TARGETDURATION:2\n#EXTINF:2.0,\n{samples / 'hd.mp4'}\n#EXT-X-ENDLIST\n"
    )

    with pytest.raises(pipeline.BadVideo):
        await pipeline._probe(playlist)  # pyright: ignore[reportPrivateUsage]


async def test_a_video_over_the_duration_limit_fails(
    db: AsyncSession, storage: Storage, samples: Path, limits: pytest.MonkeyPatch
) -> None:
    limits.setenv("MAX_VIDEO_DURATION_SEC", "1")
    video = await uploaded(db, storage, samples / "hd.mp4")

    await pipeline.process(video.id)

    video = await reload(db, video)
    assert video.status is VideoStatus.FAILED
    assert video.error_message == "The video is longer than 1 seconds"


async def test_only_one_run_processes_a_video(
    db: AsyncSession, storage: Storage, samples: Path
) -> None:
    video = await uploaded(db, storage, samples / "hd.mp4")

    await pipeline.process(video.id)
    await pipeline.process(video.id)  # a duplicate message

    video = await reload(db, video)
    assert (video.status, video.processing_attempts) == (VideoStatus.READY, 1)


async def test_a_storage_error_keeps_the_original_for_a_retry(
    db: AsyncSession, storage: Storage, samples: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    video = await uploaded(db, storage, samples / "hd.mp4")

    async def broken(*_: object, **__: object) -> int:
        raise ConnectionError("MinIO is down")

    with monkeypatch.context() as patch:
        patch.setattr(Storage, "upload_file", broken)
        await pipeline.process(video.id)

    video = await reload(db, video)
    assert (video.status, video.error_message) == (VideoStatus.UPLOADED, None)

    await pipeline.process(video.id)  # no new upload needed

    video = await reload(db, video)
    assert (video.status, video.processing_attempts) == (VideoStatus.READY, 2)


async def test_the_last_failed_attempt_gives_up(
    db: AsyncSession, storage: Storage, samples: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    video = await uploaded(db, storage, samples / "hd.mp4")
    await db.execute(
        update(Video)
        .where(Video.id == video.id)
        .values(processing_attempts=pipeline.MAX_ATTEMPTS - 1)
    )
    await db.commit()

    async def broken(*_: object, **__: object) -> int:
        raise ConnectionError("MinIO is down")

    monkeypatch.setattr(Storage, "upload_file", broken)
    await pipeline.process(video.id)

    video = await reload(db, video)
    assert (video.status, video.error_message) == (VideoStatus.FAILED, "Processing failed")
