#!/usr/bin/env python3
"""
Lastmilefirst Overwatch - Update State
Updates the Overwatch state file with scoped timestamps.

Usage:
  update_state.py <action> [--scope project|org|global] [--key KEY]
  update_state.py status [--all]
  update_state.py rename --from OLD_KEY --to NEW_KEY [--scope project|org]

Actions: review, organize, secret_scan, review_claude, review_org, plugin_check, status

Project keys are paths relative to the workspace: "org/project", or
"org/client/project" for a project inside a client directory. `rename` moves a
key's timestamps to a new key after a directory is moved or renamed, and
refuses when the new key already has state.

Default scope per action:
  review, organize, secret_scan, review_claude -> project (auto-detected from CWD)
  review_org -> org (pass --key <org> so it does not depend on CWD)
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
    _load_state_unlocked,
    _save_state_unlocked,
    file_lock,
    get_lock_file,
    load_state,
    resolve_context,
    update_scoped_state,
)

CONTAINER_MESSAGE = "container directory, not tracked"

# Default scope for each action
DEFAULT_SCOPES = {
    "review": "projects",
    "organize": "projects",
    "secret_scan": "projects",
    "review_claude": "projects",
    "review_org": "orgs",
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

        if ctx.get("client") and not ctx["project"]:
            print(f"  {ctx['org']}/{ctx['client']}: {CONTAINER_MESSAGE}")
        elif not ctx["org"] and not ctx["project"]:
            print("  (not in a recognized project — use --all to see everything)")


def rename_key(scope: str, old: str, new: str) -> str:
    """Move the state stored under `old` to `new` within a scope.

    Returns an empty string on success, or the reason it refused. Refuses when
    `old` has no state or `new` already has some, so nothing is overwritten.
    """
    if old == new:
        return "the two keys are the same"
    with file_lock(get_lock_file()):
        state = _load_state_unlocked()
        entries = state.setdefault(scope, {})
        if old not in entries:
            return f"no state under {scope}/{old}"
        if new in entries:
            return f"{scope}/{new} already has state; not overwriting it"
        entries[new] = entries.pop(old)
        _save_state_unlocked(state)
    return ""


def main() -> None:
    parser = argparse.ArgumentParser(description="Update Overwatch state")
    parser.add_argument("action", help="Action: review, organize, secret_scan, review_claude, review_org, plugin_check, status, rename")
    parser.add_argument("--scope", choices=["project", "org", "global"], help="Override default scope")
    parser.add_argument("--key", help="Explicit scope key (org name, org/project, or org/client/project)")
    parser.add_argument("--from", dest="from_key", help="rename: the key to move")
    parser.add_argument("--to", dest="to_key", help="rename: the new key")
    parser.add_argument("--all", action="store_true", dest="show_all", help="Show all scopes (status only)")
    args = parser.parse_args()

    if args.action == "status":
        print_status(show_all=args.show_all)
        return

    if args.action == "rename":
        if not args.from_key or not args.to_key:
            parser.error("rename needs --from and --to")
        if args.scope == "global":
            parser.error("rename works on the project or org scope")
        scope = "orgs" if args.scope == "org" else "projects"
        refused = rename_key(scope, args.from_key, args.to_key)
        if refused:
            print(f"Error: {refused}.", file=sys.stderr)
            sys.exit(1)
        print(f"Overwatch: moved {scope}/{args.from_key} to {scope}/{args.to_key}")
        return

    if args.action not in DEFAULT_SCOPES:
        parser.error(f"Unknown action: {args.action}. Use: {', '.join(DEFAULT_SCOPES.keys())}, status, rename")

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
            if scope == "projects" and ctx.get("client"):
                print(f"Error: {ctx['org']}/{ctx['client']} is a {CONTAINER_MESSAGE}. "
                      f"Run this from a project inside it, or use --key.", file=sys.stderr)
            else:
                print(f"Error: not in a recognized {scope[:-1]}. Use --key to specify explicitly.", file=sys.stderr)
            sys.exit(1)

    now = int(time.time())
    field = f"last_{args.action}"
    update_scoped_state(scope, key, field, now)

    scope_label = f"{scope}/{key}" if key else "global"
    print(f"Overwatch: recorded {args.action} for {scope_label} at {datetime.now().strftime('%Y-%m-%d %H:%M')}")


if __name__ == "__main__":
    main()
