"""Tests for the GitHub posture module (plan 2026-09-26-001, U1 + U2).

Everything is offline. Payloads are literal dicts shaped like the GitHub
`repos/{owner}/{repo}` response; the one subprocess primitive, `_run_gh`, is
stubbed wherever fetch_posture() is exercised.
"""

from __future__ import annotations

import copy
import json
import subprocess

import pytest

import github_protections as gp
from github_protections import DISABLED, ENABLED, UNKNOWN


# --------------------------------------------------------------------------
# Fixture payloads
# --------------------------------------------------------------------------

FULL_PAYLOAD = {
    "full_name": "ExampleOrg/example-repo",
    "visibility": "public",
    "private": False,
    "allow_squash_merge": True,
    "allow_merge_commit": True,
    "allow_rebase_merge": True,
    "allow_auto_merge": False,
    "delete_branch_on_merge": False,
    "allow_forking": True,
    "has_wiki": True,
    "has_discussions": False,
    "has_projects": True,
    "web_commit_signoff_required": False,
    "security_and_analysis": {
        "secret_scanning": {"status": "enabled"},
        "secret_scanning_push_protection": {"status": "enabled"},
        "dependabot_security_updates": {"status": "disabled"},
        "secret_scanning_non_provider_patterns": {"status": "disabled"},
        "secret_scanning_validity_checks": {"status": "disabled"},
    },
}

# What a caller without admin sees: no security_and_analysis block at all.
NO_ADMIN_PAYLOAD = {
    k: v for k, v in FULL_PAYLOAD.items() if k != "security_and_analysis"
}

# Settings fields absent entirely (e.g. a trimmed or older response).
BARE_PAYLOAD = {"full_name": "ExampleOrg/bare", "visibility": "public"}


def _payload(**overrides):
    p = copy.deepcopy(FULL_PAYLOAD)
    p.update(overrides)
    return p


def _sa(**statuses):
    """security_and_analysis block from key=status pairs."""
    return {k: {"status": v} for k, v in statuses.items()}


def _posture(visibility="PUBLIC", scanning=ENABLED, push=ENABLED, repo="ExampleOrg/example-repo"):
    return {
        "repo": repo,
        "visibility": visibility,
        "reason": None,
        "scanning": scanning,
        "push_protection": push,
    }


@pytest.fixture
def gh_stub(monkeypatch):
    """Stub _run_gh; set .result to a CompletedProcess (or None)."""
    class Stub:
        result = None
        calls = []

        def __call__(self, args, cwd, timeout):
            self.calls.append(args)
            return self.result

    stub = Stub()
    stub.calls = []
    monkeypatch.setattr(gp, "_run_gh", stub)
    return stub


def _completed(payload, returncode=0):
    stdout = payload if isinstance(payload, str) else json.dumps(payload)
    return subprocess.CompletedProcess(args=["gh"], returncode=returncode, stdout=stdout, stderr="")


# ==========================================================================
# U1: the module as it stood before U2
# ==========================================================================

