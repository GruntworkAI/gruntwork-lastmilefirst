#!/usr/bin/env python3
"""
Lastmilefirst Overwatch - Log Invocation
Logs skill and agent invocations for usage tracking.

Usage: log_invocation.py <kind>        (kind is "skill" or "agent")

Claude Code passes the hook payload as JSON on stdin. The skill or agent
name and the session id are read from it, so the log can answer "which
skills ran this week" and "did this session run a closing skill without a
compound skill". Before 0.31.0 only the kind was logged, so the weekly
"Top:" line could only ever say "skill" or "agent".

Line format (v2):  timestamp|kind|name|session_id
Legacy lines:      timestamp|kind
"""

import json
import sys
import time
from pathlib import Path

# Add script directory to path for local imports
sys.path.insert(0, str(Path(__file__).parent))

from overwatch import (
    get_invocations_file,
    get_lock_file,
    file_lock,
    invocation_name_from_payload,
)


def read_payload() -> dict:
    """Read the hook JSON from stdin. Never block, never raise."""
    try:
        if sys.stdin is None or sys.stdin.isatty():
            return {}
        raw = sys.stdin.read()
        return json.loads(raw) if raw.strip() else {}
    except (ValueError, OSError):
        return {}


def main() -> None:
    kind = sys.argv[1] if len(sys.argv) > 1 else "unknown"
    payload = read_payload()
    name = invocation_name_from_payload(payload)
    session = str(payload.get("session_id", "") or "")
    timestamp = int(time.time())

    with file_lock(get_lock_file()):
        with open(get_invocations_file(), 'a', encoding='utf-8') as f:
            f.write(f"{timestamp}|{kind}|{name}|{session}\n")


if __name__ == "__main__":
    main()
