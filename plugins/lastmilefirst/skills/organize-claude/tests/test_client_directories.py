"""organize-claude and client directories (plan 2026-09-28-001, U3).

A directory one level inside an org marked `type: client` holds projects for
one counterparty. organize-claude must find the projects inside it, never
scaffold into the client directory itself, and compare the workspace mapping
by path so two clients' `docs` repos stay distinct.

Everything is built under tmp_path, and the config path is patched, so the real
organize-claude config and workspace are never touched.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import organize_claude
from organize_claude import find_projects, short_name, validate_project_mapping


def mark_client(directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / ".claude-workspace").write_text("type: client\n")
    return directory


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = (tmp_path / "Code").resolve()
    for client in ("northwind", "contoso"):
        mark_client(ws / "acme" / client)
        (ws / "acme" / client / "docs").mkdir()
    (ws / "acme" / "acme-practice").mkdir()
    (ws / "acme" / "CLAUDE.md").write_text("# Acme\n")
    return ws


def test_find_projects_descends_and_skips_client_directories(workspace):
    names = [name for name, _path, _ in find_projects(workspace / "acme")]
    assert names == ["acme-practice", "contoso/docs", "northwind/docs"]


def test_short_name_keeps_nested_names_whole():
    assert short_name("acme-practice", "acme") == "practice"
    assert short_name("northwind/acme-docs", "acme") == "northwind/acme-docs"


def test_mapping_is_compared_by_path_so_two_docs_repos_stay_distinct(workspace):
    projects = [
        (short_name(name, "acme"), path, has)
        for name, path, has in find_projects(workspace / "acme")
    ]
    mapping = {
        "practice": str(workspace / "acme" / "acme-practice"),
        "docs": str(workspace / "acme" / "northwind" / "docs"),
    }
    missing, unmapped = validate_project_mapping(mapping, projects, workspace)
    assert missing == []
    assert unmapped == [("contoso/docs", workspace / "acme" / "contoso" / "docs")]


def test_mapping_row_for_a_moved_project_is_reported(workspace):
    projects = [(name, path, has) for name, path, has in find_projects(workspace / "acme")]
    mapping = {"docs": str(workspace / "acme" / "docs")}  # flat path, no longer on disk
    missing, unmapped = validate_project_mapping(mapping, projects, workspace)
    assert missing == ["docs"]
    assert len(unmapped) == 3


def test_scaffold_all_projects_never_writes_into_a_client_directory(workspace, tmp_path,
                                                                    monkeypatch, capsys):
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"workspace": str(workspace), "orgs": ["acme"]}))
    monkeypatch.setattr(organize_claude, "CONFIG_PATH", config_path)
    monkeypatch.setattr("sys.argv", ["organize_claude.py", "--scaffold-all-projects"])

    organize_claude.main()

    assert not (workspace / "acme" / "northwind" / "CLAUDE.md").exists()
    assert not (workspace / "acme" / "contoso" / "CLAUDE.md").exists()
    assert (workspace / "acme" / "northwind" / "docs" / "CLAUDE.md").exists()
    assert (workspace / "acme" / "contoso" / "docs" / "CLAUDE.md").exists()
    assert (workspace / "acme" / "acme-practice" / "CLAUDE.md").exists()


def test_audit_report_indents_client_rows_under_the_org(workspace, capsys):
    projects = {"acme": find_projects(workspace / "acme")}
    organize_claude.show_audit_report(
        workspace, (workspace / "CLAUDE.md", False, None),
        [("acme", workspace / "acme", True)], projects,
    )
    out = capsys.readouterr().out
    assert "\n  northwind/\n    ✗ docs MISSING" in out
    assert "\n  contoso/\n    ✗ docs MISSING" in out
    assert "\n  ✗ acme-practice MISSING" in out
