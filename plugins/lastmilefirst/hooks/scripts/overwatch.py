#!/usr/bin/env python3
"""
Lastmilefirst Overwatch - Cross-platform utilities
Provides file locking, state management, and shared functionality.

State format (v2):
{
  "version": 2,
  "global": {
    "last_plugin_check": 0,      # unix ts of the last network plugin-update check
    "last_review_claude": 0,
    "plugin_update_cache": {}    # {"<name>@<marketplace>": {"available": "x.y.z", "checked_at": ts}}
  },
  "orgs": {"gruntwork": {"last_organize": 0, "last_review_claude": 0}},
  "projects": {"gruntwork/gruntwork-leamo": {"last_review": 0, ...}}
}
"""

import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
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
    """Migrate v1 flat state to v2 nested structure in-place. Idempotent.

    Also forward-fills newer v2 fields (e.g. plugin_update_cache) so a state
    file written by an older version gains them on load without a version bump.
    """
    if state.get("version") == 2:
        state.setdefault("global", {}).setdefault("plugin_update_cache", {})
        return state

    state["version"] = 2
    state["global"] = {
        "last_plugin_check": state.pop("last_plugin_check", 0),
        "last_review_claude": 0,
        "plugin_update_cache": {},
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
    "global": {"last_plugin_check": 0, "last_review_claude": 0, "plugin_update_cache": {}},
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

    Note: only fully-numeric components are compared; a component with a
    non-numeric suffix is DROPPED entirely, so '1.2.3-beta' normalizes to
    [1, 2] (not [1, 2, 3]). Callers that must not mis-rank pre-releases should
    filter them with is_pre_release() BEFORE calling this.
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


# ---------------------------------------------------------------------------
# Network plugin-update check (upstream marketplace manifest)
#
# Reads the version /plugin update would resolve -- the upstream marketplace
# manifest on the repo's default branch -- and compares it to what's installed.
# All network egress is pinned to raw.githubusercontent.com; nothing fetched is
# executed. Every failure degrades to None/skip so a session start never breaks.
# ---------------------------------------------------------------------------

_RAW_HOST = "raw.githubusercontent.com"
_MAX_FETCH_BYTES = 1_000_000
_DEFAULT_BRANCHES = ("main", "master")
# owner/repo, two segments, conservative charset -- excludes '@', '..', '%',
# whitespace, extra slashes, leading '-'/'.'
_GITHUB_REPO_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*$")
_SOURCE_PATH_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")


# --- U3: version selection + pre-release guard ---------------------------

def is_pre_release(version: str) -> bool:
    """True if any dotted component is not purely numeric (e.g. '0.17.1-rc1')."""
    if not isinstance(version, str) or not version:
        return True
    return any(not part.isdigit() for part in version.split("."))


def is_newer(installed: str, upstream: str) -> bool:
    """True if `upstream` is a strictly-newer stable release than `installed`.

    Pre-release upstreams are never considered newer (version_compare drops
    their suffix and would mis-rank them). Versions here are plain semver with
    no leading 'v' (manifest/plugin.json values, not git tags).
    """
    if not installed or not upstream:
        return False
    if is_pre_release(upstream):
        return False
    return version_compare(installed, upstream) < 0


# --- U1: marketplace repo + source-path resolution -----------------------

def _load_known_marketplaces(plugins_dir: Path) -> Dict[str, Any]:
    """Load ~/.claude/plugins/known_marketplaces.json, or {} on any error."""
    try:
        with open(plugins_dir / "known_marketplaces.json", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, IOError, OSError):
        return {}


def resolve_github_repo(marketplace: str, known: Dict[str, Any]) -> Optional[str]:
    """Return the validated 'owner/repo' for a github-sourced marketplace, else None."""
    entry = known.get(marketplace)
    if not isinstance(entry, dict):
        return None
    source = entry.get("source")
    if not isinstance(source, dict) or source.get("source") != "github":
        return None
    repo = source.get("repo")
    if not isinstance(repo, str) or not _GITHUB_REPO_RE.match(repo):
        return None
    return repo


def _validate_source_path(source: Any) -> Optional[str]:
    """Return a safe in-repo path for a plugin `source`, or None to skip.

    Only string sources are supported (dict/external sources -> None). Rejects
    '%' (encoded traversal), '..' segments, and anything outside the allowlist.
    '.'/'./' collapse to '' (repo root).
    """
    if not isinstance(source, str) or "%" in source:
        return None
    s = source.strip()
    if s.startswith("./"):
        s = s[2:]
    s = s.strip("/")
    if s in ("", "."):
        return ""  # repo root
    if any(seg == ".." for seg in s.split("/")) or not _SOURCE_PATH_RE.match(s):
        return None
    return s


# --- U2: upstream version fetcher (stubbable HTTP boundary) ---------------

class _PinnedRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Refuse any redirect whose target host is not exactly raw.githubusercontent.com."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urllib.parse.urlsplit(newurl).hostname != _RAW_HOST:
            return None
        return super().redirect_request(req, fp, code, msg, headers, newurl)


# Built once: pinned redirects + empty ProxyHandler (ignore *_proxy env for
# deterministic, security-scoped egress). No cookie/auth handlers are added.
_OPENER = urllib.request.build_opener(
    _PinnedRedirectHandler,
    urllib.request.ProxyHandler({}),
)


def _http_get_json(url: str, timeout: float) -> Optional[Any]:
    """GET `url` (must be https://raw.githubusercontent.com/...) and parse JSON.

    Returns the parsed object, or None on any failure. Reads at most
    _MAX_FETCH_BYTES (bounded before consuming the body; Content-Length is not
    trusted). This is the ONLY function that touches the network -- tests stub it.
    """
    if not url.startswith("https://" + _RAW_HOST + "/"):
        return None
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "lastmilefirst-overwatch"})
        with _OPENER.open(req, timeout=timeout) as resp:
            if getattr(resp, "status", 200) not in (200, None):
                return None
            body = resp.read(_MAX_FETCH_BYTES + 1)
        if len(body) > _MAX_FETCH_BYTES:
            return None
        return json.loads(body.decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError, json.JSONDecodeError):
        return None


