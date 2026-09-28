"""Context resolution, state-key rename, and the workspace summary (plan 2026-09-28-001, U2).

Builds a throwaway workspace under tmp_path with a flat org and an org holding
one client directory. The organize-claude config is patched in, and the
Overwatch state directory is redirected to tmp_path, so the real state file is
never read or written.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

import overwatch
import session_start
import update_state

NOW = int(time.time())
DAY = 86400


def mark(directory: Path, kind: str = "client") -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / ".claude-workspace").write_text(f"type: {kind}\n")
    return directory


@pytest.fixture
def state_dir(tmp_path, monkeypatch):
    target = tmp_path / "state"
    target.mkdir()
    monkeypatch.setattr(overwatch, "get_state_dir", lambda: target)
    monkeypatch.setattr(session_start, "get_state_dir", lambda: target)
    return target


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    ws = tmp_path / "Code"
    (ws / "flat" / "alpha" / "src").mkdir(parents=True)
    mark(ws / "acme" / "northwind")
    (ws / "acme" / "northwind" / "web").mkdir()
    (ws / "acme" / "northwind" / "docs").mkdir()
    (ws / "acme" / "practice").mkdir()
    (ws / "acme" / "practice" / "CLAUDE.md").write_text("# practice\n\n## Archetype: Usable\n")
    (ws / "unlisted" / "thing").mkdir(parents=True)
    config = {"workspace": str(ws), "orgs": ["flat", "acme"]}
    monkeypatch.setattr(overwatch, "_load_organize_config", lambda: config)
    return ws


# --- resolve_context ----------------------------------------------------------

def test_flat_project_keeps_its_two_part_key(workspace):
    ctx = overwatch.resolve_context(workspace / "flat" / "alpha" / "src")
    assert ctx == {"org": "flat", "project": "flat/alpha", "client": None}


def test_nested_project_gets_a_three_part_key(workspace):
    ctx = overwatch.resolve_context(workspace / "acme" / "northwind" / "web")
    assert ctx == {"org": "acme", "project": "acme/northwind/web", "client": "northwind"}


def test_client_directory_has_the_org_and_no_project(workspace):
    ctx = overwatch.resolve_context(workspace / "acme" / "northwind")
    assert ctx == {"org": "acme", "project": None, "client": "northwind"}


@pytest.mark.parametrize("where", ["unlisted/thing", None])
def test_path_outside_any_configured_org_resolves_to_nothing(workspace, tmp_path, where):
    path = workspace / where if where else tmp_path / "elsewhere"
    path.mkdir(parents=True, exist_ok=True)
    ctx = overwatch.resolve_context(path)
    assert ctx == {"org": None, "project": None, "client": None}


def test_resolve_context_falls_back_to_flat_without_the_loader(workspace, monkeypatch):
    monkeypatch.setitem(sys.modules, "workspace_types", None)
    ctx = overwatch.resolve_context(workspace / "flat" / "alpha" / "src")
    assert ctx == {"org": "flat", "project": "flat/alpha", "client": None}


def test_update_project_state_writes_the_nested_key(workspace, state_dir):
    overwatch.update_project_state("last_review", NOW, workspace / "acme" / "northwind" / "docs")
    state = overwatch.load_state()
    assert state["projects"]["acme/northwind/docs"]["last_review"] == NOW


def test_client_directory_produces_no_project_state(workspace, state_dir):
    overwatch.update_project_state("last_review", NOW, workspace / "acme" / "northwind")
    assert overwatch.load_state()["projects"] == {}


# --- update_state.py ----------------------------------------------------------

def test_rename_keeps_the_timestamps(state_dir):
    overwatch.update_scoped_state("projects", "acme/web", "last_review", NOW)
    overwatch.update_scoped_state("projects", "acme/web", "last_secret_scan", NOW - DAY)

    assert update_state.rename_key("projects", "acme/web", "acme/northwind/web") == ""

    projects = overwatch.load_state()["projects"]
    assert "acme/web" not in projects
    assert projects["acme/northwind/web"] == {"last_review": NOW, "last_secret_scan": NOW - DAY}


def test_rename_refuses_to_overwrite(state_dir):
    overwatch.update_scoped_state("projects", "acme/web", "last_review", NOW)
    overwatch.update_scoped_state("projects", "acme/northwind/web", "last_review", NOW - DAY)

    refused = update_state.rename_key("projects", "acme/web", "acme/northwind/web")

    assert "already has state" in refused
    projects = overwatch.load_state()["projects"]
    assert projects["acme/web"]["last_review"] == NOW
    assert projects["acme/northwind/web"]["last_review"] == NOW - DAY


def test_rename_of_a_missing_key_refuses(state_dir):
    assert "no state" in update_state.rename_key("projects", "acme/gone", "acme/northwind/gone")


def test_rename_from_the_command_line(state_dir, monkeypatch, capsys):
    overwatch.update_scoped_state("projects", "acme/web", "last_review", NOW)
    monkeypatch.setattr(sys, "argv", ["update_state.py", "rename",
                                      "--from", "acme/web", "--to", "acme/northwind/web"])
    update_state.main()
    assert "acme/northwind/web" in overwatch.load_state()["projects"]
    assert "moved" in capsys.readouterr().out


def test_action_from_a_client_directory_says_not_tracked(workspace, state_dir, monkeypatch, capsys):
    monkeypatch.chdir(workspace / "acme" / "northwind")
    monkeypatch.setattr(sys, "argv", ["update_state.py", "review"])
    with pytest.raises(SystemExit):
        update_state.main()
    assert "container directory, not tracked" in capsys.readouterr().err
    assert overwatch.load_state()["projects"] == {}


def test_explicit_three_part_key_is_accepted(state_dir, monkeypatch):
    nested = "acme/northwind/web"
    monkeypatch.setattr(sys, "argv", ["update_state.py", "review", "--key", nested])
    update_state.main()
    assert "last_review" in overwatch.load_state()["projects"]["acme/northwind/web"]


# --- workspace summary ----------------------------------------------------------

def summary(workspace, state, full=True, commit=NOW):
    config = {"workspace": str(workspace), "orgs": ["flat", "acme"]}
    return session_start.check_workspace_summary(
        config, full=full, state=state, commit_ts=lambda _path: commit,
    )


def test_summary_lists_nested_projects_under_their_client(workspace):
    lines = summary(workspace, {"projects": {}})
    assert lines[0] == "WORKSPACE REPORT (4 projects)"
    text = "\n".join(lines)
    assert "    - northwind/docs" in text
    assert "    - northwind/web" in text
    assert "    - northwind" not in lines


def test_summary_reads_state_by_the_nested_key(workspace):
    fresh = {"last_review": NOW, "last_secret_scan": NOW, "last_organize": NOW}
    state = {"projects": {
        "acme/northwind/web": fresh,
        "acme/northwind/docs": fresh,
        "acme/practice": fresh,
        "flat/alpha": fresh,
    }}
    lines = summary(workspace, state, commit=NOW - DAY)
    text = "\n".join(lines)
    assert "Never reviewed" not in text
    assert "Never scanned" not in text
    # Only the three directories without a CLAUDE.md, never the client directory.
    assert "Missing CLAUDE.md (3)" in text


def test_compact_summary_counts_the_client_directory_as_nothing(workspace):
    lines = summary(workspace, {"projects": {}}, full=False)
    assert lines[0].startswith("WORKSPACE: 3/4 missing CLAUDE.md")


def test_client_directory_with_org_json_is_an_action_line(workspace):
    (workspace / "acme" / "northwind" / ".claude").mkdir()
    (workspace / "acme" / "northwind" / ".claude" / "org.json").write_text("{}")
    lines = summary(workspace, {"projects": {}})
    flagged = [l for l in lines if l.startswith("ACTION REQUIRED:")]
    assert len(flagged) == 1
    assert "acme/northwind" in flagged[0] and "org.json" in flagged[0]


def test_nested_client_directory_is_a_note(workspace):
    mark(workspace / "acme" / "northwind" / "web")
    lines = summary(workspace, {"projects": {}})
    notes = [l for l in lines if l.startswith("NOTE:")]
    assert len(notes) == 1 and "acme/northwind/web" in notes[0]


def test_client_directory_with_org_json_and_no_children_is_still_reported(workspace):
    """The defect used to ride on the first child, so an empty container never reported it."""
    mark(workspace / "acme" / "contoso")
    (workspace / "acme" / "contoso" / ".claude").mkdir()
    (workspace / "acme" / "contoso" / ".claude" / "org.json").write_text("{}")
    lines = summary(workspace, {"projects": {}})
    flagged = [l for l in lines if l.startswith("ACTION REQUIRED:")]
    assert len(flagged) == 1 and "acme/contoso" in flagged[0]


def test_client_directory_that_is_a_repo_is_a_warning(workspace):
    (workspace / "acme" / "northwind" / ".git").mkdir()
    lines = summary(workspace, {"projects": {}})
    warned = [l for l in lines if l.startswith("WARNING:") and "acme/northwind" in l]
    assert len(warned) == 1 and "should not be a repo" in warned[0]


def test_summary_degrades_to_the_flat_walk_without_the_loader(workspace, monkeypatch):
    monkeypatch.setattr(session_start, "iter_projects", None)
    monkeypatch.setattr(session_start, "layout_issues", None)
    lines = summary(workspace, {"projects": {}})
    assert lines[0].startswith("NOTE:") and "not descended" in lines[0]
    # acme/northwind, acme/practice, flat/alpha: the container counts as a project.
    assert "WORKSPACE REPORT (3 projects)" in lines


# --- Overwatch guidance lookup --------------------------------------------------

def guidance(workspace, cwd, home):
    config = {"workspace": str(workspace), "orgs": ["flat", "acme"]}
    return session_start.check_overwatch_guidance(cwd=cwd, config=config, home=home)


def test_guidance_in_the_org_claude_md_is_found_from_a_nested_project(workspace, tmp_path):
    home = tmp_path / "home"  # no ~/Code/CLAUDE.md here
    (workspace / "acme" / "CLAUDE.md").write_text("## Overwatch response\n")
    assert guidance(workspace, workspace / "acme" / "northwind" / "web", home) is None


def test_guidance_missing_everywhere_is_reported_from_a_nested_project(workspace, tmp_path):
    home = tmp_path / "home"
    # The client directory's parent-of-project position used to be read as the org.
    (workspace / "acme" / "northwind" / "CLAUDE.md").write_text("# northwind\n")
    alert = guidance(workspace, workspace / "acme" / "northwind" / "web", home)
    assert alert and alert.startswith("ACTION REQUIRED")


def test_guidance_in_the_client_claude_md_counts(workspace, tmp_path):
    home = tmp_path / "home"
    (workspace / "acme" / "northwind" / "CLAUDE.md").write_text("Overwatch alerts: act on them.\n")
    assert guidance(workspace, workspace / "acme" / "northwind" / "web", home) is None
