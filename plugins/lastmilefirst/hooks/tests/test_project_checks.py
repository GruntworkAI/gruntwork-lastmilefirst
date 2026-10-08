"""Project-level checks read the resolved project root, and only inside a project.

Plan 2026-10-08-001. Builds a throwaway workspace with a flat org, an org holding
a client directory, and an unlisted directory, then exercises the CLAUDE.md and
archetype checks from every kind of directory a session can start in.
"""
from __future__ import annotations

from pathlib import Path

import pytest

import overwatch
import session_start


def mark(directory: Path, kind: str = "client") -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / ".claude-workspace").write_text(f"type: {kind}\n")
    return directory


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    ws = tmp_path / "Code"
    ws.mkdir()
    (ws / "CLAUDE.md").write_text("# workspace\n\nOverwatch response guidance lives here.\n")
    # A flat project with no CLAUDE.md, entered from a subdirectory.
    (ws / "flat" / "bare" / "src").mkdir(parents=True)
    # A flat project whose root CLAUDE.md lacks an archetype.
    (ws / "flat" / "typed" / "lib").mkdir(parents=True)
    (ws / "flat" / "typed" / "CLAUDE.md").write_text("# typed\n\nNo archetype line.\n")
    # A flat project with a complete root CLAUDE.md.
    (ws / "flat" / "whole" / "deep" / "er").mkdir(parents=True)
    (ws / "flat" / "whole" / "CLAUDE.md").write_text("# whole\n\n## Archetype: Usable\n")
    # An org with a client directory holding a nested project.
    mark(ws / "acme" / "northwind")
    (ws / "acme" / "northwind" / "web" / "app").mkdir(parents=True)
    # A directory inside the workspace that is not under a configured org.
    (ws / "unlisted" / "thing").mkdir(parents=True)
    config = {"workspace": str(ws), "orgs": ["flat", "acme"]}
    monkeypatch.setattr(overwatch, "_load_organize_config", lambda: config)
    monkeypatch.setattr(session_start, "_load_organize_config", lambda: config)
    return ws


def root_for(ws: Path, where: Path) -> Path | None:
    return overwatch.project_root(overwatch.resolve_context(where))


# --- project_root -------------------------------------------------------------

def test_flat_project_root_from_a_subdirectory(workspace):
    assert root_for(workspace, workspace / "flat" / "bare" / "src") == workspace / "flat" / "bare"


def test_nested_project_root_from_a_subdirectory(workspace):
    where = workspace / "acme" / "northwind" / "web" / "app"
    assert root_for(workspace, where) == workspace / "acme" / "northwind" / "web"


@pytest.mark.parametrize("where", ["", "flat", "acme", "acme/northwind", "unlisted/thing"])
def test_non_project_directories_have_no_root(workspace, where):
    assert root_for(workspace, workspace / where if where else workspace) is None


def test_outside_the_workspace_has_no_root(workspace, tmp_path):
    elsewhere = tmp_path / "Downloads"
    elsewhere.mkdir()
    assert root_for(workspace, elsewhere) is None


def test_root_is_none_without_a_workspace_in_config():
    ctx = {"org": "flat", "project": "flat/bare", "client": None}
    assert overwatch.project_root(ctx, {}) is None


# --- check_claude_md ----------------------------------------------------------

def test_missing_root_claude_md_is_reported_from_a_subdirectory(workspace):
    alert = session_start.check_claude_md(root_for(workspace, workspace / "flat" / "bare" / "src"))
    assert alert is not None and alert.startswith("ACTION REQUIRED: No CLAUDE.md")


def test_present_root_claude_md_is_found_from_a_deep_subdirectory(workspace):
    where = workspace / "flat" / "whole" / "deep" / "er"
    assert session_start.check_claude_md(root_for(workspace, where)) is None


@pytest.mark.parametrize("where", ["", "flat", "acme", "acme/northwind", "unlisted/thing"])
def test_no_claude_md_alert_outside_a_project(workspace, where):
    target = workspace / where if where else workspace
    assert session_start.check_claude_md(root_for(workspace, target)) is None


def test_no_claude_md_alert_outside_the_workspace(workspace, tmp_path):
    elsewhere = tmp_path / "Downloads"
    elsewhere.mkdir()
    assert session_start.check_claude_md(root_for(workspace, elsewhere)) is None


# --- check_archetype ----------------------------------------------------------

@pytest.mark.skipif(session_start._detect_archetype is None, reason="archetype module unavailable")
def test_missing_archetype_is_reported_from_a_subdirectory(workspace):
    alert = session_start.check_archetype(root_for(workspace, workspace / "flat" / "typed" / "lib"))
    assert alert is not None and alert.startswith("WARNING: No archetype")


@pytest.mark.skipif(session_start._detect_archetype is None, reason="archetype module unavailable")
def test_declared_archetype_is_found_from_a_subdirectory(workspace):
    where = workspace / "flat" / "whole" / "deep" / "er"
    assert session_start.check_archetype(root_for(workspace, where)) is None


def test_archetype_check_is_silent_outside_a_project(workspace, tmp_path):
    assert session_start.check_archetype(None) is None


# --- guidance search from the project root ------------------------------------

def test_guidance_is_searched_from_the_project_root(workspace, tmp_path, monkeypatch):
    # The workspace CLAUDE.md carries guidance, but the real search also looks
    # at ~/Code/CLAUDE.md; point home at tmp_path so only the fixture counts.
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    (workspace / "CLAUDE.md").unlink()
    (workspace / "flat" / "whole" / "CLAUDE.md").write_text("# whole\n\n## Overwatch response\n")
    root = root_for(workspace, workspace / "flat" / "whole" / "deep" / "er")
    config = {"workspace": str(workspace), "orgs": ["flat", "acme"]}
    assert session_start.check_overwatch_guidance(cwd=root, config=config, home=tmp_path) is None
