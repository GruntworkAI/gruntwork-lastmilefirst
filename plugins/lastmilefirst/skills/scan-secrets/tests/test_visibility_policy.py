"""The visibility policy: three rule kinds, one function (plan 2026-10-09-001, U1).

Every finding is classified by its tags into one of four kinds (ordinary
secret, organization name, generic PII, person) and the repo's visibility
decides whether it is kept and whether it blocks. gitleaks, the merged config,
archive scanning, and the `gh` visibility call are replaced with stand-ins, the
same way test_public_only.py does it, so no real repo or rules file is touched.
All names and addresses below are invented.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import format_loader
import scanner

ORDINARY = {
    "RuleID": "generic-api-key",
    "File": "config.py",
    "StartLine": 9,
    "Severity": "HIGH",
    "Tags": ["org"],
}
ORGANIZATION = {
    "RuleID": "lmf-private-names",
    "File": "README.md",
    "StartLine": 3,
    "Severity": "MEDIUM",
    "Tags": ["org", "public-only", "private-name"],
}
PII = {
    "RuleID": "lmf-pii-personal-email",
    "File": "notes.md",
    "StartLine": 5,
    "Severity": "LOW",
    "Tags": ["pii"],
}
PERSON = {
    "RuleID": "lmf-private-people",
    "File": "notes.md",
    "StartLine": 7,
    "Severity": "MEDIUM",
    "Tags": ["org", "private-name"],
}
KINDS = {"ordinary": ORDINARY, "organization": ORGANIZATION, "pii": PII, "person": PERSON}

SUPPRESSED = {
    "PRIVATE": "1 finding(s) from public-only rules suppressed in a private repo",
    "INTERNAL": "1 finding(s) from public-only rules suppressed in an internal repo",
}
UNKNOWN_NOTE = ("public-only rules applied because visibility could not be determined; "
                "push the repo or run `gh auth login`")

# (kind, visibility) -> (kept, blocking); blocking is None when not kept.
TABLE = {
    ("ordinary", "PUBLIC"): (True, True),
    ("ordinary", "PRIVATE"): (True, True),
    ("ordinary", "INTERNAL"): (True, True),
    ("ordinary", None): (True, True),
    ("organization", "PUBLIC"): (True, True),
    ("organization", "PRIVATE"): (False, None),
    ("organization", "INTERNAL"): (False, None),
    ("organization", None): (True, True),
    ("pii", "PUBLIC"): (True, True),
    ("pii", "PRIVATE"): (True, False),
    ("pii", "INTERNAL"): (True, False),
    ("pii", None): (True, True),
    ("person", "PUBLIC"): (True, True),
    ("person", "PRIVATE"): (True, True),
    ("person", "INTERNAL"): (True, True),
    ("person", None): (True, True),
}


# --- the twelve cells (three visibility classes x four kinds) -----------------

@pytest.mark.parametrize("kind,visibility", sorted(TABLE, key=str))
def test_policy_table(kind, visibility):
    kept, lines = scanner.apply_visibility_policy([dict(KINDS[kind])], visibility)
    want_kept, want_blocking = TABLE[(kind, visibility)]

    if not want_kept:
        assert kept == []
        assert lines == [SUPPRESSED[visibility]]
        return
    assert [f["RuleID"] for f in kept] == [KINDS[kind]["RuleID"]]
    assert kept[0]["Blocking"] is want_blocking
    if kind == "organization" and visibility is None:
        assert lines == [UNKNOWN_NOTE]
    else:
        assert lines == []


def test_unrecognised_visibility_is_treated_as_unknown():
    kept, _ = scanner.apply_visibility_policy([dict(PII)], "SOMETHING")
    assert kept[0]["Blocking"] is True


def test_tag_match_ignores_case_and_accepts_a_bare_string():
    finding = dict(PII, Tags="PII")
    kept, _ = scanner.apply_visibility_policy([finding], "PRIVATE")
    assert kept[0]["Blocking"] is False


def test_finding_without_tags_is_ordinary():
    bare = {"RuleID": "x", "File": "f", "StartLine": 1, "Severity": "LOW"}
    kept, _ = scanner.apply_visibility_policy([bare], "PRIVATE")
    assert kept[0]["Blocking"] is True


# --- the overlap rule ---------------------------------------------------------

@pytest.mark.parametrize("visibility", ["PUBLIC", "PRIVATE", "INTERNAL", None])
def test_pii_and_person_on_the_same_line_report_once_as_the_person(visibility):
    pii = dict(PII, StartLine=12)
    person = dict(PERSON, StartLine=12)
    kept, _ = scanner.apply_visibility_policy([pii, person], visibility)
    assert [f["RuleID"] for f in kept] == ["lmf-private-people"]
    assert kept[0]["Blocking"] is True


def test_overlap_is_keyed_on_file_and_line():
    pii = dict(PII, StartLine=12)
    other_line = dict(PERSON, StartLine=13)
    other_file = dict(PERSON, File="other.md", StartLine=12)
    kept, _ = scanner.apply_visibility_policy([pii, other_line, other_file], "PRIVATE")
    assert sorted(f["RuleID"] for f in kept) == [
        "lmf-pii-personal-email", "lmf-private-people", "lmf-private-people"]


def test_an_organization_finding_does_not_absorb_a_pii_finding():
    pii = dict(PII, StartLine=12)
    org = dict(ORGANIZATION, File=PII["File"], StartLine=12)
    kept, _ = scanner.apply_visibility_policy([pii, org], "PRIVATE")
    assert [f["RuleID"] for f in kept] == ["lmf-pii-personal-email"]


# --- the alias ----------------------------------------------------------------

def test_apply_public_only_is_an_alias_without_the_blocking_flag():
    rows = [dict(ORGANIZATION), dict(ORDINARY), dict(PII)]
    kept, lines = scanner.apply_public_only(rows, "PRIVATE")
    assert kept == [ORDINARY, PII]
    assert lines == [SUPPRESSED["PRIVATE"]]


def test_policy_does_not_mutate_its_input():
    rows = [dict(PII)]
    scanner.apply_visibility_policy(rows, "PRIVATE")
    assert "Blocking" not in rows[0]


# --- the report ---------------------------------------------------------------

def test_non_blocking_findings_show_warning_in_the_severity_column():
    kept, _ = scanner.apply_visibility_policy([dict(ORDINARY), dict(PII)], "PRIVATE")
    text = scanner._format_findings(kept)
    rows = {line.split()[1]: line.split()[0] for line in text.splitlines()
            if line.split() and line.split()[-1].isdigit()}
    assert rows == {"lmf-pii-personal-email": "WARNING", "generic-api-key": "HIGH"}
    assert "1 blocking finding(s)" in text
    assert "1 warning(s)" in text


def test_summary_without_warnings_counts_blocking_findings_only():
    kept, _ = scanner.apply_visibility_policy([dict(ORDINARY)], "PRIVATE")
    text = scanner._format_findings(kept)
    assert "1 blocking finding(s)" in text
    assert "warning(s)" not in text


def test_summary_with_only_warnings():
    kept, _ = scanner.apply_visibility_policy([dict(PII)], "PRIVATE")
    text = scanner._format_findings(kept)
    assert "0 blocking finding(s)" not in text
    assert "1 warning(s)" in text


# --- the scan modes -------------------------------------------------------------

@pytest.fixture
def gitleaks_reports(tmp_path, monkeypatch):
    """gitleaks that writes whatever rows the test sets to the report path."""
    config = tmp_path / "merged.toml"
    rows: list = []

    def write_config(*_args, **_kwargs):
        config.write_text("")
        return config

    def run(args, config_path=None, cwd=None):
        report = Path(args[args.index("--report-path") + 1])
        report.write_text(json.dumps(rows))
        return (1 if rows else 0), "", ""

    monkeypatch.setattr(scanner, "_check_gitleaks", lambda: None)
    monkeypatch.setattr(scanner, "write_merged_config", write_config)
    monkeypatch.setattr(scanner, "consume_sync_note", lambda: None)
    monkeypatch.setattr(scanner, "scan_archives", lambda *a, **k: [])
    monkeypatch.setattr(scanner, "_run_gitleaks", run)
    return rows


def set_visibility(monkeypatch, value):
    monkeypatch.setattr(scanner, "check_repo_visibility", lambda _repo=None: value)


@pytest.mark.parametrize("scan", ["scan_repo", "scan_staged"])
def test_warnings_only_scan_exits_zero_and_prints_the_warnings(
        gitleaks_reports, monkeypatch, tmp_path, scan):
    gitleaks_reports.append(dict(PII))
    set_visibility(monkeypatch, "PRIVATE")
    code, report = getattr(scanner, scan)(tmp_path)
    assert code == 0
    assert "lmf-pii-personal-email" in report
    assert "WARNING" in report
    assert "1 warning(s)" in report


def test_warnings_only_staged_scan_does_not_claim_a_clean_commit(gitleaks_reports, monkeypatch, tmp_path):
    gitleaks_reports.append(dict(PII))
    set_visibility(monkeypatch, "PRIVATE")
    _, report = scanner.scan_staged(tmp_path)
    assert "No secrets detected" not in report


@pytest.mark.parametrize("scan", ["scan_repo", "scan_staged"])
def test_the_same_pii_finding_blocks_in_a_public_repo(gitleaks_reports, monkeypatch, tmp_path, scan):
    gitleaks_reports.append(dict(PII))
    set_visibility(monkeypatch, "PUBLIC")
    code, report = getattr(scanner, scan)(tmp_path)
    assert code == 1
    assert "1 blocking finding(s)" in report


@pytest.mark.parametrize("scan", ["scan_repo", "scan_staged"])
def test_a_person_finding_blocks_in_a_private_repo(gitleaks_reports, monkeypatch, tmp_path, scan):
    gitleaks_reports.extend([dict(PII), dict(PERSON)])
    set_visibility(monkeypatch, "PRIVATE")
    code, report = getattr(scanner, scan)(tmp_path)
    assert code == 1
    assert "lmf-private-people" in report
    assert "1 blocking finding(s)" in report
    assert "1 warning(s)" in report


def test_workspace_scan_shows_warnings_without_failing(gitleaks_reports, monkeypatch, tmp_path):
    import github_protections
    import overwatch

    gitleaks_reports.append(dict(PII))
    set_visibility(monkeypatch, "PRIVATE")
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    monkeypatch.setattr(overwatch, "get_state_dir", lambda: state_dir)
    monkeypatch.setattr(github_protections, "sweep_accounts", lambda _ws: [])
    ws = tmp_path / "Code"
    (ws / "acme" / "private-repo" / ".git").mkdir(parents=True)

    code, report = scanner.scan_workspace(ws)

    assert code == 0
    assert "acme/private-repo: clean (1 warning(s))" in report
    assert "lmf-pii-personal-email" in report
    assert "0 with findings" in report


def test_workspace_scan_fails_on_a_person_finding_in_a_private_repo(gitleaks_reports, monkeypatch, tmp_path):
    import github_protections
    import overwatch

    gitleaks_reports.append(dict(PERSON))
    set_visibility(monkeypatch, "PRIVATE")
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    monkeypatch.setattr(overwatch, "get_state_dir", lambda: state_dir)
    monkeypatch.setattr(github_protections, "sweep_accounts", lambda _ws: [])
    ws = tmp_path / "Code"
    (ws / "acme" / "private-repo" / ".git").mkdir(parents=True)

    code, report = scanner.scan_workspace(ws)

    assert code == 1
    assert "acme/private-repo: FINDINGS DETECTED" in report


# --- the org template ---------------------------------------------------------

def test_org_template_documents_both_org_tier_rules():
    text = format_loader.ORG_TEMPLATE
    assert "lmf-private-names" in text
    assert "lmf-private-people" in text
    assert '"public-only"' in text
    assert '"private-name"' in text


def test_org_template_still_parses_as_toml_with_no_active_rules():
    import tomllib

    data = tomllib.loads(format_loader.ORG_TEMPLATE)
    assert data.get("rules", []) == []


def test_severity_tag_sets_the_reported_level():
    """A `severity-low` tag on a rule reports LOW in a private repo and bumps to MEDIUM in a public one."""
    import json as _json

    row = {"RuleID": "lmf-pii-phone", "File": "notes.md", "StartLine": 2, "Tags": ["pii", "lmf", "severity-low"]}
    private = scanner._parse_findings(_json.dumps([dict(row)]), is_public=False)
    public = scanner._parse_findings(_json.dumps([dict(row)]), is_public=True)
    assert private[0]["Severity"] == "LOW"
    assert public[0]["Severity"] == "MEDIUM" and public[0].get("_bumped") is True
    untagged = scanner._parse_findings(_json.dumps([{"RuleID": "x", "File": "f", "StartLine": 1}]), is_public=False)
    assert untagged[0]["Severity"] == "MEDIUM"


def test_rows_are_ordered_by_severity_rank_not_by_name():
    rows = [dict(ORDINARY, Severity=sev, RuleID=f"rule-{sev.lower()}", Fingerprint=sev)
            for sev in ("LOW", "CRITICAL", "MEDIUM")]
    text = scanner._format_findings(rows)
    order = [line.split()[0] for line in text.splitlines()
             if line.split() and line.split()[-1].isdigit()]
    assert order == ["CRITICAL", "MEDIUM", "LOW"]
