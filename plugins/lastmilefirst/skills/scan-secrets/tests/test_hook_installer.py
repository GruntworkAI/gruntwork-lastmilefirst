"""Tests for the pre-commit hook dispatcher.

The hook is generated bash that gates every commit on this machine, so the
things worth asserting are: it parses, it fails closed on a check's non-zero
exit, and it stays loud when the install is incomplete. A silently-passing hook
is worse than no hook, because it looks like coverage.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

import hook_installer


@pytest.fixture
def script() -> str:
    return hook_installer.build_hook_script()


def test_script_is_valid_bash(script, tmp_path):
    path = tmp_path / "pre-commit"
    path.write_text(script, encoding="utf-8")
    result = subprocess.run(["bash", "-n", str(path)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_module_constant_matches_builder(script):
    """HOOK_SCRIPT is rendered at import; callers read it directly."""
    assert hook_installer.HOOK_SCRIPT == script


def test_every_registered_check_appears(script):
    for _, rel_path, _ in hook_installer.CHECKS:
        assert rel_path in script


def test_identity_check_runs_before_the_secret_scan(script):
    """Cheapest first: identity is two git-config reads, the scan shells out."""
    identity = script.index("skills/organize-orgs/scripts/check_identity.py")
    secrets = script.index("skills/scan-secrets/scripts/scan_secrets.py")
    assert identity < secrets


def test_each_check_gates_the_commit(script):
    """Every check must be followed by a non-zero test that exits 1."""
    assert script.count("if [ $? -ne 0 ]; then") == len(hook_installer.CHECKS)
    assert script.count("exit 1") == len(hook_installer.CHECKS)


def test_missing_plugin_root_warns_but_allows(script):
    """Tooling absence must not wedge commits — it is not a policy violation."""
    assert 'echo "lastmilefirst: plugin not found' in script
    # The guard exits 0, not 1. Split on "\nfi" rather than "fi" — the literal
    # "fi" also occurs inside the word "lastmilefirst".
    guard = script.split('if [ -z "$PLUGIN_ROOT" ]; then')[1].split("\nfi")[0]
    assert "exit 0" in guard
    assert "exit 1" not in guard


def test_resolved_but_incomplete_install_is_reported(script):
    """Regression guard.

    Globbing to the plugin *root* rather than to a specific script means the
    root can resolve while the check scripts are missing. Without the counter
    that state passes every commit in silence, which reads as coverage.
    """
    assert "CHECKS_RUN=0" in script
    assert script.count("CHECKS_RUN=$((CHECKS_RUN + 1))") == len(hook_installer.CHECKS)
    assert 'if [ "$CHECKS_RUN" -eq 0 ]; then' in script


def test_plugin_glob_stays_namespaced(script):
    """The glob must not widen past gruntwork-*.

    A hostile or unrelated marketplace must not be able to supply the scripts
    this hook executes with the user's shell.
    """
    assert "/gruntwork-*/" in script
    assert '"$HOME/.claude/plugins/cache"/gruntwork-*/lastmilefirst/*' in script
    assert '"$HOME/.claude/plugins/marketplaces"/gruntwork-*/plugins/lastmilefirst' in script


def _run_hook(script: str, tmp_path: Path, exit_codes: dict[str, int]) -> subprocess.CompletedProcess:
    """Execute the hook against fake check scripts with chosen exit codes."""
    plugin_root = tmp_path / ".claude" / "plugins" / "marketplaces" / "gruntwork-x" / "plugins" / "lastmilefirst"
    for _, rel_path, _ in hook_installer.CHECKS:
        target = plugin_root / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        code = exit_codes.get(rel_path, 0)
        target.write_text(
            f"import sys\nprint({rel_path!r})\nsys.exit({code})\n", encoding="utf-8"
        )
    hook = tmp_path / "pre-commit"
    hook.write_text(script, encoding="utf-8")
    return subprocess.run(
        ["bash", str(hook)],
        capture_output=True,
        text=True,
        env={"HOME": str(tmp_path), "PATH": "/usr/bin:/bin:/usr/local/bin"},
    )


def test_all_checks_passing_allows_the_commit(script, tmp_path):
    result = _run_hook(script, tmp_path, {})
    assert result.returncode == 0, result.stderr


def test_first_failing_check_stops_the_rest(script, tmp_path):
    """Identity fails -> the secret scan must not run."""
    result = _run_hook(
        script, tmp_path, {"skills/organize-orgs/scripts/check_identity.py": 1}
    )
    assert result.returncode == 1
    assert "check_identity.py" in result.stdout
    assert "scan_secrets.py" not in result.stdout


def test_later_check_failure_still_blocks(script, tmp_path):
    result = _run_hook(
        script, tmp_path, {"skills/scan-secrets/scripts/scan_secrets.py": 1}
    )
    assert result.returncode == 1
    assert "Secret scan found potential secrets" in result.stderr
