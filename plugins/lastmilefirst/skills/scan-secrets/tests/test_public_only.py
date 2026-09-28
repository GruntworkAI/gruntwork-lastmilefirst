"""The `public-only` rule tag.

A rule tagged `public-only` names something that is fine inside a private
repo but must never reach a public one. Its findings are dropped when the repo
is known to be private or internal, kept when it is public, and kept with an
explanatory line when visibility cannot be determined. gitleaks, the merged
config, archive scanning, and the `gh` visibility call are replaced with
stand-ins, so no real repo or rules file is touched.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import scanner

PUBLIC_ONLY = {
    "RuleID": "org-client-name",
    "Description": "Client name",
    "File": "README.md",
    "StartLine": 3,
    "Severity": "MEDIUM",
    "Tags": ["org", "public-only"],
}
ORDINARY = {
    "RuleID": "generic-api-key",
    "Description": "Generic API key",
    "File": "config.py",
    "StartLine": 9,
    "Severity": "HIGH",
    "Tags": ["org"],
}
UNKNOWN_NOTE = ("public-only rules applied because visibility could not be determined; "
                "push the repo or run `gh auth login`")


def rows():
    return [dict(PUBLIC_ONLY), dict(ORDINARY)]


# --- the filter ---------------------------------------------------------------

def test_public_only_finding_is_dropped_in_a_private_repo():
    kept, lines = scanner.apply_public_only(rows(), "PRIVATE")
    assert [f["RuleID"] for f in kept] == ["generic-api-key"]
    assert lines == ["1 finding(s) from public-only rules suppressed in a private repo"]


def test_public_only_finding_is_dropped_in_an_internal_repo():
    kept, lines = scanner.apply_public_only(rows(), "INTERNAL")
    assert [f["RuleID"] for f in kept] == ["generic-api-key"]
    assert lines == ["1 finding(s) from public-only rules suppressed in an internal repo"]


def test_public_only_finding_is_kept_in_a_public_repo():
    kept, lines = scanner.apply_public_only(rows(), "PUBLIC")
    assert len(kept) == 2
    assert lines == []


def test_public_only_finding_is_kept_with_a_note_when_visibility_is_unknown():
    kept, lines = scanner.apply_public_only(rows(), None)
    assert len(kept) == 2
    assert lines == [UNKNOWN_NOTE]


@pytest.mark.parametrize("visibility", ["PUBLIC", "PRIVATE", "INTERNAL", None])
def test_untagged_finding_is_never_dropped(visibility):
    kept, lines = scanner.apply_public_only([dict(ORDINARY)], visibility)
    assert kept == [ORDINARY]
    assert lines == []


def test_findings_without_tags_are_untouched():
    bare = {"RuleID": "x", "File": "f", "StartLine": 1, "Severity": "LOW"}
    kept, lines = scanner.apply_public_only([bare], "PRIVATE")
    assert kept == [bare] and lines == []


def test_tag_match_ignores_case():
    finding = dict(PUBLIC_ONLY, Tags=["Public-Only"])
    kept, _ = scanner.apply_public_only([finding], "PRIVATE")
    assert kept == []


# --- wired into the scan modes ----------------------------------------------------

@pytest.fixture
def fake_gitleaks(tmp_path, monkeypatch):
    """gitleaks that writes the two findings to the requested report path."""
    config = tmp_path / "merged.toml"

    def write_config(*_args, **_kwargs):
        config.write_text("")
        return config

    def run(args, config_path=None, cwd=None):
        report = Path(args[args.index("--report-path") + 1])
        report.write_text(json.dumps(rows()))
        return 1, "", ""

    monkeypatch.setattr(scanner, "_check_gitleaks", lambda: None)
    monkeypatch.setattr(scanner, "write_merged_config", write_config)
    monkeypatch.setattr(scanner, "consume_sync_note", lambda: None)
    monkeypatch.setattr(scanner, "scan_archives", lambda *a, **k: [])
    monkeypatch.setattr(scanner, "_run_gitleaks", run)


def set_visibility(monkeypatch, value):
    monkeypatch.setattr(scanner, "check_repo_visibility", lambda _repo=None: value)


@pytest.mark.parametrize("scan", ["scan_repo", "scan_staged"])
def test_scan_modes_drop_public_only_findings_in_a_private_repo(fake_gitleaks, monkeypatch, tmp_path, scan):
    set_visibility(monkeypatch, "PRIVATE")
    code, report = getattr(scanner, scan)(tmp_path)
    assert code == 1  # the ordinary finding still fails the scan
    assert "org-client-name" not in report
    assert "generic-api-key" in report
    assert "1 finding(s) from public-only rules suppressed in a private repo" in report


@pytest.mark.parametrize("scan", ["scan_repo", "scan_staged"])
def test_scan_modes_keep_public_only_findings_in_a_public_repo(fake_gitleaks, monkeypatch, tmp_path, scan):
    set_visibility(monkeypatch, "PUBLIC")
    _, report = getattr(scanner, scan)(tmp_path)
    assert "org-client-name" in report
    assert "suppressed" not in report


@pytest.mark.parametrize("scan", ["scan_repo", "scan_staged"])
def test_scan_modes_keep_public_only_findings_when_visibility_is_unknown(fake_gitleaks, monkeypatch, tmp_path, scan):
    set_visibility(monkeypatch, None)
    _, report = getattr(scanner, scan)(tmp_path)
    assert "org-client-name" in report
    assert UNKNOWN_NOTE in report


def test_private_repo_with_only_public_only_findings_passes(fake_gitleaks, monkeypatch, tmp_path):
    """A commit to a private repo naming a client is allowed."""
    def run(args, config_path=None, cwd=None):
        Path(args[args.index("--report-path") + 1]).write_text(json.dumps([dict(PUBLIC_ONLY)]))
        return 1, "", ""

    monkeypatch.setattr(scanner, "_run_gitleaks", run)
    set_visibility(monkeypatch, "PRIVATE")
    code, report = scanner.scan_staged(tmp_path)
    assert code == 0
    assert "No secrets detected in staged changes." in report


def test_visibility_empty_output_is_unknown(monkeypatch):
    class Done:
        returncode = 0
        stdout = "\n"

    monkeypatch.setattr(scanner.subprocess, "run", lambda *a, **k: Done())
    assert scanner.check_repo_visibility() is None


def test_all_mode_filters_per_repo_and_shows_the_suppression(fake_gitleaks, monkeypatch, tmp_path):
    import github_protections
    import overwatch

    def run(args, config_path=None, cwd=None):
        Path(args[args.index("--report-path") + 1]).write_text(json.dumps([dict(PUBLIC_ONLY)]))
        return 1, "", ""

    monkeypatch.setattr(scanner, "_run_gitleaks", run)
    visibility = {"private-repo": "PRIVATE", "public-repo": "PUBLIC"}
    monkeypatch.setattr(scanner, "check_repo_visibility", lambda repo=None: visibility[repo.name])
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    monkeypatch.setattr(overwatch, "get_state_dir", lambda: state_dir)
    monkeypatch.setattr(github_protections, "sweep_accounts", lambda _ws: [])
    ws = tmp_path / "Code"
    for name in visibility:
        (ws / "acme" / name / ".git").mkdir(parents=True)

    code, report = scanner.scan_workspace(ws)

    assert code == 1
    assert ("acme/private-repo: clean (1 finding(s) from public-only rules "
            "suppressed in a private repo)") in report
    assert "acme/public-repo: FINDINGS DETECTED" in report
