#!/usr/bin/env python3
"""
CLI entry point for secret scanning.

Usage:
    python cli.py                      # Scan current repo
    python cli.py --all                # Scan all repos in workspace
    python cli.py --pre-commit         # Scan staged changes (for hook)
    python cli.py --audit              # Audit current repo hygiene
    python cli.py --audit --github     # Audit all public GitHub repos
    python cli.py --install-hooks      # Install global pre-commit hook
    python cli.py --uninstall-hooks    # Remove pre-commit hook
    python cli.py --list-formats       # Show active format rules
    python cli.py --update-formats     # Refresh common formats from plugin
    python cli.py --add-format         # Interactive (handled by SKILL.md)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add script directory to path for local imports
sys.path.insert(0, str(Path(__file__).parent))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scan repositories for secrets and credentials",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python cli.py                    # Scan current repo
    python cli.py --all              # Scan all workspace repos
    python cli.py --audit            # Audit repo hygiene
    python cli.py --audit --github   # List all public repos
    python cli.py --install-hooks    # Install pre-commit hook
    python cli.py --list-formats     # Show format rules
        """,
    )

    # Scan modes
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--all",
        action="store_true",
        dest="scan_all",
        help="Scan all repos in workspace",
    )
    mode.add_argument(
        "--pre-commit",
        action="store_true",
        help="Scan staged changes only (for pre-commit hook)",
    )
    mode.add_argument(
        "--audit",
        action="store_true",
        help="Audit repo hygiene (.gitignore, visibility, dangerous files)",
    )
    mode.add_argument(
        "--install-hooks",
        action="store_true",
        help="Install global pre-commit hook for secret scanning",
    )
    mode.add_argument(
        "--uninstall-hooks",
        action="store_true",
        help="Remove pre-commit hook",
    )
    mode.add_argument(
        "--hook-status",
        action="store_true",
        help="Check hook installation status",
    )
    mode.add_argument(
        "--list-formats",
        action="store_true",
        help="List all active secret format rules",
    )
    mode.add_argument(
        "--update-formats",
        action="store_true",
        help="Refresh common formats from plugin (preserves org formats)",
    )
    mode.add_argument(
        "--add-format",
        action="store_true",
        help="Add a custom org-specific format (interactive via Claude)",
    )

    # Audit sub-options
    parser.add_argument(
        "--github",
        action="store_true",
        help="With --audit: scan entire GitHub account for public repos",
    )

    args = parser.parse_args()

    # Dispatch
    if args.install_hooks:
        from hook_installer import install_hooks
        print(install_hooks())
        return 0

    if args.uninstall_hooks:
        from hook_installer import uninstall_hooks
        print(uninstall_hooks())
        return 0

    if args.hook_status:
        from hook_installer import hook_status
        print(hook_status())
        return 0

    if args.list_formats:
        from format_loader import list_formats
        print(list_formats())
        return 0

    if args.update_formats:
        from format_loader import update_common_formats
        print(update_common_formats())
        return 0

    if args.add_format:
        from format_loader import get_org_formats_path
        path = get_org_formats_path()
        print(f"Org formats file: {path}")
        print("Claude will guide you through adding a custom format interactively.")
        print("(This mode is handled by the SKILL.md instructions)")
        return 0

    if args.audit:
        if args.github:
            from repo_auditor import audit_github_account
            print(audit_github_account())
        else:
            from repo_auditor import audit_repo
            print(audit_repo())
        return 0

    if args.pre_commit:
        from scanner import scan_staged, update_scan_timestamp
        exit_code, report = scan_staged()
        if report:
            print(report, file=sys.stderr)
        return exit_code

    if args.scan_all:
        from scanner import scan_workspace, update_scan_timestamp
        exit_code, report = scan_workspace()
        print(report)
        update_scan_timestamp()
        return exit_code

    # Default: scan current repo
    from scanner import scan_repo, update_scan_timestamp
    exit_code, report = scan_repo()
    print(report)
    update_scan_timestamp()
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
