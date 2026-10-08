"""Pure todo parsing and explicit bounded-adapter compatibility options."""
from pathlib import Path

import pytest

import aggregator
from aggregator import TodoAggregator, extract_todo_title, parse_todo_content, parse_todo_frontmatter


@pytest.mark.parametrize(
    "content, expected",
    [
        ("Plain text", {}),
        ("---\nstatus: done\npriority: 'high'\n---\n# Title", {"status": "done", "priority": "high"}),
        ("---\n tags: [one, 'two', , \"three\"]\n---", {"tags": ["one", "two", "three"]}),
        ("---\nstatus: first\nstatus: last\n---", {"status": "last"}),
        ("---\nstatus: done", {}),
        ("---status: done---body", {"status": "done"}),
        ("---\nunknown: x:y\nignored\n---", {"unknown": "x:y"}),
    ],
)
def test_legacy_frontmatter_is_unchanged(content, expected):
    assert parse_todo_frontmatter(content) == expected
    assert TodoAggregator.__new__(TodoAggregator)._parse_frontmatter(content) == expected


@pytest.mark.parametrize(
    "content, expected",
    [
        ("No heading", "Fix This Task"),
        ("#Heading without space", "Heading without space"),
        ("   #### Heading ## ", "Heading ##"),
        ("######## Any level", "Any level"),
        ("#", ""),
        ("```md\n# Example first\n```\n# Actual", "Example first"),
        ("---\ntitle: Metadata\n---\n# Actual", "Actual"),
        ("---\n# In malformed frontmatter", "In malformed frontmatter"),
    ],
)
def test_legacy_title_is_unchanged(content, expected):
    assert extract_todo_title(content, "fix_this-task.md") == expected
    assert TodoAggregator.__new__(TodoAggregator)._extract_title(content, Path("fix_this-task.md")) == expected


def test_parse_todo_file_uses_shared_content_and_keeps_item_metadata(tmp_path, monkeypatch):
    path = tmp_path / "todo.md"
    path.write_text("""---
status: active
priority: high
blocks: [frontmatter-block]
blocked_by: [frontmatter-dependency]
tags: [first, second]
---
# Work
[BLOCKS:inline-block] [BLOCKED-BY:inline-dependency]
""")
    calls = []
    original = aggregator.parse_todo_content

    def parse(content, filename, **options):
        calls.append(filename)
        return original(content, filename, **options)

    monkeypatch.setattr(aggregator, "parse_todo_content", parse)
    item = TodoAggregator.__new__(TodoAggregator).parse_todo_file(path, "project")
    assert calls == [path]
    assert item.title == "Work"
    assert item.status == "active"
    assert item.priority == "high"
    assert item.blocks == ["frontmatter-block", "inline-block"]
    assert item.blocked_by == ["frontmatter-dependency", "inline-dependency"]
    assert item.tags == ["first", "second"]
    assert item.project == "project"
    assert item.age_days == 0


def strict_parse(content, filename="fix_this-task.md", **options):
    return parse_todo_content(content, filename, ignore_fenced=True,
                              strict_frontmatter=True, strict_headings=True, **options)


def test_strict_frontmatter_keys_remain_unindented_exact_scalars():
    content = "---\n status: wrong\nstatus : wrong\nstatus: 'done'\npriority: [high]\nignored: value\n---\n"
    parsed = strict_parse(content)
    assert parsed["frontmatter"] == {"status": "done", "priority": "[high]"}
    assert parsed["frontmatter_status"] == "parsed"


@pytest.mark.parametrize("newline", ["\n", "\r\n", "\r"])
def test_strict_frontmatter_handles_universal_newlines(newline):
    parsed = strict_parse(newline.join(["---", "status: done", "---", "# Real", "- [ ] Todo"]))
    assert parsed["frontmatter"] == {"status": "done"}
    assert parsed["title"] == "Real"
    assert parsed["open_checkboxes"] == 1


def test_strict_frontmatter_retains_unicode_line_separator_behavior():
    parsed = strict_parse("---\nstatus: done\u2028priority: high\n---\n# Task")
    assert parsed["frontmatter"] == {"status": "done", "priority": "high"}


@pytest.mark.parametrize(
    "content, status",
    [("---\nstatus: pending", "malformed"), ("---status: done---", "absent"),
     ("---", "absent"), ("---\n---", "parsed"), ("Plain text", "absent")],
)
def test_strict_frontmatter_reports_delimiter_state(content, status):
    assert strict_parse(content)["frontmatter_status"] == status


def test_strict_fences_hide_examples_and_preserve_real_title_and_counts():
    parsed = strict_parse("""---
status: active
---
````markdown
# Example
- [ ] Example
```
# Still example
- [x] Example
~~~
````
# Actual ##
- [ ] Open
* [x] Done
+ [X] Done
[BLOCKS:real] [BLOCKED-BY:actual]
~~~
[BLOCKS:example]
- [ ] Example
~~~
""")
    assert parsed["title"] == "Actual ##"
    assert parsed["open_checkboxes"] == 1
    assert parsed["done_checkboxes"] == 2
    assert parsed["inline_blocks"] == ["real"]
    assert parsed["inline_blocked_by"] == ["actual"]


def test_strict_heading_fallback_retains_filename_case_and_punctuation():
    assert strict_parse("#Not a heading")["title"] == "fix_this-task"


def test_frontmatter_title_preference_is_explicit():
    content = "---\ntitle: 'Metadata'\n---\n# Actual"
    assert strict_parse(content)["title"] == "Actual"
    assert strict_parse(content, prefer_frontmatter_title=True)["title"] == "Metadata"
    assert parse_todo_content(content, "todo.md")["title"] == "Actual"


def test_content_helpers_do_not_load_config_read_or_stat(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Content parsing must not read files or load configuration")

    monkeypatch.setattr(Path, "read_text", forbidden)
    monkeypatch.setattr(Path, "stat", forbidden)
    monkeypatch.setattr(TodoAggregator, "_load_config", forbidden)
    assert strict_parse("# Already read\n- [ ] Todo")["title"] == "Already read"
