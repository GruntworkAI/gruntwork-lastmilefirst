#!/usr/bin/env python3
"""
Lastmilefirst Overwatch - Cross-platform utilities
Provides file locking, state management, and shared functionality.
"""

import json
import os
import sys
import time
from pathlib import Path
from contextlib import contextmanager
from typing import Any, Dict, List, Optional

# Cross-platform file locking
try:
    import fcntl
    HAS_FCNTL = True
except ImportError:
    HAS_FCNTL = False

try:
    import msvcrt
    HAS_MSVCRT = True
except ImportError:
    HAS_MSVCRT = False


def get_state_dir() -> Path:
    """Get the Overwatch state directory, creating if needed."""
    state_dir = Path.home() / ".claude" / "lastmilefirst"
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir


def get_state_file() -> Path:
    """Get the path to the state file."""
    return get_state_dir() / "overwatch-state.json"


def get_lock_file() -> Path:
    """Get the path to the lock file."""
    return get_state_dir() / "overwatch.lock"


def get_invocations_file() -> Path:
    """Get the path to the invocations log."""
    return get_state_dir() / "invocations.log"


def get_tmp_dir() -> Path:
    """Get the tmp directory for session tracking."""
    tmp_dir = Path.home() / ".claude" / "tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    return tmp_dir


@contextmanager
def file_lock(lock_path: Path):
    """
    Cross-platform file locking context manager.
    Uses fcntl on Unix, msvcrt on Windows.
    Falls back to no locking if neither is available.
    """
    lock_file = None
    try:
        lock_file = open(lock_path, 'w', encoding='utf-8')
        if HAS_FCNTL:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        elif HAS_MSVCRT:
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
        yield
    finally:
        if lock_file:
            if HAS_FCNTL:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            elif HAS_MSVCRT:
                try:
                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
                except OSError:
                    pass  # Unlock may fail if process is terminating
            lock_file.close()


def _load_state_unlocked() -> Dict[str, Any]:
    """
    Load state without acquiring lock. Internal use only.
    Callers must hold the lock if thread safety is required.
    """
    state_file = get_state_file()
    default_state: Dict[str, Any] = {
        "last_review": 0,
        "last_organize": 0,
        "last_plugin_check": 0
    }

    if not state_file.exists():
        return default_state.copy()

    try:
        with open(state_file, encoding='utf-8') as f:
            state = json.load(f)
            # Ensure all expected keys exist
            for key in default_state:
                if key not in state:
                    state[key] = default_state[key]
            return state
    except (json.JSONDecodeError, IOError):
        return default_state.copy()


def load_state() -> Dict[str, Any]:
    """
    Load the Overwatch state with file locking.
    Initializes state file if missing.
    """
    lock_file = get_lock_file()
    state_file = get_state_file()
    default_state: Dict[str, Any] = {
        "last_review": 0,
        "last_organize": 0,
        "last_plugin_check": 0
    }

    with file_lock(lock_file):
        state = _load_state_unlocked()
        # Initialize file if it doesn't exist
        if not state_file.exists():
            with open(state_file, 'w', encoding='utf-8') as f:
                json.dump(default_state, f)
            return default_state
        return state


def save_state(state: Dict[str, Any]) -> None:
    """Save the Overwatch state with file locking."""
    state_file = get_state_file()
    lock_file = get_lock_file()

    with file_lock(lock_file):
        with open(state_file, 'w', encoding='utf-8') as f:
            json.dump(state, f)


def update_state_field(field: str, value: Any) -> None:
    """Update a single field in the state file with locking."""
    lock_file = get_lock_file()
    state_file = get_state_file()

    with file_lock(lock_file):
        state = _load_state_unlocked()
        state[field] = value
        with open(state_file, 'w', encoding='utf-8') as f:
            json.dump(state, f)


def get_plugins_dir() -> Optional[Path]:
    """Get the Claude plugins directory."""
    if os.environ.get("CLAUDE_PLUGINS_DIR"):
        return Path(os.environ["CLAUDE_PLUGINS_DIR"])

    default_dir = Path.home() / ".claude" / "plugins"
    if default_dir.exists():
        return default_dir

    return None


def version_compare(v1: str, v2: str) -> int:
    """
    Compare two version strings.
    Returns: -1 if v1 < v2, 0 if equal, 1 if v1 > v2

    Note: Non-numeric components (e.g., 'beta', 'rc1') are ignored.
    '1.2.3-beta' is treated as '1.2.3'.
    """
    def normalize(v: str) -> List[int]:
        # Extract only numeric components, ignore suffixes like -beta, -rc1
        return [int(x) for x in v.split('.') if x.isdigit()]

    parts1 = normalize(v1)
    parts2 = normalize(v2)

    # Pad shorter version with zeros
    max_len = max(len(parts1), len(parts2))
    parts1.extend([0] * (max_len - len(parts1)))
    parts2.extend([0] * (max_len - len(parts2)))

    for p1, p2 in zip(parts1, parts2):
        if p1 < p2:
            return -1
        if p1 > p2:
            return 1
    return 0


if __name__ == "__main__":
    # Quick test
    print(f"State dir: {get_state_dir()}")
    print(f"Has fcntl: {HAS_FCNTL}")
    print(f"Has msvcrt: {HAS_MSVCRT}")
    print(f"State: {load_state()}")
