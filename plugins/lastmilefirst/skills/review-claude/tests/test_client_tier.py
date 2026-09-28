"""The client tier in review-claude (plan 2026-09-28-001, U3).

A directory one level inside an org marked `type: client` holds projects for
one counterparty. Its CLAUDE.md classifies as tier `client`, a project inside
it chains workspace, org, client, project, and the org's inventory check lists
its projects by full path.

Everything is built under tmp_path; the real workspace is never touched.
"""

import pytest

import review_claude
from review_claude import (
    check_inventory,
    classify_tier,
    disk_containers,
    disk_projects,
    find_projects,
    tier_files,
)


def make_claude_md(directory, text="# CLAUDE.md\n"):
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "CLAUDE.md"
    path.write_text(text)
    return path


def mark_client(directory):
    directory.mkdir(parents=True, exist_ok=True)
    (directory / ".claude-workspace").write_text("type: client\n")
    return directory


@pytest.fixture
def workspace(tmp_path):
    ws = tmp_path / "Code"
    mark_client(ws / "acme" / "northwind")
    (ws / "acme" / "northwind" / "web").mkdir()
    (ws / "acme" / "northwind" / "docs").mkdir()
    (ws / "acme" / "practice").mkdir()
    return ws


# --- tier detection -----------------------------------------------------------

def test_client_directory_claude_md_classifies_as_client(workspace):
    claude_md = make_claude_md(workspace / "acme" / "northwind")
    assert classify_tier(claude_md, workspace) == ("client", "found .claude-workspace type: client")


def test_client_directory_with_org_json_still_classifies_as_client(workspace):
    client = workspace / "acme" / "northwind"
    (client / ".claude").mkdir()
    (client / ".claude" / "org.json").write_text("{}")
    assert classify_tier(make_claude_md(client), workspace)[0] == "client"


def test_top_level_client_marker_is_still_an_org(workspace):
    mark_client(workspace / "acme")
    assert classify_tier(make_claude_md(workspace / "acme"), workspace)[0] == "org"


def test_nested_project_classifies_as_project(workspace):
    claude_md = make_claude_md(workspace / "acme" / "northwind" / "web")
    assert classify_tier(claude_md, workspace)[0] == "project"


def test_client_is_a_tier_choice():
    assert "client" in review_claude.TIER_CHOICES
    assert review_claude.resolve_tier(None, None, "client") == ("client", "set by --tier")


# --- tier chain ---------------------------------------------------------------

def test_nested_project_chains_through_the_client(workspace):
    claude_md = make_claude_md(workspace / "acme" / "northwind" / "web")
    assert tier_files(claude_md, "project", workspace) == [
        ("workspace", workspace / "CLAUDE.md"),
        ("org", workspace / "acme" / "CLAUDE.md"),
        ("client", workspace / "acme" / "northwind" / "CLAUDE.md"),
        ("project", claude_md),
    ]


def test_client_file_chains_to_the_org(workspace):
    claude_md = make_claude_md(workspace / "acme" / "northwind")
    assert tier_files(claude_md, "client", workspace) == [
        ("workspace", workspace / "CLAUDE.md"),
        ("org", workspace / "acme" / "CLAUDE.md"),
        ("client", claude_md),
    ]


def test_flat_project_chain_is_unchanged(workspace):
    claude_md = make_claude_md(workspace / "acme" / "practice")
    assert [tier for tier, _ in tier_files(claude_md, "project", workspace)] == [
        "workspace", "org", "project",
    ]


def test_overlap_report_covers_the_client_tier(workspace):
    make_claude_md(workspace / "acme" / "northwind", "# Northwind\n\n## Tools\n")
    claude_md = make_claude_md(workspace / "acme" / "northwind" / "web", "# Web\n\n## Tools\n")
    lines = review_claude.overlap_report(tier_files(claude_md, "project", workspace), claude_md)
    assert "client" in lines[1] and "project" in lines[1]


# --- discovery and inventory ----------------------------------------------------

def test_find_projects_descends_and_skips_the_client_directory(workspace):
    names = [name for name, _path, _ in find_projects(workspace / "acme")]
    assert names == ["northwind/docs", "northwind/web", "practice"]


ORG_TABLE = """# Acme

## Projects

| Project | Path |
|---------|------|
| web | ~/Code/acme/northwind/web |
| northwind | client directory |
| practice | ~/Code/acme/practice |
"""


def test_inventory_matches_by_full_path_and_not_by_the_client_name(workspace):
    claude_md = make_claude_md(workspace / "acme", ORG_TABLE)
    result = check_inventory(
        ORG_TABLE, "org",
        disk_projects(claude_md, "org", []),
        disk_containers(claude_md, "org", []),
    )
    assert result["status"] == "ok"
    # web is listed by its full path; docs is only covered by the client's row.
    assert result["unlisted"] == ["northwind/docs"]
    # The client's own row names a directory that exists.
    assert result["not_on_disk"] == []


def test_workspace_inventory_sees_nested_projects(workspace):
    ws_md = make_claude_md(workspace, "# Workspace\n\n## Project Directory Mapping\n\n"
                           "| Project | Path |\n|---|---|\n"
                           "| web | ~/Code/acme/northwind/web |\n")
    names = disk_projects(ws_md, "user", ["acme"])
    assert "northwind/web" in names and "northwind" not in names
    result = check_inventory(ws_md.read_text(), "user", names, disk_containers(ws_md, "user", ["acme"]))
    assert "northwind/web" not in result["unlisted"]
    assert "northwind/docs" in result["unlisted"]


def test_full_walk_labels_a_nested_project_with_its_client(workspace, monkeypatch, capsys):
    make_claude_md(workspace / "acme" / "northwind" / "web", "# Web\n")
    make_claude_md(workspace / "acme" / "northwind", "# Northwind\n")
    config = {"workspace": str(workspace), "orgs": ["acme"]}
    monkeypatch.setattr(review_claude, "load_config", lambda: config)
    monkeypatch.setattr("sys.argv", ["review_claude.py"])
    review_claude.main()
    out = capsys.readouterr().out
    assert "northwind/web/CLAUDE.md" in out
    # The client directory's own file has no expected sections, so the walk skips it.
    assert "  northwind/CLAUDE.md" not in out
