"""
Cross-tier checks for review-claude (plan 2026-09-21-001, U3).

Two scripted checks: a tier's project table against the directories on disk,
and a map of which tiers carry a section on the same topic. Both measure and
neither judges content; the contradiction reading is left to Claude.

Everything is built under tmp_path; the real workspace is never touched.
"""

import pytest

from review_claude import (
    check_inventory,
    disk_projects,
    format_inventory,
    overlap_report,
    tier_files,
)


def make_dirs(parent, *names):
    for name in names:
        (parent / name).mkdir(parents=True)


@pytest.fixture
def workspace(tmp_path):
    ws = tmp_path / "Code"
    ws.mkdir()
    return ws


ORG_TWO_ROWS = """# Acme

## Projects

| Project | Description |
|---------|-------------|
| acme-api | Backend |
| acme-web | Frontend |
"""


def test_org_with_three_dirs_and_two_rows_reports_one_unlisted(workspace):
    org = workspace / "acme"
    make_dirs(org, "acme-api", "acme-web", "acme-cli")
    claude_md = org / "CLAUDE.md"
    claude_md.write_text(ORG_TWO_ROWS)

    result = check_inventory(ORG_TWO_ROWS, "org", disk_projects(claude_md, "org", []))

    assert result["status"] == "ok"
    assert result["unlisted"] == ["acme-cli"]
    assert result["not_on_disk"] == []
    lines = format_inventory(result, "org")
    assert lines[0] == "Inventory: 2 of 3 project directories are listed in ## Projects"
    assert "  - on disk, not listed: acme-cli" in lines


def test_row_without_directory_is_a_finding_at_org_tier():
    content = ORG_TWO_ROWS + "| acme-gone | Retired |\n"
    result = check_inventory(content, "org", ["acme-api", "acme-web"])

    assert result["not_on_disk"] == ["acme-gone"]
    lines = format_inventory(result, "org")
    assert "1 of 3 rows name no directory on disk" in lines
    assert not any("informational" in line for line in lines)
    assert "  - listed, not on disk: acme-gone" in lines


def test_row_without_directory_is_informational_at_workspace_tier(workspace):
    make_dirs(workspace / "acme", "acme-api")
    claude_md = workspace / "CLAUDE.md"
    content = """# Me

## Project Directory Mapping

### Acme

| Project Name | Directory Path |
|-------------|---------------|
| api | ~/Code/acme/acme-api |
| later | ~/Code/acme/acme-not-cloned |
"""
    claude_md.write_text(content)

    result = check_inventory(content, "user", disk_projects(claude_md, "user", ["acme", "absent-org"]))

    assert result["unlisted"] == []
    assert result["not_on_disk"] == ["acme-not-cloned"]
    lines = format_inventory(result, "user")
    assert lines[0] == "Inventory: 1 of 1 project directories are listed in ## Project Directory Mapping"
    assert any(line.startswith("1 of 2 rows name no directory on disk (informational") for line in lines)


@pytest.mark.parametrize(
    "row",
    [
        "| acme-api | Backend |",
        "| [acme-api](../acme-api) | Backend |",
        "| `acme-api` | Backend |",
    ],
)
def test_bare_names_links_and_code_spans_all_parse(row):
    content = f"## Projects\n\n| Project | Description |\n|---|---|\n{row}\n"
    result = check_inventory(content, "org", ["acme-api"])
    assert result["status"] == "ok"
    assert result["unlisted"] == []
    assert result["not_on_disk"] == []


def test_name_inside_a_longer_name_does_not_count_as_listed():
    content = "## Projects\n\n| Project |\n|---|\n| acme-api-v2 |\n"
    result = check_inventory(content, "org", ["acme-api", "acme-api-v2"])
    assert result["unlisted"] == ["acme-api"]


def test_projects_section_without_a_table_says_could_not_read():
    content = "# Acme\n\n## Projects\n\n- acme-api\n- acme-web\n\n## Tech Stack\n"
    result = check_inventory(content, "org", ["acme-api", "acme-web"])

    assert result["status"] == "unreadable"
    assert format_inventory(result, "org") == [
        "Inventory: ## Projects is present but could not read the table"
    ]


def test_absent_section_is_one_line_and_skipped():
    result = check_inventory("# Acme\n\n## Tech Stack\n", "org", ["acme-api"])
    assert format_inventory(result, "org") == ["Inventory: no ## Projects section, check skipped"]


def test_overlap_map_names_both_tiers_carrying_tools(workspace):
    (workspace / "CLAUDE.md").write_text("# Me\n\n## Development Tools\n\n| a | b |\n")
    org = workspace / "acme"
    org.mkdir()
    org_md = org / "CLAUDE.md"
    org_md.write_text("# Acme\n\n## Approved Tools & Resources\n\n## Projects\n")

    lines = overlap_report(tier_files(org_md, "org", workspace), org_md)

    tools = next(line for line in lines if line.strip().startswith("tools:"))
    assert 'workspace "development tools"' in tools
    assert 'org "approved tools & resources" (this file)' in tools
    inventory = next(line for line in lines if line.strip().startswith("project inventory:"))
    assert 'org "projects" (this file)' in inventory
    assert "workspace" not in inventory


def test_overlap_map_ignores_headings_that_only_mention_projects(workspace):
    ws_md = workspace / "CLAUDE.md"
    ws_md.write_text("# Me\n\n## snake_case Convention (All Projects)\n")
    lines = overlap_report(tier_files(ws_md, "user", workspace), ws_md)
    assert "  project inventory: no tier" in lines