class TestParsePostureSecurity:
    def test_full_payload(self):
        p = gp.parse_posture(FULL_PAYLOAD)
        assert p["scanning"] == ENABLED
        assert p["push_protection"] == ENABLED
        assert p["secret_scanning_non_provider_patterns"] == DISABLED
        assert p["secret_scanning_validity_checks"] == DISABLED

    def test_disabled_values(self):
        payload = _payload(security_and_analysis=_sa(
            secret_scanning="disabled", secret_scanning_push_protection="disabled"))
        p = gp.parse_posture(payload)
        assert p["scanning"] == DISABLED
        assert p["push_protection"] == DISABLED

    def test_no_security_and_analysis_is_unknown_not_disabled(self):
        p = gp.parse_posture(NO_ADMIN_PAYLOAD)
        assert p["scanning"] == UNKNOWN
        assert p["push_protection"] == UNKNOWN
        # Tier-gated fields are not reported when the whole block is absent.
        for field in gp.TIER_GATED_FIELDS:
            assert field not in p

    @pytest.mark.parametrize("sa", [None, "enabled", [], 42])
    def test_malformed_block_is_unknown(self, sa):
        p = gp.parse_posture(_payload(security_and_analysis=sa))
        assert p["scanning"] == UNKNOWN
        assert p["push_protection"] == UNKNOWN

    @pytest.mark.parametrize("entry", [
        "enabled",               # not a dict
        {},                      # no status
        {"status": "ENABLED"},   # wrong case
        {"status": "on"},        # unrecognized
        {"status": None},
    ])
    def test_malformed_entry_is_unknown(self, entry):
        payload = _payload(security_and_analysis={
            "secret_scanning": entry,
            "secret_scanning_push_protection": {"status": "enabled"},
        })
        p = gp.parse_posture(payload)
        assert p["scanning"] == UNKNOWN
        assert p["push_protection"] == ENABLED

    def test_missing_entry_is_unknown(self):
        payload = _payload(security_and_analysis=_sa(secret_scanning="enabled"))
        p = gp.parse_posture(payload)
        assert p["scanning"] == ENABLED
        assert p["push_protection"] == UNKNOWN
        assert p["secret_scanning_validity_checks"] == UNKNOWN

    def test_does_not_mutate_unknown_template(self):
        p = gp.parse_posture(NO_ADMIN_PAYLOAD)
        p["scanning"] = "tampered"
        assert gp.parse_posture(NO_ADMIN_PAYLOAD)["scanning"] == UNKNOWN


class TestIsExposed:
    def test_public_all_on(self):
        assert gp.is_exposed(_posture()) is False

    @pytest.mark.parametrize("scanning,push", [
        (DISABLED, ENABLED), (ENABLED, DISABLED), (DISABLED, DISABLED)])
    def test_public_something_off(self, scanning, push):
        assert gp.is_exposed(_posture(scanning=scanning, push=push)) is True

    @pytest.mark.parametrize("visibility", ["PRIVATE", "INTERNAL", None])
    def test_non_public_never_exposed(self, visibility):
        assert gp.is_exposed(_posture(visibility=visibility, scanning=DISABLED, push=DISABLED)) is False

    def test_unknown_is_silent(self):
        assert gp.is_exposed(_posture(scanning=UNKNOWN, push=UNKNOWN)) is False

    def test_unknown_plus_disabled_is_exposed(self):
        assert gp.is_exposed(_posture(scanning=UNKNOWN, push=DISABLED)) is True


# The exact alert text as it stood before U2. Session-start alerts must not
# change (plan D2), so this literal is the byte-identity reference.
EXPECTED_ALERT_BOTH_OFF = (
    "ACTION REQUIRED: PUBLIC repo (ExampleOrg/example-repo) has secret scanning "
    "and push protection disabled. Enable with:\n"
    "gh api -X PATCH repos/ExampleOrg/example-repo \\\n"
    "  -F 'security_and_analysis[secret_scanning][status]=enabled' \\\n"
    "  -F 'security_and_analysis[secret_scanning_push_protection][status]=enabled'"
)


class TestPostureAlert:
    def test_none_when_protected(self):
        assert gp.posture_alert(_posture()) is None

    def test_none_when_private(self):
        assert gp.posture_alert(_posture(visibility="PRIVATE", scanning=DISABLED, push=DISABLED)) is None

    def test_none_when_unknown(self):
        assert gp.posture_alert(_posture(scanning=UNKNOWN, push=UNKNOWN)) is None

    def test_both_off_exact_text(self):
        assert gp.posture_alert(_posture(scanning=DISABLED, push=DISABLED)) == EXPECTED_ALERT_BOTH_OFF

    def test_one_off_names_only_that_one(self):
        alert = gp.posture_alert(_posture(scanning=ENABLED, push=DISABLED))
        assert alert.startswith(
            "ACTION REQUIRED: PUBLIC repo (ExampleOrg/example-repo) has push protection disabled.")
        assert "secret scanning and" not in alert

    def test_missing_repo_name(self):
        alert = gp.posture_alert(_posture(repo=None, scanning=DISABLED, push=ENABLED))
        assert "PUBLIC repo (this repo) has secret scanning disabled" in alert


