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
from app.modules.videos.models import GAVE_UP_REASON, Video, VideoStatus
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


def probe(path: Path, *extra: str) -> dict[str, Any]:
    command = ["ffprobe", "-v", "error", *extra, "-show_streams", "-show_format", "-of", "json"]
    out = subprocess.run([*command, str(path)], check=True, capture_output=True).stdout  # noqa: S603
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
    # A codec outside the decoder list (lossless FFV1).
    ffmpeg(
        "-f", "lavfi", "-i", "testsrc=duration=1:size=320x240:rate=25",
        "-c:v", "ffv1", str(root / "ffv1.mkv"),
    )  # fmt: skip
    # A cover picture as the first video stream, the real video second.
    ffmpeg("-f", "lavfi", "-i", "testsrc=size=96x96", "-frames:v", "1", str(root / "cover.jpg"))
    ffmpeg(
        "-f", "lavfi", "-i", "testsrc=duration=2:size=640x360:rate=25", "-c:v", "libx264",
        str(root / "real.mp4"),
    )  # fmt: skip
    ffmpeg(
        "-i", str(root / "real.mp4"), "-i", str(root / "cover.jpg"),
        "-map", "0", "-map", "1", "-c", "copy", "-disposition:v:1", "attached_pic",
        "-movflags", "+faststart", str(root / "cover.mp4"),
    )  # fmt: skip
    move_cover_first(root / "cover.mp4")
    # Small frames in the header, then 8192x8192 ones: the probe sees only the small size.
    ffmpeg(
        "-f", "lavfi", "-i", "testsrc=duration=1:size=320x240:rate=25",
        "-c:v", "libx264", "-f", "mpegts", str(root / "small.ts"),
    )  # fmt: skip
    ffmpeg(
        "-f", "lavfi", "-i", "color=c=gray:size=8192x8192:duration=0.2:rate=25",
        "-c:v", "libx264", "-preset", "ultrafast", "-f", "mpegts", str(root / "big.ts"),
    )  # fmt: skip
    (root / "bigframes.ts").write_bytes(
        (root / "small.ts").read_bytes() + (root / "big.ts").read_bytes()
    )
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


def boxes(data: bytes, start: int, end: int) -> list[tuple[str, int, int]]:
    """MP4 boxes in order as (type, start, end) (ISO BMFF: 4-byte size, 4-byte type)."""
    found, offset = [], start
    while offset + 8 <= end:
        size = int.from_bytes(data[offset : offset + 4], "big")
        if size == 1:  # 64-bit size follows
            size = int.from_bytes(data[offset + 8 : offset + 16], "big")
        elif size == 0:  # runs to the end
            size = end - offset
        if size < 8:
            break
        found.append((data[offset + 4 : offset + 8].decode(), offset, offset + size))
        offset += size
    return found


def top_level_boxes(path: Path) -> list[str]:
    data = path.read_bytes()
    return [kind for kind, _, _ in boxes(data, 0, len(data))]


def move_cover_first(path: Path) -> None:
    """Puts moov's udta, where MP4 keeps cover art, before the track: the cover becomes stream 0.

    moov keeps its size and place, so the media offsets in it stay right.
    """
    data = path.read_bytes()
    _, start, end = next(box for box in boxes(data, 0, len(data)) if box[0] == "moov")
    children = sorted(boxes(data, start + 8, end), key=lambda box: box[0] != "udta")
    path.write_bytes(data[: start + 8] + b"".join(data[a:b] for _, a, b in children) + data[end:])


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


async def test_a_codec_outside_the_decoder_list_is_refused(
    db: AsyncSession, storage: Storage, samples: Path
) -> None:
    video = await uploaded(db, storage, samples / "ffv1.mkv")

    await pipeline.process(video.id)

    video = await reload(db, video)
    assert video.status is VideoStatus.FAILED


async def test_the_real_video_is_converted_not_the_cover_picture(
    db: AsyncSession, storage: Storage, s3: S3Client, samples: Path, tmp_path: Path
) -> None:
    assert probe(samples / "cover.mp4")["streams"][0]["disposition"]["attached_pic"] == 1
    found = await pipeline._probe(samples / "cover.mp4")  # pyright: ignore[reportPrivateUsage]
    assert (found.width, found.height) == (640, 360)
    video = await uploaded(db, storage, samples / "cover.mp4")

    await pipeline.process(video.id)

    video = await reload(db, video)
    assert video.status is VideoStatus.READY
    output = probe(await download(s3, video.media_key, tmp_path / "out.mp4"))
    assert [(s["width"], s["height"]) for s in output["streams"]] == [(640, 360)]
    assert video.duration_sec == 2


async def test_frames_over_8k_later_in_the_file_are_not_decoded(
    db: AsyncSession, storage: Storage, s3: S3Client, samples: Path, tmp_path: Path
) -> None:
    video = await uploaded(db, storage, samples / "bigframes.ts")

    await pipeline.process(video.id)

    video = await reload(db, video)
    assert video.status is VideoStatus.READY
    # Only the 25 small frames: the decoder refused the big ones instead of allocating them.
    output = await download(s3, video.media_key, tmp_path / "out.mp4")
    streams = probe(output, "-count_frames")["streams"]
    assert [(s["width"], s["height"], s["nb_read_frames"]) for s in streams] == [(320, 240, "25")]


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
    assert (video.status, video.error_message) == (VideoStatus.FAILED, GAVE_UP_REASON)
