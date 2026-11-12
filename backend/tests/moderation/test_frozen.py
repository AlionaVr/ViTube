"""A hidden video is frozen for everyone, its owner and moderators too: no comments, ratings,
views or reports (ADR 0009). They may still open the video itself."""

from httpx2 import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.videos.models import Video
from tests.interactions.conftest import csrf
from tests.moderation.conftest import hide_directly, report


async def test_no_one_interacts_with_a_hidden_video(
    owner: AsyncClient, moderator: AsyncClient, db: AsyncSession, video: Video
) -> None:
    await hide_directly(db, video)
    base = f"/api/videos/{video.public_id}"

    for client in (owner, moderator):
        headers = csrf(client)
        assert (await client.get(base)).status_code == 200
        assert (await client.get(f"{base}/comments")).status_code == 404
        response = await client.post(f"{base}/comments", json={"text": "Hi"}, headers=headers)
        assert response.status_code == 404
        response = await client.put(f"{base}/rating", json={"rating": "like"}, headers=headers)
        assert response.status_code == 404
        assert (await client.post(f"{base}/views/start", headers=headers)).status_code == 404
    assert (await report(moderator, video)).status_code == 404
