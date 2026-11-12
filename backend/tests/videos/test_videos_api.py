"""/api/videos: drafts, details, the watch data and the file upload (ADR 0004, 0006)."""

import re
import secrets
from collections.abc import AsyncIterator, Callable, Coroutine, Iterator, Mapping
from dataclasses import dataclass
from datetime import timedelta
from typing import Any
from uuid import UUID

import anyio
import pytest
from botocore.exceptions import ClientError
from fastapi import FastAPI
from httpx2 import ASGITransport, AsyncClient, Cookies, Response
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.types import ASGIApp, Message, Receive, Scope, Send
from types_aiobotocore_s3 import S3Client

from app.core.rate_limit import RateLimit
from app.core.slots import Slots
from app.core.storage import PART_SIZE, get_storage_settings, open_s3_client
from app.modules.users.models import Role
from app.modules.videos import service
from app.modules.videos.config import MIB, get_video_settings
from app.modules.videos.models import Video, VideoAccess, VideoStatus
from app.worker.celery_app import celery_app
from tests.videos.factories import get_video, grant, set_role, set_status

PASSWORD = "correct horse battery"
OWNER_EMAIL = "owner@example.com"
STRANGER_EMAIL = "stranger@example.com"
MODERATOR_EMAIL = "moderator@example.com"
NOT_READY = [status for status in VideoStatus if status is not VideoStatus.READY]


# --- Clients and accounts ---


def browser(
    app: ASGIApp,
    ip: str = "127.0.0.1",
    origin: str | None = "http://test",
    cookies: Cookies | None = None,
) -> AsyncClient:
    """A client like another browser: its own IP and cookies. origin=None sends no Origin."""
    transport = ASGITransport(app=app, client=(ip, 1234))
    headers = {"Origin": origin} if origin else {}
    return AsyncClient(
        transport=transport, base_url="http://test", headers=headers, cookies=cookies
    )


def csrf(client: AsyncClient) -> dict[str, str]:
    """The header the web app adds to unsafe requests once it has a session."""
    token = client.cookies.get("csrf_token")
    return {"X-CSRF-Token": token} if token else {}


async def signup(client: AsyncClient, email: str) -> str:
    """Sign up and in; returns the handle."""
    response = await client.post("/api/auth/signup", json={"email": email, "password": PASSWORD})
    assert response.status_code == 201
    return response.json()["handle"]


async def handle_of(client: AsyncClient) -> str:
    return (await client.get("/api/auth/me")).json()["handle"]


@pytest.fixture
async def owner(db: AsyncSession, client: AsyncClient) -> AsyncClient:
    """`client`, signed in. After `db`: its reset would wipe the account."""
    await signup(client, OWNER_EMAIL)
    return client


@pytest.fixture
async def stranger(
    app: FastAPI, db: AsyncSession, client: AsyncClient
) -> AsyncIterator[AsyncClient]:
    """Another signed-in user. After `db` and `client`: their resets would wipe the account."""
    async with browser(app, "10.0.0.2") as other:
        await signup(other, STRANGER_EMAIL)
        yield other


@pytest.fixture
async def moderator(
    app: FastAPI, db: AsyncSession, client: AsyncClient
) -> AsyncIterator[AsyncClient]:
    async with browser(app, "10.0.0.3") as other:
        await signup(other, MODERATOR_EMAIL)
        await set_role(db, MODERATOR_EMAIL, Role.MODERATOR)
        yield other


