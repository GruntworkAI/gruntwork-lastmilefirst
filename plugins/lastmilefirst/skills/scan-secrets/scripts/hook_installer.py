#!/usr/bin/env python3
"""
Global pre-commit hook installer.

Uses git config --global core.hooksPath to apply to all repos.
Installs to ~/.claude/lastmilefirst/git-hooks/pre-commit.

The installed hook is a *dispatcher*: it resolves the plugin root once, then
runs each registered check in order and fails on the first non-zero exit.
Checks are listed in CHECKS below. Adding one is a single entry — the hook was
previously a single-purpose script, which meant a second concern could not be
added without rewriting it.
"""
from __future__ import annotations

import os
import stat
import subprocess
import sys
from pathlib import Path
from typing import Optional

HOOKS_DIR = Path.home() / ".claude" / "lastmilefirst" / "git-hooks"
HOOK_FILE = HOOKS_DIR / "pre-commit"

# Registered pre-commit checks, in run order.
#
# Ordered cheapest-first so an obvious failure reports before slower work runs:
# the identity check is a couple of `git config` reads and a small JSON parse,
# while the secret scan shells out to gitleaks over the staged diff.
#
# Each entry: (label, path relative to the plugin root, failure message).
CHECKS = [
    (
        "identity",
        "skills/organize-orgs/scripts/check_identity.py",
        # check_identity.py prints its own diagnosis and remedy, so the hook
        # adds nothing here.
        "",
    ),
    (
        "secret scan",
        "skills/scan-secrets/scripts/scan_secrets.py",
        "\n".join(
            [
                "Secret scan found potential secrets in staged changes.",
                "Review the findings above and either:",
                "  1. Remove the secrets and re-stage",
                "  2. Add to .gitignore if the file shouldn't be tracked",
                "  3. Add a gitleaks:allow comment if it's a false positive",
            ]
        ),
    ),
]


def _render_check(label: str, rel_path: str, failure_message: str) -> str:
    """Emit the bash for one check: skip if absent, else run and gate on it."""
    message_block = ""
    if failure_message:
        echoes = "\n".join(
            f'        echo "{line}" >&2' for line in failure_message.split("\n")
        )
        message_block = f'\n        echo "" >&2\n{echoes}\n        echo "" >&2'
    return f"""
# {label}
CHECK_PATH="$PLUGIN_ROOT/{rel_path}"
if [ -f "$CHECK_PATH" ]; then
    CHECKS_RUN=$((CHECKS_RUN + 1))
    python3 "$CHECK_PATH" --pre-commit
    if [ $? -ne 0 ]; then{message_block}
        exit 1
    fi
fi"""


def build_hook_script() -> str:
    """Assemble the dispatcher installed as the global pre-commit hook."""
    checks = "".join(
        _render_check(label, rel, msg) for label, rel, msg in CHECKS
    )
    return f"""\
#!/usr/bin/env bash
# lastmilefirst pre-commit hook (dispatcher)
# Installed by: /run-scan-secrets --install-hooks
# Remove with:  /run-scan-secrets --uninstall-hooks
#
# Runs each registered check in order, failing on the first non-zero exit.
# Checks: {', '.join(label for label, _, _ in CHECKS)}

# Resolve the plugin root. The marketplace name and version are globbed rather
# than hard-coded so a marketplace rename (e.g. gruntwork-marketplace ->
# gruntwork-lastmilefirst) or a version bump can't silently disarm the hook. The
# marketplace glob is constrained to the gruntwork-* namespace so an unrelated or
# hostile marketplace can't supply the scripts this hook executes.
# Glob expands sorted, so the last existing match wins -> newest installed version.
PLUGIN_ROOT=""
for candidate in \\
    "$HOME/.claude/plugins/cache"/gruntwork-*/lastmilefirst/* \\
    "$HOME/.claude/plugins/marketplaces"/gruntwork-*/plugins/lastmilefirst; do
    [ -d "$candidate" ] && PLUGIN_ROOT="$candidate"
done

if [ -z "$PLUGIN_ROOT" ]; then
    # Plugin not found — don't block commits, just warn.
    echo "lastmilefirst: plugin not found, skipping pre-commit checks" >&2
    exit 0
fi

# Counted so a resolved-but-incomplete install (plugin root present, check
# scripts missing) reports instead of silently passing every commit.
CHECKS_RUN=0
{checks}

if [ "$CHECKS_RUN" -eq 0 ]; then
    echo "lastmilefirst: no check scripts found under $PLUGIN_ROOT" >&2
    echo "lastmilefirst: commit allowed, but the install looks incomplete" >&2
fi

exit 0
"""


