"""View counting in Redis: a view needs real playback, and counts once per viewer and video a day.

The client reports `start` when playback begins and `finish` after the threshold. The server checks
the time between them itself, so a single "I watched it" request counts nothing.
"""

import hashlib
import time
from uuid import UUID

from redis.asyncio import Redis

WATCH_SECONDS = 30  # playback that makes a view, or the whole video if it is shorter
# Durations round down, so a sub-second video has 0: it still needs a moment of playback.
MIN_WATCH_SECONDS = 1
MAX_SPEED = 2  # the player's fastest rate: 30 s of video can play in 15 s
VIEW_WINDOW = 24 * 60 * 60  # one view per viewer and video in this many seconds
START_TTL = 6 * 60 * 60  # a start older than this is forgotten


def now() -> float:
    return time.time()  # wall clock: the same in every API process, unlike a monotonic one


def viewer_id(user_id: UUID | None, ip: str) -> str:
    """Users count per account, so people behind one NAT count apart. Guests count per IP."""
    return f"user:{user_id}" if user_id else f"ip:{ip}"


def _key(kind: str, video_id: UUID, viewer: str) -> str:
    # Hashed: Redis holds no IPs in plain text, and keys have a fixed length.
    return f"{kind}:{hashlib.sha256(f'{video_id} {viewer}'.encode()).hexdigest()}"


async def start(redis: Redis, video_id: UUID, viewer: str) -> None:
    """Playback began. One key per viewer and video: repeated starts overwrite it."""
    await redis.set(_key("viewstart", video_id, viewer), now(), ex=START_TTL)


async def finish(redis: Redis, video_id: UUID, viewer: str, duration_sec: int | None) -> bool:
    """True if this playback is a new view: long enough since `start`, first in the window."""
    started = await redis.get(_key("viewstart", video_id, viewer))
    if started is None:
        return False
    threshold = WATCH_SECONDS if duration_sec is None else min(WATCH_SECONDS, duration_sec)
    threshold = max(threshold, MIN_WATCH_SECONDS)
    if now() - float(started) < threshold / MAX_SPEED:
        return False
    # NX: of parallel requests exactly one sets the key, so a view counts once.
    return bool(await redis.set(_key("view", video_id, viewer), 1, nx=True, ex=VIEW_WINDOW))
