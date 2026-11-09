"""/internal: answers for nginx only. nginx returns 404 for /internal/* from outside."""

from fastapi import APIRouter, Request, Response

from app.core.errors import Forbidden, Unauthorized
from app.db.session import DbSession
from app.modules.auth.deps import OptionalUser
from app.modules.videos.access import can_fetch_media

router = APIRouter(prefix="/internal", include_in_schema=False)


@router.api_route("/media-auth", methods=["GET", "HEAD"])
async def media_auth(request: Request, user: OptionalUser, db: DbSession) -> Response:
    """nginx auth_request for /media/* (ADR 0004). Checked on every request: no cache.

    auth_request passes only 401 and 403 on, so "signed in, no access" is 403 and nginx shows
    it as 404. A guest gets 401 whether or not the video exists: nothing to learn from it.
    """
    if await can_fetch_media(db, user, request.headers.get("x-original-uri", "")):
        return Response(status_code=200)
    if user is None:
        raise Unauthorized()
    raise Forbidden()