class TestEnableCommand:
    def test_exact(self):
        assert gp.enable_command("o/r") == (
            "gh api -X PATCH repos/o/r \\\n"
            "  -F 'security_and_analysis[secret_scanning][status]=enabled' \\\n"
            "  -F 'security_and_analysis[secret_scanning_push_protection][status]=enabled'"
        )


class TestDescribeShape:
    def test_not_applicable_for_private(self):
        out = gp.describe({"visibility": "PRIVATE", "reason": "private repo"})
        assert out.splitlines()[0] == "GitHub protections: not applicable (private repo)"

    def test_unknown_when_no_admin(self):
        out = gp.describe(_posture(scanning=UNKNOWN, push=UNKNOWN) | {"reason": "no admin access to this repo"})
        assert out.splitlines()[0] == "GitHub protections: unknown (no admin access to this repo)"

    def test_protected_block(self):
        lines = gp.describe(_posture()).splitlines()
        assert lines[:3] == [
            "GitHub protections:",
            "  Secret scanning:  enabled",
            "  Push protection:  enabled",
        ]
        assert not any("WARNING" in l for l in lines)

    def test_exposed_block_carries_warning_and_command(self):
        out = gp.describe(_posture(scanning=DISABLED))
        assert "  WARNING: this public repo is missing a free protection." in out
        assert "  Enable: gh api -X PATCH repos/ExampleOrg/example-repo" in out

    def test_tier_gated_line(self):
        posture = _posture() | {
            "secret_scanning_non_provider_patterns": DISABLED,
            "secret_scanning_validity_checks": UNKNOWN,
        }
        out = gp.describe(posture)
        assert "  Tier-gated (not alerted on): non_provider_patterns=disabled" in out


class TestFetchPosture:
    def test_public_full(self, gh_stub):
        gh_stub.result = _completed(FULL_PAYLOAD)
        p = gp.fetch_posture()
        assert p["repo"] == "ExampleOrg/example-repo"
        assert p["visibility"] == "PUBLIC"
        assert p["scanning"] == ENABLED
        assert p["reason"] is None
        assert gh_stub.calls[0] == ["gh", "api", "repos/{owner}/{repo}"]

    def test_explicit_repo_endpoint(self, gh_stub):
        gh_stub.result = _completed(FULL_PAYLOAD)
        gp.fetch_posture(repo="o/r")
        assert gh_stub.calls[0] == ["gh", "api", "repos/o/r"]

    def test_private_short_circuits(self, gh_stub):
        gh_stub.result = _completed(_payload(visibility="private", security_and_analysis=_sa(
            secret_scanning="disabled", secret_scanning_push_protection="disabled")))
        p = gp.fetch_posture()
        assert p["visibility"] == "PRIVATE"
        assert p["scanning"] == UNKNOWN
        assert "private repo" in p["reason"]
        assert gp.posture_alert(p) is None

    def test_no_admin_reason(self, gh_stub):
        gh_stub.result = _completed(NO_ADMIN_PAYLOAD)
        p = gp.fetch_posture()
        assert p["reason"] == "no admin access to this repo"

    def test_gh_unavailable(self, gh_stub):
        gh_stub.result = None
        p = gp.fetch_posture()
        assert p["visibility"] is None
        assert p["reason"] == "gh unavailable or timed out"

    def test_gh_error(self, gh_stub):
        gh_stub.result = _completed("", returncode=1)
        assert gp.fetch_posture()["reason"] == "no remote, no access, or repo not found"

    def test_unreadable_json(self, gh_stub):
        gh_stub.result = _completed("not json")
        assert gp.fetch_posture()["reason"] == "unreadable API response"


