#!/usr/bin/env python3
"""
Lastmilefirst Overwatch - Session Start Hook
Runs at the start of every Claude Code session.
Output becomes part of Claude's context.
"""

import json
import os
import random
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional

# Add script directory to path for local imports
sys.path.insert(0, str(Path(__file__).parent))

from overwatch import (
    load_state,
    get_plugins_dir,
    get_invocations_file,
    get_tmp_dir,
    get_lock_file,
    file_lock,
    version_compare,
)

# Path to todos-summary scripts (sibling skill)
TODOS_SUMMARY_SCRIPTS = Path(__file__).parent.parent.parent / "skills" / "todos-summary" / "scripts"


def check_git_status() -> Optional[str]:
    """Check for uncommitted git changes in current directory."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode != 0:
            return None

        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=5
        )
        lines = [line for line in result.stdout.strip().split('\n') if line]
        if lines:
            return f"  {len(lines)} uncommitted file(s) in this repo"
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass  # Git not available or too slow - skip silently
    return None


def check_review_status(state: Dict) -> Optional[str]:
    """Check days since last review."""
    last_review = state.get("last_review", 0)
    if last_review == 0:
        return "No project review on record - consider running /review-project"

    days_since = (int(time.time()) - last_review) // 86400
    if days_since >= 7:
        return f"{days_since} days since last /review-project"
    return None


def check_organize_status(state: Dict) -> Optional[str]:
    """Check days since last organize."""
    last_organize = state.get("last_organize", 0)
    if last_organize == 0:
        return None  # Don't alert on first run

    days_since = (int(time.time()) - last_organize) // 86400
    if days_since >= 14:
        return f"{days_since} days since last /organize-project"
    return None


def check_plugin_updates() -> List[str]:
    """Check for available plugin updates."""
    plugins_dir = get_plugins_dir()
    if not plugins_dir:
        return []

    installed_file = plugins_dir / "installed_plugins.json"
    marketplaces_dir = plugins_dir / "marketplaces"

    if not installed_file.exists() or not marketplaces_dir.exists():
        return []

    try:
        with open(installed_file, encoding='utf-8') as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError):
        return []

    updates = []
    plugins = data.get("plugins", {})

    for plugin_id, installs in plugins.items():
        if not installs:
            continue

        installed = installs[0].get("version", "")
        if not installed:
            continue

        parts = plugin_id.split("@")
        if len(parts) != 2:
            continue

        plugin_name, marketplace = parts

        marketplace_json = (
            marketplaces_dir / marketplace / "plugins" / plugin_name /
            ".claude-plugin" / "plugin.json"
        )

        if not marketplace_json.exists():
            continue

        try:
            with open(marketplace_json, encoding='utf-8') as f:
                mp_data = json.load(f)
            available = mp_data.get("version", "")
        except (json.JSONDecodeError, IOError):
            continue

        if available and version_compare(installed, available) < 0:
            updates.append(f"   {plugin_name}@{marketplace}: {installed} -> {available}")

    return updates


def check_usage_stats() -> List[str]:
    """Generate usage statistics for the past week."""
    invocations_file = get_invocations_file()
    if not invocations_file.exists():
        return []

    week_ago = int(time.time()) - 604800
    month_ago = int(time.time()) - 2592000

    weekly_invocations: List[str] = []
    retained_lines: List[str] = []

    try:
        with open(invocations_file, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split("|")
                if len(parts) >= 2:
                    try:
                        ts = int(parts[0])
                        if ts >= month_ago:
                            retained_lines.append(line)
                        if ts >= week_ago:
                            weekly_invocations.append(parts[1])
                    except ValueError:
                        continue

        # Prune old entries with file locking to prevent race with log_invocation
        with file_lock(get_lock_file()):
            with open(invocations_file, 'w', encoding='utf-8') as f:
                if retained_lines:
                    f.write('\n'.join(retained_lines) + '\n')

    except IOError:
        return []

    if not weekly_invocations:
        return []

    results = [f"{len(weekly_invocations)} skill invocations this week"]

    # Count top skills
    counts = Counter(s for s in weekly_invocations if s != "unknown")
    if counts:
        top = counts.most_common(3)
        top_str = " ".join(f"{name} ({count})" for name, count in top)
        results.append(f"   Top: {top_str}")

    # Occasional prompt (roughly 1 in 10)
    if random.randint(0, 9) == 0 and len(weekly_invocations) >= 10:
        results.append("   Enjoying these plugins? Consider starring their repos!")

    return results


def check_stale_todos() -> Optional[str]:
    """Check for stale todos in .claude/work/todos."""
    todos_dir = Path(".claude/work/todos")
    if not todos_dir.exists():
        return None

    fourteen_days_ago = time.time() - (14 * 86400)
    stale_count = 0

    try:
        for todo_file in todos_dir.glob("*.md"):
            if todo_file.stat().st_mtime < fourteen_days_ago:
                stale_count += 1
    except (OSError, IOError):
        pass

    if stale_count > 0:
        return f"{stale_count} todo(s) older than 14 days - consider /review-work"
    return None


def check_claude_md() -> Optional[str]:
    """Check if CLAUDE.md exists in current directory."""
    if not Path("CLAUDE.md").exists():
        return "No CLAUDE.md in this project - consider /organize-claude scaffold"
    return None


def check_cross_project_blockers() -> List[str]:
    """
    Check for urgent/blocked todos across all projects.

    Uses the todos-summary aggregator to scan workspaces and report
    items that need attention.
    """
    results: List[str] = []

    # Only run if the todos-summary skill is available
    if not TODOS_SUMMARY_SCRIPTS.exists():
        return results

    try:
        # Import the aggregator dynamically
        sys.path.insert(0, str(TODOS_SUMMARY_SCRIPTS))
        from aggregator import TodoAggregator
        from formatters import OverwatchFormatter

        aggregator = TodoAggregator()
        data = aggregator.aggregate_todos(use_cache=True)

        # Use the Overwatch formatter for compact output
        formatter = OverwatchFormatter()
        output = formatter.format(data)

        if output:
            for line in output.split("\n"):
                results.append(line)

    except ImportError:
        pass  # Skill not properly installed - skip silently
    except Exception:
        pass  # Any error - skip silently to not break session start
    finally:
        # Clean up sys.path
        if str(TODOS_SUMMARY_SCRIPTS) in sys.path:
            sys.path.remove(str(TODOS_SUMMARY_SCRIPTS))

    return results


def main() -> None:
    alerts: List[str] = []

    # Load state
    state = load_state()

    # Check 1: Git status
    git_alert = check_git_status()
    if git_alert:
        alerts.append(git_alert)

    # Check 2: Review status
    review_alert = check_review_status(state)
    if review_alert:
        alerts.append(review_alert)

    # Check 3: Organize status
    organize_alert = check_organize_status(state)
    if organize_alert:
        alerts.append(organize_alert)

    # Check 4: Plugin updates
    plugin_updates = check_plugin_updates()
    if plugin_updates:
        alerts.append("Plugin updates available:")
        alerts.extend(plugin_updates)
        alerts.append("   Run: claude plugin update <plugin>@<marketplace>")

    # Check 5: Usage stats
    usage_stats = check_usage_stats()
    if usage_stats:
        alerts.extend(usage_stats)

    # Check 6: Stale todos
    todos_alert = check_stale_todos()
    if todos_alert:
        alerts.append(todos_alert)

    # Check 7: CLAUDE.md
    claude_md_alert = check_claude_md()
    if claude_md_alert:
        alerts.append(claude_md_alert)

    # Check 8: Cross-project blockers
    blocker_alerts = check_cross_project_blockers()
    if blocker_alerts:
        alerts.extend(blocker_alerts)

    # Output to both stdout (for Claude context) and stderr (for user terminal)
    if alerts:
        header = [
            "",
            "-" * 59,
            "|  OVERWATCH" + " " * 46 + "|",
            "-" * 59,
        ]
        # Print to stdout for Claude
        for line in header:
            print(line)
        for alert in alerts:
            print(alert)
        # Echo to stderr for user visibility
        for line in header:
            print(line, file=sys.stderr)
        for alert in alerts:
            print(alert, file=sys.stderr)

    # Clear session change log
    session_log = get_tmp_dir() / "session-changes.log"
    try:
        session_log.unlink(missing_ok=True)
    except (OSError, IOError):
        pass  # Ignore errors clearing log


if __name__ == "__main__":
    main()
