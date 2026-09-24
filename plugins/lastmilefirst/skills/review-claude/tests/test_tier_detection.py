"""
Tier detection for review-claude (plan 2026-09-21-001, U1).

Tier used to be inferred from directory depth alone, and single-file mode
resolved symlinks first. A symlinked org CLAUDE.md (source kept in a versioned
repo) resolved into that repo and was classified as a project. These tests pin
the fix: classify the unresolved path, trust `.claude/org.json` before depth,
and let `--tier` override detection.

Everything is built under tmp_path; the real workspace is never touched.
"""

import sys

import pytest

import review_claude
from review_claude import classify_tier, determine_level, resolve_tier


def make_claude_md(directory, text="# CLAUDE.md\n"):
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "CLAUDE.md"
    path.write_text(text)
    return path


def mark_org(directory):
    (directory / ".claude").mkdir(parents=True, exist_ok=True)
    (directory / ".claude" / "org.json").write_text("{}")


@pytest.fixture
def workspace(tmp_path):
    ws = tmp_path / "Code"
    ws.mkdir()
    return ws


# --- org.json is checked before depth ----------------------------------------

@pytest.mark.parametrize("rel", ["acme", "nested/acme", "a/b/c/acme"])
def test_org_json_classifies_as_org_at_any_depth(workspace, rel):
    org_dir = workspace / rel
    claude_md = make_claude_md(org_dir)
    mark_org(org_dir)
    assert classify_tier(claude_md, workspace) == ("org", "found .claude/org.json")


def test_org_without_org_json_still_classifies_by_depth(workspace):
    claude_md = make_claude_md(workspace / "acme")
    assert classify_tier(claude_md, workspace) == ("org", "by position")


def test_depth_fallback_for_workspace_and_project(workspace):
    top = make_claude_md(workspace)
    project = make_claude_md(workspace / "acme" / "widget")
    assert classify_tier(top, workspace) == ("user", "by position")
    assert classify_tier(project, workspace) == ("project", "by position")
    assert determine_level(project, workspace) == "project"


# --- symlinked CLAUDE.md ------------------------------------------------------

def test_symlinked_org_file_classifies_as_org(workspace):
    """The observed failure: source lives deep in a repo, symlinked into the org."""
    org_dir = workspace / "acme"
    mark_org(org_dir)
    source = make_claude_md(org_dir / "acme-wisdom" / "claude" / "org-file")
    link = org_dir / "CLAUDE.md"
    link.symlink_to(source)

    assert classify_tier(link, workspace)[0] == "org"
    # Resolving the link is exactly what went wrong before.
    assert classify_tier(link.resolve(), workspace)[0] == "project"


# --- --tier override ----------------------------------------------------------

@pytest.mark.parametrize(
    "override,level",
    [("workspace", "user"), ("user", "user"), ("org", "org"), ("project", "project")],
)
def test_tier_override_wins_over_detection(workspace, override, level):
    org_dir = workspace / "acme"
    mark_org(org_dir)
    claude_md = make_claude_md(org_dir)
    assert resolve_tier(claude_md, workspace, override) == (level, "set by --tier")


def test_no_override_falls_through_to_detection(workspace):
    claude_md = make_claude_md(workspace / "acme")
    assert resolve_tier(claude_md, workspace, None) == ("org", "by position")


# --- end to end through main() ------------------------------------------------

def run_main(monkeypatch, capsys, workspace, argv):
    monkeypatch.setattr(review_claude, "load_config", lambda: {"workspace": str(workspace), "orgs": []})
    monkeypatch.setattr(sys, "argv", ["review_claude.py", *argv])
    review_claude.main()
    return capsys.readouterr().out


def test_main_classifies_symlinked_org_file_as_org(monkeypatch, capsys, workspace):
    org_dir = workspace / "acme"
    mark_org(org_dir)
    source = make_claude_md(org_dir / "acme-wisdom" / "org-file")
    (org_dir / "CLAUDE.md").symlink_to(source)

    out = run_main(monkeypatch, capsys, workspace, ["--file", str(org_dir / "CLAUDE.md")])
    assert "Tier: org (found .claude/org.json)" in out
    assert "archetype" not in out.lower()


def test_main_tier_flag_overrides(monkeypatch, capsys, workspace):
    claude_md = make_claude_md(workspace / "acme" / "widget")
    out = run_main(monkeypatch, capsys, workspace, ["--file", str(claude_md), "--tier", "org"])
    assert "Tier: org (set by --tier)" in out
