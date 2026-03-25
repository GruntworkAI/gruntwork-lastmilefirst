#!/usr/bin/env python3
"""
Lastmilefirst Overwatch - Cross-platform utilities
Provides file locking, state management, and shared functionality.

State format (v2):
{
  "version": 2,
  "global": {"last_plugin_check": 0, "last_review_claude": 0},
  "orgs": {"gruntwork": {"last_organize": 0, "last_review_claude": 0}},
  "projects": {"gruntwork/gruntwork-leamo": {"last_review": 0, ...}}
}
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


# ---------------------------------------------------------------------------
# v1 -> v2 migration
# ---------------------------------------------------------------------------

def _ensure_v2(state: Dict[str, Any]) -> Dict[str, Any]:
    """Migrate v1 flat state to v2 nested structure in-place. Idempotent."""
    if state.get("version") == 2:
        return state

    state["version"] = 2
    state["global"] = {
        "last_plugin_check": state.pop("last_plugin_check", 0),
        "last_review_claude": 0,
    }
    # Discard old global timestamps -- they were never scoped to a project
    state.pop("last_review", None)
    state.pop("last_organize", None)
    state.pop("last_secret_scan", None)
    state.setdefault("orgs", {})
    state.setdefault("projects", {})
    return state


_V2_DEFAULT: Dict[str, Any] = {
    "version": 2,
    "global": {"last_plugin_check": 0, "last_review_claude": 0},
    "orgs": {},
    "projects": {},
}


# ---------------------------------------------------------------------------
# State load / save
# ---------------------------------------------------------------------------

def _load_state_unlocked() -> Dict[str, Any]:
    """
    Load state without acquiring lock. Internal use only.
    Callers must hold the lock if thread safety is required.
    """
    state_file = get_state_file()

    if not state_file.exists():
        return json.loads(json.dumps(_V2_DEFAULT))  # deep copy

    try:
        with open(state_file, encoding='utf-8') as f:
            state = json.load(f)
            return _ensure_v2(state)
    except (json.JSONDecodeError, IOError):
        return json.loads(json.dumps(_V2_DEFAULT))


def _save_state_unlocked(state: Dict[str, Any]) -> None:
    """Save state without acquiring lock. Callers must hold the lock."""
    state_file = get_state_file()
    with open(state_file, 'w', encoding='utf-8') as f:
        json.dump(state, f, indent=2)


def load_state() -> Dict[str, Any]:
    """Load the Overwatch state with file locking. Returns v2 structure."""
    lock_file = get_lock_file()
    state_file = get_state_file()

    with file_lock(lock_file):
        state = _load_state_unlocked()
        # Initialize file if it doesn't exist
        if not state_file.exists():
            _save_state_unlocked(state)
        return state


def save_state(state: Dict[str, Any]) -> None:
    """Save the Overwatch state with file locking."""
    lock_file = get_lock_file()
    with file_lock(lock_file):
        _save_state_unlocked(state)


def update_state_field(field: str, value: Any) -> None:
    """Update a single field in the global scope. Backward-compatible."""
    update_scoped_state("global", None, field, value)


# ---------------------------------------------------------------------------
# Scoped state operations
# ---------------------------------------------------------------------------

def get_scoped_state(scope: str, key: Optional[str]) -> Dict[str, Any]:
    """
    Get state for a given scope/key.
    scope: "global", "orgs", or "projects"
    key: org name or project key (ignored for "global")
    Returns empty dict if not found.
    """
    state = load_state()
    if scope == "global":
        return state.get("global", {})
    return state.get(scope, {}).get(key, {}) if key else {}


def update_scoped_state(scope: str, key: Optional[str], field: str, value: Any) -> None:
    """
    Update a field within a scope.
    scope: "global", "orgs", or "projects"
    key: org name or project key (ignored for "global")
    """
    lock_file = get_lock_file()
    with file_lock(lock_file):
        state = _load_state_unlocked()
        if scope == "global":
            state.setdefault("global", {})[field] = value
        else:
            state.setdefault(scope, {}).setdefault(key, {})[field] = value
        _save_state_unlocked(state)


# ---------------------------------------------------------------------------
# Context detection
# ---------------------------------------------------------------------------

def _load_organize_config() -> Optional[Dict[str, Any]]:
    """Load ~/.config/organize-claude/config.json if it exists."""
    config_file = Path.home() / ".config" / "organize-claude" / "config.json"
    if not config_file.exists():
        return None
    try:
        with open(config_file, encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def resolve_context(cwd: Optional[Path] = None) -> Dict[str, Optional[str]]:
    """
    Derive org name and project key from CWD and workspace config.
    Returns {"org": "gruntwork", "project": "gruntwork/gruntwork-leamo"}
    or {"org": None, "project": None} if outside a recognized workspace.
    """
    cwd = cwd or Path.cwd()
    config = _load_organize_config()
    if not config:
        return {"org": None, "project": None}

    workspace = Path(config.get("workspace", ""))
    if not workspace.is_dir():
        return {"org": None, "project": None}

    # Resolve symlinks for reliable comparison
    try:
        cwd_resolved = cwd.resolve()
        workspace_resolved = workspace.resolve()
    except OSError:
        return {"org": None, "project": None}

    try:
        rel = cwd_resolved.relative_to(workspace_resolved)
    except ValueError:
        return {"org": None, "project": None}

    parts = rel.parts
    orgs = config.get("orgs", [])

    org = parts[0] if len(parts) >= 1 and parts[0] in orgs else None
    project_key = f"{parts[0]}/{parts[1]}" if len(parts) >= 2 and org else None

    return {"org": org, "project": project_key}


def update_project_state(field: str, value: Any, cwd: Optional[Path] = None) -> None:
    """Update a field for the current project (auto-detected from CWD)."""
    ctx = resolve_context(cwd)
    if ctx["project"]:
        update_scoped_state("projects", ctx["project"], field, value)


def update_org_state(field: str, value: Any, cwd: Optional[Path] = None) -> None:
    """Update a field for the current org (auto-detected from CWD)."""
    ctx = resolve_context(cwd)
    if ctx["org"]:
        update_scoped_state("orgs", ctx["org"], field, value)


# ---------------------------------------------------------------------------
# Plugin utilities (unchanged)
# ---------------------------------------------------------------------------

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
    state = load_state()
    print(f"State (v{state.get('version', '?')}): {json.dumps(state, indent=2)}")
    ctx = resolve_context()
    print(f"Context: {ctx}")
