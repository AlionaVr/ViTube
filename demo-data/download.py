#!/usr/bin/env python3
"""Download the demo videos from videos.json and render their thumbnails. Safe to re-run."""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VIDEOS = ROOT / "videos"
THUMBNAILS = ROOT / "thumbnails"
MAX_BYTES = 20 * 1024 * 1024
# Static ffmpeg build, pinned by digest.
FFMPEG = (
    "mwader/static-ffmpeg:7.1"
    "@sha256:a8090df5f5608daef387e1b2e93b98aaacb4d92153ad904e7d715c725724fca4"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def download(video: dict) -> Path:
    path = VIDEOS / video["file"]
    if path.exists() and sha256(path) == video["sha256"]:
        return path
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
    part.replace(path)
    return path


def render_thumbnails(docker: str, video: dict, path: Path) -> None:
    # Optional crop drops letterbox bars; the UI fills 16:9 with object-fit: cover.
    crop = f"crop={video['crop']}," if "crop" in video else ""
    for at in video["thumbnails_at"]:
        out = THUMBNAILS / f"{path.stem}-{at:g}.jpg"
        if out.exists() and out.stat().st_mtime >= path.stat().st_mtime:
            continue
        print(f"thumbnail {out.name}")
        # No network, read-only rootfs and videos; writes only to thumbnails/. No shell is involved.
        subprocess.run(  # noqa: S603
            [docker, "run", "--rm", "--network", "none", "--read-only", "--cap-drop", "ALL",
             "--security-opt", "no-new-privileges", "--user", f"{os.getuid()}:{os.getgid()}",
             "-v", f"{VIDEOS}:/videos:ro", "-v", f"{THUMBNAILS}:/thumbnails", FFMPEG,
             "-v", "error", "-y", "-ss", f"{at}", "-i", f"/videos/{path.name}",
             "-vf", f"{crop}scale='min(640,iw)':-2", "-frames:v", "1", "-update", "1", "-q:v", "3",
             f"/thumbnails/{out.name}"],
            check=True,
        )  # fmt: skip


def main() -> None:
    docker = shutil.which("docker")
    if docker is None:
        sys.exit("Docker is needed to render thumbnails")
    VIDEOS.mkdir(exist_ok=True)
    THUMBNAILS.mkdir(exist_ok=True)
    for video in json.loads((ROOT / "videos.json").read_text())["videos"]:
        render_thumbnails(docker, video, download(video))
    print("demo data ready")


if __name__ == "__main__":
    main()
