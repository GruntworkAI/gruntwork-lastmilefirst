"""Posture-check behavior.

The load-bearing property under test is that an UNKNOWN posture never
produces an alert. Treating "we could not tell" as "it is switched off"
would fire on every contributor for every repo they do not administer,
which is precisely the noise failure that makes people stop reading scan
output.
"""
import json
import subprocess

import pytest

import github_protections as gp


def _payload(visibility="public", scanning="enabled", push="enabled", omit_sa=False):
    payload = {"full_name": "owner/name", "visibility": visibility}
    if not omit_sa:
        payload["security_and_analysis"] = {
            "secret_scanning": {"status": scanning},
            "secret_scanning_push_protection": {"status": push},
            "secret_scanning_non_provider_patterns": {"status": "disabled"},
            "secret_scanning_validity_checks": {"status": "disabled"},
        }
    return payload


class _Result:
    def __init__(self, stdout, returncode=0):
        self.stdout = stdout
        self.returncode = returncode


@pytest.fixture
def fake_gh(monkeypatch):
    """Patch the subprocess boundary and record the calls made."""
    calls = []

    def _install(payload=None, returncode=0, raises=None):
        def fake_run(args, **kwargs):
            calls.append(args)
            if raises is not None:
                raise raises
            return _Result(json.dumps(payload) if payload is not None else "", returncode)

        monkeypatch.setattr(gp.subprocess, "run", fake_run)
        return calls

    return _install


# --- posture parsing -------------------------------------------------------

def test_public_fully_enabled_produces_no_alert(fake_gh):
    fake_gh(_payload())
    posture = gp.fetch_posture()
    assert posture["visibility"] == "PUBLIC"
    assert not gp.is_exposed(posture)
    assert gp.posture_alert(posture) is None


def test_push_protection_disabled_alerts(fake_gh):
    fake_gh(_payload(push="disabled"))
    posture = gp.fetch_posture()
    alert = gp.posture_alert(posture)
    assert alert is not None
    assert "ACTION REQUIRED" in alert
    assert "push protection" in alert
    assert "secret scanning" not in alert  # scanning is on; don't overstate
    assert "gh api -X PATCH repos/owner/name" in alert


def test_scanning_disabled_alerts_on_both_when_both_off(fake_gh):
    fake_gh(_payload(scanning="disabled", push="disabled"))
    alert = gp.posture_alert(gp.fetch_posture())
    assert "secret scanning and push protection" in alert


# --- the silence guarantees ------------------------------------------------

def test_private_repo_reports_no_posture_and_never_alerts(fake_gh):
    fake_gh(_payload(visibility="private", scanning="disabled", push="disabled"))
    posture = gp.fetch_posture()
    assert posture["visibility"] == "PRIVATE"
    assert posture["scanning"] == gp.UNKNOWN
    assert posture["push_protection"] == gp.UNKNOWN
    assert gp.posture_alert(posture) is None
    assert "paid tier" in posture["reason"]


def test_absent_security_block_is_unknown_not_disabled(fake_gh):
    """No admin access -> GitHub omits security_and_analysis entirely."""
    fake_gh(_payload(omit_sa=True))
    posture = gp.fetch_posture()
    assert posture["scanning"] == gp.UNKNOWN
    assert posture["push_protection"] == gp.UNKNOWN
    assert not gp.is_exposed(posture)
    assert gp.posture_alert(posture) is None
    assert "no admin access" in posture["reason"]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"returncode": 1},
        {"raises": FileNotFoundError("gh")},
        {"raises": subprocess.TimeoutExpired(cmd="gh", timeout=10)},
    ],
    ids=["non-zero-exit", "gh-missing", "timeout"],
)
def test_gh_failures_degrade_silently(fake_gh, kwargs):
    fake_gh(**kwargs)
    posture = gp.fetch_posture()
    assert posture["visibility"] is None
    assert gp.posture_alert(posture) is None
    assert posture["reason"]


def test_malformed_json_degrades_silently(monkeypatch):
    monkeypatch.setattr(
        gp.subprocess, "run", lambda *a, **k: _Result("not json at all", 0)
    )
    posture = gp.fetch_posture()
    assert gp.posture_alert(posture) is None
    assert "unreadable" in posture["reason"]


def test_unrecognized_status_string_is_unknown():
    posture = gp.parse_posture(
        {"security_and_analysis": {"secret_scanning": {"status": "pending"}}}
    )
    assert posture["scanning"] == gp.UNKNOWN


# --- targeting -------------------------------------------------------------

def test_named_repo_uses_explicit_endpoint(fake_gh):
    calls = fake_gh(_payload())
    gp.fetch_posture(repo="owner/other")
    assert calls[0] == ["gh", "api", "repos/owner/other"]


def test_local_repo_uses_gh_placeholders(fake_gh):
    """gh resolves {owner}/{repo} from the working directory's remote, so no
    remote parsing is needed."""
    calls = fake_gh(_payload())
    gp.fetch_posture()
    assert calls[0] == ["gh", "api", "repos/{owner}/{repo}"]


# --- account discovery -----------------------------------------------------

def test_discover_accounts_reads_identity_contracts(tmp_path):
    for org, account in (("gruntwork", "AcctOne"), ("other", "AcctTwo")):
        d = tmp_path / org / ".claude"
        d.mkdir(parents=True)
        (d / "org.json").write_text(json.dumps({"identity": {"github_account": account}}))
    assert gp.discover_accounts(tmp_path) == ["AcctOne", "AcctTwo"]


def test_discover_accounts_dedupes_and_skips_malformed(tmp_path):
    for org, body in (
        ("a", json.dumps({"identity": {"github_account": "Same"}})),
        ("b", json.dumps({"identity": {"github_account": "Same"}})),
        ("c", json.dumps({"no_identity": True})),
        ("d", "{ not json"),
    ):
        d = tmp_path / org / ".claude"
        d.mkdir(parents=True)
        (d / "org.json").write_text(body)
    assert gp.discover_accounts(tmp_path) == ["Same"]


def test_sweep_without_contracts_is_explicit(tmp_path):
    out = "\n".join(gp.sweep_accounts(tmp_path))
    assert "no org identity contracts found" in out


def test_list_public_repos_excludes_forks(fake_gh):
    fake_gh([
        {"nameWithOwner": "acct/mine", "isFork": False},
        {"nameWithOwner": "acct/theirs", "isFork": True},
    ])
    assert gp.list_public_repos("acct") == ["acct/mine"]
