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

def run_outside(machine, monkeypatch, capsys, hooks_installed):
    configure(monkeypatch, {"workspace": str(machine / "Code"), "orgs": ["studio"]})
    monkeypatch.setattr(session_start, "git_hooks_installed", lambda: hooks_installed)
    monkeypatch.chdir(machine / "Downloads")
    session_start.main()
    return capsys.readouterr()


def test_outside_the_workspace_gets_the_notice_and_no_alerts(machine, monkeypatch, capsys):
    out = run_outside(machine, monkeypatch, capsys, hooks_installed=True)
    assert "outside your workspace (~/Code)" in out.out
    assert "does not reach it" in out.out
    for absent in ("ACTION REQUIRED", "WARNING", "DIRECTIVE", "WORKSPACE:"):
        assert absent not in out.out


def test_the_notice_says_the_hooks_still_run_when_they_are_installed(machine, monkeypatch, capsys):
    out = run_outside(machine, monkeypatch, capsys, hooks_installed=True)
    assert "installed machine-wide and still run here" in out.out
    assert "--install-hooks" not in out.out


def test_the_notice_says_nothing_scans_commits_when_the_hooks_are_missing(machine, monkeypatch, capsys):
    out = run_outside(machine, monkeypatch, capsys, hooks_installed=False)
    assert "not installed on this machine" in out.out
    assert "/run-scan-secrets --install-hooks" in out.out


def test_the_instruction_to_claude_stays_off_the_users_terminal(machine, monkeypatch, capsys):
    out = run_outside(machine, monkeypatch, capsys, hooks_installed=True)
    assert "NOTE: Tell the user" in out.out
    assert "outside your workspace" in out.err
    assert "NOTE:" not in out.err


# --- git_hooks_installed ------------------------------------------------------

class Result:
    def __init__(self, stdout="", returncode=0):
        self.stdout, self.returncode = stdout, returncode


def test_hooks_count_as_installed_only_when_git_points_at_them(machine, monkeypatch):
    hooks = machine / ".claude" / "lastmilefirst" / "git-hooks"
    hooks.mkdir(parents=True)
    (hooks / "pre-commit").write_text("#!/bin/sh\n")
    monkeypatch.setattr(session_start.subprocess, "run", lambda *a, **k: Result(f"{hooks}\n"))
    assert session_start.git_hooks_installed(machine) is True
    monkeypatch.setattr(session_start.subprocess, "run", lambda *a, **k: Result("/somewhere/else\n"))
    assert session_start.git_hooks_installed(machine) is False
    monkeypatch.setattr(session_start.subprocess, "run", lambda *a, **k: Result("", 1))
    assert session_start.git_hooks_installed(machine) is False


def test_hooks_are_not_installed_when_the_hook_file_is_missing(machine, monkeypatch):
    hooks = machine / ".claude" / "lastmilefirst" / "git-hooks"
    monkeypatch.setattr(session_start.subprocess, "run", lambda *a, **k: Result(f"{hooks}\n"))
    assert session_start.git_hooks_installed(machine) is False


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
