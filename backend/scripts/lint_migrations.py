"""Lint the SQL of the migrations added since a base ref with squawk: long locks, unsafe changes.

Run from backend/: python -m scripts.lint_migrations origin/main. Rules: .squawk.toml.
Only new migrations: applied ones can't change, and their findings were accepted then.
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from alembic.config import Config
from alembic.script import ScriptDirectory

BACKEND = Path(__file__).resolve().parent.parent
# Offline SQL needs a dialect, not a database: the settings only have to parse.
OFFLINE_ENV = {
    "DATABASE_URL": "postgresql+asyncpg://offline:offline@localhost/offline",
    "REDIS_URL": "redis://localhost",
}


def run(*command: str, **kwargs: Any) -> subprocess.CompletedProcess[str]:
    # git, alembic and squawk from PATH (uv run puts the venv first); no shell.
    return subprocess.run(command, cwd=BACKEND, text=True, **kwargs)  # noqa: S603


def added_files(base: str) -> set[Path]:
    diff = run(
        "git", "diff", "--name-only", "--diff-filter=A", f"{base}...HEAD", "--", "alembic/versions",
        check=True, capture_output=True,
    )  # fmt: skip
    root = BACKEND.parent  # git prints paths from the repository root
    return {(root / name).resolve() for name in diff.stdout.split() if name.endswith(".py")}


def offline_sql(start: str, revision: str) -> str:
    upgrade = run(
        "alembic", "upgrade", f"{start}:{revision}", "--sql",
        env={**os.environ, **OFFLINE_ENV}, check=True, capture_output=True,
    )  # fmt: skip
    return upgrade.stdout


def main(base: str) -> int:
    added = added_files(base)
    script = ScriptDirectory.from_config(Config(str(BACKEND / "alembic.ini")))
    revisions = [r for r in script.walk_revisions() if r.path and Path(r.path).resolve() in added]
    if not revisions:
        print(f"No new migrations since {base}.")
        return 0
    with tempfile.TemporaryDirectory() as tmp:
        files = []
        for rev in revisions:
            down = rev.down_revision
            if not (down is None or isinstance(down, str)):
                print(f"{rev.revision}: a merge point, no SQL of its own; skipped.")
                continue
            path = Path(tmp) / f"{Path(rev.path).stem}.sql"
            path.write_text(offline_sql(down or "base", rev.revision))
            files.append(str(path))
        if not files:
            return 0
        return run("squawk", "--config", str(BACKEND / ".squawk.toml"), *files).returncode


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
