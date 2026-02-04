#!/usr/bin/env python3
"""
CLI entry point for cross-project todo aggregation.

Usage:
    python cli.py                           # Default org, terminal format
    python cli.py --all                     # All orgs in workspace
    python cli.py --org gruntwork           # Specific org
    python cli.py --format json             # JSON output
    python cli.py --format compact          # For Overwatch
    python cli.py --no-cache                # Force fresh scan
    python cli.py --verbose                 # Show all items
"""

import argparse
import sys
from pathlib import Path

# Add script directory to path for local imports
sys.path.insert(0, str(Path(__file__).parent))

from aggregator import TodoAggregator, get_aggregated_summary
from formatters import get_formatter


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Aggregate todos across projects in workspace orgs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python cli.py                     # Default org, terminal format
    python cli.py --all               # All orgs in workspace
    python cli.py --org gruntwork     # Specific org
    python cli.py --format json       # JSON output
    python cli.py --verbose           # Full item details
        """,
    )

    parser.add_argument(
        "-o", "--org",
        type=str,
        help="Specific org to scan (e.g., personal, client-work)",
    )

    parser.add_argument(
        "--all",
        action="store_true",
        dest="all_orgs",
        help="Scan all configured orgs in the workspace",
    )

    parser.add_argument(
        "-f", "--format",
        type=str,
        choices=["terminal", "json", "compact", "overwatch", "project"],
        default="terminal",
        help="Output format (default: terminal)",
    )

    parser.add_argument(
        "--by-project",
        action="store_true",
        help="Group output by project (shortcut for --format project)",
    )

    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Force fresh scan, ignore cache",
    )

    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show all items (terminal format only)",
    )

    parser.add_argument(
        "--list-orgs",
        action="store_true",
        help="List configured orgs and exit",
    )

    args = parser.parse_args()

    # Handle --list-orgs
    if args.list_orgs:
        aggregator = TodoAggregator()
        orgs = aggregator.get_orgs()

        if not orgs:
            print("No orgs configured.")
            print(f"Create ~/.claude/workspace-config.json or add directories to ~/Code/")
            return 1

        print(f"Workspace: {aggregator.get_workspace_path()}")
        print("\nConfigured orgs:")
        for org in orgs:
            default_marker = " (default)" if org.default else ""
            sensitive_marker = " [sensitive]" if org.sensitive else ""
            print(f"  {org.name}: {org.path}{default_marker}{sensitive_marker}")
        return 0

    # Get aggregated data
    try:
        data = get_aggregated_summary(
            org_name=args.org,
            all_orgs=args.all_orgs,
            use_cache=not args.no_cache,
        )
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    # Check if any data
    total_todos = sum(len(todos) for todos in data.values())
    if total_todos == 0:
        print("No pending todos found.")
        return 0

    # Determine format (--by-project is shortcut for --format project)
    format_name = "project" if args.by_project else args.format

    # Format and output
    formatter = get_formatter(format_name, verbose=args.verbose)
    output = formatter.format(data)

    if output:
        print(output)

    return 0


if __name__ == "__main__":
    sys.exit(main())
