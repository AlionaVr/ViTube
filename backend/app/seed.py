"""Demo data for a fresh deployment: accounts, then the videos from demo-data/ (ADR 0008).

install.sh runs it after the stack is up: docker compose run --rm seed. Each step finds its row by
a natural key first (an account by email, a video by owner and title), so a re-run changes nothing
or goes on from where a failed run stopped. An uploaded video is never uploaded again.
"""

import asyncio
import json
import logging
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.core.redis import create_redis
from app.core.storage import Storage, get_storage_settings, open_storage, read_chunks
from app.db.session import create_engine, create_sessionmaker
from app.modules.auth.passwords import hash_password, verify_password
from app.modules.users import repository as users
from app.modules.users.models import Role
from app.modules.videos import repository as videos
from app.modules.videos import service as video_service
from app.modules.videos.models import Category, Video, VideoStatus, Visibility
from app.modules.videos.schemas import VideoCreate

log = logging.getLogger("app.seed")  # not __main__ under python -m

POLL_SECONDS = 2.0
PROCESSING_TIMEOUT_SEC = 10 * 60  # the three demo clips take about a minute
DONE = (VideoStatus.READY, VideoStatus.FAILED)


class SeedSettings(BaseSettings):
    """Only the seed reads them."""

    demo_password: SecretStr = Field(min_length=16)  # refuses "change-me" from .env.example
    demo_data_dir: Path = Path("/demo-data")


@dataclass(frozen=True)
class Account:
    email: str
    handle: str
    role: Role = Role.USER


ACCOUNTS = (
    Account("admin@example.com", "admin", Role.ADMIN),
    Account("moderator@example.com", "moderator", Role.MODERATOR),
    Account("openmovies@example.com", "open-movies"),
    Account("nature@example.com", "nature-clips"),
    Account("anna@example.com", "anna"),
    Account("ben@example.com", "ben"),
)


@dataclass(frozen=True)
class Upload:
    file: str  # in demo-data/videos; title and description come from demo-data/videos.json
    owner: str  # an account's email
    category: Category


UPLOADS = (
    Upload("big-buck-bunny-trailer.mp4", "openmovies@example.com", Category.FILM),
    Upload("sintel-trailer.mp4", "openmovies@example.com", Category.FILM),
    Upload("flower.mp4", "nature@example.com", Category.SCIENCE),
)


class SeedError(Exception):
    """Stops the seed with a message instead of a traceback."""


async def ensure_accounts(db: AsyncSession, password: str) -> None:
    """Create the missing demo accounts. A role is given only at creation: never changed later."""
    for account in ACCOUNTS:
        user = await users.get_by_email(db, account.email)
        if user is None:
            user = await users.insert_unless_taken(
                db,
                email=account.email,
                handle=account.handle,
                password_hash=await hash_password(password),
                role=account.role,
            )
            if user is None:
                raise SeedError(f"{account.email} or @{account.handle} belongs to another account")
            await db.commit()
            log.info("Created %s (@%s, %s)", account.email, account.handle, account.role.value)
        # The site is open while the seed runs: someone may have signed up with a demo email.
        elif not await verify_password(user.password_hash, password):
            raise SeedError(
                f"{account.email} exists with a password other than DEMO_PASSWORD; "
                "the seed doesn't touch it. Delete that account or change DEMO_PASSWORD back."
            )


async def ensure_videos(
    db: AsyncSession, redis: Redis, storage: Storage, demo_dir: Path
) -> dict[str, UUID]:
    """Upload the demo videos that are missing and queue the ones not processed yet.

    Returns the ids of the demo videos found or uploaded, by file name.
    """
    meta = {entry["file"]: entry for entry in _read_videos_json(demo_dir)}
    ids: dict[str, UUID] = {}
    for upload in UPLOADS:
        path = demo_dir / "videos" / upload.file
        if not path.is_file():
            log.warning("Skipped %s: not found. Run python3 demo-data/download.py", upload.file)
            continue
        owner = await users.get_by_email(db, upload.owner)
        if owner is None:  # ensure_accounts ran first
            raise SeedError(f"No account {upload.owner}")
        title = meta[upload.file]["title"]
        video = await videos.get_owned_by_title(db, owner.id, title)
        if video is None:
            draft = VideoCreate(
                title=title,
                description=meta[upload.file]["description"],
                visibility=Visibility.PUBLIC,
                category=upload.category,
            )
            created = await video_service.create_draft(db, redis, owner, draft)
            video = await videos.get_by_public_id(db, created.id)
            if video is None:  # just committed
                raise SeedError(f"The draft of {upload.file} is gone")
        if video.status is VideoStatus.UPLOADING:
            await video_service.upload_file(
                db, redis, storage, owner, video.public_id, read_chunks(path), path.stat().st_size
            )
            log.info("Uploaded %s", upload.file)
        elif video.status is VideoStatus.UPLOADED:
            # A run stopped before the worker took it; the worker skips a duplicate.
            await video_service.enqueue_processing(video.id)
        ids[upload.file] = video.id
    return ids


async def wait_until_processed(db: AsyncSession, ids: Sequence[UUID]) -> dict[UUID, VideoStatus]:
    """Poll until the worker has finished every video. Raises on timeout: a re-run waits again."""
    deadline = asyncio.timeout(PROCESSING_TIMEOUT_SEC)
    try:
        async with deadline:
            while True:
                # Plain columns, not Video objects: the session would hand back its cached status.
                query = select(Video.id, Video.status).where(Video.id.in_(ids))
                statuses = dict((await db.execute(query)).all())
                await db.commit()  # no transaction stays open while we sleep
                if all(status in DONE for status in statuses.values()):
                    return statuses
                await asyncio.sleep(POLL_SECONDS)
    except TimeoutError:
        if deadline.expired():  # ours, not a library's own timeout
            raise SeedError("The worker didn't process the demo videos in time") from None
        raise


async def run(
    sessionmaker: async_sessionmaker[AsyncSession],
    redis: Redis,
    storage: Storage,
    settings: SeedSettings,
) -> None:
    # A session per phase, as the API has one per request.
    password = settings.demo_password.get_secret_value()
    async with sessionmaker() as db:
        await ensure_accounts(db, password)
    async with sessionmaker() as db:
        ids = await ensure_videos(db, redis, storage, settings.demo_data_dir)
    async with sessionmaker() as db:
        statuses = await wait_until_processed(db, list(ids.values()))
    for file, video_id in ids.items():
        if statuses[video_id] is VideoStatus.FAILED:  # never retried: the file won't change
            log.warning("Demo video %s failed processing; see the worker's log", file)


def _read_videos_json(demo_dir: Path) -> list[dict[str, Any]]:
    return json.loads((demo_dir / "videos.json").read_text())["videos"]


async def _main() -> None:
    seed_settings = SeedSettings()  # pyright: ignore[reportCallIssue]
    settings = get_settings()
    engine = create_engine(settings)
    redis = create_redis(settings)
    try:
        async with open_storage(get_storage_settings()) as storage:
            await run(create_sessionmaker(engine), redis, storage, seed_settings)
    finally:
        await redis.aclose()
        await engine.dispose()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    try:
        asyncio.run(_main())
    except SeedError as error:
        log.error("%s", error)
        sys.exit(1)
    log.info("Demo data is ready")


if __name__ == "__main__":
    main()
