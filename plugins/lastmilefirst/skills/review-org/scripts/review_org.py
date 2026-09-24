#!/usr/bin/env python3
"""
Project roll-up for one org, read from the Overwatch state file.

For each project directory in the org, reports whether it has a CLAUDE.md,
whether that file declares an archetype, which actions (review, organize,
secret scan, CLAUDE.md review) are on record, and which are past the Overwatch
threshold. Also prints the org's own record (review_org, review_claude,
organize).

Read-only. The state file is read directly, without taking the Overwatch lock
(taking it would write a lock file) and without the load_state() side effect of
creating the file when it is missing.

"Project directory" and the threshold rule match Overwatch's workspace summary
in session_start.py, so the two never disagree about the same project:

- every non-hidden subdirectory of the org counts as a project directory;
- an action past its threshold only counts when the repo has commits since
  that action ran, since a repo that has not changed has nothing new to check.

Output says what was measured ("3 of 5 project directories have a CLAUDE.md"),
never a judgment word.

Usage:
  review_org.py --org ~/Code/gruntwork
  review_org.py --org ~/Code/gruntwork --json
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

_SKILLS = Path(__file__).resolve().parents[2]
_HOOKS_SCRIPTS = _SKILLS.parent / "hooks" / "scripts"
_ARCHETYPES_DIR = _SKILLS / "organize-claude" / "scripts"
for _p in (_HOOKS_SCRIPTS, _ARCHETYPES_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

# Thresholds come from Overwatch so the roll-up and the session-start alerts
# use the same numbers. overwatch.py is stdlib-only and has no import-time
# side effects.
from overwatch import (  # noqa: E402
    ORGANIZE_THRESHOLD_DAYS,
    REVIEW_CLAUDE_THRESHOLD_DAYS,
    REVIEW_THRESHOLD_DAYS,
    SECRET_SCAN_THRESHOLD_DAYS,
    _ensure_v2,
)

try:
    from archetypes import detect_archetype  # noqa: E402
except ImportError:  # pragma: no cover - sibling skill missing
    detect_archetype = None

DEFAULT_STATE_FILE = Path.home() / ".claude" / "lastmilefirst" / "overwatch-state.json"

# (state field suffix, label, threshold in days)
PROJECT_ACTIONS = [
    ("review", "project review", REVIEW_THRESHOLD_DAYS),
    ("organize", "organize", ORGANIZE_THRESHOLD_DAYS),
    ("secret_scan", "secret scan", SECRET_SCAN_THRESHOLD_DAYS),
    ("review_claude", "CLAUDE.md review", REVIEW_CLAUDE_THRESHOLD_DAYS),
]

ORG_ACTIONS = [
    ("review_org", "org review"),
    ("review_claude", "org CLAUDE.md review"),
    ("organize", "organize"),
]

DAY = 86400


def read_state(state_file: Path) -> Optional[Dict[str, Any]]:
    """Return the v2 state dict, or None if the file is missing or unreadable."""
    if not state_file.exists():
        return None
    try:
        with open(state_file, encoding="utf-8") as f:
            return _ensure_v2(json.load(f))
    except (json.JSONDecodeError, OSError):
        return None


def last_commit_ts(repo: Path) -> int:
    """Unix time of the latest commit, or 0 if not a repo or no commits."""
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), "log", "-1", "--format=%ct"],
            capture_output=True, text=True, timeout=3,
        )
        if result.returncode == 0 and result.stdout.strip():
            return int(result.stdout.strip())
    except (subprocess.TimeoutExpired, FileNotFoundError, ValueError):
        pass
    return 0


def project_dirs(org_dir: Path) -> List[Path]:
    return sorted(
        p for p in org_dir.iterdir()
        if p.is_dir() and not p.name.startswith(".")
    )


def _action_status(last: int, last_commit: int, threshold_days: int, now: int) -> Dict[str, Any]:
    days = (now - last) // DAY if last else None
    past = bool(last) and days >= threshold_days and last_commit > last
    return {
        "last": last,
        "days_since": days,
        "threshold_days": threshold_days,
        "commits_since": bool(last) and last_commit > last,
        "past_threshold": past,
    }


def build_rollup(
    org_dir: Path,
    state: Optional[Dict[str, Any]],
    now: Optional[int] = None,
    commit_ts: Callable[[Path], int] = last_commit_ts,
) -> Dict[str, Any]:
    now = now if now is not None else int(time.time())
    org_key = org_dir.name
    projects_state = (state or {}).get("projects", {})
    org_state = (state or {}).get("orgs", {}).get(org_key, {})

    projects = []
    for pdir in project_dirs(org_dir):
        key = f"{org_key}/{pdir.name}"
        pstate = projects_state.get(key, {})
        claude_md = pdir / "CLAUDE.md"
        has_claude = claude_md.is_file()
        archetype = None
        if has_claude and detect_archetype is not None:
            try:
                archetype = detect_archetype(claude_md.read_text(encoding="utf-8"))
            except OSError:
                pass
        lc = commit_ts(pdir)
        actions = {
            field: _action_status(int(pstate.get(f"last_{field}", 0) or 0), lc, thr, now)
            for field, _label, thr in PROJECT_ACTIONS
        }
        projects.append({
            "name": pdir.name,
            "key": key,
            "has_claude_md": has_claude,
            "archetype": archetype,
            "has_commits": lc > 0,
            "last_commit": lc,
            "in_state": key in projects_state,
            "actions": actions,
        })

    org_record = {}
    for field, _label in ORG_ACTIONS:
        ts = int(org_state.get(f"last_{field}", 0) or 0)
        org_record[field] = {"last": ts, "days_since": (now - ts) // DAY if ts else None}

    return {
        "org": org_key,
        "org_path": str(org_dir),
        "state_found": state is not None,
        "generated_at": now,
        "org_record": org_record,
        "projects": projects,
    }


def _fmt_ts(ts: int, days: Optional[int]) -> str:
    if not ts:
        return "none on record"
    date = datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
    if days == 0:
        return f"{date} (today)"
    return f"{date} ({days} day{'s' if days != 1 else ''} ago)"


def _names(items) -> str:
    return ", ".join(items)


def format_text(rollup: Dict[str, Any], state_file: Path) -> str:
    projects = rollup["projects"]
    total = len(projects)
    noun = "project directory" if total == 1 else "project directories"
    lines = [f"Project roll-up: {rollup['org']} ({total} {noun})"]
    if rollup["state_found"]:
        lines.append(f"Overwatch state: {state_file} (read-only)")
    else:
        lines.append(
            f"Overwatch state: no readable file at {state_file}, so every action reads as none on record"
        )
    lines.append("")

    lines.append("Org record")
    for field, label in ORG_ACTIONS:
        rec = rollup["org_record"][field]
        lines.append(f"  {label}: {_fmt_ts(rec['last'], rec['days_since'])}")
    lines.append("")

    if total == 0:
        lines.append("No project directories in this org.")
        return "\n".join(lines)

    with_claude = [p for p in projects if p["has_claude_md"]]
    without_claude = [p["name"] for p in projects if not p["has_claude_md"]]
    no_arch = [p["name"] for p in with_claude if not p["archetype"]]
    lines.append("Project files")
    line = f"  {len(with_claude)} of {total} project directories have a CLAUDE.md"
    lines.append(line + (f". Without one: {_names(without_claude)}" if without_claude else ""))
    if with_claude:
        line = f"  {len(with_claude) - len(no_arch)} of {len(with_claude)} CLAUDE.md files declare an archetype"
        lines.append(line + (f". Without one: {_names(no_arch)}" if no_arch else ""))
    no_commits = [p["name"] for p in projects if not p["has_commits"]]
    if no_commits:
        lines.append(
            f"  {len(no_commits)} of {total} have no commits (not a git repo, or empty): {_names(no_commits)}"
        )
    lines.append("")

    lines.append("On record")
    for field, label, _thr in PROJECT_ACTIONS:
        none = [p["name"] for p in projects if not p["actions"][field]["last"]]
        line = f"  {label}: {total - len(none)} of {total} have one on record"
        lines.append(line + (f". None: {_names(none)}" if none else ""))
    lines.append("")

    lines.append("Past the Overwatch threshold (counted only when there are commits since the last run)")
    for field, label, thr in PROJECT_ACTIONS:
        past = [p for p in projects if p["actions"][field]["past_threshold"]]
        detail = _names(f"{p['name']} ({p['actions'][field]['days_since']} days)" for p in past)
        line = f"  {label}, {thr} days: {len(past)} of {total}"
        lines.append(line + (f": {detail}" if past else ""))

    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read-only project roll-up for one org, from the Overwatch state file."
    )
    parser.add_argument("--org", required=True, type=Path, help="path to the org directory")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--state-file", type=Path, default=DEFAULT_STATE_FILE,
                        help="Overwatch state file (default: %(default)s)")
    args = parser.parse_args(argv)

    org_dir = args.org.expanduser()
    if not org_dir.is_dir():
        print(f"Error: {org_dir} is not a directory.", file=sys.stderr)
        return 2
    # Absolute without resolving symlinks, so the org key is the name the
    # user sees in the workspace, which is what Overwatch keys state by.
    org_dir = Path(os.path.abspath(org_dir))

    state_file = args.state_file.expanduser()
    rollup = build_rollup(org_dir, read_state(state_file))

    if args.json:
        rollup["state_file"] = str(state_file)
        print(json.dumps(rollup, indent=2))
    else:
        print(format_text(rollup, state_file))
    return 0


if __name__ == "__main__":
    sys.exit(main())
