"""Session start reports only where there is a workspace to report on.

Three positions: no workspace configured on the machine (print nothing), a
configured workspace with the session outside it (one notice saying what is
and is not covered), and inside the workspace (the alerts, as before, with a
reminder that the user can change what gets raised).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

import session_start


@pytest.fixture
def machine(tmp_path, monkeypatch):
    """A home directory with a workspace in it, and a folder outside the workspace."""
    home = (tmp_path / "home").resolve()
    workspace = home / "Code"
    (workspace / "studio" / "tool").mkdir(parents=True)
    (home / "Downloads").mkdir()
    monkeypatch.setattr(session_start.Path, "home", classmethod(lambda cls: home))
    monkeypatch.setattr(session_start, "get_tmp_dir", lambda: home)
    monkeypatch.setattr(sys, "argv", ["session_start.py"])
    return home


def configure(monkeypatch, config):
    monkeypatch.setattr(session_start, "_load_organize_config", lambda: config)


# --- workspace_position -------------------------------------------------------

@pytest.mark.parametrize("config", [None, {}, {"orgs": ["studio"]}, {"workspace": ""}])
def test_no_workspace_in_config_is_unconfigured(machine, config):
    assert session_start.workspace_position(config, machine / "Downloads") == "unconfigured"


def test_a_workspace_path_that_is_not_here_is_unconfigured(machine):
    config = {"workspace": str(machine / "Elsewhere")}
    assert session_start.workspace_position(config, machine / "Downloads") == "unconfigured"


@pytest.mark.parametrize("where", ["Code", "Code/studio", "Code/studio/tool"])
def test_the_workspace_and_everything_under_it_is_inside(machine, where):
    config = {"workspace": str(machine / "Code")}
    assert session_start.workspace_position(config, machine / where) == "inside"


def test_a_folder_beside_the_workspace_is_outside(machine):
    config = {"workspace": str(machine / "Code")}
    assert session_start.workspace_position(config, machine / "Downloads") == "outside"


def test_a_sibling_sharing_the_workspace_name_prefix_is_outside(machine):
    (machine / "Code-old").mkdir()
    config = {"workspace": str(machine / "Code")}
    assert session_start.workspace_position(config, machine / "Code-old") == "outside"


# --- main: unconfigured -------------------------------------------------------

def test_an_unconfigured_machine_prints_nothing(machine, monkeypatch, capsys):
    configure(monkeypatch, None)
    monkeypatch.chdir(machine / "Downloads")
    session_start.main()
    out = capsys.readouterr()
    assert out.out == "" and out.err == ""


def test_an_explicit_full_run_on_an_unconfigured_machine_says_why(machine, monkeypatch, capsys):
    configure(monkeypatch, None)
    monkeypatch.chdir(machine / "Downloads")
    monkeypatch.setattr(sys, "argv", ["session_start.py", "--full"])
    session_start.main()
    out = capsys.readouterr().out
    assert "no workspace is configured" in out
    assert "ACTION REQUIRED" not in out and "WARNING" not in out


# --- main: outside the workspace ----------------------------------------------

def run_outside(machine, monkeypatch, capsys, hooks="both", repo_alerts=()):
    configure(monkeypatch, {"workspace": str(machine / "Code"), "orgs": ["studio"]})
    monkeypatch.setattr(session_start, "git_hooks_status", lambda: hooks)
    monkeypatch.setattr(session_start, "_visibility_checks", lambda key: list(repo_alerts))
    monkeypatch.chdir(machine / "Downloads")
    session_start.main()
    return capsys.readouterr()


def test_outside_the_workspace_gets_the_notice_and_no_alerts(machine, monkeypatch, capsys):
    out = run_outside(machine, monkeypatch, capsys, hooks="both")
    assert "outside your workspace (~/Code)" in out.out
    assert "does not reach it" in out.out
    for absent in ("ACTION REQUIRED", "WARNING", "DIRECTIVE", "WORKSPACE:"):
        assert absent not in out.out


def test_the_notice_says_the_hooks_still_run_when_they_are_installed(machine, monkeypatch, capsys):
    out = run_outside(machine, monkeypatch, capsys, hooks="both")
    assert "installed machine-wide and still run here" in out.out
    assert "--install-hooks" not in out.out


def test_the_notice_says_nothing_scans_commits_when_the_hooks_are_missing(machine, monkeypatch, capsys):
    out = run_outside(machine, monkeypatch, capsys, hooks="none")
    assert "do not run here" in out.out
    assert "Nothing scans commits or pushes made here" in out.out
    assert "/run-scan-secrets --install-hooks" in out.out


def test_the_notice_says_pushes_are_not_scanned_when_only_the_commit_hook_exists(machine, monkeypatch, capsys):
    out = run_outside(machine, monkeypatch, capsys, hooks="commit-only")
    assert "commit secret-scan hook still runs here" in out.out
    assert "pushes are not scanned" in out.out
    assert "commit and push secret-scan hooks are installed" not in out.out


def test_repo_visibility_alerts_still_appear_outside_the_workspace(machine, monkeypatch, capsys):
    alert = "WARNING: PUBLIC repo (someone/thing) -- do not commit secrets or sensitive content"
    out = run_outside(machine, monkeypatch, capsys, repo_alerts=[alert])
    assert alert in out.out and alert in out.err
    assert "Also present each ACTION REQUIRED and WARNING line above" in out.out
    assert "outside your workspace" in out.out


def test_no_extra_instruction_when_the_repo_has_no_alerts(machine, monkeypatch, capsys):
    out = run_outside(machine, monkeypatch, capsys)
    assert "Also present each" not in out.out


def test_the_instruction_to_claude_stays_off_the_users_terminal(machine, monkeypatch, capsys):
    out = run_outside(machine, monkeypatch, capsys, hooks="both")
    assert "NOTE: Tell the user" in out.out
    assert "outside your workspace" in out.err
    assert "NOTE:" not in out.err


# --- git_hooks_status ---------------------------------------------------------

class Result:
    def __init__(self, stdout="", returncode=0):
        self.stdout, self.returncode = stdout, returncode


def install(machine, *names, executable=True):
    hooks = machine / ".claude" / "lastmilefirst" / "git-hooks"
    hooks.mkdir(parents=True, exist_ok=True)
    for name in names:
        (hooks / name).write_text("#!/bin/sh\n")
        (hooks / name).chmod(0o755 if executable else 0o644)
    return hooks


def git_says(monkeypatch, stdout, returncode=0):
    calls = []

    def run(cmd, **kwargs):
        calls.append((cmd, kwargs))
        return Result(stdout, returncode)

    monkeypatch.setattr(session_start.subprocess, "run", run)
    return calls


def test_both_hooks_when_git_uses_the_plugin_directory_here(machine, monkeypatch):
    hooks = install(machine, "pre-commit", "pre-push")
    calls = git_says(monkeypatch, f"{hooks}\n")
    assert session_start.git_hooks_status(machine, machine / "Downloads") == "both"
    cmd, kwargs = calls[0]
    # The effective path for this directory, so a repo-local override is seen.
    assert "--global" not in cmd and kwargs["cwd"] == str(machine / "Downloads")


def test_an_install_from_before_the_push_hook_is_commit_only(machine, monkeypatch):
    hooks = install(machine, "pre-commit")
    git_says(monkeypatch, f"{hooks}\n")
    assert session_start.git_hooks_status(machine) == "commit-only"


def test_a_repo_with_its_own_hooks_path_runs_neither_hook(machine, monkeypatch):
    install(machine, "pre-commit", "pre-push")
    git_says(monkeypatch, ".husky\n")
    assert session_start.git_hooks_status(machine) == "none"


def test_no_hooks_path_or_a_failed_git_call_is_none(machine, monkeypatch):
    install(machine, "pre-commit", "pre-push")
    git_says(monkeypatch, "", returncode=1)
    assert session_start.git_hooks_status(machine) == "none"


def test_a_hook_that_is_not_executable_does_not_count(machine, monkeypatch):
    hooks = install(machine, "pre-commit", "pre-push", executable=False)
    git_says(monkeypatch, f"{hooks}\n")
    assert session_start.git_hooks_status(machine) == "none"


def test_a_missing_hook_file_is_none(machine, monkeypatch):
    hooks = machine / ".claude" / "lastmilefirst" / "git-hooks"
    git_says(monkeypatch, f"{hooks}\n")
    assert session_start.git_hooks_status(machine) == "none"


# --- an unreadable config -----------------------------------------------------

def test_a_config_that_exists_but_cannot_be_read_is_reported(machine, monkeypatch, capsys):
    config_file = machine / ".config" / "organize-claude" / "config.json"
    config_file.parent.mkdir(parents=True)
    config_file.write_text("{ not json")
    configure(monkeypatch, None)
    monkeypatch.chdir(machine / "Downloads")
    session_start.main()
    out = capsys.readouterr()
    assert "~/.config/organize-claude/config.json exists but could not be read" in out.out
    assert "NOTE: Tell the user" in out.out and "NOTE:" not in out.err


# --- main: --full outside, and inside the workspace ---------------------------

def stub_checks(monkeypatch, warning):
    """Replace every check main() runs with a quiet stub, plus one warning."""
    none = lambda *a, **k: None
    empty = lambda *a, **k: []
    for name in ("check_git_status", "check_review_status", "check_organize_status",
                 "check_stale_todos", "check_secret_scan_status", "check_workspace_scan_status",
                 "check_claude_md", "check_overwatch_guidance", "check_archetype"):
        monkeypatch.setattr(session_start, name, none)
    for name in ("check_plugin_updates", "check_usage_stats", "_visibility_checks",
                 "check_cross_project_blockers", "check_org_infrastructure",
                 "check_identity_contracts", "check_device", "check_workspace_summary"):
        monkeypatch.setattr(session_start, name, empty)
    monkeypatch.setattr(session_start, "check_claude_review_status", lambda *a, **k: [warning])
    monkeypatch.setattr(session_start, "get_scoped_state", lambda *a, **k: {})


def test_an_explicit_full_run_outside_the_workspace_gets_the_report_not_the_notice(machine, monkeypatch, capsys):
    configure(monkeypatch, {"workspace": str(machine / "Code"), "orgs": ["studio"]})
    stub_checks(monkeypatch, "WARNING: 40 days since last review of workspace CLAUDE.md.")
    monkeypatch.setattr(sys, "argv", ["session_start.py", "--full"])
    monkeypatch.chdir(machine / "Downloads")
    session_start.main()
    out = capsys.readouterr().out
    assert "WARNING: 40 days since last review" in out
    assert "DIRECTIVE: 1 item(s)" in out
    assert "outside your workspace" not in out


def test_inside_the_workspace_the_reminder_shows_until_preferences_exist(machine, monkeypatch, capsys):
    config = {"workspace": str(machine / "Code"), "orgs": ["studio"]}
    configure(monkeypatch, config)
    monkeypatch.setattr(session_start, "resolve_context",
                        lambda cwd=None: {"org": "studio", "project": "studio/tool", "client": None})
    stub_checks(monkeypatch, "WARNING: 40 days since last review of workspace CLAUDE.md.")
    monkeypatch.chdir(machine / "Code" / "studio" / "tool")

    session_start.main()
    out = capsys.readouterr()
    assert "DIRECTIVE: 1 item(s)" in out.out
    assert "Changing what Overwatch raises" in out.out
    assert "DIRECTIVE" not in out.err and "Changing what Overwatch raises" not in out.err

    (machine / "Code" / "CLAUDE.md").write_text("# Workspace\n\n## Overwatch preferences\n\nWarnings only when relevant.\n")
    session_start.main()
    out = capsys.readouterr().out
    assert "Changing what Overwatch raises" not in out
    assert "follow it." in out


# --- the directive and the preferences reminder -------------------------------

ALERTS = ["ACTION REQUIRED: something", "WARNING: something else", "2 skill invocations this week"]


def test_the_directive_counts_only_actionable_lines_and_carries_the_reminder():
    directive = "\n".join(session_start.build_directive(ALERTS, preferences_reminder=True))
    assert "DIRECTIVE: 2 item(s)" in directive
    assert "Overwatch preferences" in directive
    assert "Changing what Overwatch raises" in directive


def test_existing_preferences_replace_the_reminder_and_win_over_the_directive():
    directive = "\n".join(session_start.build_directive(ALERTS, preferences_reminder=False))
    assert "DIRECTIVE: 2 item(s)" in directive
    assert "Changing what Overwatch raises" not in directive
    assert "Where it differs from this\ndirective, follow it." in directive


def test_no_directive_and_no_reminder_without_an_actionable_line():
    assert session_start.build_directive(["2 skill invocations this week"], True) == []


@pytest.mark.parametrize("text,expected", [
    ("# Workspace\n\n## Overwatch preferences\n\nRaise action-required items only.\n", True),
    ("# Workspace\n\n### Overwatch Preferences (mine)\n", True),
    ("# Workspace\n\nSee the overwatch preferences section of the skill.\n", False),
    ("# Workspace\n\n## Session Start Protocol\n\nOverwatch alerts appear at session start.\n", False),
])
def test_preferences_are_recognized_by_heading_only(machine, monkeypatch, text, expected):
    config = {"workspace": str(machine / "Code"), "orgs": ["studio"]}
    configure(monkeypatch, config)
    (machine / "Code" / "CLAUDE.md").write_text(text)
    found = session_start.has_overwatch_preferences(
        cwd=machine / "Code" / "studio" / "tool", config=config, home=machine
    )
    assert found is expected


def test_guidance_is_still_found_in_the_workspace_file(machine, monkeypatch):
    config = {"workspace": str(machine / "Code"), "orgs": ["studio"]}
    configure(monkeypatch, config)
    (machine / "Code" / "CLAUDE.md").write_text("# Workspace\n\nWhen Overwatch alerts appear, list them.\n")
    assert session_start.check_overwatch_guidance(
        cwd=machine / "Code" / "studio" / "tool", config=config, home=machine
    ) is None
