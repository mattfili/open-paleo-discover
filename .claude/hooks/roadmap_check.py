#!/usr/bin/env python3
"""PreToolUse hook: enforce "update ROADMAP.md in the same commit".

CLAUDE.md's strongest working convention — any commit that finishes something,
breaks something, or discovers a constraint updates ROADMAP.md in the same
commit — is enforced here mechanically. A `git commit` whose staged changes
touch src/ or sql/ without also staging ROADMAP.md is blocked with a reminder.

Escape hatch, deliberate and greppable (same pattern as cq-allow): include
`[no-roadmap]` in the commit command when the change genuinely carries no
state the roadmap tracks (pure refactor, comment fix). The marker lands in the
commit message, so every exemption is visible in history.

Exit 2 blocks; stderr is fed back to Claude.
"""

import json
import re
import subprocess
import sys

WATCHED = ("src/", "sql/", "plugin/", "semantic/", "weights/")


def staged_files() -> list[str]:
    """Return the paths currently staged for commit, empty on any git failure."""
    try:
        out = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        return out.stdout.split()
    except OSError:
        return []


def main() -> int:
    """Block `git commit` when watched paths are staged without ROADMAP.md."""
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    command = (payload.get("tool_input") or {}).get("command") or ""
    if not re.search(r"\bgit\b[^\n;|&]*\bcommit\b", command):
        return 0
    if "[no-roadmap]" in command or "--amend" in command:
        return 0

    staged = staged_files()
    # A compound `git add X && git commit` stages within the same call, so the
    # cached diff can't see it yet; scan the command text for watched paths too.
    named_in_command = [p for p in WATCHED if re.search(rf"\b{re.escape(p)}", command)]
    touches_watched = any(f.startswith(WATCHED) for f in staged) or named_in_command
    roadmap_staged = "ROADMAP.md" in staged or "ROADMAP.md" in command

    if touches_watched and not roadmap_staged:
        print(
            "Blocked: this commit touches "
            + ", ".join(
                sorted(
                    {f.split("/")[0] + "/" for f in staged if f.startswith(WATCHED)}
                    | set(named_in_command)
                )
            )
            + " but does not stage ROADMAP.md. CLAUDE.md: any commit that finishes "
            "something, breaks something, or discovers a constraint updates the "
            "roadmap in the same commit — including negative results. Either stage "
            "a ROADMAP.md update, or add [no-roadmap] to the commit message if the "
            "change genuinely carries no state the roadmap tracks.",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
