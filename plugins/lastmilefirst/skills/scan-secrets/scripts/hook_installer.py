#!/usr/bin/env python3
"""
Global pre-commit and pre-push hook installer.

Uses git config --global core.hooksPath to apply to all repos.
Installs to ~/.claude/lastmilefirst/git-hooks/pre-commit and .../pre-push.

Each installed hook is a *dispatcher*: it resolves the plugin root once, then
runs each registered check in order and fails on the first non-zero exit.
Checks are listed in CHECKS (pre-commit) and PRE_PUSH_CHECKS (pre-push) below.
Adding one is a single entry — the hook was previously a single-purpose
script, which meant a second concern could not be added without rewriting it.
"""
from __future__ import annotations

import os
import stat
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

HOOKS_DIR = Path.home() / ".claude" / "lastmilefirst" / "git-hooks"
HOOK_FILE = HOOKS_DIR / "pre-commit"
PRE_PUSH_HOOK_FILE = HOOKS_DIR / "pre-push"

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


# Registered pre-push checks, in run order.
#
# One entry on purpose: git passes the pushed refs on the hook's stdin, and
# stdin can be read once. The dispatcher reads nothing itself, so the single
# check inherits it. A second check here would need the dispatcher to buffer
# stdin and replay it to each.
PRE_PUSH_CHECKS = [
    (
        "secret scan",
        "skills/scan-secrets/scripts/scan_secrets.py",
        "\n".join(
            [
                "Push blocked by the secret scan (see the report above).",
                "Remove the finding from the commits being pushed (amend or",
                "rewrite them), or fix the visibility mismatch it names, then",
                "push again. A gitleaks:allow comment marks a false positive.",
            ]
        ),
    ),
]

# kind -> (registry, flag passed to each check, what the hook gates)
_HOOK_KINDS = {
    "pre-commit": (CHECKS, "--pre-commit", "commit"),
    "pre-push": (PRE_PUSH_CHECKS, "--pre-push", "push"),
}


def _render_check(label: str, rel_path: str, failure_message: str, flag: str) -> str:
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
    python3 "$CHECK_PATH" {flag}
    if [ $? -ne 0 ]; then{message_block}
        exit 1
    fi
fi"""


def build_hook_script(kind: str = "pre-commit") -> str:
    """Assemble the dispatcher installed as the global `kind` hook.

    `kind` is "pre-commit" or "pre-push". Both share the plugin-root glob, the
    CHECKS_RUN counter, and the plugin-missing warning; they differ only in the
    registry and the flag each check receives. For pre-push the dispatcher
    reads nothing from stdin, so the check inherits the ref lines git sends.
    """
    if kind not in _HOOK_KINDS:
        raise ValueError(f"unknown hook kind: {kind!r}")
    registry, flag, action = _HOOK_KINDS[kind]
    checks = "".join(
        _render_check(label, rel, msg, flag) for label, rel, msg in registry
    )
    return f"""\
#!/usr/bin/env bash
# lastmilefirst {kind} hook (dispatcher)
# Installed by: /run-scan-secrets --install-hooks
# Remove with:  /run-scan-secrets --uninstall-hooks
#
# Runs each registered check in order, failing on the first non-zero exit.
# Checks: {', '.join(label for label, _, _ in registry)}

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
    # Plugin not found — don't block, just warn.
    echo "lastmilefirst: plugin not found, skipping {kind} checks" >&2
    exit 0
fi

# Counted so a resolved-but-incomplete install (plugin root present, check
# scripts missing) reports instead of silently passing every {action}.
CHECKS_RUN=0
{checks}

if [ "$CHECKS_RUN" -eq 0 ]; then
    echo "lastmilefirst: no check scripts found under $PLUGIN_ROOT" >&2
    echo "lastmilefirst: {action} allowed, but the install looks incomplete" >&2
fi

exit 0
"""


# Rendered once at import so callers can still read HOOK_SCRIPT directly.
HOOK_SCRIPT = build_hook_script("pre-commit")
PRE_PUSH_HOOK_SCRIPT = build_hook_script("pre-push")


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


def _write_hook(hook_file: Path, script: str, lines: List[str]) -> None:
    """Write one hook file, backing up a foreign one to <name>.backup first."""
    if hook_file.exists():
        existing = hook_file.read_text(encoding="utf-8")
        if "lastmilefirst" in existing:
            lines.append(f"{hook_file.name} hook already installed. Updating to latest version...")
        else:
            lines.append(f"WARNING: Existing {hook_file.name} hook at {hook_file}")
            lines.append(f"Backing up to {hook_file.name}.backup before overwriting.")
            hook_file.rename(hook_file.parent / f"{hook_file.name}.backup")

    hook_file.write_text(script, encoding="utf-8")
    hook_file.chmod(hook_file.stat().st_mode | stat.S_IEXEC)


def install_hooks() -> str:
    """Install the global pre-commit and pre-push hooks."""
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

    # Write both hook scripts, backing up any foreign hook first.
    _write_hook(HOOK_FILE, HOOK_SCRIPT, lines)
    _write_hook(PRE_PUSH_HOOK_FILE, PRE_PUSH_HOOK_SCRIPT, lines)

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
    lines.append(f"Pre-push hook installed at:   {PRE_PUSH_HOOK_FILE}")
    lines.append(f"Global core.hooksPath set to: {HOOKS_DIR}")
    lines.append("")
    lines.append("Checks run before every commit, in order:")
    for label, rel_path, _ in CHECKS:
        lines.append(f"  - {label} ({rel_path})")
    lines.append("Checks run before every push, in order:")
    for label, rel_path, _ in PRE_PUSH_CHECKS:
        lines.append(f"  - {label} ({rel_path})")
    lines.append("")
    lines.append("To uninstall: /run-scan-secrets --uninstall-hooks")

    return "\n".join(lines)


def uninstall_hooks() -> str:
    """Remove the global pre-commit and pre-push hooks and reset core.hooksPath."""
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

    for hook_file in (HOOK_FILE, PRE_PUSH_HOOK_FILE):
        if hook_file.exists():
            hook_file.unlink()
            lines.append(f"Removed hook file: {hook_file}")
        else:
            lines.append(f"No {hook_file.name} hook file to remove.")

        # A backed-up foreign hook is reported, not restored.
        backup = hook_file.parent / f"{hook_file.name}.backup"
        if backup.exists():
            lines.append(f"Note: Backup exists at {backup}")

    lines.append("\nPre-commit and pre-push hooks uninstalled.")
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

    for hook_file in (HOOK_FILE, PRE_PUSH_HOOK_FILE):
        if hook_file.exists():
            lines.append(f"Hook file exists: {hook_file}")
            is_executable = os.access(hook_file, os.X_OK)
            lines.append(f"  Executable: {'yes' if is_executable else 'no'}")
        else:
            lines.append(f"{hook_file.name} hook file: not installed")

    return "\n".join(lines)
