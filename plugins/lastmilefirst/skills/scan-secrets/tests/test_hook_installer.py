"""Tests for the pre-commit hook dispatcher.

The hook is generated bash that gates every commit on this machine, so the
things worth asserting are: it parses, it fails closed on a check's non-zero
exit, and it stays loud when the install is incomplete. A silently-passing hook
is worse than no hook, because it looks like coverage.
"""
from __future__ import annotations

import os
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


# --- the pre-push dispatcher ------------------------------------------------

KINDS = ["pre-commit", "pre-push"]


def _registry(kind: str):
    return hook_installer.CHECKS if kind == "pre-commit" else hook_installer.PRE_PUSH_CHECKS


def test_default_kind_is_pre_commit():
    assert hook_installer.build_hook_script() == hook_installer.build_hook_script("pre-commit")


def test_pre_push_registry_is_the_scan_alone():
    assert [rel for _, rel, _ in hook_installer.PRE_PUSH_CHECKS] == [
        "skills/scan-secrets/scripts/scan_secrets.py"
    ]


def test_unknown_kind_is_refused():
    with pytest.raises(ValueError):
        hook_installer.build_hook_script("post-merge")


@pytest.mark.parametrize("kind", KINDS)
def test_both_scripts_are_valid_bash(kind, tmp_path):
    path = tmp_path / kind
    path.write_text(hook_installer.build_hook_script(kind), encoding="utf-8")
    result = subprocess.run(["bash", "-n", str(path)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("kind", KINDS)
def test_each_script_passes_its_own_flag(kind):
    script = hook_installer.build_hook_script(kind)
    other = "--pre-push" if kind == "pre-commit" else "--pre-commit"
    assert f'python3 "$CHECK_PATH" --{kind} "$@"' in script
    assert other not in script


def test_pre_push_dispatcher_reads_nothing_from_stdin():
    """The check inherits the hook's stdin; a `read` in bash would consume it."""
    script = hook_installer.build_hook_script("pre-push")
    assert "read " not in script
    assert "/dev/stdin" not in script


def _run_kind(kind: str, tmp_path: Path, exit_codes: dict, stdin: str = "",
              args: tuple = ()) -> subprocess.CompletedProcess:
    plugin_root = tmp_path / ".claude" / "plugins" / "marketplaces" / "gruntwork-x" / "plugins" / "lastmilefirst"
    for _, rel_path, _ in _registry(kind):
        target = plugin_root / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        code = exit_codes.get(rel_path, 0)
        # Echo stdin back so the test can see the check inherited it.
        target.write_text(
            "import sys\n"
            f"print({rel_path!r}, sys.argv[1:], repr(sys.stdin.read()))\n"
            f"sys.exit({code})\n",
            encoding="utf-8",
        )
    hook = tmp_path / kind
    hook.write_text(hook_installer.build_hook_script(kind), encoding="utf-8")
    return subprocess.run(
        ["bash", str(hook), *args],
        input=stdin,
        capture_output=True,
        text=True,
        env={"HOME": str(tmp_path), "PATH": "/usr/bin:/bin:/usr/local/bin"},
    )


@pytest.mark.parametrize("kind", KINDS)
def test_both_scripts_fail_closed_on_a_check_failure(kind, tmp_path):
    rel = "skills/scan-secrets/scripts/scan_secrets.py"
    result = _run_kind(kind, tmp_path, {rel: 1})
    assert result.returncode == 1


@pytest.mark.parametrize("kind", KINDS)
def test_both_scripts_pass_when_every_check_passes(kind, tmp_path):
    result = _run_kind(kind, tmp_path, {})
    assert result.returncode == 0, result.stderr


def test_pre_push_check_inherits_the_hook_stdin(tmp_path):
    line = "refs/heads/main " + "a" * 40 + " refs/heads/main " + "0" * 40 + "\n"
    result = _run_kind("pre-push", tmp_path, {}, stdin=line)
    assert result.returncode == 0, result.stderr
    assert "['--pre-push']" in result.stdout
    assert repr(line) in result.stdout


def test_pre_push_check_receives_the_remote_name_and_url(tmp_path):
    """git calls pre-push with `<remote name> <remote url>`; the check needs the URL."""
    url = "git@github.com:example-org/example-repo.git"
    result = _run_kind("pre-push", tmp_path, {}, args=("origin", url))
    assert result.returncode == 0, result.stderr
    assert f"['--pre-push', 'origin', '{url}']" in result.stdout


def test_pre_commit_check_gets_only_its_flag(tmp_path):
    result = _run_kind("pre-commit", tmp_path, {})
    assert result.returncode == 0, result.stderr
    assert "['--pre-commit']" in result.stdout


def test_pre_push_failure_message_names_the_push(tmp_path):
    result = _run_kind("pre-push", tmp_path, {"skills/scan-secrets/scripts/scan_secrets.py": 1})
    assert "Push blocked" in result.stderr


@pytest.fixture
def hooks_home(tmp_path, monkeypatch):
    """Point the installer at tmp_path and stub the global git config call."""
    hooks_dir = tmp_path / "git-hooks"
    monkeypatch.setattr(hook_installer, "HOOKS_DIR", hooks_dir)
    monkeypatch.setattr(hook_installer, "HOOK_FILE", hooks_dir / "pre-commit")
    monkeypatch.setattr(hook_installer, "PRE_PUSH_HOOK_FILE", hooks_dir / "pre-push")
    state = {"hooks_path": None, "calls": []}

    def fake_run(cmd, **_kwargs):
        state["calls"].append(cmd)
        if cmd[:3] == ["git", "config", "--global"] and "--unset" in cmd:
            state["hooks_path"] = None
        elif cmd[:3] == ["git", "config", "--global"] and len(cmd) == 5:
            state["hooks_path"] = cmd[4]
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(hook_installer.subprocess, "run", fake_run)
    monkeypatch.setattr(hook_installer, "get_current_hooks_path", lambda: state["hooks_path"])
    return hooks_dir, state


def test_install_writes_both_hooks(hooks_home):
    hooks_dir, state = hooks_home
    hook_installer.install_hooks()
    for name, kind in (("pre-commit", "pre-commit"), ("pre-push", "pre-push")):
        path = hooks_dir / name
        assert path.read_text(encoding="utf-8") == hook_installer.build_hook_script(kind)
        assert os.access(path, os.X_OK)
    assert state["hooks_path"] == str(hooks_dir)


def test_install_backs_up_a_foreign_pre_push_hook(hooks_home):
    hooks_dir, _ = hooks_home
    hooks_dir.mkdir(parents=True)
    (hooks_dir / "pre-push").write_text("#!/bin/sh\necho someone else's\n", encoding="utf-8")
    hook_installer.install_hooks()
    assert "someone else's" in (hooks_dir / "pre-push.backup").read_text(encoding="utf-8")
    assert "lastmilefirst" in (hooks_dir / "pre-push").read_text(encoding="utf-8")


def test_uninstall_removes_both_hooks(hooks_home):
    hooks_dir, _ = hooks_home
    hook_installer.install_hooks()
    hook_installer.uninstall_hooks()
    assert not (hooks_dir / "pre-commit").exists()
    assert not (hooks_dir / "pre-push").exists()