class TestDiscoverAccounts:
    def test_reads_identity_contracts(self, tmp_path):
        for org, acct in (("a", "AcctA"), ("b", "AcctB"), ("c", "AcctA")):
            d = tmp_path / org / ".claude"
            d.mkdir(parents=True)
            (d / "org.json").write_text(json.dumps({"identity": {"github_account": acct}}))
        bad = tmp_path / "z" / ".claude"
        bad.mkdir(parents=True)
        (bad / "org.json").write_text("{not json")
        assert gp.discover_accounts(tmp_path) == ["AcctA", "AcctB"]


class TestListPublicRepos:
    def test_filters_forks(self, gh_stub):
        gh_stub.result = _completed([
            {"nameWithOwner": "o/a", "isFork": False},
            {"nameWithOwner": "o/b", "isFork": True},
        ])
        assert gp.list_public_repos("o") == ["o/a"]

    def test_failure_is_none(self, gh_stub):
        gh_stub.result = _completed("", returncode=1)
        assert gp.list_public_repos("o") is None


class TestSweepAccounts:
    def test_reports_exposed(self, tmp_path, monkeypatch):
        d = tmp_path / "org" / ".claude"
        d.mkdir(parents=True)
        (d / "org.json").write_text(json.dumps({"identity": {"github_account": "o"}}))
        monkeypatch.setattr(gp, "list_public_repos", lambda a: ["o/a", "o/b"])
        monkeypatch.setattr(gp, "fetch_posture", lambda repo: _posture(
            repo=repo, scanning=DISABLED if repo == "o/b" else ENABLED))
        lines = gp.sweep_accounts(tmp_path)
        assert "  2 public repo(s) checked, 1 MISSING protections:" in lines
        assert "    o/b: scanning disabled" in lines

    def test_no_contracts(self, tmp_path):
        assert gp.sweep_accounts(tmp_path) == [
            "\nGitHub protections: no org identity contracts found — skipped."]


# ==========================================================================
# U2: zero-cost repository settings (cached, described, never alerted on)
# ==========================================================================

