#!/usr/bin/env python3
"""
Cross-platform Python script launcher for lastmilefirst hooks.

Finds the correct Python interpreter and runs the target script.
Works on Windows (python/py), macOS (python3), and Linux (python3).

Usage: Invoke with any available Python:
  python run.py <script.py> [args...]
  python3 run.py <script.py> [args...]
  py run.py <script.py> [args...]
"""

import os
import subprocess
import sys
from pathlib import Path


def find_python() -> str:
    """Find a working Python 3 interpreter."""
    # First, use the current interpreter if it's Python 3
    if sys.version_info[0] >= 3:
        return sys.executable

    # Try common Python 3 commands
    candidates = ["python3", "python", "py -3"]

    for cmd in candidates:
        try:
            result = subprocess.run(
                cmd.split() + ["--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0 and "Python 3" in result.stdout:
                return cmd
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            continue

    # Fallback to current executable
    return sys.executable


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: run.py <script.py> [args...]", file=sys.stderr)
        return 1

    script = sys.argv[1]
    args = sys.argv[2:]

    # Resolve script path relative to this launcher's directory
    script_dir = Path(__file__).parent
    script_path = script_dir / script

    if not script_path.exists():
        # Try as absolute path
        script_path = Path(script)

    if not script_path.exists():
        print(f"Script not found: {script}", file=sys.stderr)
        return 1

    # Run with current Python (we're already in Python 3 if we got here)
    try:
        result = subprocess.run(
            [sys.executable, str(script_path)] + args,
            timeout=30,
        )
        return result.returncode
    except subprocess.TimeoutExpired:
        print(f"Script timed out: {script}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error running script: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
