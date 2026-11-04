#!/usr/bin/env python3
"""PreToolUse hook: block the agent from reading or editing real .env files."""

import json
import re
import sys

# Matches .env, .env.local, backend/.env, but not .env.example.
ENV_FILE = re.compile(r"(^|[\s/'\"=])\.env(?!\.example)(\.[\w-]+)?($|[\s'\";|&)])")

data = json.load(sys.stdin)
tool_input = data.get("tool_input", {})
target = tool_input.get("file_path") or tool_input.get("command") or ""

if ENV_FILE.search(target):
    print("Blocked: .env holds secrets. Use .env.example instead.", file=sys.stderr)
    sys.exit(2)  # exit 2 = deny and show the reason to the agent
