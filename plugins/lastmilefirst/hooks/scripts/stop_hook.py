#!/usr/bin/env python3
"""
Lastmilefirst Overwatch - Stop Hook
Checks for uncommitted changes at session end.
"""

import subprocess
from pathlib import Path


def main() -> None:
    # Check if session had file changes
    session_log = Path.home() / ".claude" / "tmp" / "session-changes.log"

    if not session_log.exists():
        return

    try:
        content = session_log.read_text().strip()
        if not content:
            return
    except IOError:
        return

    # Check if we're in a git repo with uncommitted changes
    try:
        # Check if in a git repo
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode != 0:
            return

        # Check for uncommitted changes
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=5
        )

        lines = [line for line in result.stdout.strip().split('\n') if line]
        if lines:
            print(f"Note: {len(lines)} uncommitted file(s) in this repo.")

    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass


if __name__ == "__main__":
    main()
