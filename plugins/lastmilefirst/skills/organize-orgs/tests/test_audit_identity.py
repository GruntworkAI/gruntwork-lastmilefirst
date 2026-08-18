"""Tests for the workspace-wide identity contract audit.

The audit's job is the half the pre-commit hook structurally cannot do: find
orgs that are unconfigured and repos that are *already* wrong. Its other job is
staying cheap enough for session start, which is why `cheap_findings` is tested
separately from the full walk.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

import audit_identity
from audit_identity import ERROR, INFO, WARNING


CONTRACT = {
    "github_account": "outsideshot",
    "git_user_name": "outsideshot",
    "git_email": "outsideshot@gmail.com",
    "owns_remotes": ["outsideshot"],
    "enforcement": "block",
}

STUDIO = {
    "github_account": "GruntworkAI",
    "git_user_name": "GruntworkAI",
    "git_email": "admin@gruntwork.ai",
    "owns_remotes": ["GruntworkAI"],
    "enforcement": "block",
}


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    root = tmp_path / "Code"
    root.mkdir()
    return root


def write_org(org_dir: Path, name: str, identity: dict | None,
              claude_md: str | None = None) -> Path:
    (org_dir / ".claude").mkdir(parents=True, exist_ok=True)
    config: dict = {"name": name}
    if identity is not None:
        config["identity"] = identity
    (org_dir / ".claude" / "org.json").write_text(json.dumps(config), encoding="utf-8")
    if claude_md is not None:
        (org_dir / "CLAUDE.md").write_text(claude_md, encoding="utf-8")
    return org_dir


def make_repo(path: Path, name: str = "unset", email: str = "unset@example.com",
              remotes: dict[str, str] | None = None) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", name], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", email], cwd=path, check=True)
    for remote_name, url in (remotes or {}).items():
        subprocess.run(["git", "remote", "add", remote_name, url], cwd=path, check=True)
    return path


def severities(findings, severity):
    return [f for f in findings if f.severity == severity]


# --------------------------------------------------------------------------
# check 1 — presence and completeness
# --------------------------------------------------------------------------

def test_complete_contract_is_clean(workspace):
    write_org(workspace / "outsideshot", "outsideshot", CONTRACT,
              claude_md="Commits as outsideshot / outsideshot@gmail.com")
    assert audit_identity.cheap_findings(workspace) == []


def test_org_with_repos_but_no_contract_is_an_error(workspace):
    org = workspace / "newthing"
    make_repo(org / "site")
    findings = audit_identity.cheap_findings(workspace)
    assert len(severities(findings, ERROR)) == 1
    assert "no identity contract" in findings[0].message


def test_empty_org_dir_is_not_yet_a_problem(workspace):
    """A directory with no repos cannot receive a commit, so it is not an alert.

    Session-start noise is the failure mode being avoided: alerting about a
    directory nobody can commit in trains the user to ignore the alert.
    """
    (workspace / "placeholder").mkdir()
    assert audit_identity.cheap_findings(workspace) == []


def test_org_json_without_identity_is_an_error(workspace):
    write_org(workspace / "someorg", "someorg", identity=None)
    findings = audit_identity.cheap_findings(workspace)
    assert severities(findings, ERROR)
    assert "no `identity` block" in findings[0].message


def test_missing_required_field_is_an_error(workspace):
    partial = {k: v for k, v in CONTRACT.items() if k != "git_email"}
    write_org(workspace / "someorg", "someorg", partial)
    findings = audit_identity.cheap_findings(workspace)
    assert severities(findings, ERROR)
    assert "git_email" in findings[0].message


# --------------------------------------------------------------------------
# check 2 — well-formedness
# --------------------------------------------------------------------------

@pytest.mark.parametrize("account", ["not valid", "-leading", "trailing-", "a" * 40])
def test_malformed_account_is_an_error(workspace, account):
    write_org(workspace / "org", "org", {**CONTRACT, "github_account": account})
    findings = audit_identity.cheap_findings(workspace)
    assert any("not a valid GitHub username" in f.message for f in findings)


@pytest.mark.parametrize("account", ["outsideshot", "GruntworkAI", "a", "a-b-c1"])
def test_valid_accounts_pass(workspace, account):
    write_org(workspace / "org", "org", {**CONTRACT, "github_account": account})
    findings = audit_identity.cheap_findings(workspace)
    assert not any("not a valid GitHub username" in f.message for f in findings)


def test_malformed_email_is_an_error(workspace):
    write_org(workspace / "org", "org", {**CONTRACT, "git_email": "not-an-email"})
    findings = audit_identity.cheap_findings(workspace)
    assert any("not a valid address" in f.message for f in findings)


def test_owner_claimed_by_two_accounts_is_an_error(workspace):
    """Ambiguous claims break the cross-context check — it cannot pick a winner."""
    write_org(workspace / "a", "a", {**CONTRACT, "owns_remotes": ["shared"]})
    write_org(workspace / "b", "b", {**STUDIO, "owns_remotes": ["shared"]})
    findings = audit_identity.cheap_findings(workspace)
    assert any("claimed by more than one account" in f.message for f in findings)


def test_two_orgs_one_account_is_not_a_conflict(workspace):
    """gruntwork/ and lastmilefirst.ai/ both push to GruntworkAI. Legitimate."""
    write_org(workspace / "gruntwork", "gruntwork", STUDIO,
              claude_md="GruntworkAI admin@gruntwork.ai")
    write_org(workspace / "lastmilefirst.ai", "lastmilefirst.ai", STUDIO,
              claude_md="GruntworkAI admin@gruntwork.ai")
    findings = audit_identity.cheap_findings(workspace)
    assert not any("more than one account" in f.message for f in findings)


def test_no_owns_remotes_is_informational_only(workspace):
    write_org(workspace / "org", "org", {**CONTRACT, "owns_remotes": []},
              claude_md="outsideshot outsideshot@gmail.com")
    findings = audit_identity.cheap_findings(workspace)
    assert not severities(findings, ERROR)
    assert severities(findings, INFO)


# --------------------------------------------------------------------------
# check 5 — prose mirror agreement
# --------------------------------------------------------------------------

def test_claude_md_missing_the_account_warns(workspace):
    write_org(workspace / "org", "org", CONTRACT,
              claude_md="This org has some prose but no identity details.")
    findings = audit_identity.cheap_findings(workspace)
    warnings = severities(findings, WARNING)
    assert warnings and "may have drifted" in warnings[0].message


def test_absent_claude_md_is_not_a_drift_finding(workspace):
    """Missing CLAUDE.md is a different skill's alert, not this one's."""
    write_org(workspace / "org", "org", CONTRACT)
    findings = audit_identity.cheap_findings(workspace)
    assert not severities(findings, WARNING)


# --------------------------------------------------------------------------
# workspace type markers
# --------------------------------------------------------------------------

@pytest.mark.parametrize("marker_type", ["external", "scratch"])
def test_marked_dirs_are_exempt(workspace, marker_type):
    """`every/` and `drafts/` must not generate a session-start alert forever."""
    org = workspace / "third-party"
    make_repo(org / "cloned")
    (org / ".claude-workspace").write_text(f"type: {marker_type}\n", encoding="utf-8")
    assert audit_identity.cheap_findings(workspace) == []


def test_studio_marker_is_still_governed(workspace):
    org = workspace / "mine"
    make_repo(org / "proj")
    (org / ".claude-workspace").write_text("type: studio\n", encoding="utf-8")
    assert severities(audit_identity.cheap_findings(workspace), ERROR)


def test_malformed_marker_does_not_exempt(workspace):
    """Failing open on a broken marker would let a typo disable enforcement."""
    org = workspace / "mine"
    make_repo(org / "proj")
    (org / ".claude-workspace").write_text("this is not: valid: yaml\n:", encoding="utf-8")
    assert severities(audit_identity.cheap_findings(workspace), ERROR)


# --------------------------------------------------------------------------
# check 4 — drift
# --------------------------------------------------------------------------

def test_drift_detects_wrong_email_in_existing_repo(workspace):
    write_org(workspace / "outsideshot", "outsideshot", CONTRACT)
    make_repo(workspace / "outsideshot" / "site",
              name="outsideshot", email="admin@gruntwork.ai")
    findings = audit_identity.drift_findings(workspace)
    assert any("commits as admin@gruntwork.ai" in f.message for f in findings)
    assert any("git -C" in (f.remedy or "") for f in findings)


def test_drift_is_clean_when_repos_comply(workspace):
    write_org(workspace / "outsideshot", "outsideshot", CONTRACT)
    make_repo(workspace / "outsideshot" / "site",
              name="outsideshot", email="outsideshot@gmail.com",
              remotes={"upstream": "git@github.com:andyfish3/site.git"})
    assert audit_identity.drift_findings(workspace) == []


def test_drift_flags_cross_context_remote(workspace):
    write_org(workspace / "outsideshot", "outsideshot", CONTRACT)
    write_org(workspace / "gruntwork", "gruntwork", STUDIO)
    make_repo(workspace / "outsideshot" / "site",
              name="outsideshot", email="outsideshot@gmail.com",
              remotes={"origin": "git@github.com:GruntworkAI/thing.git"})
    findings = audit_identity.drift_findings(workspace)
    assert any("claimed by GruntworkAI" in f.message for f in findings)


def test_drift_skips_orgs_with_enforcement_off(workspace):
    write_org(workspace / "org", "org", {**CONTRACT, "enforcement": "off"})
    make_repo(workspace / "org" / "proj", name="wrong", email="wrong@example.com")
    assert audit_identity.drift_findings(workspace) == []


# --------------------------------------------------------------------------
# check 3 — liveness
# --------------------------------------------------------------------------

def test_liveness_reports_unknown_account(workspace):
    write_org(workspace / "org", "org", CONTRACT)
    findings = audit_identity.liveness_findings(workspace, probe=lambda a: False)
    assert findings and findings[0].severity == WARNING


def test_liveness_never_errors(workspace):
    """A typo degrades to a silent no-match in the hook, so this cannot block."""
    write_org(workspace / "org", "org", CONTRACT)
    findings = audit_identity.liveness_findings(workspace, probe=lambda a: False)
    assert not severities(findings, ERROR)


def test_liveness_indeterminate_is_silent(workspace):
    """Offline, or no `gh` — must not manufacture findings."""
    write_org(workspace / "org", "org", CONTRACT)
    assert audit_identity.liveness_findings(workspace, probe=lambda a: None) == []


def test_liveness_probes_each_account_once(workspace):
    """Two orgs sharing an account is one probe, not two."""
    write_org(workspace / "gruntwork", "gruntwork", STUDIO)
    write_org(workspace / "lastmilefirst.ai", "lastmilefirst.ai", STUDIO)
    probed: list[str] = []

    def probe(account):
        probed.append(account)
        return True

    audit_identity.liveness_findings(workspace, probe=probe)
    assert probed == ["GruntworkAI"]


# --------------------------------------------------------------------------
# cost discipline
# --------------------------------------------------------------------------

def test_cheap_findings_spawns_no_subprocesses(workspace, monkeypatch):
    """Session start shares a 10-second budget; this path must stay filesystem-only."""
    write_org(workspace / "outsideshot", "outsideshot", CONTRACT,
              claude_md="outsideshot outsideshot@gmail.com")
    for i in range(5):
        make_repo(workspace / "outsideshot" / f"repo{i}")

    def explode(*args, **kwargs):
        raise AssertionError("cheap_findings must not spawn subprocesses")

    monkeypatch.setattr(subprocess, "run", explode)
    audit_identity.cheap_findings(workspace)


# --------------------------------------------------------------------------
# exit codes
# --------------------------------------------------------------------------

def test_main_exits_nonzero_on_error(workspace, capsys):
    write_org(workspace / "org", "org", identity=None)
    code = audit_identity.main(["--cheap", "--workspace-root", str(workspace)])
    assert code == 1


def test_main_exits_zero_when_clean(workspace, capsys):
    write_org(workspace / "org", "org", CONTRACT,
              claude_md="outsideshot outsideshot@gmail.com")
    code = audit_identity.main(["--cheap", "--workspace-root", str(workspace)])
    assert code == 0
    assert "all orgs clean" in capsys.readouterr().out


def test_main_json_output_is_parseable(workspace, capsys):
    write_org(workspace / "org", "org", identity=None)
    audit_identity.main(["--cheap", "--json", "--workspace-root", str(workspace)])
    payload = json.loads(capsys.readouterr().out)
    assert payload[0]["severity"] == ERROR