class TestParseSettingsFields:
    def test_full_payload_values(self):
        p = gp.parse_posture(FULL_PAYLOAD)
        assert p["visibility"] == "PUBLIC"
        assert p["merge_methods"] == ["squash", "merge", "rebase"]
        assert p["allow_auto_merge"] == gp.OFF
        assert p["delete_branch_on_merge"] == gp.OFF
        assert p["allow_forking"] == gp.ON
        assert p["features"] == {"wiki": gp.ON, "discussions": gp.OFF, "projects": gp.ON}
        assert p["dependabot_security_updates"] == DISABLED
        assert p["web_commit_signoff_required"] == gp.OFF

    def test_every_settings_field_present(self):
        p = gp.parse_posture(FULL_PAYLOAD)
        for field in gp.SETTINGS_FIELDS:
            assert field in p

    def test_bare_payload_every_field_unknown(self):
        p = gp.parse_posture({})
        assert p["visibility"] == UNKNOWN
        assert p["merge_methods"] == UNKNOWN
        assert p["allow_auto_merge"] == UNKNOWN
        assert p["delete_branch_on_merge"] == UNKNOWN
        assert p["allow_forking"] == UNKNOWN
        assert p["features"] == {"wiki": UNKNOWN, "discussions": UNKNOWN, "projects": UNKNOWN}
        assert p["dependabot_security_updates"] == UNKNOWN
        assert p["web_commit_signoff_required"] == UNKNOWN

    def test_private_visibility_uppercased(self):
        assert gp.parse_posture(_payload(visibility="private"))["visibility"] == "PRIVATE"

    @pytest.mark.parametrize("flags,expected", [
        ((True, False, False), ["squash"]),
        ((False, True, True), ["merge", "rebase"]),
        ((False, False, False), []),
    ])
    def test_merge_methods_subsets(self, flags, expected):
        payload = _payload(allow_squash_merge=flags[0], allow_merge_commit=flags[1],
                           allow_rebase_merge=flags[2])
        assert gp.parse_posture(payload)["merge_methods"] == expected

    @pytest.mark.parametrize("missing", ["allow_squash_merge", "allow_merge_commit", "allow_rebase_merge"])
    def test_merge_methods_unknown_if_any_flag_absent(self, missing):
        payload = copy.deepcopy(FULL_PAYLOAD)
        del payload[missing]
        assert gp.parse_posture(payload)["merge_methods"] == UNKNOWN

    def test_merge_methods_unknown_if_flag_malformed(self):
        assert gp.parse_posture(_payload(allow_merge_commit="yes"))["merge_methods"] == UNKNOWN

    @pytest.mark.parametrize("key,field", [
        ("allow_auto_merge", "allow_auto_merge"),
        ("delete_branch_on_merge", "delete_branch_on_merge"),
        ("allow_forking", "allow_forking"),
        ("web_commit_signoff_required", "web_commit_signoff_required"),
    ])
    def test_boolean_fields(self, key, field):
        assert gp.parse_posture(_payload(**{key: True}))[field] == gp.ON
        assert gp.parse_posture(_payload(**{key: False}))[field] == gp.OFF
        assert gp.parse_posture(_payload(**{key: "true"}))[field] == UNKNOWN
        assert gp.parse_posture(_payload(**{key: None}))[field] == UNKNOWN
        absent = copy.deepcopy(FULL_PAYLOAD)
        del absent[key]
        assert gp.parse_posture(absent)[field] == UNKNOWN

    @pytest.mark.parametrize("label,key", [
        ("wiki", "has_wiki"), ("discussions", "has_discussions"), ("projects", "has_projects")])
    def test_feature_fields(self, label, key):
        assert gp.parse_posture(_payload(**{key: True}))["features"][label] == gp.ON
        assert gp.parse_posture(_payload(**{key: False}))["features"][label] == gp.OFF
        absent = copy.deepcopy(FULL_PAYLOAD)
        del absent[key]
        assert gp.parse_posture(absent)["features"][label] == UNKNOWN

    def test_dependabot_enabled(self):
        payload = _payload(security_and_analysis=_sa(dependabot_security_updates="enabled"))
        assert gp.parse_posture(payload)["dependabot_security_updates"] == ENABLED

    @pytest.mark.parametrize("sa", [
        _sa(secret_scanning="enabled"),                      # entry absent
        {"dependabot_security_updates": "enabled"},          # not a dict
        _sa(dependabot_security_updates="paused"),           # unrecognized
    ])
    def test_dependabot_unknown(self, sa):
        assert gp.parse_posture(_payload(security_and_analysis=sa))["dependabot_security_updates"] == UNKNOWN

    def test_no_admin_still_reads_settings(self):
        p = gp.parse_posture(NO_ADMIN_PAYLOAD)
        assert p["scanning"] == UNKNOWN
        assert p["dependabot_security_updates"] == UNKNOWN
        assert p["merge_methods"] == ["squash", "merge", "rebase"]
        assert p["features"]["wiki"] == gp.ON

    def test_security_keys_unchanged_by_settings(self):
        """The pre-U2 keys keep exactly their pre-U2 values."""
        p = gp.parse_posture(FULL_PAYLOAD)
        assert {k: p[k] for k in ("scanning", "push_protection", *gp.TIER_GATED_FIELDS)} == {
            "scanning": ENABLED,
            "push_protection": ENABLED,
            "secret_scanning_non_provider_patterns": DISABLED,
            "secret_scanning_validity_checks": DISABLED,
        }
        assert {k: gp.parse_posture(NO_ADMIN_PAYLOAD)[k] for k in ("scanning", "push_protection")} == {
            "scanning": UNKNOWN, "push_protection": UNKNOWN}

    def test_serializable_for_cache(self):
        p = gp.parse_posture(FULL_PAYLOAD)
        assert json.loads(json.dumps(p)) == p


