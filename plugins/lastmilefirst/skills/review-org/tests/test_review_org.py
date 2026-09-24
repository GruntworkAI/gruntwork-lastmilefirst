"""Tests for the review-org project roll-up (scripts/review_org.py)."""

from __future__ import annotations

import json
from pathlib import Path

import overwatch
import pytest
import review_org

DAY = 86400
NOW = 1_800_000_000


def _write(path: Path, text: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture
def org(tmp_path: Path) -> Path:
    """A fake org: three project dirs, plus things that are not projects."""
    org_dir = tmp_path / "acme"
    _write(org_dir / "CLAUDE.md", "# Acme\n")
    _write(org_dir / ".claude" / "org.json", json.dumps({"name": "acme"}))
    _write(org_dir / "acme-api" / "CLAUDE.md", "# API\n\n## Archetype: Deployable\n")
    _write(org_dir / "acme-docs" / "CLAUDE.md", "# Docs\n\nNo archetype here.\n")
    (org_dir / "acme-scratch").mkdir()
    (org_dir / ".hidden").mkdir()
    return org_dir


@pytest.fixture
def state() -> dict:
    return {
        "version": 2,
        "global": {},
        "orgs": {"acme": {"last_review_claude": NOW - 3 * DAY}},
        "projects": {
            # review 10 days ago, commits since: past the 7-day threshold
            # organize 20 days ago, no commits since: not counted
            # secret scan 2 days ago: within threshold
            "acme/acme-api": {
                "last_review": NOW - 10 * DAY,
                "last_organize": NOW - 20 * DAY,
                "last_secret_scan": NOW - 2 * DAY,
            },
        },
    }


def _commits(mapping: dict):
    return lambda path: mapping.get(path.name, 0)


def test_project_dirs_skip_hidden_and_files(org: Path) -> None:
    names = [p.name for p in review_org.project_dirs(org)]
    assert names == ["acme-api", "acme-docs", "acme-scratch"]


def test_claude_md_and_archetype(org: Path, state: dict) -> None:
    rollup = review_org.build_rollup(org, state, now=NOW, commit_ts=_commits({}))
    by_name = {p["name"]: p for p in rollup["projects"]}
    assert by_name["acme-api"]["has_claude_md"] is True
    assert by_name["acme-api"]["archetype"] == "deployable"
    assert by_name["acme-docs"]["has_claude_md"] is True
    assert by_name["acme-docs"]["archetype"] is None
    assert by_name["acme-scratch"]["has_claude_md"] is False


def test_threshold_is_gated_on_commits_since(org: Path, state: dict) -> None:
    # Last commit 1 day ago: after the review and the organize runs.
    commits = _commits({"acme-api": NOW - 1 * DAY})
    api = {p["name"]: p for p in review_org.build_rollup(org, state, now=NOW, commit_ts=commits)["projects"]}["acme-api"]
    assert api["actions"]["review"]["past_threshold"] is True
    assert api["actions"]["review"]["days_since"] == 10
    assert api["actions"]["organize"]["past_threshold"] is True
    assert api["actions"]["secret_scan"]["past_threshold"] is False
    assert api["actions"]["review_claude"]["last"] == 0

    # Last commit 30 days ago: nothing changed since any action, so nothing counts.
    commits = _commits({"acme-api": NOW - 30 * DAY})
    api = {p["name"]: p for p in review_org.build_rollup(org, state, now=NOW, commit_ts=commits)["projects"]}["acme-api"]
    assert not any(a["past_threshold"] for a in api["actions"].values())


def test_thresholds_come_from_overwatch() -> None:
    thresholds = {field: thr for field, _label, thr in review_org.PROJECT_ACTIONS}
    assert thresholds == {
        "review": overwatch.REVIEW_THRESHOLD_DAYS,
        "organize": overwatch.ORGANIZE_THRESHOLD_DAYS,
        "secret_scan": overwatch.SECRET_SCAN_THRESHOLD_DAYS,
        "review_claude": overwatch.REVIEW_CLAUDE_THRESHOLD_DAYS,
    }


def test_org_record(org: Path, state: dict) -> None:
    rollup = review_org.build_rollup(org, state, now=NOW, commit_ts=_commits({}))
    assert rollup["org"] == "acme"
    assert rollup["org_record"]["review_claude"] == {"last": NOW - 3 * DAY, "days_since": 3}
    assert rollup["org_record"]["review_org"] == {"last": 0, "days_since": None}


def test_missing_state_file_reads_as_none_on_record(org: Path, tmp_path: Path) -> None:
    assert review_org.read_state(tmp_path / "nope.json") is None
    rollup = review_org.build_rollup(org, None, now=NOW, commit_ts=_commits({}))
    assert rollup["state_found"] is False
    assert all(
        a["last"] == 0 for p in rollup["projects"] for a in p["actions"].values()
    )
    text = review_org.format_text(rollup, tmp_path / "nope.json")
    assert "no readable file" in text


def test_text_reports_measurements_not_judgments(org: Path, state: dict, tmp_path: Path) -> None:
    commits = _commits({"acme-api": NOW - 1 * DAY})
    rollup = review_org.build_rollup(org, state, now=NOW, commit_ts=commits)
    text = review_org.format_text(rollup, tmp_path / "state.json")
    assert "2 of 3 project directories have a CLAUDE.md. Without one: acme-scratch" in text
    assert "1 of 2 CLAUDE.md files declare an archetype. Without one: acme-docs" in text
    assert "project review: 1 of 3 have one on record" in text
    assert "project review, 7 days: 1 of 3: acme-api (10 days)" in text
    assert "stale" not in text.lower()


def test_main_json_is_read_only(org: Path, state: dict, tmp_path: Path, capsys) -> None:
    state_file = tmp_path / "state.json"
    state_file.write_text(json.dumps(state), encoding="utf-8")
    before = state_file.read_bytes()
    lock = tmp_path / "overwatch.lock"

    assert review_org.main(["--org", str(org), "--json", "--state-file", str(state_file)]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["org"] == "acme"
    assert [p["name"] for p in out["projects"]] == ["acme-api", "acme-docs", "acme-scratch"]
    assert state_file.read_bytes() == before
    assert not lock.exists()


def test_main_rejects_missing_org(tmp_path: Path, capsys) -> None:
    assert review_org.main(["--org", str(tmp_path / "missing"), "--state-file", str(tmp_path / "s.json")]) == 2


def test_last_commit_ts_non_repo_is_zero(tmp_path: Path) -> None:
    assert review_org.last_commit_ts(tmp_path) == 0
