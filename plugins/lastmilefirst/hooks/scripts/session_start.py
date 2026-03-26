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
    resolve_context,
    get_scoped_state,
    get_plugins_dir,
    get_invocations_file,
    get_tmp_dir,
    get_lock_file,
    file_lock,
    version_compare,
    _load_organize_config,
)

# Import archetype detection from organize-claude
_ARCHETYPES_DIR = Path(__file__).parent.parent.parent / "skills" / "organize-claude" / "scripts"
sys.path.insert(0, str(_ARCHETYPES_DIR))
try:
    from archetypes import detect_archetype as _detect_archetype
except ImportError:
    _detect_archetype = None

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
            return f"ACTION REQUIRED: {len(lines)} uncommitted file(s) in this repo. Commit or stash before proceeding."
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass  # Git not available or too slow - skip silently
    return None


def check_review_status(state: Dict, project_label: Optional[str] = None) -> Optional[str]:
    """Check days since last review for a project."""
    last_review = state.get("last_review", 0)
    label = f" of {project_label}" if project_label else ""
    if last_review == 0:
        return f"ACTION REQUIRED: No project review on record{label}. Run /run-review-project before starting other work."

    days_since = (int(time.time()) - last_review) // 86400
    if days_since >= 7:
        return f"ACTION REQUIRED: {days_since} days since last review{label}. Run /run-review-project."
    return None


def check_organize_status(state: Dict, project_label: Optional[str] = None) -> Optional[str]:
    """Check days since last organize for a project."""
    last_organize = state.get("last_organize", 0)
    if last_organize == 0:
        return None  # Don't alert on first run

    label = f" of {project_label}" if project_label else ""
    days_since = (int(time.time()) - last_organize) // 86400
    if days_since >= 14:
        return f"ACTION REQUIRED: {days_since} days since last organization{label}. Run /run-organize-project."
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
        return f"ACTION REQUIRED: {stale_count} todo(s) older than 14 days. Run /run-review-work to triage."
    return None


def check_secret_scan_status(state: Dict, project_label: Optional[str] = None) -> Optional[str]:
    """Check days since last secret scan for a project."""
    last_scan = state.get("last_secret_scan", 0)
    label = f" of {project_label}" if project_label else ""
    if last_scan == 0:
        return f"ACTION REQUIRED: Never scanned for secrets{label}. Run /run-scan-secrets before proceeding."

    days_since = (int(time.time()) - last_scan) // 86400
    if days_since >= 7:
        return f"ACTION REQUIRED: {days_since} days since last secrets scan{label}. Run /run-scan-secrets."
    return None


def check_claude_review_status(
    project_state: Dict,
    org_state: Dict,
    global_state: Dict,
    project_label: Optional[str] = None,
    org_label: Optional[str] = None,
) -> List[str]:
    """Check CLAUDE.md review freshness at all levels. 30-day threshold."""
    alerts: List[str] = []
    threshold = 30 * 86400
    now = int(time.time())

    checks = [
        (global_state, "last_review_claude", "user-level CLAUDE.md"),
    ]
    if org_label:
        checks.append((org_state, "last_review_claude", f"org CLAUDE.md ({org_label})"))
    if project_label:
        checks.append((project_state, "last_review_claude", f"project CLAUDE.md ({project_label})"))

    for state, field, label in checks:
        ts = state.get(field, 0)
        if ts == 0:
            alerts.append(f"WARNING: Never reviewed {label}. Consider running /run-review-claude.")
        elif (now - ts) >= threshold:
            days = (now - ts) // 86400
            alerts.append(f"WARNING: {days} days since last review of {label}. Consider running /run-review-claude.")

    return alerts


