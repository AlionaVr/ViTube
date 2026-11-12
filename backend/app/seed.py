"""Demo data for a fresh deployment: accounts, the videos from demo-data/, then what people do with
them: views, likes, comments, subscriptions, playlists and one report (ADR 0008).

install.sh runs it after the stack is up: docker compose run --rm --no-deps seed. Each step finds
its row by a natural key first (an account by email, a video by owner and title, a comment by
author and text), so a re-run changes nothing or goes on from where a failed run stopped. An
uploaded video is never uploaded again, and nothing a moderator removed comes back. Each step acts
as its account the way the API does, so a banned or terminated account does nothing.

The keys are what people see, so a re-run doesn't know what they changed: a demo video or playlist
whose owner renamed it is made again, and a like or subscription a demo account took back returns.
"""

import asyncio
import json
import logging
import sys
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Concatenate
from uuid import UUID

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.core.errors import DomainError
from app.core.redis import create_redis
from app.core.storage import Storage, get_storage_settings, open_storage, read_chunks
from app.db.session import create_engine, create_sessionmaker
from app.modules.auth.passwords import hash_password, verify_password
from app.modules.channels import service as channels
from app.modules.comments import repository as comments
from app.modules.comments import service as comment_service
from app.modules.comments.schemas import CommentIn
from app.modules.playlists import repository as playlists
from app.modules.playlists import service as playlist_service
from app.modules.playlists.schemas import PlaylistCreate
from app.modules.reactions import service as reactions
from app.modules.reactions.schemas import Rating
from app.modules.reports import repository as reports
from app.modules.reports import service as report_service
from app.modules.reports.models import ReportReason
from app.modules.reports.schemas import ReportIn
from app.modules.users import repository as users
from app.modules.users.models import Role, User, UserStatus
from app.modules.videos import repository as videos
from app.modules.videos import service as video_service
from app.modules.videos.models import Category, Video, VideoStatus, Visibility
from app.modules.videos.schemas import VideoCreate
from app.modules.views import repository as views

log = logging.getLogger("app.seed")  # not __main__ under python -m

POLL_SECONDS = 2.0
PROCESSING_TIMEOUT_SEC = 10 * 60  # the three demo clips take about a minute
DONE = (VideoStatus.READY, VideoStatus.FAILED)


class SeedSettings(BaseSettings):
    """Only the seed reads them."""

    model_config = SettingsConfigDict(hide_input_in_errors=True)  # a short password isn't printed
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
class DemoComment:
    author: str  # a handle, as everywhere below
    text: str  # as the API stores it: stripped
    liked_by: tuple[str, ...] = ()
    reported_by: tuple[str, ...] = ()  # as spam
    replies: tuple["DemoComment", ...] = ()


@dataclass(frozen=True)
class Upload:
    file: str  # in demo-data/videos; title and description come from demo-data/videos.json
    owner: str
    category: Category
    liked_by: tuple[str, ...] = ()
    comments: tuple[DemoComment, ...] = ()
    saved_by: tuple[str, ...] = ()  # to Watch later


UPLOADS = (
    Upload(
        "big-buck-bunny-trailer.mp4",
        "open-movies",
        Category.FILM,
        liked_by=("anna", "ben", "nature-clips"),
        comments=(
            DemoComment(
                "anna",
                "The squirrels steal the show every time.",
                liked_by=("ben", "open-movies"),
                replies=(
                    DemoComment("ben", "The flying squirrel at the end gets me."),
                    DemoComment("open-movies", "Thanks for watching! The whole film is free."),
                ),
            ),
            DemoComment("ben", "Made with open-source tools in 2008, and it still looks great."),
        ),
    ),
    Upload(
        "sintel-trailer.mp4",
        "open-movies",
        Category.FILM,
        liked_by=("anna", "ben"),
        comments=(
            DemoComment("ben", "That music gives me chills.", liked_by=("anna",)),
            DemoComment(
                "anna",
                "A girl and her dragon. I'm not ready for that ending again.",
                replies=(DemoComment("ben", "Nobody is."),),
            ),
            DemoComment(
                "ben",
                "Free gift cards for the first 100 viewers!!! Visit example.com/gift",
                reported_by=("anna",),
            ),
        ),
        saved_by=("nature-clips",),
    ),
    Upload(
        "flower.mp4",
        "nature-clips",
        Category.SCIENCE,
        liked_by=("anna",),
        comments=(
            DemoComment(
                "anna",
                "Five seconds of calm. Thank you.",
                replies=(DemoComment("nature-clips", "Glad you liked it!"),),
            ),
        ),
        saved_by=("ben",),
    ),
)

