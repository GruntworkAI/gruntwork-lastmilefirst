#!/usr/bin/env python3
"""
Plugin Inventory Tool

Displays installed Claude Code plugins with versions, stats, and usage data.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path


def get_claude_dir() -> Path:
    """Get the Claude configuration directory."""
    return Path.home() / ".claude"


def parse_semver(version: str) -> tuple[int, int, int]:
    """Parse a semver string into a tuple for comparison."""
    try:
        parts = version.split(".")
        return (int(parts[0]), int(parts[1]) if len(parts) > 1 else 0, int(parts[2]) if len(parts) > 2 else 0)
    except (ValueError, IndexError):
        return (0, 0, 0)


def get_latest_cached_version(marketplace: str, plugin_name: str) -> tuple[str, Path] | None:
    """Find the latest cached version of a plugin."""
    cache_dir = get_claude_dir() / "plugins" / "cache" / marketplace / plugin_name
    if not cache_dir.exists():
        return None

    versions = []
    for item in cache_dir.iterdir():
        if item.is_dir() and not item.name.startswith("."):
            versions.append((parse_semver(item.name), item.name, item))

    if not versions:
        return None

    versions.sort(reverse=True)
    _, version_str, path = versions[0]
    return (version_str, path)


def load_installed_plugins() -> dict:
    """Load installed plugins from installed_plugins.json."""
    plugins_file = get_claude_dir() / "plugins" / "installed_plugins.json"
    if not plugins_file.exists():
        return {}

    try:
        with open(plugins_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("plugins", {})
    except (json.JSONDecodeError, IOError):
        return {}


def load_plugin_json(install_path: Path) -> dict:
    """Load plugin.json from a plugin's install path."""
    plugin_json = install_path / ".claude-plugin" / "plugin.json"
    if not plugin_json.exists():
        return {}

    try:
        with open(plugin_json, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def count_skills(install_path: Path) -> int:
    """Count skills in a plugin."""
    skills_dir = install_path / "skills"
    if not skills_dir.exists():
        return 0

    count = 0
    for item in skills_dir.iterdir():
        if item.is_dir():
            skill_md = item / "SKILL.md"
            if skill_md.exists():
                count += 1
    return count


def count_commands(install_path: Path) -> int:
    """Count commands in a plugin."""
    commands_dir = install_path / "commands"
    if not commands_dir.exists():
        return 0

    return len(list(commands_dir.glob("*.md")))


def count_agents(install_path: Path) -> int:
    """Count agents in a plugin."""
    agents_dir = install_path / "agents"
    if not agents_dir.exists():
        return 0

    return len(list(agents_dir.glob("*.md")))


def load_invocations(days: int = 7) -> list[tuple[int, str]]:
    """Load invocations from the log file within the specified days."""
    invocations_file = get_claude_dir() / "lastmilefirst" / "invocations.log"
    if not invocations_file.exists():
        return []

    cutoff = int(time.time()) - (days * 24 * 60 * 60)
    invocations = []

    try:
        with open(invocations_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if "|" in line:
                    parts = line.split("|", 1)
                    if len(parts) == 2:
                        try:
                            timestamp = int(parts[0])
                            if timestamp >= cutoff:
                                invocations.append((timestamp, parts[1]))
                        except ValueError:
                            continue
    except IOError:
        return []

    return invocations


def aggregate_invocations(invocations: list[tuple[int, str]]) -> dict[str, int]:
    """Aggregate invocations by skill name."""
    counts: dict[str, int] = {}
    for _, skill_name in invocations:
        counts[skill_name] = counts.get(skill_name, 0) + 1
    return counts


def format_time_ago(timestamp: int) -> str:
    """Format a timestamp as a human-readable time ago string."""
    now = int(time.time())
    diff = now - timestamp

    if diff < 60:
        return "just now"
    elif diff < 3600:
        mins = diff // 60
        return f"{mins} minute{'s' if mins != 1 else ''} ago"
    elif diff < 86400:
        hours = diff // 3600
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    else:
        days = diff // 86400
        return f"{days} day{'s' if days != 1 else ''} ago"


def format_date(iso_date: str) -> str:
    """Format an ISO date string."""
    try:
        dt = datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        return iso_date[:10] if len(iso_date) >= 10 else iso_date


def print_separator(char: str = "─", width: int = 60) -> None:
    """Print a separator line."""
    print(char * width)


def print_inventory(
    plugins: dict,
    invocations: list[tuple[int, str]],
    verbose: bool = False,
    show_usage: bool = False,
    days: int = 7,
) -> None:
    """Print the plugin inventory."""
    print()
    print("Installed Plugins")
    print_separator()
    print()

    aggregated = aggregate_invocations(invocations)
    total_invocations = len(invocations)
    last_invocation = max((ts for ts, _ in invocations), default=0) if invocations else 0

    plugin_count = 0

    for plugin_key, plugin_entries in sorted(plugins.items()):
        if not plugin_entries:
            continue

        # Use first entry (typically only one per plugin)
        entry = plugin_entries[0]
        install_path = Path(entry.get("installPath", ""))
        version = entry.get("version", "unknown")

        # Check for newer cached version
        # plugin_key format: "name@marketplace"
        parts = plugin_key.split("@")
        plugin_name = parts[0]
        marketplace = parts[1] if len(parts) > 1 else ""

        cached_info = get_latest_cached_version(marketplace, plugin_name) if marketplace else None
        cached_version, cached_path = cached_info if cached_info else (None, None)

        # Use cached path if it's newer (Claude Code loads from cache after marketplace update)
        active_path = install_path
        active_version = version
        version_mismatch = False

        if cached_version and parse_semver(cached_version) > parse_semver(version):
            active_path = cached_path
            active_version = cached_version
            version_mismatch = True

        # Load plugin metadata from active path
        plugin_json = load_plugin_json(active_path)
        name = plugin_json.get("name", plugin_key.split("@")[0])
        description = plugin_json.get("description", "")

        # Truncate description
        if len(description) > 70:
            description = description[:67] + "..."

        # Count components from active path
        skills = count_skills(active_path)
        commands = count_commands(active_path)
        agents = count_agents(active_path)

        # Print plugin info
        if version_mismatch:
            print(f"{plugin_key}  v{active_version} (cached, installed: v{version})")
        else:
            print(f"{plugin_key}  v{active_version}")
        if description:
            print(f"  {description}")

        # Components line
        components = []
        if skills:
            components.append(f"Skills: {skills}")
        if commands:
            components.append(f"Commands: {commands}")
        if agents:
            components.append(f"Agents: {agents}")
        if components:
            print(f"  {' | '.join(components)}")

        # Verbose info
        if verbose:
            print()
            print(f"  Path: {install_path}")
            installed_at = entry.get("installedAt", "")
            updated_at = entry.get("lastUpdated", "")
            git_sha = entry.get("gitCommitSha", "")[:8] if entry.get("gitCommitSha") else ""

            if installed_at:
                print(f"  Installed: {format_date(installed_at)}")
            if updated_at and updated_at != installed_at:
                print(f"  Updated: {format_date(updated_at)}")
            if git_sha:
                print(f"  Commit: {git_sha}")

        # Usage stats (only for lastmilefirst which has tracking)
        if "lastmilefirst" in plugin_key and aggregated:
            print()
            print(f"  Usage (last {days} days):")

            if show_usage:
                # Detailed breakdown
                for skill_name, count in sorted(aggregated.items(), key=lambda x: -x[1]):
                    print(f"    {skill_name}: {count}")
            else:
                # Summary line
                top_items = sorted(aggregated.items(), key=lambda x: -x[1])[:3]
                summary = "    " + "  ".join(f"{name}: {count}" for name, count in top_items)
                print(summary)
                if len(aggregated) > 3:
                    print(f"    ... and {len(aggregated) - 3} more")

            print(f"    Total: {total_invocations}")
            if last_invocation:
                print(f"  Last invocation: {format_time_ago(last_invocation)}")

        print()
        plugin_count += 1

    if plugin_count == 0:
        print("No plugins installed.")
        print()

    print_separator()
    summary_parts = [f"{plugin_count} plugin{'s' if plugin_count != 1 else ''} installed"]
    if total_invocations:
        summary_parts.append(f"{total_invocations} invocations (last {days} days)")
    print(" | ".join(summary_parts))
    print()


def print_json(
    plugins: dict,
    invocations: list[tuple[int, str]],
    days: int = 7,
) -> None:
    """Print the plugin inventory as JSON."""
    aggregated = aggregate_invocations(invocations)

    output = {
        "plugins": [],
        "usage": {
            "days": days,
            "total_invocations": len(invocations),
            "by_skill": aggregated,
        },
    }

    for plugin_key, plugin_entries in sorted(plugins.items()):
        if not plugin_entries:
            continue

        entry = plugin_entries[0]
        install_path = Path(entry.get("installPath", ""))
        version = entry.get("version", "unknown")

        # Check for newer cached version
        parts = plugin_key.split("@")
        plugin_name = parts[0]
        marketplace = parts[1] if len(parts) > 1 else ""

        cached_info = get_latest_cached_version(marketplace, plugin_name) if marketplace else None
        cached_version, cached_path = cached_info if cached_info else (None, None)

        # Use cached path if it's newer
        active_path = install_path
        active_version = version

        if cached_version and parse_semver(cached_version) > parse_semver(version):
            active_path = cached_path
            active_version = cached_version

        plugin_json = load_plugin_json(active_path)

        plugin_data = {
            "key": plugin_key,
            "name": plugin_json.get("name", plugin_key.split("@")[0]),
            "version": active_version,
            "installed_version": version,
            "description": plugin_json.get("description", ""),
            "install_path": str(install_path),
            "active_path": str(active_path),
            "installed_at": entry.get("installedAt", ""),
            "last_updated": entry.get("lastUpdated", ""),
            "git_commit_sha": entry.get("gitCommitSha", ""),
            "components": {
                "skills": count_skills(active_path),
                "commands": count_commands(active_path),
                "agents": count_agents(active_path),
            },
        }
        output["plugins"].append(plugin_data)

    print(json.dumps(output, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Display installed Claude Code plugins with versions and usage stats"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed info (paths, timestamps, git SHA)",
    )
    parser.add_argument(
        "--usage", "-u",
        action="store_true",
        help="Show detailed usage breakdown by skill name",
    )
    parser.add_argument(
        "--since",
        type=int,
        default=7,
        metavar="DAYS",
        help="Filter usage to last N days (default: 7)",
    )
    args = parser.parse_args()

    # Load data
    plugins = load_installed_plugins()
    invocations = load_invocations(days=args.since)

    if args.json:
        print_json(plugins, invocations, days=args.since)
    else:
        print_inventory(
            plugins,
            invocations,
            verbose=args.verbose,
            show_usage=args.usage,
            days=args.since,
        )


if __name__ == "__main__":
    main()
