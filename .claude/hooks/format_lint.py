#!/usr/bin/env python3
"""PostToolUse hook: format and lint the edited file. Lint errors go back to the agent."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

data = json.load(sys.stdin)
path = Path(data.get("tool_input", {}).get("file_path", "")).resolve()
# Project root, not cwd: the session may be inside backend/ or frontend/.
root = Path(os.environ.get("CLAUDE_PROJECT_DIR") or data.get("cwd", ".")).resolve()
backend = root / "backend"
frontend = root / "frontend"


def run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)


def fail(output: str) -> None:
    print(output.strip(), file=sys.stderr)
    sys.exit(2)  # exit 2 = show errors to the agent so it fixes them


# Same files as CI: Python in backend/, TS and CSS in frontend/.
if path.suffix == ".py" and path.is_relative_to(backend) and shutil.which("uv"):
    if (backend / "pyproject.toml").exists():
        # Fix first, then format: fixes like removed imports can leave unformatted code.
        result = run(["uv", "run", "ruff", "check", "--fix", str(path)], backend)
        run(["uv", "run", "ruff", "format", str(path)], backend)
        if result.returncode != 0:
            fail(result.stdout + result.stderr)

elif path.suffix in {".ts", ".tsx", ".css"} and path.is_relative_to(frontend):
    if (frontend / "node_modules").exists():
        run(["npx", "prettier", "--write", str(path)], frontend)
        if path.suffix != ".css":
            result = run(["npx", "eslint", "--fix", str(path)], frontend)
            if result.returncode != 0:
                fail(result.stdout + result.stderr)

# Tools not installed yet (early stages) -> skip silently.
