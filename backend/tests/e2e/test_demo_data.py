"""Demo data on a deployed stack: install.sh runs the seed (ADR 0008).

Run: E2E_BASE_URL=http://localhost uv run pytest tests/e2e -v   (after ./install.sh)
"""

import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from app import seed
from tests.e2e.test_scenario import BASE_URL, Browser

pytestmark = pytest.mark.skipif(not BASE_URL, reason="needs a running stack: set E2E_BASE_URL")

DEMO_DATA = Path(__file__).resolve().parents[3] / "demo-data"


@pytest.fixture
def guest() -> Iterator[Browser]:
    browser = Browser()
    yield browser
    browser.http.close()


def test_a_guest_finds_the_demo_videos_on_their_channels_and_plays_them(guest: Browser) -> None:
    entries = json.loads((DEMO_DATA / "videos.json").read_text())["videos"]
    titles = {entry["file"]: entry["title"] for entry in entries}
    handles = {account.email: account.handle for account in seed.ACCOUNTS}
    for upload in seed.UPLOADS:
        page = guest.get(f"/api/channels/{handles[upload.owner]}/videos")
        assert page.status_code == 200, page.text
        listed = {item["title"]: item["id"] for item in page.json()["items"]}
        video = guest.get(f"/api/videos/{listed[titles[upload.file]]}").json()
        assert video["status"] == "ready"
        assert guest.get(video["media_url"], headers={"Range": "bytes=0-99"}).status_code == 206
        assert guest.get(video["thumbnail_url"]).status_code == 200
