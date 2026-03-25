#!/usr/bin/env python3
"""
Lastmilefirst Overwatch - Update State
Updates the Overwatch state file with scoped timestamps.

Usage:
  update_state.py <action> [--scope project|org|global] [--key KEY]
  update_state.py status [--all]

Actions: review, organize, secret_scan, review_claude, plugin_check, status

Default scope per action:
  review, organize, secret_scan, review_claude -> project (auto-detected from CWD)
  plugin_check -> global
"""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

# Add script directory to path for local imports
sys.path.insert(0, str(Path(__file__).parent))

from overwatch import (
    load_state,
    resolve_context,
    update_scoped_state,
)

# Default scope for each action
DEFAULT_SCOPES = {
    "review": "projects",
    "organize": "projects",
    "secret_scan": "projects",
    "review_claude": "projects",
    "plugin_check": "global",
}


def print_status(show_all: bool = False) -> None:
    """Print current Overwatch state."""
    state = load_state()
    ctx = resolve_context()

    def fmt_ts(ts: int) -> str:
        if ts == 0:
            return "never"
        days = (int(time.time()) - ts) // 86400
        dt = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
        return f"{dt} ({days}d ago)" if days > 0 else f"{dt} (today)"

    def print_scope(label: str, data: dict) -> None:
        if not data:
            print(f"  {label}: (no data)")
            return
        print(f"  {label}:")
        for field, val in sorted(data.items()):
            if isinstance(val, int) and field.startswith("last_"):
                print(f"    {field}: {fmt_ts(val)}")

    print("Overwatch State (v2)")
    print()

    # Global
    print_scope("global", state.get("global", {}))

    if show_all:
        # All orgs
        for org_name, org_data in sorted(state.get("orgs", {}).items()):
            print_scope(f"org/{org_name}", org_data)
        # All projects
        for proj_key, proj_data in sorted(state.get("projects", {}).items()):
            print_scope(f"project/{proj_key}", proj_data)
    else:
        # Current context only
        if ctx["org"]:
            org_data = state.get("orgs", {}).get(ctx["org"], {})
            print_scope(f"org/{ctx['org']}", org_data)
        if ctx["project"]:
            proj_data = state.get("projects", {}).get(ctx["project"], {})
            print_scope(f"project/{ctx['project']}", proj_data)

        if not ctx["org"] and not ctx["project"]:
            print("  (not in a recognized project — use --all to see everything)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Update Overwatch state")
    parser.add_argument("action", help="Action: review, organize, secret_scan, review_claude, plugin_check, status")
    parser.add_argument("--scope", choices=["project", "org", "global"], help="Override default scope")
    parser.add_argument("--key", help="Explicit scope key (org name or org/project)")
    parser.add_argument("--all", action="store_true", dest="show_all", help="Show all scopes (status only)")
    args = parser.parse_args()

    if args.action == "status":
        print_status(show_all=args.show_all)
        return

    if args.action not in DEFAULT_SCOPES:
        parser.error(f"Unknown action: {args.action}. Use: {', '.join(DEFAULT_SCOPES.keys())}, status")

    # Determine scope
    if args.scope:
        scope_map = {"project": "projects", "org": "orgs", "global": "global"}
        scope = scope_map[args.scope]
    else:
        scope = DEFAULT_SCOPES[args.action]

    # Determine key
    if args.key:
        key = args.key
    elif scope == "global":
        key = None
    else:
        ctx = resolve_context()
        if scope == "projects":
            key = ctx["project"]
        else:
            key = ctx["org"]

        if not key:
            print(f"Error: not in a recognized {scope[:-1]}. Use --key to specify explicitly.", file=sys.stderr)
            sys.exit(1)

    now = int(time.time())
    field = f"last_{args.action}"
    update_scoped_state(scope, key, field, now)

    scope_label = f"{scope}/{key}" if key else "global"
    print(f"Overwatch: recorded {args.action} for {scope_label} at {datetime.now().strftime('%Y-%m-%d %H:%M')}")


if __name__ == "__main__":
    main()
