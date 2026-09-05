#!/usr/bin/env python3
"""PreToolUse hook: block Edit/Write to .env files.

The repo is public and CLAUDE.md forbids credentials in tracked files; the same
discipline applies to the agent editing .env itself — a wrong edit can silently
break the database roles, and .env contents must never round-trip through a
model transcript. .env.example is tracked documentation and stays editable.

Exit 2 blocks the tool call; stderr is fed back to Claude as the reason.
"""

import json
import sys
from pathlib import Path


def main() -> int:
    """Read the hook payload from stdin and block if the target is a .env file."""
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0  # malformed payload: never block on our own bug
    file_path = (payload.get("tool_input") or {}).get("file_path") or ""
    name = Path(file_path).name
    if name == ".env" or (name.startswith(".env.") and name != ".env.example"):
        print(
            f"Blocked: {file_path} holds local credentials. Edit it by hand, or "
            "change .env.example if the documented shape is what needs updating.",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
