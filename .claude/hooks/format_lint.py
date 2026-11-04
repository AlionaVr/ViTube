#!/usr/bin/env python3
"""PostToolUse hook: format and lint the edited file. Lint errors go back to the agent."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

data = json.load(sys.stdin)
path = Path(data.get("tool_input", {}).get("file_path", ""))
root = Path(data.get("cwd", ".")).resolve()


def run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)


def fail(output: str) -> None:
    print(output.strip(), file=sys.stderr)
    sys.exit(2)  # exit 2 = show errors to the agent so it fixes them


if path.suffix == ".py" and shutil.which("uv"):
    backend = root / "backend"
    if (backend / "pyproject.toml").exists():
        run(["uv", "run", "ruff", "format", str(path)], backend)
        result = run(["uv", "run", "ruff", "check", "--fix", str(path)], backend)
        if result.returncode != 0:
            fail(result.stdout + result.stderr)

elif path.suffix in {".ts", ".tsx", ".css"}:
    frontend = root / "frontend"
    if (frontend / "node_modules").exists():
        run(["npx", "prettier", "--write", str(path)], frontend)
        if path.suffix != ".css":
            result = run(["npx", "eslint", "--fix", str(path)], frontend)
            if result.returncode != 0:
                fail(result.stdout + result.stderr)

# Tools not installed yet (early stages) -> skip silently.
