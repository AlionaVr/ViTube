"""My channel on a running stack: the owner's own tabs, editing a video, sharing it privately.

Run: E2E_BASE_URL=http://localhost uv run pytest tests/e2e -v   (needs ffmpeg for the sample video)
"""

from collections.abc import Iterator
from pathlib import Path

import pytest

from tests.e2e.test_scenario import BASE_URL, Browser, ffmpeg, upload, wait_until_processed

pytestmark = pytest.mark.skipif(not BASE_URL, reason="needs a running stack: set E2E_BASE_URL")


@pytest.fixture
def owner() -> Iterator[tuple[Browser, str]]:
    # The scenario's accounts: sign-ups are limited per IP, so runs make no new ones.
    browser = Browser()
    handle = browser.sign_in("e2e-owner@example.com")
    yield browser, handle
    browser.http.close()


@pytest.fixture
def stranger() -> Iterator[tuple[Browser, str]]:
    browser = Browser()
    handle = browser.sign_in("e2e-stranger@example.com")
    yield browser, handle
    browser.http.close()


@pytest.fixture
def private_video(owner: tuple[Browser, str], tmp_path: Path) -> str:
    browser, _ = owner
    sample = tmp_path / "sample.mp4"
    ffmpeg("-f", "lavfi", "-i", "testsrc=duration=1:size=320x240:rate=25", str(sample))
    public_id = upload(browser, sample.read_bytes(), "E2E my channel private")
    assert wait_until_processed(browser, public_id)["status"] == "ready"
    return public_id


def ids(browser: Browser, path: str) -> list[str]:
    response = browser.get(path)
    assert response.status_code == 200, response.text
    return [item["id"] for item in response.json()["items"]]


def test_the_owner_sees_a_private_video_on_their_own_tab_only(
    owner: tuple[Browser, str], stranger: tuple[Browser, str], private_video: str
) -> None:
    browser, handle = owner
    other, _ = stranger

    mine = browser.get("/api/me/channel/videos").json()["items"]
    assert (mine[0]["id"], mine[0]["visibility"]) == (private_video, "private")
    # The public tab stays the same for everyone, the owner too (ADR 0012).
    for viewer in (browser, other, Browser()):
        assert private_video not in ids(viewer, f"/api/channels/{handle}/videos")


def test_edit_share_and_take_back(
    owner: tuple[Browser, str], stranger: tuple[Browser, str], private_video: str
) -> None:
    browser, _ = owner
    other, other_handle = stranger
    access = f"/api/videos/{private_video}/access"

    edited = browser.send("PATCH", f"/api/videos/{private_video}", json={"title": "E2E renamed"})
    assert (edited.status_code, edited.json()["title"]) == (200, "E2E renamed")
    assert other.get(f"/api/videos/{private_video}").status_code == 404

    assert browser.send("POST", access, json={"handle": other_handle}).status_code == 204
    assert [person["handle"] for person in browser.get(access).json()] == [other_handle]
    watched = other.get(f"/api/videos/{private_video}")
    assert (watched.status_code, watched.json()["title"]) == (200, "E2E renamed")
    assert other.get(watched.json()["media_url"], headers={"Range": "bytes=0-1"}).status_code == 206

    assert browser.send("DELETE", f"{access}/{other_handle}").status_code == 204
    assert browser.get(access).json() == []
    assert other.get(f"/api/videos/{private_video}").status_code == 404
    assert other.get(watched.json()["media_url"]).status_code == 404