@pytest.fixture
async def guest(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with browser(app, "10.0.0.4") as other:
        yield other


# --- Videos ---


async def post_draft(client: AsyncClient, **fields: object) -> Response:
    body = {"title": "My video", **fields}
    return await client.post("/api/videos", json=body, headers=csrf(client))


async def create_draft(client: AsyncClient, **fields: object) -> str:
    """A draft of the client's user; returns its public id."""
    response = await post_draft(client, **fields)
    assert response.status_code == 201
    return response.json()["id"]


async def video_in(
    owner: AsyncClient, db: AsyncSession, status: VideoStatus, visibility: str = "private"
) -> Video:
    """The owner's video in this status, as if the worker had moved it there."""
    return await set_status(db, await create_draft(owner, visibility=visibility), status)


async def edit(client: AsyncClient, public_id: str, changes: Mapping[str, object]) -> Response:
    return await client.patch(f"/api/videos/{public_id}", json=changes, headers=csrf(client))


@pytest.fixture
async def draft(owner: AsyncClient, db: AsyncSession) -> Video:
    """The owner's new draft, as its DB row: object keys come from its uuid."""
    return await get_video(db, await create_draft(owner))


# --- Uploads ---


async def upload(
    client: AsyncClient,
    public_id: str,
    content: bytes | AsyncIterator[bytes],
    headers: dict[str, str] | None = None,
) -> Response:
    return await client.put(
        f"/api/videos/{public_id}/file", content=content, headers=csrf(client) | (headers or {})
    )


async def streamed(content: bytes, chunk_size: int = 64 * 1024) -> AsyncIterator[bytes]:
    """The body in pieces, as a server receives it. httpx sends no Content-Length for it."""
    for start in range(0, len(content), chunk_size):
        yield content[start : start + chunk_size]


@dataclass(frozen=True)
class Queued:
    task: str
    video_id: str
    committed_status: VideoStatus | None  # what the worker would read at that moment


@pytest.fixture(autouse=True)
def queued(app: FastAPI, monkeypatch: pytest.MonkeyPatch) -> list[Queued]:
    """Tasks sent to the broker. No test talks to a real one."""
    calls: list[Queued] = []

    async def committed_status(video_id: str) -> VideoStatus | None:
        # Its own connection: it sees only committed rows, like the worker.
        async with app.state.sessionmaker() as session:
            return await session.scalar(select(Video.status).where(Video.id == UUID(video_id)))

    def send_task(name: str, args: list[str]) -> None:
        # Runs in a worker thread, like kombu's blocking call.
        calls.append(Queued(name, args[0], anyio.from_thread.run(committed_status, args[0])))

    monkeypatch.setattr(celery_app, "send_task", send_task)
    return calls


@pytest.fixture
def video_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[Callable[..., None]]:
    """Set video settings through env, as in production. None unsets a variable."""

    def set_env(**values: str | None) -> None:
        for name, value in values.items():
            if value is None:
                monkeypatch.delenv(name, raising=False)
            else:
                monkeypatch.setenv(name, value)
        get_video_settings.cache_clear()

    yield set_env
    get_video_settings.cache_clear()  # monkeypatch restores the env right after this


@pytest.fixture
def upload_limit(video_env: Callable[..., None]) -> int:
    """A 1 MiB limit: over-limit bodies stay small."""
    video_env(MAX_UPLOAD_SIZE_MB="1")
    return MIB


@pytest.fixture
async def s3(app: FastAPI) -> AsyncIterator[S3Client]:
    """A raw client to look at the bucket."""
    async with open_s3_client(get_storage_settings()) as client:
        yield client


async def read_object(s3: S3Client, key: str) -> bytes:
    response = await s3.get_object(Bucket=get_storage_settings().s3_bucket, Key=key)
    async with response["Body"] as body:
        return await body.read()


async def assert_still_a_draft(
    db: AsyncSession, s3: S3Client, queued: list[Queued], video: Video
) -> None:
    """A refused or cut-off upload: no object, no half-done upload, nothing queued, no change."""
    bucket = get_storage_settings().s3_bucket
    with pytest.raises(ClientError, match="404"):
        await s3.head_object(Bucket=bucket, Key=video.original_key)
    uploads = await s3.list_multipart_uploads(Bucket=bucket, Prefix=video.original_key)
    assert uploads.get("Uploads", []) == []
    assert queued == []
    assert (await get_video(db, video.public_id)).status is VideoStatus.UPLOADING


def cut_off_after_first_chunk(app: ASGIApp) -> ASGIApp:
    """The app behind a connection that drops after the first piece of the body."""

    async def wrapped(scope: Scope, receive: Receive, send: Send) -> None:
        received = False

        async def receive_until_cut_off() -> Message:
            nonlocal received
            if received:
                return {"type": "http.disconnect"}  # what the server sends when the client leaves
            received = True
            return await receive()

        await app(scope, receive_until_cut_off, send)

    return wrapped


# --- POST /api/videos ---


async def test_draft_is_created_private_and_waiting_for_its_file(client: AsyncClient) -> None:
    handle = await signup(client, OWNER_EMAIL)

    response = await client.post("/api/videos", json={"title": "My video"}, headers=csrf(client))

    assert response.status_code == 201
    body = response.json()
    assert re.fullmatch(r"[A-Za-z0-9_-]{11}", body["id"])
    assert {key: value for key, value in body.items() if key not in ("id", "created_at")} == {
        "title": "My video",
        "description": "",
        "visibility": "private",
        "category": "people",
        "status": "uploading",
        "error_message": None,
        "duration_sec": None,
        "is_hidden": False,
        "thumbnail_url": None,
        "media_url": None,
        "view_count": 0,
        "like_count": 0,
        "comment_count": 0,
        "channel": {"handle": handle, "name": handle, "avatar_url": None},
    }
    # The watch page data adds what this viewer did with the video.
    assert (await client.get(f"/api/videos/{body['id']}")).json() == body | {
        "my_rating": "none",
        "channel_terminated": False,
    }


async def test_draft_keeps_the_given_details(owner: AsyncClient) -> None:
    response = await post_draft(
        owner, description="About it", visibility="unlisted", category="music"
    )

    assert response.status_code == 201
    assert response.json()["description"] == "About it"
    assert response.json()["visibility"] == "unlisted"
    assert response.json()["category"] == "music"


async def test_draft_title_is_stripped(owner: AsyncClient) -> None:
    response = await post_draft(owner, title="  My video \n")

    assert response.status_code == 201
    assert response.json()["title"] == "My video"


async def test_draft_accepts_the_longest_title_and_description(owner: AsyncClient) -> None:
    response = await post_draft(owner, title="t" * 100, description="d" * 5000)

    assert response.status_code == 201


@pytest.mark.parametrize(
    "fields",
    [
        {"title": None},
        {"title": ""},
        {"title": "  \t "},
        {"title": "t" * 101},
        {"description": "d" * 5001},
        {"visibility": "secret"},
        {"category": "cats"},
    ],
    ids=[
        "null title",
        "empty title",
        "blank title",
        "long title",
        "long description",
        "visibility",
        "category",
    ],
)
async def test_draft_checks_input(
    owner: AsyncClient, db: AsyncSession, fields: dict[str, object]
) -> None:
    response = await post_draft(owner, **fields)

    assert response.status_code == 422
    assert await db.scalar(select(func.count()).select_from(Video)) == 0


async def test_guest_cannot_create_a_draft(client: AsyncClient) -> None:
    response = await post_draft(client)

    assert response.status_code == 401


@pytest.mark.parametrize(
    ("origin", "with_token"),
    [(None, True), ("http://evil.example", True), ("http://test", False)],
    ids=["no origin", "other site", "no csrf token"],
)
async def test_draft_needs_our_origin_and_the_csrf_token(
    app: FastAPI, owner: AsyncClient, db: AsyncSession, origin: str | None, with_token: bool
) -> None:
    headers = csrf(owner) if with_token else {}
    async with browser(app, origin=origin, cookies=owner.cookies) as other_site:
        response = await other_site.post("/api/videos", json={"title": "x"}, headers=headers)

    assert response.status_code == 403
    assert await db.scalar(select(func.count()).select_from(Video)) == 0


async def test_21st_draft_in_an_hour_is_refused(
    owner: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(service, "OPEN_DRAFTS_MAX", 100)  # only the hourly limit is tested here
    for _ in range(20):
        await create_draft(owner)

    response = await post_draft(owner)

    assert response.status_code == 429
    assert 0 < int(response.headers["retry-after"]) <= 60 * 60


async def test_draft_limit_is_per_user(
    owner: AsyncClient, stranger: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(service, "DRAFTS_PER_USER", RateLimit("video_draft", limit=1, window=60))
    await create_draft(owner)

    assert (await post_draft(owner)).status_code == 429
    assert (await post_draft(stranger)).status_code == 201


# --- GET /api/videos/upload-limits ---


async def test_upload_limits_default_to_1_gib_and_30_minutes(
    client: AsyncClient, video_env: Callable[..., None]
) -> None:
    video_env(MAX_UPLOAD_SIZE_MB=None, MAX_VIDEO_DURATION_SEC=None)

    response = await client.get("/api/videos/upload-limits")

    assert response.json() == {"max_size_bytes": 1024 * MIB, "max_duration_sec": 30 * 60}


async def test_upload_limits_come_from_env(
    client: AsyncClient, video_env: Callable[..., None]
) -> None:
    video_env(MAX_UPLOAD_SIZE_MB="3", MAX_VIDEO_DURATION_SEC="60")

    response = await client.get("/api/videos/upload-limits")

    assert response.status_code == 200
    assert response.json() == {"max_size_bytes": 3 * MIB, "max_duration_sec": 60}


# --- PATCH /api/videos/{id} ---


@pytest.mark.parametrize("status", list(VideoStatus))
async def test_owner_edits_details_in_any_status(
    owner: AsyncClient, db: AsyncSession, status: VideoStatus
) -> None:
    video = await video_in(owner, db, status)
    changes = {
        "title": " New title ",
        "description": "New description",
        "visibility": "public",
        "category": "music",
    }

    response = await edit(owner, video.public_id, changes)

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "New title"
    assert body["description"] == "New description"
    assert body["visibility"] == "public"
    assert body["category"] == "music"
    assert body["status"] == status.value
    page = await owner.get(f"/api/videos/{video.public_id}")
    assert page.json() == body | {"my_rating": "none", "channel_terminated": False}


async def test_null_and_missing_fields_are_left_as_they_are(owner: AsyncClient) -> None:
    public_id = await create_draft(
        owner, description="Old description", visibility="unlisted", category="music"
    )

    response = await edit(owner, public_id, {"title": "New title", "description": None})

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "New title"
    assert body["description"] == "Old description"
    assert body["visibility"] == "unlisted"
    assert body["category"] == "music"


async def test_empty_description_clears_it(owner: AsyncClient) -> None:
    public_id = await create_draft(owner, description="Old description")

    response = await edit(owner, public_id, {"description": ""})

    assert response.json()["description"] == ""


@pytest.mark.parametrize(
    "changes",
    [
        {"title": "  "},
        {"title": "t" * 101},
        {"description": "d" * 5001},
        {"visibility": "secret"},
        {"category": "cats"},
    ],
    ids=["blank title", "long title", "long description", "visibility", "category"],
)
async def test_edit_checks_input(
    owner: AsyncClient, db: AsyncSession, changes: dict[str, object]
) -> None:
    public_id = await create_draft(owner)

    response = await edit(owner, public_id, changes)

    assert response.status_code == 422
    assert (await get_video(db, public_id)).title == "My video"


async def test_stranger_gets_404_when_editing(
    owner: AsyncClient, stranger: AsyncClient, db: AsyncSession
) -> None:
    public_id = await create_draft(owner)

    response = await edit(stranger, public_id, {"title": "Mine now"})

    assert response.status_code == 404
    assert (await get_video(db, public_id)).title == "My video"


async def test_moderator_gets_404_when_editing(
    owner: AsyncClient, moderator: AsyncClient, db: AsyncSession
) -> None:
    video = await video_in(owner, db, VideoStatus.READY)

    response = await edit(moderator, video.public_id, {"title": "Moderated"})

    assert response.status_code == 404  # moderators may watch any video, not edit it


async def test_guest_cannot_edit(owner: AsyncClient, guest: AsyncClient) -> None:
    public_id = await create_draft(owner)

    response = await edit(guest, public_id, {"title": "Mine now"})

    assert response.status_code == 401


async def test_editing_an_unknown_video_is_404(owner: AsyncClient) -> None:
    response = await edit(owner, "nosuchvideo", {"title": "New title"})

    assert response.status_code == 404


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/api/videos/short"),
        ("PATCH", "/api/videos/has.a.dot.x"),
        ("PUT", "/api/videos/twelve_chars/file"),
    ],
)
async def test_malformed_id_is_422(owner: AsyncClient, method: str, path: str) -> None:
    response = await owner.request(method, path, json={"title": "x"}, headers=csrf(owner))

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["path", "public_id"]


# --- GET /api/videos/{id} ---


async def test_guest_gets_404_for_private_video(
    owner: AsyncClient, guest: AsyncClient, db: AsyncSession
) -> None:
    video = await video_in(owner, db, VideoStatus.READY, "private")

    response = await guest.get(f"/api/videos/{video.public_id}")

    assert response.status_code == 404


async def test_stranger_gets_404_for_private_video(
    owner: AsyncClient, stranger: AsyncClient, db: AsyncSession
) -> None:
    video = await video_in(owner, db, VideoStatus.READY, "private")

    response = await stranger.get(f"/api/videos/{video.public_id}")

    # The same answer as for an unknown id: a stranger can't tell that the video exists.
    unknown = await stranger.get("/api/videos/nosuchvideo")
    assert response.status_code == unknown.status_code == 404
    assert response.json() == unknown.json()


async def test_owner_sees_their_private_video(owner: AsyncClient, db: AsyncSession) -> None:
    video = await video_in(owner, db, VideoStatus.READY, "private")

    response = await owner.get(f"/api/videos/{video.public_id}")

    assert response.status_code == 200


async def test_user_with_a_grant_sees_private_video(
    owner: AsyncClient, stranger: AsyncClient, db: AsyncSession
) -> None:
    video = await video_in(owner, db, VideoStatus.READY, "private")
    await grant(db, video.public_id, STRANGER_EMAIL)

    response = await stranger.get(f"/api/videos/{video.public_id}")

    assert response.status_code == 200


async def test_moderator_sees_private_video(
    owner: AsyncClient, moderator: AsyncClient, db: AsyncSession
) -> None:
    video = await video_in(owner, db, VideoStatus.READY, "private")

    response = await moderator.get(f"/api/videos/{video.public_id}")

    assert response.status_code == 200


@pytest.mark.parametrize("visibility", ["public", "unlisted"])
async def test_guest_sees_public_and_unlisted_videos(
    owner: AsyncClient, guest: AsyncClient, db: AsyncSession, visibility: str
) -> None:
    video = await video_in(owner, db, VideoStatus.READY, visibility)

    response = await guest.get(f"/api/videos/{video.public_id}")

    assert response.status_code == 200
    assert response.json()["channel"]["handle"] == await handle_of(owner)


@pytest.mark.parametrize("status", NOT_READY)
async def test_unfinished_video_is_hidden_from_others(
    owner: AsyncClient,
    stranger: AsyncClient,
    guest: AsyncClient,
    db: AsyncSession,
    status: VideoStatus,
) -> None:
    video = await video_in(owner, db, status, "public")

    assert (await guest.get(f"/api/videos/{video.public_id}")).status_code == 404
    assert (await stranger.get(f"/api/videos/{video.public_id}")).status_code == 404


@pytest.mark.parametrize("status", NOT_READY)
async def test_owner_sees_their_unfinished_video_without_media(
    owner: AsyncClient, db: AsyncSession, status: VideoStatus
) -> None:
    video = await video_in(owner, db, status)

    response = await owner.get(f"/api/videos/{video.public_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == status.value
    assert body["media_url"] is None
    assert body["thumbnail_url"] is None


async def test_owner_sees_why_processing_failed(owner: AsyncClient, db: AsyncSession) -> None:
    video = await video_in(owner, db, VideoStatus.FAILED)

    response = await owner.get(f"/api/videos/{video.public_id}")

    assert response.json()["error_message"] == "Not a video"


async def test_ready_video_has_media_and_thumbnail_urls(
    owner: AsyncClient, db: AsyncSession
) -> None:
    video = await video_in(owner, db, VideoStatus.READY)

    response = await owner.get(f"/api/videos/{video.public_id}")

    body = response.json()
    assert body["media_url"] == f"/media/videos/{video.id}/720p.mp4"
    assert body["thumbnail_url"] == f"/media/thumbs/{video.id}.jpg"
    assert body["duration_sec"] == 10


# --- PUT /api/videos/{id}/file ---


async def test_upload_stores_the_file_and_queues_processing(
    owner: AsyncClient, s3: S3Client, queued: list[Queued], draft: Video
) -> None:
    content = secrets.token_bytes(1000)

    response = await upload(owner, draft.public_id, content)

    assert response.status_code == 200
    assert response.json()["status"] == "uploaded"
    assert await read_object(s3, f"originals/{draft.id}") == content
    # Once, and after `uploaded` was committed: the worker must find the video uploaded.
    assert queued == [Queued("videos.process", str(draft.id), VideoStatus.UPLOADED)]


async def test_upload_ignores_the_clients_content_type(
    owner: AsyncClient, s3: S3Client, draft: Video
) -> None:
    await upload(owner, draft.public_id, b"<html>", {"Content-Type": "text/html"})

    head = await s3.head_object(Bucket=get_storage_settings().s3_bucket, Key=draft.original_key)
    assert head["ContentType"] == "application/octet-stream"


async def test_upload_bigger_than_one_part_is_stored_in_parts(
    owner: AsyncClient, s3: S3Client, draft: Video
) -> None:
    content = secrets.token_bytes(PART_SIZE + 1)

    response = await upload(owner, draft.public_id, streamed(content))

    assert response.status_code == 200
    assert await read_object(s3, draft.original_key) == content
    head = await s3.head_object(Bucket=get_storage_settings().s3_bucket, Key=draft.original_key)
    assert head["ETag"].endswith('-2"')  # a multipart ETag ends with the part count


async def test_upload_is_kept_when_the_broker_is_down(
    owner: AsyncClient, s3: S3Client, draft: Video, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broker_down(*args: object, **kwargs: object) -> None:
        raise ConnectionError("Redis is down")

    monkeypatch.setattr(celery_app, "send_task", broker_down)

    response = await upload(owner, draft.public_id, b"the whole file")

    assert response.status_code == 200
    assert response.json()["status"] == "uploaded"  # the sweeper queues it later (ADR 0003)
    assert await read_object(s3, draft.original_key) == b"the whole file"


async def test_stranger_gets_404_when_uploading(
    stranger: AsyncClient, db: AsyncSession, s3: S3Client, queued: list[Queued], draft: Video
) -> None:
    response = await upload(stranger, draft.public_id, b"not yours")

    assert response.status_code == 404
    await assert_still_a_draft(db, s3, queued, draft)


async def test_guest_cannot_upload(
    guest: AsyncClient, db: AsyncSession, s3: S3Client, queued: list[Queued], draft: Video
) -> None:
    response = await upload(guest, draft.public_id, b"the whole file")

    assert response.status_code == 401
    await assert_still_a_draft(db, s3, queued, draft)


async def test_upload_needs_the_csrf_token(
    owner: AsyncClient, db: AsyncSession, s3: S3Client, queued: list[Queued], draft: Video
) -> None:
    response = await owner.put(f"/api/videos/{draft.public_id}/file", content=b"the whole file")

    assert response.status_code == 403
    await assert_still_a_draft(db, s3, queued, draft)


async def test_second_upload_is_409_and_keeps_the_first_file(
    owner: AsyncClient, s3: S3Client, draft: Video
) -> None:
    await upload(owner, draft.public_id, b"first file")

    response = await upload(owner, draft.public_id, b"second file")

    assert response.status_code == 409
    assert response.json() == {"detail": "This video already has a file"}
    assert await read_object(s3, draft.original_key) == b"first file"


@pytest.mark.parametrize("status", [s for s in VideoStatus if s is not VideoStatus.UPLOADING])
async def test_upload_after_the_draft_stage_is_409(
    owner: AsyncClient, db: AsyncSession, s3: S3Client, status: VideoStatus
) -> None:
    video = await video_in(owner, db, status)

    response = await upload(owner, video.public_id, b"the whole file")

    assert response.status_code == 409
    with pytest.raises(ClientError, match="404"):
        await s3.head_object(Bucket=get_storage_settings().s3_bucket, Key=video.original_key)


async def test_upload_of_exactly_the_limit_is_accepted(
    owner: AsyncClient, s3: S3Client, draft: Video, upload_limit: int
) -> None:
    response = await upload(owner, draft.public_id, b"x" * upload_limit)

    assert response.status_code == 200
    head = await s3.head_object(Bucket=get_storage_settings().s3_bucket, Key=draft.original_key)
    assert head["ContentLength"] == upload_limit


async def test_upload_declared_over_the_limit_is_refused_before_reading(
    owner: AsyncClient,
    db: AsyncSession,
    s3: S3Client,
    queued: list[Queued],
    draft: Video,
    upload_limit: int,
) -> None:
    read = False

    async def body() -> AsyncIterator[bytes]:
        nonlocal read
        read = True
        yield b"x"

    response = await upload(
        owner, draft.public_id, body(), {"Content-Length": str(upload_limit + 1)}
    )

    assert response.status_code == 413
    assert response.json() == {"detail": "The file is larger than 1 MB"}
    assert not read
    await assert_still_a_draft(db, s3, queued, draft)
    assert (await upload(owner, draft.public_id, b"the whole file")).status_code == 200


@pytest.mark.parametrize(
    "headers", [{}, {"Content-Length": "100"}], ids=["no length", "lying length"]
)
async def test_upload_over_the_limit_is_refused_mid_stream(
    owner: AsyncClient,
    db: AsyncSession,
    s3: S3Client,
    queued: list[Queued],
    draft: Video,
    upload_limit: int,
    headers: dict[str, str],
) -> None:
    response = await upload(owner, draft.public_id, streamed(b"x" * (upload_limit + 1)), headers)

    assert response.status_code == 413
    assert response.json() == {"detail": "The file is larger than 1 MB"}
    await assert_still_a_draft(db, s3, queued, draft)
    # The lock was released: the client can retry.
    assert (await upload(owner, draft.public_id, b"the whole file")).status_code == 200


async def test_empty_upload_is_refused(
    owner: AsyncClient, db: AsyncSession, s3: S3Client, queued: list[Queued], draft: Video
) -> None:
    response = await upload(owner, draft.public_id, b"")

    assert response.status_code == 400
    assert response.json() == {"detail": "The file is empty"}
    await assert_still_a_draft(db, s3, queued, draft)
    assert (await upload(owner, draft.public_id, b"the whole file")).status_code == 200


async def test_second_upload_while_one_is_running_is_409(
    owner: AsyncClient, queued: list[Queued], draft: Video
) -> None:
    waiting_for_more = anyio.Event()
    go_on = anyio.Event()
    responses: dict[str, Response] = {}

    async def slow_body() -> AsyncIterator[bytes]:
        yield b"first half "
        waiting_for_more.set()  # the server holds the upload lock now
        await go_on.wait()
        yield b"second half"

    async def first_upload() -> None:
        responses["first"] = await upload(owner, draft.public_id, slow_body())

    with anyio.fail_after(10):  # a hang here is a bug
        async with anyio.create_task_group() as tasks:
            tasks.start_soon(first_upload)
            await waiting_for_more.wait()
            responses["second"] = await upload(owner, draft.public_id, b"another file")
            go_on.set()

    assert responses["second"].status_code == 409
    assert responses["second"].json() == {"detail": "This video is already being uploaded"}
    assert responses["first"].status_code == 200
    assert responses["first"].json()["status"] == "uploaded"
    assert len(queued) == 1


async def test_upload_failing_mid_stream_stores_nothing(
    owner: AsyncClient, db: AsyncSession, s3: S3Client, queued: list[Queued], draft: Video
) -> None:
    async def broken_body() -> AsyncIterator[bytes]:
        yield b"x" * PART_SIZE  # one part is already in MinIO
        raise ConnectionResetError("client went away")

    # The ASGI test transport passes the error into the app and back out.
    with pytest.raises(ConnectionResetError):
        await upload(owner, draft.public_id, broken_body())

    await assert_still_a_draft(db, s3, queued, draft)
    # The lock was released: the client can retry.
    assert (await upload(owner, draft.public_id, b"the whole file")).status_code == 200


async def test_long_upload_renews_its_lock(
    owner: AsyncClient, monkeypatch: pytest.MonkeyPatch, app: FastAPI, draft: Video
) -> None:
    monkeypatch.setattr(service, "UPLOAD_LOCK_RENEW_SECONDS", -1)  # renew on every chunk
    ttls: list[int] = []

    async def body() -> AsyncIterator[bytes]:
        for _ in range(3):
            yield b"x" * 1024
            # Runs once the chunk went on: did it renew the lock we shortened before it?
            ttls.append(await app.state.redis.ttl(f"upload:{draft.id}"))
            await app.state.redis.expire(f"upload:{draft.id}", 5)  # as if time went by

    response = await upload(owner, draft.public_id, body())

    assert response.status_code == 200
    assert all(ttl > 5 for ttl in ttls[1:])  # back to the full lifetime each time


async def test_upload_that_lost_its_lock_stops(
    owner: AsyncClient,
    db: AsyncSession,
    s3: S3Client,
    queued: list[Queued],
    monkeypatch: pytest.MonkeyPatch,
    app: FastAPI,
    draft: Video,
) -> None:
    monkeypatch.setattr(service, "UPLOAD_LOCK_RENEW_SECONDS", -1)

    async def body() -> AsyncIterator[bytes]:
        yield b"x" * 1024
        await app.state.redis.delete(f"upload:{draft.id}")  # expired, e.g. Redis restarted
        yield b"y" * 1024

    response = await upload(owner, draft.public_id, body())

    assert response.status_code == 409
    assert response.json() == {"detail": "The upload was interrupted. Try again."}
    await assert_still_a_draft(db, s3, queued, draft)


async def test_dropped_connection_mid_upload_is_400_and_stores_nothing(
    app: FastAPI,
    owner: AsyncClient,
    db: AsyncSession,
    s3: S3Client,
    queued: list[Queued],
    draft: Video,
) -> None:
    async with browser(cut_off_after_first_chunk(app), cookies=owner.cookies) as dropping:
        response = await upload(dropping, draft.public_id, streamed(b"x" * 1000, chunk_size=100))

    assert response.status_code == 400
    assert response.json() == {"detail": "The upload was interrupted"}
    await assert_still_a_draft(db, s3, queued, draft)
    assert (await upload(owner, draft.public_id, b"the whole file")).status_code == 200


# --- Sharing a private video ---


async def share(client: AsyncClient, public_id: str, handle: str) -> Response:
    return await client.post(
        f"/api/videos/{public_id}/access", json={"handle": handle}, headers=csrf(client)
    )


async def unshare(client: AsyncClient, public_id: str, handle: str) -> Response:
    return await client.delete(f"/api/videos/{public_id}/access/{handle}", headers=csrf(client))


async def test_shared_private_video_can_be_watched_until_unshared(
    owner: AsyncClient, stranger: AsyncClient, db: AsyncSession
) -> None:
    video = await video_in(owner, db, VideoStatus.READY)
    handle = await handle_of(stranger)
    assert (await stranger.get(f"/api/videos/{video.public_id}")).status_code == 404

    assert (await share(owner, video.public_id, handle)).status_code == 204
    assert (await stranger.get(f"/api/videos/{video.public_id}")).status_code == 200

    assert (await unshare(owner, video.public_id, handle)).status_code == 204
    assert (await stranger.get(f"/api/videos/{video.public_id}")).status_code == 404


async def test_sharing_twice_is_fine(
    owner: AsyncClient, stranger: AsyncClient, db: AsyncSession
) -> None:
    video = await video_in(owner, db, VideoStatus.READY)
    handle = await handle_of(stranger)

    assert (await share(owner, video.public_id, handle)).status_code == 204
    assert (await share(owner, video.public_id, handle.upper())).status_code == 204  # citext

    assert await db.scalar(select(func.count()).select_from(VideoAccess)) == 1


async def test_only_the_owner_shares(
    owner: AsyncClient, stranger: AsyncClient, moderator: AsyncClient, db: AsyncSession
) -> None:
    video = await video_in(owner, db, VideoStatus.READY)
    handle = await handle_of(stranger)

    assert (await share(stranger, video.public_id, handle)).status_code == 404
    assert (await share(moderator, video.public_id, handle)).status_code == 404
    assert (await unshare(stranger, video.public_id, handle)).status_code == 404
    assert await db.scalar(select(func.count()).select_from(VideoAccess)) == 0


async def test_guest_cannot_share(owner: AsyncClient, guest: AsyncClient, db: AsyncSession) -> None:
    video = await video_in(owner, db, VideoStatus.READY)

    assert (await share(guest, video.public_id, "someone")).status_code == 401


async def test_sharing_needs_the_csrf_token(
    owner: AsyncClient, stranger: AsyncClient, db: AsyncSession
) -> None:
    video = await video_in(owner, db, VideoStatus.READY)
    url = f"/api/videos/{video.public_id}/access"

    response = await owner.post(url, json={"handle": await handle_of(stranger)})

    assert response.status_code == 403


async def test_sharing_with_an_unknown_handle_is_404(owner: AsyncClient, db: AsyncSession) -> None:
    video = await video_in(owner, db, VideoStatus.READY)

    response = await share(owner, video.public_id, "no-such-user")

    assert response.status_code == 404
    assert response.json() == {"detail": "No user with this handle"}


async def test_sharing_with_yourself_is_refused(owner: AsyncClient, db: AsyncSession) -> None:
    video = await video_in(owner, db, VideoStatus.READY)

    response = await share(owner, video.public_id, await handle_of(owner))

    assert response.status_code == 400


@pytest.mark.parametrize("handle", ["ab", "x" * 31, "@anna", "an na"])
async def test_sharing_checks_the_handle(owner: AsyncClient, db: AsyncSession, handle: str) -> None:
    video = await video_in(owner, db, VideoStatus.READY)

    assert (await share(owner, video.public_id, handle)).status_code == 422


async def test_unsharing_an_unknown_handle_is_fine(owner: AsyncClient, db: AsyncSession) -> None:
    video = await video_in(owner, db, VideoStatus.READY)

    assert (await unshare(owner, video.public_id, "no-such-user")).status_code == 204


# --- Upload limits per user and in total (ADR 0006) ---


async def test_unfinished_drafts_are_capped(
    owner: AsyncClient, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(service, "OPEN_DRAFTS_MAX", 2)
    first = await create_draft(owner)
    await create_draft(owner)

    refused = await post_draft(owner)
    assert refused.status_code == 409
    assert refused.json() == {"detail": "You have 2 unfinished uploads. Finish one first."}

    # A draft that got its file no longer counts; nor does one abandoned over a day ago.
    await set_status(db, first, VideoStatus.UPLOADED)
    second = await create_draft(owner)
    await db.execute(
        update(Video)
        .where(Video.public_id == second)
        .values(created_at=func.now() - timedelta(days=2))
    )
    await db.commit()
    assert (await post_draft(owner)).status_code == 201


async def test_parallel_drafts_cannot_pass_the_cap(
    owner: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(service, "OPEN_DRAFTS_MAX", 3)
    codes: list[int] = []

    async def one() -> None:
        codes.append((await post_draft(owner)).status_code)

    async with anyio.create_task_group() as tasks:
        for _ in range(8):
            tasks.start_soon(one)

    assert sorted(codes) == [201] * 3 + [409] * 5


async def hold_an_upload(
    client: AsyncClient, public_id: str, results: dict[str, Response]
) -> tuple[anyio.Event, anyio.Event, Callable[[], Coroutine[Any, Any, None]]]:
    """An upload that stops mid-body until `go_on` is set; `started` says its slot is taken."""
    started, go_on = anyio.Event(), anyio.Event()

    async def body() -> AsyncIterator[bytes]:
        yield b"first half "
        started.set()
        await go_on.wait()
        yield b"second half"

    async def run() -> None:
        results[public_id] = await upload(client, public_id, body())

    return started, go_on, run


async def test_uploads_at_once_are_capped_per_user(
    owner: AsyncClient, monkeypatch: pytest.MonkeyPatch, queued: list[Queued]
) -> None:
    monkeypatch.setattr(service, "UPLOADS_PER_USER", Slots("uploads_user", limit=1, ttl=60))
    first, second = await create_draft(owner), await create_draft(owner)
    results: dict[str, Response] = {}
    started, go_on, run = await hold_an_upload(owner, first, results)

    with anyio.fail_after(10):
        async with anyio.create_task_group() as tasks:
            tasks.start_soon(run)
            await started.wait()
            results["refused"] = await upload(owner, second, b"another file")
            go_on.set()

    assert results["refused"].status_code == 429
    assert results["refused"].json() == {
        "detail": "Too many uploads at once. Wait for one to finish."
    }
    assert results[first].status_code == 200
    # The finished upload gave its slot back.
    assert (await upload(owner, second, b"another file")).status_code == 200


async def test_uploads_at_once_are_capped_in_total(
    owner: AsyncClient, stranger: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(service, "UPLOADS_TOTAL", Slots("uploads_total", limit=1, ttl=60))
    mine, theirs = await create_draft(owner), await create_draft(stranger)
    results: dict[str, Response] = {}
    started, go_on, run = await hold_an_upload(owner, mine, results)

    with anyio.fail_after(10):
        async with anyio.create_task_group() as tasks:
            tasks.start_soon(run)
            await started.wait()
            results["refused"] = await upload(stranger, theirs, b"their file")
            go_on.set()

    assert results["refused"].status_code == 429
    assert (await upload(stranger, theirs, b"their file")).status_code == 200


async def test_a_failed_upload_gives_its_slot_back(
    owner: AsyncClient, monkeypatch: pytest.MonkeyPatch, draft: Video
) -> None:
    monkeypatch.setattr(service, "UPLOADS_PER_USER", Slots("uploads_user", limit=1, ttl=60))

    async def broken_body() -> AsyncIterator[bytes]:
        yield b"x" * 1024
        raise ConnectionResetError("client went away")

    with pytest.raises(ConnectionResetError):
        await upload(owner, draft.public_id, broken_body())

    assert (await upload(owner, draft.public_id, b"the whole file")).status_code == 200


async def test_upload_over_the_deadline_is_refused(
    owner: AsyncClient,
    db: AsyncSession,
    s3: S3Client,
    queued: list[Queued],
    monkeypatch: pytest.MonkeyPatch,
    draft: Video,
) -> None:
    monkeypatch.setattr(service, "UPLOAD_DEADLINE_SEC", 0.5)

    async def trickle() -> AsyncIterator[bytes]:
        yield b"x" * PART_SIZE  # one part already in MinIO
        await anyio.sleep_forever()  # then nothing more: a client holding the slot
        yield b""  # pragma: no cover

    with anyio.fail_after(10):
        response = await upload(owner, draft.public_id, trickle())

    assert response.status_code == 408
    await assert_still_a_draft(db, s3, queued, draft)
    assert (await upload(owner, draft.public_id, b"the whole file")).status_code == 200
