"""/internal/media-auth: nginx asks it before each /media request (ADR 0004)."""

import uuid

import pytest
from fastapi import FastAPI
from httpx2 import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app as vitube_app
from app.modules.users.models import Role, User
from app.modules.videos.models import Video, VideoAccess, VideoStatus, Visibility
from app.modules.videos.schemas import VideoOut
from tests.videos.factories import make_user, make_video


async def sign_in(app: FastAPI, user: User) -> str:
    session = await app.state.sessions.create(user.id)
    return session.id


async def ask(client: AsyncClient, uri: str, session_id: str | None = None, method: str = "GET"):
    headers = {"X-Original-URI": uri}
    if session_id:
        headers["Cookie"] = f"sid={session_id}"
    return await client.request(method, "/internal/media-auth", headers=headers)


def media(video: Video) -> str:
    return f"/media/{video.media_key}"


@pytest.fixture
async def anna(db: AsyncSession) -> User:
    return await make_user(db, "anna")


async def test_guest_may_fetch_a_public_video(
    client: AsyncClient, db: AsyncSession, anna: User
) -> None:
    video = await make_video(db, anna, visibility=Visibility.PUBLIC)

    assert (await ask(client, media(video))).status_code == 200
    assert (await ask(client, f"/media/{video.thumbnail_key}")).status_code == 200
    assert (await ask(client, media(video), method="HEAD")).status_code == 200


@pytest.mark.parametrize(
    ("viewer", "expected"),
    [("guest", 401), ("stranger", 403), ("granted", 200), ("owner", 200), ("moderator", 200)],
)
async def test_private_video(
    client: AsyncClient, db: AsyncSession, app: FastAPI, anna: User, viewer: str, expected: int
) -> None:
    video = await make_video(db, anna, visibility=Visibility.PRIVATE)
    carol = await make_user(db, "carol")
    db.add(VideoAccess(video_id=video.id, user_id=carol.id))
    await db.commit()
    users = {
        "guest": None,
        "stranger": await make_user(db, "bob"),
        "granted": carol,
        "owner": anna,
        "moderator": await make_user(db, "mod", Role.MODERATOR),
    }
    user = users[viewer]

    response = await ask(client, media(video), await sign_in(app, user) if user else None)

    # 403 reaches the browser as 404 (nginx), 401 as 401.
    assert response.status_code == expected


async def test_revoked_access_applies_to_the_next_request(
    client: AsyncClient, db: AsyncSession, app: FastAPI, anna: User
) -> None:
    video = await make_video(db, anna, visibility=Visibility.PRIVATE)
    bob = await make_user(db, "bob")
    grant = VideoAccess(video_id=video.id, user_id=bob.id)
    db.add(grant)
    await db.commit()
    session_id = await sign_in(app, bob)
    assert (await ask(client, media(video), session_id)).status_code == 200

    await db.delete(grant)
    await db.commit()

    assert (await ask(client, media(video), session_id)).status_code == 403


async def test_unfinished_video_files_are_only_for_the_owner(
    client: AsyncClient, db: AsyncSession, app: FastAPI, anna: User
) -> None:
    video = await make_video(db, anna, status=VideoStatus.PROCESSING)
    bob = await make_user(db, "bob")

    assert (await ask(client, media(video), await sign_in(app, bob))).status_code == 403
    assert (await ask(client, media(video), await sign_in(app, anna))).status_code == 200


async def test_unknown_video_looks_like_a_private_one(
    client: AsyncClient, db: AsyncSession, app: FastAPI, anna: User
) -> None:
    unknown = f"/media/videos/{uuid.uuid4()}/720p.mp4"

    assert (await ask(client, unknown)).status_code == 401
    assert (await ask(client, unknown, await sign_in(app, anna))).status_code == 403


@pytest.mark.parametrize(
    "uri",
    [
        "/media/originals/{id}",  # originals are never served, even to the owner
        "/media/videos/{id}/original.mp4",
        "/media/videos/{id}/720p.mp4/../../originals/{id}",
        "/media/videos/{ID}/720p.mp4",  # uuids are lowercase
        "/media/thumbs/{id}.png",
        "/media/videos/{id}%2F720p.mp4",
        "/api/videos",
        "",
    ],
)
async def test_other_paths_are_refused(
    client: AsyncClient, db: AsyncSession, app: FastAPI, anna: User, uri: str
) -> None:
    video = await make_video(db, anna, visibility=Visibility.PUBLIC)
    path = uri.format(id=video.id, ID=str(video.id).upper())

    response = await ask(client, path, await sign_in(app, anna))

    assert response.status_code == 403


async def test_query_string_is_ignored(client: AsyncClient, db: AsyncSession, anna: User) -> None:
    video = await make_video(db, anna, visibility=Visibility.PUBLIC)

    # nginx drops the query before MinIO, so it can't change what is served.
    assert (await ask(client, media(video) + "?response-content-type=text/html")).status_code == 200


async def test_urls_in_the_api_are_the_ones_media_serves(
    client: AsyncClient, db: AsyncSession, anna: User
) -> None:
    video = await make_video(db, anna, visibility=Visibility.PUBLIC)
    out = VideoOut.of(video, anna)

    for url in (out.media_url, out.thumbnail_url):
        assert url is not None
        assert (await ask(client, url)).status_code == 200


def test_media_auth_is_not_in_the_api_docs() -> None:
    assert not any(path.startswith("/internal") for path in vitube_app.openapi()["paths"])