class TestFetchPostureCarriesSettings:
    def test_public_carries_settings(self, gh_stub):
        gh_stub.result = _completed(FULL_PAYLOAD)
        p = gp.fetch_posture()
        assert p["visibility"] == "PUBLIC"
        assert p["merge_methods"] == ["squash", "merge", "rebase"]
        assert p["delete_branch_on_merge"] == gp.OFF
        assert p["dependabot_security_updates"] == DISABLED
        assert p["features"]["wiki"] == gp.ON

    def test_private_carries_settings_but_no_security(self, gh_stub):
        gh_stub.result = _completed(_payload(visibility="private", security_and_analysis=_sa(
            secret_scanning="disabled", dependabot_security_updates="enabled")))
        p = gp.fetch_posture()
        assert p["visibility"] == "PRIVATE"
        assert p["scanning"] == UNKNOWN
        assert p["allow_forking"] == gp.ON
        assert p["dependabot_security_updates"] == ENABLED

    def test_absent_visibility_stays_none(self, gh_stub):
        """fetch_posture's visibility keeps its None-when-absent contract;
        parse_settings' UNKNOWN must not leak into it."""
        payload = copy.deepcopy(FULL_PAYLOAD)
        del payload["visibility"]
        gh_stub.result = _completed(payload)
        assert gp.fetch_posture()["visibility"] is None

    def test_gh_failure_has_no_settings(self, gh_stub):
        gh_stub.result = None
        p = gp.fetch_posture()
        assert "merge_methods" not in p
        assert gp.describe_settings(p) == ""


class TestCacheCarriesSettings:
    """session_start caches whatever fetch_posture returns; verify the new
    fields survive the round trip through Overwatch state."""

    def test_round_trip(self, tmp_path, monkeypatch, gh_stub):
        import overwatch
        import session_start

        state_dir = tmp_path / "state"
        state_dir.mkdir()
        monkeypatch.setattr(overwatch, "get_state_dir", lambda: state_dir)
        # check_repo_visibility first asks git for a remote; stub that too.
        real_run = subprocess.run

        def fake_run(args, *a, **kw):
            if args[:3] == ["git", "remote", "get-url"]:
                return subprocess.CompletedProcess(args, 0, "git@github.com:o/r.git\n", "")
            return real_run(args, *a, **kw)

        monkeypatch.setattr(session_start.subprocess, "run", fake_run)
        monkeypatch.setattr(session_start, "fetch_posture", gp.fetch_posture)
        gh_stub.result = _completed(FULL_PAYLOAD)

        out = session_start.check_repo_visibility("proj-key")
        assert out == ("WARNING: PUBLIC repo (ExampleOrg/example-repo) — do not commit "
                       "secrets or sensitive content")

        # The write landed in the isolated state dir, not the real one.
        assert (state_dir / "overwatch-state.json").exists()
        cached = session_start._cached_posture("proj-key", int(__import__("time").time()))
        assert cached is not None
        for field in gp.SETTINGS_FIELDS:
            assert field in cached
        assert cached["merge_methods"] == ["squash", "merge", "rebase"]
        assert cached["features"] == {"wiki": gp.ON, "discussions": gp.OFF, "projects": gp.ON}


