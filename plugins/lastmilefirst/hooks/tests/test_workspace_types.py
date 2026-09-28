"""The workspace layout loader (plan 2026-09-28-001, U1).

Builds a throwaway workspace under tmp_path with four shapes: a flat org, an
org holding one client directory with two repos, a client directory inside a
client directory, and a client directory that wrongly carries `.claude/org.json`.
The real workspace is never read.
"""
from __future__ import annotations

from pathlib import Path

import pytest

import workspace_types as wt


def mark(directory: Path, kind: str = "client") -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / ".claude-workspace").write_text(f"type: {kind}\n")
    return directory


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "Code"
    # Flat org.
    (ws / "flat" / "alpha").mkdir(parents=True)
    (ws / "flat" / "beta").mkdir()
    (ws / "flat" / ".hidden").mkdir()
    (ws / "flat" / "README.md").write_text("not a directory\n")
    # Org with one client directory holding two repos, plus a flat repo.
    mark(ws / "acme" / "northwind")
    (ws / "acme" / "northwind" / "web").mkdir()
    (ws / "acme" / "northwind" / "docs").mkdir()
    (ws / "acme" / "northwind" / ".scratch").mkdir()
    (ws / "acme" / "practice").mkdir()
    # Container inside a container.
    mark(ws / "nested" / "outer")
    mark(ws / "nested" / "outer" / "inner")
    (ws / "nested" / "outer" / "inner" / "repo").mkdir()
    # Container carrying org.json.
    mark(ws / "broken" / "contoso")
    (ws / "broken" / "contoso" / ".claude").mkdir()
    (ws / "broken" / "contoso" / ".claude" / "org.json").write_text("{}")
    (ws / "broken" / "contoso" / "one").mkdir()
    (ws / "broken" / "contoso" / "two").mkdir()
    return ws


def keys(org_dir: Path) -> list[str]:
    return [p.key for p in wt.iter_projects(org_dir)]


def test_loader_reuses_the_hook_parser():
    import check_identity

    assert wt.workspace_type is check_identity.workspace_type
    assert wt.WORKSPACE_MARKER == check_identity.WORKSPACE_MARKER


def test_flat_org_yields_every_non_hidden_directory(workspace):
    projects = list(wt.iter_projects(workspace / "flat"))
    assert [p.key for p in projects] == ["flat/alpha", "flat/beta"]
    assert [p.label for p in projects] == ["alpha", "beta"]
    assert all(p.client is None and p.note is None and p.defect is None for p in projects)


def test_container_yields_its_children_not_itself(workspace):
    projects = list(wt.iter_projects(workspace / "acme"))
    assert [p.key for p in projects] == ["acme/northwind/docs", "acme/northwind/web", "acme/practice"]
    assert [p.label for p in projects] == ["northwind/docs", "northwind/web", "practice"]
    assert [p.client for p in projects] == ["northwind", "northwind", None]
    assert projects[0].key_parts == ("acme", "northwind", "docs")


def test_container_inside_container_is_a_project_with_a_note(workspace):
    (project,) = wt.iter_projects(workspace / "nested")
    assert project.key == "nested/outer/inner"
    assert project.note and "only one level" in project.note.lower()
    assert project.defect is None


def test_container_with_org_json_is_flagged_once_and_still_descended(workspace):
    projects = list(wt.iter_projects(workspace / "broken"))
    assert [p.key for p in projects] == ["broken/contoso/one", "broken/contoso/two"]
    assert "org.json" in projects[0].defect
    assert projects[1].defect is None


def test_loader_never_filters(workspace):
    """No .git anywhere in the fixture, and every directory still comes back."""
    assert len(keys(workspace / "acme")) == 3


@pytest.mark.parametrize("kind", ["studio", "external", "scratch", ""])
def test_other_marker_types_are_not_containers(workspace, kind):
    target = workspace / "flat" / "alpha"
    (target / ".claude-workspace").write_text(f"type: {kind}\n")
    assert not wt.is_container(target)
    assert "flat/alpha" in keys(workspace / "flat")


def test_marker_value_is_case_insensitive(workspace):
    target = workspace / "flat" / "beta"
    (target / ".claude-workspace").write_text("type: Client\n")
    assert wt.is_container(target)


# --- keys and resolve -------------------------------------------------------

@pytest.mark.parametrize(
    "rel,expected",
    [
        ("flat/alpha", "flat/alpha"),
        ("flat/alpha/src/deep", "flat/alpha"),
        ("acme/northwind/web", "acme/northwind/web"),
        ("acme/northwind/web/src", "acme/northwind/web"),
        ("acme/practice", "acme/practice"),
        ("acme/northwind", None),
        ("acme", None),
        ("", None),
        ("nested/outer/inner/repo", "nested/outer/inner"),
    ],
)
def test_project_key(workspace, rel, expected):
    assert wt.project_key(workspace / rel, workspace) == expected


def test_project_key_outside_workspace_is_none(workspace, tmp_path):
    assert wt.project_key(tmp_path / "elsewhere", workspace) is None


def test_resolve_from_container_has_org_and_client_but_no_project(workspace):
    ctx = wt.resolve(workspace / "acme" / "northwind", workspace, ["acme"])
    assert ctx == wt.Context(org="acme", client="northwind", project=None, key=None)


def test_resolve_nested_project(workspace):
    ctx = wt.resolve(workspace / "acme" / "northwind" / "docs", workspace, ["acme"])
    assert ctx == wt.Context("acme", "northwind", "docs", "acme/northwind/docs")


def test_resolve_respects_the_org_list(workspace):
    assert wt.resolve(workspace / "flat" / "alpha", workspace, ["acme"]) == wt.Context()
    assert wt.resolve(workspace / "flat" / "alpha", workspace).key == "flat/alpha"


def test_top_level_client_marker_does_nothing(workspace):
    """D1: a client that is a whole org is an ordinary org."""
    mark(workspace / "flat")
    assert keys(workspace / "flat") == ["flat/alpha", "flat/beta"]
    assert wt.project_key(workspace / "flat" / "alpha", workspace) == "flat/alpha"