SUBSCRIPTIONS = (("anna", "open-movies"), ("anna", "nature-clips"), ("ben", "open-movies"))


@dataclass(frozen=True)
class DemoPlaylist:
    owner: str
    title: str
    files: tuple[str, ...]


PLAYLISTS = (
    DemoPlaylist("anna", "Open movies", ("big-buck-bunny-trailer.mp4", "sintel-trailer.mp4")),
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


class Actors:
    """Service calls as the demo accounts, each read the way the API reads a signed-in user for a
    write (auth.deps): with the account's write lock, in the transaction of the write."""

    def __init__(self, db: AsyncSession, redis: Redis, ids: Mapping[str, UUID]) -> None:
        self.db = db
        self.redis = redis
        self.ids = ids  # by handle

    async def active(self, handle: str, what: str) -> User | None:
        """The account, with its write lock until the next commit: a ban waits for the step under
        way, and no step commits after a ban (ADR 0005). None if it is restricted: skip the step."""
        user = await users.get_for_write(self.db, self.ids[handle])
        if user is None or user.status is not UserStatus.ACTIVE:
            await self.db.rollback()  # ends the transaction and its lock
            log.warning("Skipped %s: @%s is not active", what, handle)
            return None
        return user

    async def act[**P, T](
        self,
        handle: str,
        what: str,
        service: Callable[Concatenate[AsyncSession, Redis, User, P], Awaitable[T]],
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> T | None:
        """One service call as the account, in one transaction with the check above. A refusal
        (a moderator hid the video, say) skips only this step: the demo never undoes moderation."""
        user = await self.active(handle, what)
        if user is None:
            return None
        try:
            result = await service(self.db, self.redis, user, *args, **kwargs)
        except DomainError as error:
            await self.db.rollback()
            log.warning("Skipped %s: %s", what, error.detail)
            return None
        await self.db.commit()  # the service has committed; this ends the lock on an early return
        return result


async def ensure_videos(
    db: AsyncSession, redis: Redis, storage: Storage, demo_dir: Path
) -> dict[str, UUID]:
    """Upload the demo videos that are missing and queue the ones not processed yet.

    Returns the ids of the demo videos found or uploaded, by file name.
    """
    meta = {entry["file"]: entry for entry in _read_videos_json(demo_dir)}
    actors = Actors(db, redis, await _ids(db))
    ids: dict[str, UUID] = {}
    for upload in UPLOADS:
        path = demo_dir / "videos" / upload.file
        if not path.is_file():
            log.warning("Skipped %s: not found. Run python3 demo-data/download.py", upload.file)
            continue
        what = f"the upload of {upload.file}"
        title = meta[upload.file]["title"]
        video = await videos.get_owned_by_title(db, actors.ids[upload.owner], title)
        if video is None:
            draft = VideoCreate(
                title=title,
                description=meta[upload.file]["description"],
                visibility=Visibility.PUBLIC,
                category=upload.category,
            )
            created = await actors.act(upload.owner, what, video_service.create_draft, draft)
            video = await videos.get_by_public_id(db, created.id) if created else None
            if video is None:
                continue
        if video.status is VideoStatus.UPLOADING:
            owner = await actors.active(upload.owner, what)
            if owner is None:
                continue
            try:  # it checks the owner again under the lock before the file counts as uploaded
                await video_service.upload_file(
                    db,
                    redis,
                    storage,
                    owner,
                    video.public_id,
                    read_chunks(path),
                    path.stat().st_size,
                )
            except DomainError as error:
                await db.rollback()
                log.warning("Skipped %s: %s", what, error.detail)
                continue
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


async def ensure_activity(db: AsyncSession, redis: Redis, ready: Mapping[str, UUID]) -> None:
    """Views, likes, comments, Watch later, subscriptions and playlists on the ready videos."""
    actors = Actors(db, redis, await _ids(db))
    public_ids: dict[str, str] = {}
    for upload in UPLOADS:
        video_id = ready.get(upload.file)
        video = await videos.get_by_id(db, video_id) if video_id else None
        if video_id is None or video is None:
            continue
        # Plain values from here on: a skipped step rolls back, which expires ORM objects.
        public_id = public_ids[upload.file] = video.public_id
        await _ensure_views(db, video_id, len(ACCOUNTS) - 1)  # everyone but the owner
        for handle in upload.liked_by:
            what = f"@{handle}'s like of {upload.file}"
            await actors.act(handle, what, reactions.rate_video, public_id, Rating.LIKE)
        for comment in upload.comments:
            await _ensure_comment(actors, video_id, public_id, comment, parent_id=None)
        for handle in upload.saved_by:
            watch_later = await playlists.get_watch_later(db, actors.ids[handle])
            if watch_later is not None:  # a DB trigger makes it with the account
                what = f"@{handle}'s Watch later of {upload.file}"
                await actors.act(
                    handle, what, playlist_service.add_video, watch_later.id, public_id
                )
    for subscriber, channel in SUBSCRIPTIONS:
        what = f"@{subscriber}'s subscription to @{channel}"
        await actors.act(subscriber, what, channels.subscribe, channel)
    for playlist in PLAYLISTS:
        await _ensure_playlist(actors, playlist, public_ids)


async def _ensure_views(db: AsyncSession, video_id: UUID, count: int) -> None:
    """One view per demo viewer, once: real views count after playback (ADR 0011)."""
    if await db.scalar(select(Video.view_count).where(Video.id == video_id)) == 0:
        for _ in range(count):
            await views.add_view(db, video_id)
    await db.commit()


async def _ensure_comment(
    actors: Actors,
    video_id: UUID,
    public_id: str,
    comment: DemoComment,
    *,
    parent_id: UUID | None,
) -> None:
    found = await comments.find(
        actors.db,
        video_id=video_id,
        author_id=actors.ids[comment.author],
        parent_id=parent_id,
        text=comment.text,
    )
    if found is not None and found.is_deleted:
        return  # a moderator deleted it: it stays gone, with its likes, report and replies
    comment_id = found.id if found is not None else None
    if comment_id is None:
        what = f"@{comment.author}'s comment on {public_id}"
        data = CommentIn(text=comment.text, parent_id=parent_id)
        posted = await actors.act(
            comment.author, what, comment_service.add_comment, public_id, data
        )
        if posted is None:
            return
        comment_id = posted.id
    for handle in comment.liked_by:
        what = f"@{handle}'s like of a comment"
        await actors.act(handle, what, reactions.rate_comment, comment_id, Rating.LIKE)
    for handle in comment.reported_by:
        # Once: a report a moderator resolved isn't filed again.
        if not await reports.exists(
            actors.db, reporter_id=actors.ids[handle], comment_id=comment_id
        ):
            what = f"@{handle}'s report of a comment"
            data = ReportIn(reason=ReportReason.SPAM)
            await actors.act(handle, what, report_service.report_comment, comment_id, data)
    for reply in comment.replies:
        await _ensure_comment(actors, video_id, public_id, reply, parent_id=comment_id)


async def _ensure_playlist(
    actors: Actors, playlist: DemoPlaylist, public_ids: Mapping[str, str]
) -> None:
    owner_id = actors.ids[playlist.owner]
    found = await playlists.get_owned_by_title(actors.db, owner_id, playlist.title)
    playlist_id = found.id if found is not None else None
    if playlist_id is None:
        what = f"@{playlist.owner}'s {playlist.title}"
        data = PlaylistCreate(title=playlist.title, visibility=Visibility.PUBLIC)
        created = await actors.act(playlist.owner, what, playlist_service.create, data)
        if created is None:
            return
        playlist_id = created.id
    for file in playlist.files:
        if file in public_ids:
            what = f"{file} in {playlist.title}"
            add = playlist_service.add_video
            await actors.act(playlist.owner, what, add, playlist_id, public_ids[file])


async def _ids(db: AsyncSession) -> dict[str, UUID]:
    """The demo accounts' ids by handle."""
    found = {account.handle: await users.get_by_handle(db, account.handle) for account in ACCOUNTS}
    missing = [handle for handle, user in found.items() if user is None]
    if missing:  # ensure_accounts ran first
        raise SeedError(f"No account @{missing[0]}")
    return {handle: user.id for handle, user in found.items() if user is not None}


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
    ready: dict[str, UUID] = {}
    for file, video_id in ids.items():
        if statuses[video_id] is VideoStatus.READY:
            ready[file] = video_id
        else:  # never retried: the file won't change
            log.warning("Demo video %s failed processing; see the worker's log", file)
    async with sessionmaker() as db:
        await ensure_activity(db, redis, ready)


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
