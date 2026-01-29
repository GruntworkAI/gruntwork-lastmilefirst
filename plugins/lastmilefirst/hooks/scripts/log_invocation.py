#!/usr/bin/env python3
"""
Lastmilefirst Overwatch - Log Invocation
Logs skill/command invocations for usage tracking.
Usage: log_invocation.py <skill-name>
"""

import sys
import time
from pathlib import Path

# Add script directory to path for local imports
sys.path.insert(0, str(Path(__file__).parent))

from overwatch import get_invocations_file, get_lock_file, file_lock


def main() -> None:
    skill_name = sys.argv[1] if len(sys.argv) > 1 else "unknown"
    invocations_file = get_invocations_file()
    timestamp = int(time.time())

    # Use file locking to prevent interleaved writes from concurrent processes
    with file_lock(get_lock_file()):
        with open(invocations_file, 'a', encoding='utf-8') as f:
            f.write(f"{timestamp}|{skill_name}\n")


if __name__ == "__main__":
    main()