def check_repo_visibility() -> Optional[str]:
    """Check if current repo is public via gh CLI."""
    try:
        # First check if we're in a git repo with a remote
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return None  # No remote, skip check

        result = subprocess.run(
            ["gh", "repo", "view", "--json", "visibility,nameWithOwner",
             "-q", '.visibility + " " + .nameWithOwner'],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            parts = result.stdout.strip().split(" ", 1)
            if len(parts) == 2 and parts[0].upper() == "PUBLIC":
                return f"WARNING: PUBLIC repo ({parts[1]}) — do not commit secrets or sensitive content"
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass  # gh not available or too slow - skip silently
    return None


def check_claude_md() -> Optional[str]:
    """Check if CLAUDE.md exists in current directory."""
    if not Path("CLAUDE.md").exists():
        return "ACTION REQUIRED: No CLAUDE.md in this project. Run /run-organize-project to scaffold."
    return None


def check_overwatch_guidance() -> Optional[str]:
    """Check if any CLAUDE.md in the hierarchy contains Overwatch response guidance."""
    search_paths = [
        Path("CLAUDE.md"),           # Project level
        Path.home() / "Code" / "CLAUDE.md",  # Top-level workspace
    ]

    # Walk up to find org-level CLAUDE.md (parent of current project)
    cwd = Path.cwd()
    if cwd.parent != cwd:
        org_claude = cwd.parent / "CLAUDE.md"
        if org_claude not in search_paths:
            search_paths.insert(1, org_claude)

    keywords = ["overwatch", "overwatch alert", "overwatch response"]

    for path in search_paths:
        try:
            if path.exists():
                content = path.read_text(encoding="utf-8").lower()
                if any(kw in content for kw in keywords):
                    return None  # Found guidance, no alert needed
        except (OSError, IOError):
            continue

    return "ACTION REQUIRED: No Overwatch response guidance in CLAUDE.md. Run /run-organize-claude to add it."


def check_archetype() -> Optional[str]:
    """Check if project CLAUDE.md declares an archetype."""
    if _detect_archetype is None:
        return None  # Archetype module not available, skip silently

    claude_md = Path("CLAUDE.md")
    if not claude_md.exists():
        return None  # No CLAUDE.md — separate check handles this

    try:
        content = claude_md.read_text()
        archetype = _detect_archetype(content)
        if archetype is None:
            return "WARNING: No archetype set in project CLAUDE.md. Add `## Archetype: Deployable|Usable|Referenceable|Experimental` for targeted section checks."
    except (OSError, IOError):
        pass
    return None


def check_org_infrastructure(config: Dict) -> List[str]:
    """Check org infrastructure: org.json, operatives repo, stack-wisdom repo."""
    alerts: List[str] = []
    workspace = Path(config.get("workspace", ""))
    if not workspace.is_dir():
        return alerts

    for org_name in config.get("orgs", []):
        org_dir = workspace / org_name
        if not org_dir.is_dir():
            continue

        org_json = org_dir / ".claude" / "org.json"
        operatives_dir = None
        wisdom_dir = None

        if org_json.exists():
            try:
                with open(org_json, encoding="utf-8") as f:
                    org_data = json.load(f)
                operatives_dir = org_dir / org_data.get("operatives", {}).get("repo", f"{org_name}-operatives")
                wisdom_dir = org_dir / org_data.get("stack_wisdom", {}).get("repo", f"{org_name}-stack-wisdom")
            except (json.JSONDecodeError, IOError):
                operatives_dir = org_dir / f"{org_name}-operatives"
                wisdom_dir = org_dir / f"{org_name}-stack-wisdom"
        else:
            alerts.append(f"WARNING: Org '{org_name}' missing .claude/org.json — run /run-organize-orgs")
            operatives_dir = org_dir / f"{org_name}-operatives"
            wisdom_dir = org_dir / f"{org_name}-stack-wisdom"

        if not operatives_dir.is_dir():
            alerts.append(f"WARNING: Org '{org_name}' missing operatives repo — run /run-organize-orgs")
        if not wisdom_dir.is_dir():
            alerts.append(f"WARNING: Org '{org_name}' missing stack-wisdom repo — run /run-organize-orgs")

    return alerts


def check_workspace_summary(config: Dict, full: bool = False) -> List[str]:
    """
    Scan all projects across all orgs for health metrics.
    Returns compact summary (session start) or full per-project detail (--full).
    """
    workspace = Path(config.get("workspace", ""))
    if not workspace.is_dir():
        return []

    state = load_state()
    now = int(time.time())

    total = 0
    missing_archetype = []
    never_reviewed = []
    stale_reviewed = []
    never_scanned = []
    stale_scanned = []
    never_organized = []
    stale_organized = []
    missing_claude_md = []

    for org_name in config.get("orgs", []):
        org_dir = workspace / org_name
        if not org_dir.is_dir():
            continue

        for project_dir in sorted(org_dir.iterdir()):
            if not project_dir.is_dir():
                continue
            # Skip hidden dirs and non-project dirs (like CLAUDE.md files)
            if project_dir.name.startswith("."):
                continue

            project_key = f"{org_name}/{project_dir.name}"
            project_label = project_dir.name
            total += 1

            project_state = state.get("projects", {}).get(project_key, {})

            # Check CLAUDE.md exists
            claude_md = project_dir / "CLAUDE.md"
            if not claude_md.exists():
                missing_claude_md.append(project_label)
            else:
                # Check archetype
                if _detect_archetype is not None:
                    try:
                        content = claude_md.read_text(encoding="utf-8")
                        if _detect_archetype(content) is None:
                            missing_archetype.append(project_label)
                    except (OSError, IOError):
                        pass

            # Check review freshness
            last_review = project_state.get("last_review", 0)
            if last_review == 0:
                never_reviewed.append(project_label)
            elif (now - last_review) // 86400 >= 7:
                stale_reviewed.append(project_label)

            # Check secret scan freshness
            last_scan = project_state.get("last_secret_scan", 0)
            if last_scan == 0:
                never_scanned.append(project_label)
            elif (now - last_scan) // 86400 >= 7:
                stale_scanned.append(project_label)

            # Check organize freshness
            last_organize = project_state.get("last_organize", 0)
            if last_organize == 0:
                never_organized.append(project_label)
            elif (now - last_organize) // 86400 >= 14:
                stale_organized.append(project_label)

    if total == 0:
        return []

    if full:
        return _format_workspace_full(
            total, missing_claude_md, missing_archetype,
            never_reviewed, stale_reviewed,
            never_scanned, stale_scanned,
            never_organized, stale_organized,
        )

    return _format_workspace_summary(
        total, missing_claude_md, missing_archetype,
        never_reviewed, stale_reviewed,
        never_scanned, stale_scanned,
    )


def _format_workspace_summary(
    total: int,
    missing_claude_md: List[str],
    missing_archetype: List[str],
    never_reviewed: List[str],
    stale_reviewed: List[str],
    never_scanned: List[str],
    stale_scanned: List[str],
) -> List[str]:
    """Compact one-line summary for session start."""
    parts = []
    if missing_claude_md:
        parts.append(f"{len(missing_claude_md)}/{total} missing CLAUDE.md")
    if missing_archetype:
        parts.append(f"{len(missing_archetype)}/{total} missing archetype")
    review_issues = len(never_reviewed) + len(stale_reviewed)
    if review_issues:
        parts.append(f"{review_issues}/{total} need review")
    scan_issues = len(never_scanned) + len(stale_scanned)
    if scan_issues:
        parts.append(f"{scan_issues}/{total} need secret scan")

    if not parts:
        return [f"WORKSPACE: All {total} projects healthy"]

    summary = " | ".join(parts)
    return [
        f"WORKSPACE: {summary}",
        "   Run /run-overwatch check for per-project details",
    ]


def _format_workspace_full(
    total: int,
    missing_claude_md: List[str],
    missing_archetype: List[str],
    never_reviewed: List[str],
    stale_reviewed: List[str],
    never_scanned: List[str],
    stale_scanned: List[str],
    never_organized: List[str],
    stale_organized: List[str],
) -> List[str]:
    """Full per-project breakdown for /run-overwatch check."""
    lines: List[str] = []
    lines.append(f"WORKSPACE REPORT ({total} projects)")
    lines.append("-" * 50)

    if missing_claude_md:
        lines.append(f"  Missing CLAUDE.md ({len(missing_claude_md)}):")
        for p in missing_claude_md:
            lines.append(f"    - {p}")

    if missing_archetype:
        lines.append(f"  Missing archetype ({len(missing_archetype)}):")
        for p in missing_archetype:
            lines.append(f"    - {p}")

    if never_reviewed:
        lines.append(f"  Never reviewed ({len(never_reviewed)}):")
        for p in never_reviewed:
            lines.append(f"    - {p}")
    if stale_reviewed:
        lines.append(f"  Review overdue >7d ({len(stale_reviewed)}):")
        for p in stale_reviewed:
            lines.append(f"    - {p}")

    if never_scanned:
        lines.append(f"  Never scanned for secrets ({len(never_scanned)}):")
        for p in never_scanned:
            lines.append(f"    - {p}")
    if stale_scanned:
        lines.append(f"  Secret scan overdue >7d ({len(stale_scanned)}):")
        for p in stale_scanned:
            lines.append(f"    - {p}")

    if never_organized:
        lines.append(f"  Never organized ({len(never_organized)}):")
        for p in never_organized:
            lines.append(f"    - {p}")
    if stale_organized:
        lines.append(f"  Organize overdue >14d ({len(stale_organized)}):")
        for p in stale_organized:
            lines.append(f"    - {p}")

    if not any([missing_claude_md, missing_archetype, never_reviewed, stale_reviewed,
                never_scanned, stale_scanned, never_organized, stale_organized]):
        lines.append("  All projects healthy!")

    return lines


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
    full_mode = "--full" in sys.argv
    alerts: List[str] = []

    # Resolve current context and load scoped state
    ctx = resolve_context()
    project_label = ctx["project"].split("/")[-1] if ctx["project"] else None
    org_label = ctx["org"]

    project_state = get_scoped_state("projects", ctx["project"]) if ctx["project"] else {}
    org_state = get_scoped_state("orgs", ctx["org"]) if ctx["org"] else {}
    global_state = get_scoped_state("global", None)

    # Load workspace config for cross-project checks
    config = _load_organize_config() or {}

    # Check 1: Git status
    git_alert = check_git_status()
    if git_alert:
        alerts.append(git_alert)

    # Check 2: Review status (project-scoped, skip if not in a project)
    if ctx["project"]:
        review_alert = check_review_status(project_state, project_label)
        if review_alert:
            alerts.append(review_alert)

    # Check 3: Organize status (project-scoped, skip if not in a project)
    if ctx["project"]:
        organize_alert = check_organize_status(project_state, project_label)
        if organize_alert:
            alerts.append(organize_alert)

    # Check 4: Plugin updates
    plugin_updates = check_plugin_updates()
    if plugin_updates:
        alerts.append("ACTION REQUIRED: Plugin updates available. Update before starting work:")
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

    # Check 7: Secret scan status (project-scoped, skip if not in a project)
    if ctx["project"]:
        secret_scan_alert = check_secret_scan_status(project_state, project_label)
        if secret_scan_alert:
            alerts.append(secret_scan_alert)

    # Check 8: Repo visibility
    visibility_alert = check_repo_visibility()
    if visibility_alert:
        alerts.append(visibility_alert)

    # Check 9: CLAUDE.md
    claude_md_alert = check_claude_md()
    if claude_md_alert:
        alerts.append(claude_md_alert)

    # Check 10: Overwatch response guidance
    guidance_alert = check_overwatch_guidance()
    if guidance_alert:
        alerts.append(guidance_alert)

    # Check 11: Cross-project blockers
    blocker_alerts = check_cross_project_blockers()
    if blocker_alerts:
        alerts.extend(blocker_alerts)

    # Check 12: Project archetype declaration (current project only)
    if ctx["project"]:
        archetype_alert = check_archetype()
        if archetype_alert:
            alerts.append(archetype_alert)

    # Check 13: CLAUDE.md review freshness (all levels)
    claude_review_alerts = check_claude_review_status(
        project_state, org_state, global_state, project_label, org_label
    )
    if claude_review_alerts:
        alerts.extend(claude_review_alerts)

    # Check 14: Org infrastructure (all orgs)
    if config:
        org_infra_alerts = check_org_infrastructure(config)
        if org_infra_alerts:
            alerts.extend(org_infra_alerts)

    # Check 15: Workspace-level project summary (summary or full)
    if config:
        workspace_alerts = check_workspace_summary(config, full=full_mode)
        if workspace_alerts:
            alerts.extend(workspace_alerts)

    # Output to both stdout (for Claude context) and stderr (for user terminal)
    if alerts:
        header = [
            "",
            "-" * 59,
            "|  OVERWATCH" + " " * 46 + "|",
            "-" * 59,
        ]
        # Count actionable alerts
        action_count = sum(1 for a in alerts if a.startswith("ACTION REQUIRED:") or a.startswith("WARNING:"))

        # Directive block for Claude (only on stdout, not stderr)
        directive = []
        if action_count > 0:
            directive = [
                "",
                f"DIRECTIVE: {action_count} item(s) above require action. Present each as a recommendation",
                "to the user BEFORE proceeding with their request. Do not silently skip them.",
            ]

        # Print to stdout for Claude
        for line in header:
            print(line)
        for alert in alerts:
            print(alert)
        for line in directive:
            print(line)
        # Echo to stderr for user visibility (alerts only, no directive)
        for line in header:
            print(line, file=sys.stderr)
        for alert in alerts:
            print(alert, file=sys.stderr)

    # Clear session change log (skip in --full mode, only for session start)
    if not full_mode:
        session_log = get_tmp_dir() / "session-changes.log"
        try:
            session_log.unlink(missing_ok=True)
        except (OSError, IOError):
            pass  # Ignore errors clearing log


if __name__ == "__main__":
    main()
