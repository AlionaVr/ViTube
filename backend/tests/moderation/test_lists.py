"""Public lists (feed, categories, search, suggestions, Up next) leave hidden videos out for
everyone, moderators too: they find hidden videos on the moderation page (ADR 0009)."""

from httpx2 import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.videos.models import Category
from tests.interactions.conftest import user_by_email
from tests.moderation.conftest import OWNER_EMAIL, hide_directly
from tests.search.test_search import found
from tests.search.test_suggestions import suggestions
from tests.videos.factories import make_video
from tests.videos.test_feed import feed_ids
from tests.videos.test_up_next import up_next_ids


async def test_a_hidden_video_is_in_no_public_list(
    owner: AsyncClient, guest: AsyncClient, moderator: AsyncClient, db: AsyncSession
) -> None:
    anna = await user_by_email(db, OWNER_EMAIL)
    shown = await make_video(db, anna, title="Dragon shown", category=Category.MUSIC)
    hidden = await make_video(db, anna, title="Dragon hidden", category=Category.GAMING)
    await hide_directly(db, hidden)

    for client in (guest, owner, moderator):
        assert await feed_ids(client) == [shown.public_id]
        assert await feed_ids(client, Category.GAMING) == []
        assert (await client.get("/api/categories")).json() == ["music"]
        assert await found(client, "dragon") == ["Dragon shown"]
        assert await suggestions(client, "dragon") == ["dragon shown"]
        assert await up_next_ids(client, shown.public_id) == []
