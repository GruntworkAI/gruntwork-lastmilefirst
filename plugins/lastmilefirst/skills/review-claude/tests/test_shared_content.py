"""Shared overlap and fence helpers preserve canonical report behavior."""
from pathlib import Path

import review_claude
from review_claude import extract_section, overlap_report, topic_overlaps


def test_topic_overlaps_preserves_prefix_rule_first_heading_and_order():
    result = topic_overlaps(iter([
        ("workspace", Path("workspace/CLAUDE.md"), ["development tools", "tools extra", "projects"]),
        ("org", "org/AGENTS.md", ["approved tools", "snake_case convention (all projects)"]),
    ]))
    assert result == [
        {"topic": "tools", "carriers": [
            {"tier": "workspace", "path": Path("workspace/CLAUDE.md"), "heading": "development tools"},
            {"tier": "org", "path": "org/AGENTS.md", "heading": "approved tools"},
        ]},
        {"topic": "project inventory", "carriers": [
            {"tier": "workspace", "path": Path("workspace/CLAUDE.md"), "heading": "projects"},
        ]},
    ]


def test_topic_overlaps_includes_empty_topics():
    assert topic_overlaps([]) == [{"topic": name, "carriers": []}
                                  for name, _prefixes in review_claude.OVERLAP_TOPICS]


def test_overlap_report_calls_pure_helper_and_keeps_presentation(tmp_path, monkeypatch):
    path = tmp_path / "CLAUDE.md"
    path.write_text("## Tools\n## Projects")
    calls = []
    original = review_claude.topic_overlaps

    def inspect(entries):
        calls.append(entries)
        return original(entries)

    monkeypatch.setattr(review_claude, "topic_overlaps", inspect)
    assert overlap_report([("project", path)], path) == [
        "Overlapping topics (tiers with a section on each; content not compared):",
        '  tools: project "tools" (this file)',
        '  project inventory: project "projects" (this file)',
    ]
    assert calls == [[("project", path, ["tools", "projects"])]]


def test_extract_section_uses_fence_rules_without_altering_body():
    content = "## Tools\nbody\n````md\n## Example\n```\n## Legacy end\n````\n## Actual end\nafter"
    assert extract_section(content, "tools") == ("Tools", "body\n````md\n## Example\n```")
    assert extract_section(content, "tools", strict_fences=True) == (
        "Tools", "body\n````md\n## Example\n```\n## Legacy end\n````")
