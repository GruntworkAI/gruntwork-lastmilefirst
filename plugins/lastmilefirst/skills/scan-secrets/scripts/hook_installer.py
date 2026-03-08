#!/usr/bin/env python3
"""
Global pre-commit hook installer for secret scanning.

Uses git config --global core.hooksPath to apply to all repos.
Installs to ~/.claude/lastmilefirst/git-hooks/pre-commit.
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

# The pre-commit hook script
HOOK_SCRIPT = """\
#!/usr/bin/env bash
# lastmilefirst secret scanner pre-commit hook
# Installed by: /run-scan-secrets --install-hooks
# Remove with:  /run-scan-secrets --uninstall-hooks

SCRIPT_DIR="$(dirname "$(readlink -f "$0" 2>/dev/null || echo "$0")")"

# Find the scan-secrets CLI
CLI_CANDIDATES=(
    "$HOME/.claude/plugins/cache/gruntwork-marketplace/lastmilefirst"/*/skills/scan-secrets/scripts/cli.py
    "$HOME/.claude/plugins/marketplaces/gruntwork-marketplace/plugins/lastmilefirst/skills/scan-secrets/scripts/cli.py"
)

CLI_PATH=""
for candidate in "${CLI_CANDIDATES[@]}"; do
    if [ -f "$candidate" ]; then
        CLI_PATH="$candidate"
        break
    fi
done

if [ -z "$CLI_PATH" ]; then
    # Plugin not found — don't block commits, just warn
    echo "lastmilefirst: scan-secrets plugin not found, skipping secret scan" >&2
    exit 0
fi

# Run staged scan
python3 "$CLI_PATH" --pre-commit
EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    echo "" >&2
    echo "Secret scan found potential secrets in staged changes." >&2
    echo "Review the findings above and either:" >&2
    echo "  1. Remove the secrets and re-stage" >&2
    echo "  2. Add to .gitignore if the file shouldn't be tracked" >&2
    echo "  3. Add a gitleaks:allow comment if it's a false positive" >&2
    echo "" >&2
    exit 1
fi

exit 0
"""


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
    lines.append("The hook will scan staged changes for secrets before every commit.")
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