def _find_plugin_entry(manifest: Any, plugin_name: str) -> Optional[Dict[str, Any]]:
    """Find the plugins[] entry matching plugin_name in a marketplace manifest."""
    if not isinstance(manifest, dict):
        return None
    for p in manifest.get("plugins", []):
        if isinstance(p, dict) and p.get("name") == plugin_name:
            return p
    return None


def _plugin_json_url(repo: str, branch: str, source_path: str) -> str:
    """Build the raw URL for a plugin's plugin.json ('' source_path = repo root)."""
    prefix = f"{source_path}/" if source_path else ""
    return f"https://{_RAW_HOST}/{repo}/{branch}/{prefix}.claude-plugin/plugin.json"


def fetch_upstream_version(
    repo: str,
    plugin_name: str,
    deadline: float,
    per_timeout: float = 2.0,
) -> Optional[str]:
    """Return the upstream manifest version for plugin_name in repo, or None.

    Two-level: inline plugins[].version, else the plugin's own plugin.json at a
    validated in-repo string source. Tries default branches (main, master) until
    a manifest is found. Respects `deadline` (time.monotonic()) as a hard stop.
    """
    for branch in _DEFAULT_BRANCHES:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return None
        manifest = _http_get_json(
            f"https://{_RAW_HOST}/{repo}/{branch}/.claude-plugin/marketplace.json",
            timeout=min(remaining, per_timeout),
        )
        if manifest is None:
            continue  # branch 404 or fetch failure -- try the next candidate
        entry = _find_plugin_entry(manifest, plugin_name)
        if entry is None:
            return None  # plugin not listed upstream -- skip
        version = entry.get("version")
        if isinstance(version, str) and version:
            return version
        source_path = _validate_source_path(entry.get("source"))
        if source_path is None:
            return None  # dict/external/unsafe source -- skip
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return None
        plugin_json = _http_get_json(
            _plugin_json_url(repo, branch, source_path),
            timeout=min(remaining, per_timeout),
        )
        if not isinstance(plugin_json, dict):
            return None
        v = plugin_json.get("version")
        return v if isinstance(v, str) and v else None
    return None


# --- U4: throttle + result cache -----------------------------------------

def is_plugin_check_due(state: Dict[str, Any], now: int, interval: int = 86400) -> bool:
    """True if the network plugin check hasn't run within `interval` seconds."""
    last = state.get("global", {}).get("last_plugin_check", 0) or 0
    return (now - last) > interval


def record_check_started(now: int) -> None:
    """Advance last_plugin_check BEFORE fetching, so the throttle holds even if
    the refresh is interrupted (R3)."""
    update_state_field("last_plugin_check", now)


def get_plugin_update_cache(state: Dict[str, Any]) -> Dict[str, Any]:
    """Return the cached {id: {available, checked_at}} map from state."""
    cache = state.get("global", {}).get("plugin_update_cache", {})
    return cache if isinstance(cache, dict) else {}


def write_plugin_update_results(results: Dict[str, str], now: int) -> None:
    """Persist a fresh cache from `results` ({id: available}).

    Writing wholesale from the current installed set (the caller's `results`)
    naturally prunes entries for uninstalled plugins (R8/KTD5).
    """
    cache = {pid: {"available": ver, "checked_at": now} for pid, ver in results.items()}
    update_state_field("plugin_update_cache", cache)


if __name__ == "__main__":
    # Quick test
    print(f"State dir: {get_state_dir()}")
    print(f"Has fcntl: {HAS_FCNTL}")
    print(f"Has msvcrt: {HAS_MSVCRT}")
    state = load_state()
    print(f"State (v{state.get('version', '?')}): {json.dumps(state, indent=2)}")
    ctx = resolve_context()
    print(f"Context: {ctx}")