class TestPostureAlertUnchanged:
    """D2: session-start alerts do not grow. Same payload in, same bytes out."""

    @pytest.mark.parametrize("sa", [
        _sa(secret_scanning="disabled", secret_scanning_push_protection="disabled"),
        _sa(secret_scanning="enabled", secret_scanning_push_protection="disabled"),
        _sa(secret_scanning="enabled", secret_scanning_push_protection="enabled",
            dependabot_security_updates="disabled"),
    ])
    def test_byte_identical_with_and_without_settings(self, gh_stub, sa):
        gh_stub.result = _completed(_payload(security_and_analysis=sa))
        with_settings = gp.fetch_posture()
        legacy = {k: with_settings[k] for k in
                  ("repo", "visibility", "reason", "scanning", "push_protection")}
        assert gp.posture_alert(with_settings) == gp.posture_alert(legacy)

    def test_both_off_matches_pre_u2_literal(self, gh_stub):
        gh_stub.result = _completed(_payload(security_and_analysis=_sa(
            secret_scanning="disabled", secret_scanning_push_protection="disabled")))
        assert gp.posture_alert(gp.fetch_posture()) == EXPECTED_ALERT_BOTH_OFF

    @pytest.mark.parametrize("overrides", [
        {"allow_forking": True, "has_wiki": True, "delete_branch_on_merge": False},
        {"allow_squash_merge": True, "allow_merge_commit": True, "allow_rebase_merge": True},
        {"web_commit_signoff_required": False, "allow_auto_merge": True},
    ])
    def test_settings_never_alert(self, gh_stub, overrides):
        gh_stub.result = _completed(_payload(**overrides))
        assert gp.posture_alert(gp.fetch_posture()) is None


class TestDescribeSettings:
    def test_block_lines(self):
        out = gp.describe(gp.parse_posture(FULL_PAYLOAD) | {"repo": "o/r", "reason": None})
        lines = out.splitlines()
        i = lines.index("Repository settings (--audit only, not alerted on):")
        block = [l.split(":", 1) for l in lines[i + 1:]]
        measured = {k.strip(): v.strip() for k, v in block}
        assert measured == {
            "Merge methods allowed": "squash, merge, rebase",
            "Auto-merge": "off",
            "Delete branch on merge": "off",
            "Forking": "on",
            "Wiki": "on",
            "Discussions": "off",
            "Projects": "on",
            "Dependabot security updates": "disabled",
            "Web commit sign-off required": "off",
        }

    def test_protections_block_precedes_settings(self):
        out = gp.describe(gp.parse_posture(FULL_PAYLOAD) | {"repo": "o/r"})
        assert out.index("GitHub protections:") < out.index("Repository settings")

    def test_no_merge_methods_reads_none(self):
        p = gp.parse_posture(_payload(allow_squash_merge=False, allow_merge_commit=False,
                                      allow_rebase_merge=False))
        assert "  Merge methods allowed:         none" in gp.describe_settings(p)

    def test_unknown_values_print_unknown(self):
        payload = copy.deepcopy(FULL_PAYLOAD)
        del payload["has_wiki"]
        del payload["allow_rebase_merge"]
        out = gp.describe_settings(gp.parse_posture(payload))
        assert "  Merge methods allowed:         unknown" in out
        assert "  Wiki:                          unknown" in out

    def test_private_repo_shows_settings(self, gh_stub):
        gh_stub.result = _completed(_payload(visibility="private"))
        out = gp.describe(gp.fetch_posture())
        assert out.splitlines()[0].startswith("GitHub protections: not applicable")
        assert "Repository settings (--audit only, not alerted on):" in out

    def test_legacy_cache_entry_describes_as_before(self):
        """An entry cached before U2 has no settings keys; describe() output is
        exactly the pre-U2 block."""
        legacy = _posture()
        assert gp.describe(legacy) == (
            "GitHub protections:\n"
            "  Secret scanning:  enabled\n"
            "  Push protection:  enabled"
        )

    def test_all_unknown_block_omitted(self):
        assert gp.describe_settings(gp.parse_posture({})) == ""

    def test_no_alert_vocabulary_in_settings_block(self):
        out = gp.describe_settings(gp.parse_posture(FULL_PAYLOAD)).upper()
        for word in ("WARNING", "ACTION REQUIRED", "MISSING", "SHOULD"):
            assert word not in out
