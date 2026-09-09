#!/usr/bin/env python3
"""
Lastmilefirst Overwatch - Stop Hook
At turn end: note uncommitted changes, and nudge once per session when a
cycle closed (a review, PR, commit, or strict-PARC skill ran) with no
compound skill run afterwards.
"""

import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from overwatch import (
    get_state_dir,
    read_invocations,
    session_needs_compound_nudge,
    COMPOUND_NUDGE,
)


def read_payload() -> dict:
    try:
        if sys.stdin is None or sys.stdin.isatty():
            return {}
        raw = sys.stdin.read()
        return json.loads(raw) if raw.strip() else {}
    except (ValueError, OSError):
        return {}


def check_uncommitted() -> None:
    session_log = Path.home() / ".claude" / "tmp" / "session-changes.log"
    if not session_log.exists():
        return
    try:
        if not session_log.read_text().strip():
            return
    except IOError:
        return
    try:
        result = subprocess.run(["git", "rev-parse", "--git-dir"],
                                capture_output=True, text=True, timeout=5)
        if result.returncode != 0:
            return
        result = subprocess.run(["git", "status", "--porcelain"],
                                capture_output=True, text=True, timeout=5)
        lines = [line for line in result.stdout.strip().split("\n") if line]
        if lines:
            print(f"Note: {len(lines)} uncommitted file(s) in this repo.")
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass


def nudge_flag(session_id: str) -> Path:
    return get_state_dir() / f"compound-nudged-{session_id}"


def check_compound_nudge(session_id: str, now: int = None) -> bool:
    """Print the nudge once per session. Returns True when printed."""
    if not session_id:
        return False
    flag = nudge_flag(session_id)
    if flag.exists():
        return False
    now = now or int(time.time())
    records = read_invocations(now - 86400)
    if not session_needs_compound_nudge(session_id, records):
        return False
    print(COMPOUND_NUDGE)
    try:
        flag.touch()
    except OSError:
        pass
    return True


def main() -> None:
    payload = read_payload()
    check_uncommitted()
    check_compound_nudge(str(payload.get("session_id", "") or ""))


if __name__ == "__main__":
    main()