# Rendered once at import so callers can still read HOOK_SCRIPT directly.
HOOK_SCRIPT = build_hook_script()


def get_current_hooks_path() -> Optional[str]:
    """Get current global core.hooksPath setting."""
    try:
        result = subprocess.run(
            ["git", "config", "--global", "core.hooksPath"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


def install_hooks() -> str:
    """Install global pre-commit hook for secret scanning."""
    lines = []

    # Check for existing hooksPath
    current = get_current_hooks_path()
    if current and str(HOOKS_DIR) not in current:
        lines.append(f"WARNING: core.hooksPath is already set to: {current}")
        lines.append(f"Installing will override this to: {HOOKS_DIR}")
        lines.append("The previous hooks path will not be used.")
        lines.append("")

    # Create hooks directory
    HOOKS_DIR.mkdir(parents=True, exist_ok=True)

    # Check for existing hook file
    if HOOK_FILE.exists():
        existing = HOOK_FILE.read_text(encoding="utf-8")
        if "lastmilefirst" in existing:
            lines.append("Hook already installed. Updating to latest version...")
        else:
            lines.append(f"WARNING: Existing pre-commit hook at {HOOK_FILE}")
            lines.append("Backing up to pre-commit.backup before overwriting.")
            backup = HOOKS_DIR / "pre-commit.backup"
            HOOK_FILE.rename(backup)

    # Write hook script
    HOOK_FILE.write_text(HOOK_SCRIPT, encoding="utf-8")
    HOOK_FILE.chmod(HOOK_FILE.stat().st_mode | stat.S_IEXEC)

    # Set global hooksPath
    try:
        subprocess.run(
            ["git", "config", "--global", "core.hooksPath", str(HOOKS_DIR)],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as e:
        return f"Error setting core.hooksPath: {e}"

    lines.append(f"Pre-commit hook installed at: {HOOK_FILE}")
    lines.append(f"Global core.hooksPath set to: {HOOKS_DIR}")
    lines.append("")
    lines.append("Checks run before every commit, in order:")
    for label, rel_path, _ in CHECKS:
        lines.append(f"  - {label} ({rel_path})")
    lines.append("")
    lines.append("To uninstall: /run-scan-secrets --uninstall-hooks")

    return "\n".join(lines)


def uninstall_hooks() -> str:
    """Remove the global pre-commit hook and reset core.hooksPath."""
    lines = []

    current = get_current_hooks_path()
    if current and str(HOOKS_DIR) in current:
        try:
            subprocess.run(
                ["git", "config", "--global", "--unset", "core.hooksPath"],
                capture_output=True,
                text=True,
                timeout=5,
                check=True,
            )
            lines.append("Removed global core.hooksPath setting.")
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            lines.append("Warning: Could not unset core.hooksPath.")
    elif current:
        lines.append(f"core.hooksPath points to {current} (not ours), leaving it alone.")
    else:
        lines.append("core.hooksPath was not set.")

    if HOOK_FILE.exists():
        HOOK_FILE.unlink()
        lines.append(f"Removed hook file: {HOOK_FILE}")
    else:
        lines.append("No hook file to remove.")

    # Restore backup if exists
    backup = HOOKS_DIR / "pre-commit.backup"
    if backup.exists():
        lines.append(f"Note: Backup exists at {backup}")

    lines.append("\nPre-commit hook uninstalled.")
    return "\n".join(lines)


def hook_status() -> str:
    """Check current hook installation status."""
    lines = []

    current = get_current_hooks_path()
    if current:
        lines.append(f"Global core.hooksPath: {current}")
        is_ours = str(HOOKS_DIR) in current
        lines.append(f"  Managed by lastmilefirst: {'yes' if is_ours else 'no'}")
    else:
        lines.append("Global core.hooksPath: not set")

    if HOOK_FILE.exists():
        lines.append(f"Hook file exists: {HOOK_FILE}")
        is_executable = os.access(HOOK_FILE, os.X_OK)
        lines.append(f"  Executable: {'yes' if is_executable else 'no'}")
    else:
        lines.append(f"Hook file: not installed")

    return "\n".join(lines)
