"""Todo discovery through client directories (plan 2026-09-28-001, U3).

The aggregator's config loading is replaced with a no-op and it is given one
org by hand, so neither the real workspace config nor ~/Code is read. The cache
is never used.
"""
from __future__ import annotations

from pathlib import Path

import pytest

import aggregator
from aggregator import OrgConfig, TodoAggregator


def todo(project: Path, name: str, title: str) -> None:
    todos = project / ".claude" / "work" / "todos"
    todos.mkdir(parents=True, exist_ok=True)
    (todos / f"{name}.md").write_text(f"---\nstatus: pending\n---\n# {title}\n")


@pytest.fixture
def org(tmp_path, monkeypatch) -> OrgConfig:
    monkeypatch.setattr(TodoAggregator, "_load_config", lambda self: None)
    monkeypatch.setattr(aggregator, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(aggregator, "CACHE_FILE", tmp_path / "cache" / "todos.json")
    org_dir = tmp_path / "Code" / "acme"
    client = org_dir / "northwind"
    client.mkdir(parents=True)
    (client / ".claude-workspace").write_text("type: client\n")
    todo(client / "web", "001", "Ship the landing page")
    (client / "docs").mkdir()  # no todos
    todo(org_dir / "practice", "002", "Write the proposal")
    return OrgConfig(name="acme", path=org_dir)


def make_aggregator(org: OrgConfig) -> TodoAggregator:
    agg = TodoAggregator()
    agg._orgs = [org]
    return agg


def test_discovery_descends_through_the_client_directory(org):
    found = make_aggregator(org).discover_projects(org)
    assert found == [org.path / "northwind" / "web", org.path / "practice"]


def test_nested_todos_aggregate_under_the_client_label(org):
    result = make_aggregator(org).aggregate_todos(org=org, use_cache=False)
    by_project = {t.project: t.title for t in result["acme"]}
    assert by_project == {
        "northwind/web": "Ship the landing page",
        "practice": "Write the proposal",
    }


def test_client_directory_with_todos_of_its_own_is_not_a_project(org):
    """The container is not a project, so todos placed directly in it are not read."""
    todo(org.path / "northwind", "003", "Misplaced")
    result = make_aggregator(org).aggregate_todos(org=org, use_cache=False)
    assert "northwind" not in {t.project for t in result["acme"]}
