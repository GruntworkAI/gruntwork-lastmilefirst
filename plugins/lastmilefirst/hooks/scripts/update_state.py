#!/usr/bin/env python3
"""
Lastmilefirst Overwatch - Update State
Updates the Overwatch state file with timestamps.
Usage: update_state.py <action>
Actions: review, organize, plugin_check, status
"""

import json
import sys
import time
from datetime import datetime
from pathlib import Path

# Add script directory to path for local imports
sys.path.insert(0, str(Path(__file__).parent))

from overwatch import load_state, update_state_field, get_state_file


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: update_state.py <review|organize|plugin_check|status>")
        sys.exit(1)

    action = sys.argv[1]
    now = int(time.time())

    if action == "review":
        update_state_field("last_review", now)
        print(f"Overwatch: recorded review at {datetime.now()}")

    elif action == "organize":
        update_state_field("last_organize", now)
        print(f"Overwatch: recorded organize at {datetime.now()}")

    elif action == "plugin_check":
        update_state_field("last_plugin_check", now)
        print(f"Overwatch: recorded plugin check at {datetime.now()}")

    elif action == "status":
        print("Overwatch State:")
        state = load_state()
        print(json.dumps(state, indent=2))

    else:
        print(f"Unknown action: {action}")
        print("Usage: update_state.py <review|organize|plugin_check|status>")
        sys.exit(1)


if __name__ == "__main__":
    main()
