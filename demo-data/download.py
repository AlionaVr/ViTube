#!/usr/bin/env python3
"""Download the demo videos from videos.json. Safe to re-run: files with the right hash are kept."""

import hashlib
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VIDEOS = ROOT / "videos"
MAX_BYTES = 20 * 1024 * 1024
# The seed container's user (uid 10001) reads the files through a read-only mount.
FILE_MODE = 0o644
DIR_MODE = 0o755


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def download(video: dict) -> None:
    path = VIDEOS / video["file"]
    if path.exists() and sha256(path) == video["sha256"]:
        path.chmod(FILE_MODE)  # may come from a run under a strict umask
        return
    url = video["url"]
    if not url.startswith("https://"):
        sys.exit(f"{video['file']}: only https URLs are allowed")
    print(f"download {url}")
    with urllib.request.urlopen(url, timeout=60) as response:  # noqa: S310 - https only, see above
        data = response.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        sys.exit(f"{video['file']}: larger than {MAX_BYTES} bytes")
    # The pinned hash is of a file checked by hand (see README), so only those bytes pass.
    if hashlib.sha256(data).hexdigest() != video["sha256"]:
        sys.exit(f"{video['file']}: sha256 mismatch")
    part = path.with_suffix(".part")
    part.write_bytes(data)
    part.chmod(FILE_MODE)
    part.replace(path)


def main() -> None:
    VIDEOS.mkdir(exist_ok=True)
    VIDEOS.chmod(DIR_MODE)  # mkdir's mode is cut by the umask
    for video in json.loads((ROOT / "videos.json").read_text())["videos"]:
        download(video)
    print("demo videos ready")


if __name__ == "__main__":
    main()
