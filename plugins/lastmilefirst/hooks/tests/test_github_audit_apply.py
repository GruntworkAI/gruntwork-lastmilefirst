"""Tests for the per-call audit checks and the gated apply
(plan 2026-09-26-001, U3 + U3b).

Everything is offline. `_run_gh` is replaced by FakeGh, which maps
(method, endpoint) to (status, payload) and renders the `gh api -i` output
shape (status line, headers, blank line, body) that `_api` parses. Writes
are recorded with their JSON body so tests can assert the exact calls.
"""

from __future__ import annotations

import copy
import json
import subprocess

import pytest

import github_protections as gp
from github_protections import NOT_AVAILABLE, OFF, OK, ON, UNKNOWN

R = "o/r"

# --------------------------------------------------------------------------
# Fake gh
# --------------------------------------------------------------------------


class FakeGh:
    def __init__(self, routes=None, on_write=None):
        self.routes = dict(routes or {})
        self.on_write = dict(on_write or {})
        self.calls = []

    def __call__(self, args, cwd, timeout, input_text=None):
        assert args[:3] == ["gh", "api", "-i"] and args[3] == "-X", args
        method, endpoint = args[4], args[5]
        body = json.loads(input_text) if input_text is not None else None
        self.calls.append((method, endpoint, body))
        if method != "GET" and (method, endpoint) in self.on_write:
            self.on_write[(method, endpoint)](self, body)
        status, payload = self.routes.get((method, endpoint), (404, {"message": "Not Found"}))
        text = "" if payload is None else json.dumps(payload)
        reason = {200: "OK", 201: "Created", 204: "No Content"}.get(status, "Error")
        stdout = f"HTTP/2.0 {status} {reason}\r\nX-Github-Media-Type: github.v3\r\n\r\n{text}"
        return subprocess.CompletedProcess(args, 0 if status < 300 else 1, stdout, "")

    @property
    def writes(self):
        return [c for c in self.calls if c[0] != "GET"]


def _get(endpoint):
    return ("GET", endpoint)


REPO_PAYLOAD = {
    "full_name": R,
    "default_branch": "main",
    "visibility": "public",
    "permissions": {"admin": True, "push": True, "pull": True},
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
    },
}

MAIN_RULESET = {
    "id": 1, "name": "protect main", "target": "branch", "enforcement": "active",
    "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
    "rules": [{"type": "deletion"}, {"type": "non_fast_forward"}],
}
TAG_RULESET = {
    "id": 2, "name": "protect release tags", "target": "tag", "enforcement": "active",
    "conditions": {"ref_name": {"include": ["refs/tags/v*"], "exclude": []}},
    "rules": [{"type": "deletion"}, {"type": "update"}],
}


def _listing(*rulesets):
    return [{k: r[k] for k in ("id", "name", "target", "enforcement")} for r in rulesets]


def bare_routes(**repo_overrides):
    """A repo with nothing from the baseline in place."""
    repo = copy.deepcopy(REPO_PAYLOAD)
    repo.update(repo_overrides)
    return {
        _get(f"repos/{R}"): (200, repo),
        _get(f"repos/{R}/rulesets?per_page=100"): (200, []),
        _get(f"repos/{R}/branches/main/protection"): (
            404, {"message": "Branch not protected", "status": "404"}),
        _get(f"repos/{R}/contents/.claude-plugin/marketplace.json"): (404, {"message": "Not Found"}),
        _get(f"repos/{R}/vulnerability-alerts"): (404, {"message": "Not Found"}),
        _get(f"repos/{R}/actions/permissions"): (200, {"enabled": True, "allowed_actions": "all"}),
        _get(f"repos/{R}/actions/permissions/workflow"): (
            200, {"default_workflow_permissions": "read", "can_approve_pull_request_reviews": False}),
        _get(f"repos/{R}/hooks?per_page=100"): (200, []),
        _get(f"repos/{R}/keys?per_page=100"): (200, []),
    }


def baseline_routes():
    """A repo at the plan's six-part baseline."""
    routes = bare_routes(
        delete_branch_on_merge=True,
        has_wiki=False,
        security_and_analysis={
            "secret_scanning": {"status": "enabled"},
            "secret_scanning_push_protection": {"status": "enabled"},
            "dependabot_security_updates": {"status": "enabled"},
        },
    )
    routes.update({
        _get(f"repos/{R}/rulesets?per_page=100"): (200, _listing(MAIN_RULESET, TAG_RULESET)),
        _get(f"repos/{R}/rulesets/1"): (200, MAIN_RULESET),
        _get(f"repos/{R}/rulesets/2"): (200, TAG_RULESET),
        _get(f"repos/{R}/vulnerability-alerts"): (204, None),
        _get(f"repos/{R}/actions/permissions"): (200, {"enabled": True, "allowed_actions": "selected"}),
        _get(f"repos/{R}/actions/permissions/selected-actions"): (
            200, {"github_owned_allowed": True, "verified_allowed": True, "patterns_allowed": []}),
    })
    return routes


@pytest.fixture
def fake(monkeypatch):
    f = FakeGh()
    monkeypatch.setattr(gp, "_run_gh", f)
    return f


# ==========================================================================
# _api: parsing gh api -i output
# ==========================================================================


class TestApi:
    def test_status_payload_message(self, fake):
        fake.routes[_get("x")] = (404, {"message": "Branch not protected"})
        assert gp._api("GET", "x") == (404, {"message": "Branch not protected"},
                                       "Branch not protected")

    def test_204_empty_body(self, fake):
        fake.routes[_get("x")] = (204, None)
        assert gp._api("GET", "x") == (204, None, None)

    def test_gh_unusable(self, monkeypatch):
        monkeypatch.setattr(gp, "_run_gh", lambda *a, **k: None)
        status, payload, _ = gp._api("GET", "x")
        assert status is None and payload is None

    def test_no_status_line(self, monkeypatch):
        monkeypatch.setattr(gp, "_run_gh", lambda *a, **k: subprocess.CompletedProcess(
            a[0], 1, "", "gh: not logged in"))
        assert gp._api("GET", "x")[0] is None

    def test_body_sent_on_stdin(self, fake):
        fake.routes[("PATCH", "x")] = (200, {})
        gp._api("PATCH", "x", {"has_wiki": False})
        assert fake.calls == [("PATCH", "x", {"has_wiki": False})]


# ==========================================================================
# U3: each check on 2xx, 403, 404
# ==========================================================================


class TestBranchRulesets:
    def test_baseline(self, fake):
        fake.routes = baseline_routes()
        c = gp.check_branch_rulesets(R, "main")
        assert c["status"] == OK and c["count"] == 1 and c["active"] == 1
        assert (c["non_fast_forward"], c["deletion"], c["pull_request"]) == (True, True, False)
        assert c["classic_protection"] == OFF

    def test_detail_read_for_rules(self, fake):
        fake.routes = baseline_routes()
        gp.check_branch_rulesets(R, "main")
        assert _get(f"repos/{R}/rulesets/1") in [(m, e) for m, e, _ in fake.calls]
        # The tag ruleset is read too (one listing serves both), but no
        # ruleset of another target is.

    @pytest.mark.parametrize("include,expected", [
        (["~DEFAULT_BRANCH"], 1),
        (["~ALL"], 1),
        (["refs/heads/main"], 1),
        (["main"], 1),
        (["refs/heads/*"], 1),
        (["refs/heads/dev"], 0),
    ])
    def test_targeting(self, fake, include, expected):
        rs = copy.deepcopy(MAIN_RULESET)
        rs["conditions"]["ref_name"]["include"] = include
        fake.routes = bare_routes()
        fake.routes[_get(f"repos/{R}/rulesets?per_page=100")] = (200, _listing(rs))
        fake.routes[_get(f"repos/{R}/rulesets/1")] = (200, rs)
        assert gp.check_branch_rulesets(R, "main")["count"] == expected

    def test_excluded_branch_not_counted(self, fake):
        rs = copy.deepcopy(MAIN_RULESET)
        rs["conditions"]["ref_name"] = {"include": ["~ALL"], "exclude": ["refs/heads/main"]}
        fake.routes = bare_routes()
        fake.routes[_get(f"repos/{R}/rulesets?per_page=100")] = (200, _listing(rs))
        fake.routes[_get(f"repos/{R}/rulesets/1")] = (200, rs)
        assert gp.check_branch_rulesets(R, "main")["count"] == 0

    def test_evaluate_mode_counts_but_not_active(self, fake):
        rs = dict(MAIN_RULESET, enforcement="evaluate")
        fake.routes = bare_routes()
        fake.routes[_get(f"repos/{R}/rulesets?per_page=100")] = (200, _listing(rs))
        fake.routes[_get(f"repos/{R}/rulesets/1")] = (200, rs)
        c = gp.check_branch_rulesets(R, "main")
        assert (c["count"], c["active"], c["deletion"]) == (1, 0, False)

    def test_403_is_unknown(self, fake):
        fake.routes = bare_routes()
        fake.routes[_get(f"repos/{R}/rulesets?per_page=100")] = (403, {"message": "Must have admin rights"})
        c = gp.check_branch_rulesets(R, "main")
        assert c["status"] == UNKNOWN and c["reason"] == "HTTP 403"

    def test_404_is_unknown(self, fake):
        fake.routes = bare_routes()
        fake.routes[_get(f"repos/{R}/rulesets?per_page=100")] = (404, {"message": "Not Found"})
        assert gp.check_branch_rulesets(R, "main")["status"] == UNKNOWN

    def test_plan_gated_403(self, fake):
        msg = "Upgrade to GitHub Pro or make this repository public to enable this feature."
        fake.routes = bare_routes()
        fake.routes[_get(f"repos/{R}/rulesets?per_page=100")] = (403, {"message": msg})
        fake.routes[_get(f"repos/{R}/branches/main/protection")] = (403, {"message": msg})
        c = gp.check_branch_rulesets(R, "main")
        assert c["status"] == NOT_AVAILABLE
        assert c["classic_protection"] == NOT_AVAILABLE

    def test_failed_detail_read_is_unknown_not_partial(self, fake):
        fake.routes = baseline_routes()
        fake.routes[_get(f"repos/{R}/rulesets/1")] = (500, {"message": "oops"})
        assert gp.check_branch_rulesets(R, "main")["status"] == UNKNOWN

    def test_classic_protection_on(self, fake):
        fake.routes = bare_routes()
        fake.routes[_get(f"repos/{R}/branches/main/protection")] = (200, {"url": "x"})
        assert gp.check_branch_rulesets(R, "main")["classic_protection"] == ON

    def test_branch_not_protected_404_is_off(self, fake):
        fake.routes = bare_routes()
        assert gp.check_branch_rulesets(R, "main")["classic_protection"] == OFF

    def test_permissions_404_is_unknown(self, fake):
        fake.routes = bare_routes()
        fake.routes[_get(f"repos/{R}/branches/main/protection")] = (404, {"message": "Not Found"})
        assert gp.check_branch_rulesets(R, "main")["classic_protection"] == UNKNOWN


class TestTagRulesets:
    def test_baseline(self, fake):
        fake.routes = baseline_routes()
        c = gp.check_tag_rulesets(R)
        assert c["status"] == OK and c["active"] == 1
        assert (c["update"], c["deletion"]) == (True, True)

    @pytest.mark.parametrize("include,expected", [
        (["refs/tags/v*"], 1),
        (["~ALL"], 1),
        (["refs/tags/*"], 1),
        (["refs/tags/release-*"], 0),
    ])
    def test_pattern_match(self, fake, include, expected):
        rs = copy.deepcopy(TAG_RULESET)
        rs["conditions"]["ref_name"]["include"] = include
        fake.routes = bare_routes()
        fake.routes[_get(f"repos/{R}/rulesets?per_page=100")] = (200, _listing(rs))
        fake.routes[_get(f"repos/{R}/rulesets/2")] = (200, rs)
        assert gp.check_tag_rulesets(R)["count"] == expected

    def test_403_unknown(self, fake):
        fake.routes = bare_routes()
        fake.routes[_get(f"repos/{R}/rulesets?per_page=100")] = (403, {"message": "Forbidden"})
        assert gp.check_tag_rulesets(R)["status"] == UNKNOWN

    def test_marketplace_from_api(self, fake):
        fake.routes = bare_routes()
        fake.routes[_get(f"repos/{R}/contents/.claude-plugin/marketplace.json")] = (200, {"name": "m"})
        assert gp.check_tag_rulesets(R)["marketplace"] is True

    def test_marketplace_absent_from_api(self, fake):
        fake.routes = bare_routes()
        assert gp.check_tag_rulesets(R)["marketplace"] is False

    def test_marketplace_from_working_tree(self, fake, tmp_path):
        (tmp_path / ".git").mkdir()
        (tmp_path / ".claude-plugin").mkdir()
        (tmp_path / ".claude-plugin" / "marketplace.json").write_text("{}")
        sub = tmp_path / "a" / "b"
        sub.mkdir(parents=True)
        fake.routes = bare_routes()
        assert gp.check_tag_rulesets(R, repo_path=sub)["marketplace"] is True
        assert not any("contents" in e for _, e, _ in fake.calls)

    def test_marketplace_clause_when_no_tag_ruleset(self, fake):
        fake.routes = bare_routes()
        fake.routes[_get(f"repos/{R}/contents/.claude-plugin/marketplace.json")] = (200, {})
        out = gp.describe_audit(gp.audit_posture(repo=R))
        line = next(l for l in out.splitlines() if "release tags" in l)
        assert line == ("  Rulesets on release tags (v*): 0 active; this repo ships a "
                        "marketplace.json, and consumer installs resolve from this tag")

    def test_no_clause_without_marketplace(self, fake):
        fake.routes = bare_routes()
        out = gp.describe_audit(gp.audit_posture(repo=R))
        assert "consumer installs" not in out


class TestDependabotAlerts:
    def test_204_on(self, fake):
        fake.routes[_get(f"repos/{R}/vulnerability-alerts")] = (204, None)
        assert gp.check_dependabot_alerts(R) == {"status": OK, "alerts": ON}

    def test_404_off(self, fake):
        fake.routes[_get(f"repos/{R}/vulnerability-alerts")] = (404, {"message": "Not Found"})
        assert gp.check_dependabot_alerts(R) == {"status": OK, "alerts": OFF}

    def test_403_unknown(self, fake):
        fake.routes[_get(f"repos/{R}/vulnerability-alerts")] = (403, {"message": "Forbidden"})
        assert gp.check_dependabot_alerts(R)["status"] == UNKNOWN

    def test_repo_404_stops_audit(self, fake):
        """The repo itself 404ing makes the whole audit unknown, so the
        alerts 404 is never read as off."""
        a = gp.audit_posture(repo=R)
        assert a["status"] == UNKNOWN and a["checks"] == {}
        assert gp.describe_audit(a) == "Per-call checks: unknown (HTTP 404)"


class TestActionsPolicy:
    def test_all(self, fake):
        fake.routes[_get(f"repos/{R}/actions/permissions")] = (200, {"enabled": True, "allowed_actions": "all"})
        assert gp.check_actions_policy(R) == {"status": OK, "enabled": True, "allowed_actions": "all"}

    def test_selected_reads_detail(self, fake):
        fake.routes = baseline_routes()
        fake.routes[_get(f"repos/{R}/actions/permissions/selected-actions")] = (
            200, {"github_owned_allowed": True, "verified_allowed": False,
                  "patterns_allowed": ["a/b@*", "c/d@*"]})
        c = gp.check_actions_policy(R)
        assert (c["github_owned_allowed"], c["verified_allowed"], c["patterns_allowed"]) == (True, False, 2)

    def test_selected_detail_unreadable(self, fake):
        fake.routes[_get(f"repos/{R}/actions/permissions")] = (200, {"enabled": True, "allowed_actions": "selected"})
        c = gp.check_actions_policy(R)
        assert c["github_owned_allowed"] == UNKNOWN

    @pytest.mark.parametrize("status", [403, 404])
    def test_non_2xx_unknown(self, fake, status):
        fake.routes[_get(f"repos/{R}/actions/permissions")] = (status, {"message": "x"})
        assert gp.check_actions_policy(R) == {"status": UNKNOWN, "reason": f"HTTP {status}"}


class TestWorkflowToken:
    def test_read(self, fake):
        fake.routes[_get(f"repos/{R}/actions/permissions/workflow")] = (
            200, {"default_workflow_permissions": "write", "can_approve_pull_request_reviews": True})
        c = gp.check_workflow_token(R)
        assert c == {"status": OK, "default_workflow_permissions": "write",
                     "can_approve_pull_request_reviews": True}

    @pytest.mark.parametrize("status", [403, 404])
    def test_non_2xx_unknown(self, fake, status):
        fake.routes[_get(f"repos/{R}/actions/permissions/workflow")] = (status, {"message": "x"})
        assert gp.check_workflow_token(R)["status"] == UNKNOWN


class TestWebhooks:
    def test_counts(self, fake):
        fake.routes[_get(f"repos/{R}/hooks?per_page=100")] = (200, [
            {"config": {"url": "https://a", "secret": "********", "insecure_ssl": "0"}},
            {"config": {"url": "https://b", "insecure_ssl": "1"}},
            {"config": {"url": "http://c", "insecure_ssl": "0"}},
        ])
        assert gp.check_webhooks(R) == {"status": OK, "count": 3, "no_secret": 2, "insecure_ssl": 1}

    @pytest.mark.parametrize("status", [403, 404])
    def test_non_2xx_unknown(self, fake, status):
        fake.routes[_get(f"repos/{R}/hooks?per_page=100")] = (status, {"message": "x"})
        assert gp.check_webhooks(R)["status"] == UNKNOWN


class TestDeployKeys:
    def test_counts(self, fake):
        fake.routes[_get(f"repos/{R}/keys?per_page=100")] = (200, [
            {"id": 1, "read_only": True}, {"id": 2, "read_only": False}])
        assert gp.check_deploy_keys(R) == {"status": OK, "count": 2, "writable": 1}

    @pytest.mark.parametrize("status", [403, 404])
    def test_non_2xx_unknown(self, fake, status):
        fake.routes[_get(f"repos/{R}/keys?per_page=100")] = (status, {"message": "x"})
        assert gp.check_deploy_keys(R)["status"] == UNKNOWN


class TestAuditPosture:
    def test_placeholder_endpoint_then_full_name(self, fake):
        routes = bare_routes()
        routes[_get("repos/{owner}/{repo}")] = routes[_get(f"repos/{R}")]
        fake.routes = routes
        a = gp.audit_posture()
        assert a["repo"] == R
        assert fake.calls[0][1] == "repos/{owner}/{repo}"
        assert all(e.startswith(f"repos/{R}") for _, e, _ in fake.calls[1:])

    def test_seven_checks_and_only_gets(self, fake):
        fake.routes = baseline_routes()
        a = gp.audit_posture(repo=R)
        assert set(a["checks"]) == {
            "branch_rulesets", "tag_rulesets", "dependabot_alerts", "actions",
            "workflow_token", "webhooks", "deploy_keys"}
        assert fake.writes == []

    def test_one_ruleset_listing(self, fake):
        fake.routes = baseline_routes()
        gp.audit_posture(repo=R)
        listings = [e for _, e, _ in fake.calls if e.endswith("/rulesets?per_page=100")]
        assert len(listings) == 1


class TestDescribeAudit:
    def test_baseline_block(self, fake):
        fake.routes = baseline_routes()
        assert gp.describe_audit(gp.audit_posture(repo=R)) == "\n".join([
            "Per-call checks (--audit only, not alerted on):",
            "  Rulesets on main: 1 active (blocks force pushes, blocks deletion; no pull request requirement)",
            "  Classic branch protection on main: none",
            "  Rulesets on release tags (v*): 1 active (blocks updates, blocks deletion)",
            "  Dependabot alerts: on",
            "  Actions: enabled, allowed actions selected (GitHub-owned allowed: yes, verified allowed: yes, patterns: 0)",
            "  Workflow token default: read; can approve pull requests: no",
            "  Webhooks: 0 (0 without a secret, 0 with SSL verification off)",
            "  Deploy keys: 0 (0 writable)",
        ])

    def test_unknown_and_plan_gated_lines(self, fake):
        msg = "Upgrade to GitHub Pro or make this repository public to enable this feature."
        fake.routes = bare_routes()
        fake.routes[_get(f"repos/{R}/rulesets?per_page=100")] = (403, {"message": msg})
        fake.routes[_get(f"repos/{R}/hooks?per_page=100")] = (403, {"message": "Must have admin rights"})
        out = gp.describe_audit(gp.audit_posture(repo=R)).splitlines()
        assert "  Rulesets on main: not available on this plan" in out
        assert "  Rulesets on release tags (v*): not available on this plan" in out
        assert "  Webhooks: unknown (HTTP 403)" in out

    def test_no_alert_vocabulary(self, fake):
        fake.routes = bare_routes()
        out = gp.describe_audit(gp.audit_posture(repo=R)).upper()
        for word in ("WARNING", "ACTION REQUIRED", "MISSING", "SHOULD", "UNPROTECTED"):
            assert word not in out


class TestDeepAudit:
    def test_running_count(self, fake):
        fake.routes = bare_routes()
        seen = []
        lines = gp.deep_audit([R, "o/gone"], progress=lambda i, n, r: seen.append((i, n, r)))
        assert seen == [(1, 2, R), (2, 2, "o/gone")]
        assert "\n[2/2] o/gone" in lines
        assert "Per-call checks: unknown (HTTP 404)" in lines


# ==========================================================================
# U3b: propose()
# ==========================================================================


def _ids(items, group=None):
    return [i["id"] for i in items if group is None or i["group"] == group]


class TestPropose:
    def test_baseline_has_no_default_items(self, fake):
        fake.routes = baseline_routes()
        items = gp.propose(gp.audit_posture(repo=R))
        assert _ids(items, "default") == []
        assert _ids(items, "consider") == ["ruleset-main-pr", "merge-commit-only"]

    def test_bare_repo_all_default_and_consider(self, fake):
        fake.routes = bare_routes()
        items = gp.propose(gp.audit_posture(repo=R))
        assert _ids(items, "default") == list(gp.DEFAULT_IDS)
        assert _ids(items, "consider") == ["ruleset-main-pr", "merge-commit-only"]

    def test_item_fields(self, fake):
        fake.routes = bare_routes()
        item = gp.propose(gp.audit_posture(repo=R))[0]
        assert set(item) >= {"id", "setting", "current", "proposed", "reason",
                             "consequence", "group"}
        assert item["consequence"] == "blocks force pushes to main and its deletion; direct pushes still work"

    def test_private_repo_adds_forking_off(self, fake):
        fake.routes = bare_routes(visibility="private")
        assert "forking-off" in _ids(gp.propose(gp.audit_posture(repo=R)), "consider")

    def test_existing_pull_request_rule_not_duplicated(self, fake):
        rs = copy.deepcopy(MAIN_RULESET)
        rs["rules"].append({"type": "pull_request", "parameters": {}})
        fake.routes = bare_routes()
        fake.routes[_get(f"repos/{R}/rulesets?per_page=100")] = (200, _listing(rs))
        fake.routes[_get(f"repos/{R}/rulesets/1")] = (200, rs)
        ids = _ids(gp.propose(gp.audit_posture(repo=R)))
        assert "ruleset-main" not in ids and "ruleset-main-pr" not in ids

    def test_pull_request_only_ruleset_proposes_main_once(self, fake):
        rs = copy.deepcopy(MAIN_RULESET)
        rs["rules"] = [{"type": "pull_request", "parameters": {}}]
        fake.routes = bare_routes()
        fake.routes[_get(f"repos/{R}/rulesets?per_page=100")] = (200, _listing(rs))
        fake.routes[_get(f"repos/{R}/rulesets/1")] = (200, rs)
        ids = _ids(gp.propose(gp.audit_posture(repo=R)))
        assert ids.count("ruleset-main") == 1 and "ruleset-main-pr" not in ids

    def test_merge_only_repo_gets_no_merge_item(self, fake):
        fake.routes = bare_routes(allow_squash_merge=False, allow_rebase_merge=False)
        assert "merge-commit-only" not in _ids(gp.propose(gp.audit_posture(repo=R)))

    def test_merge_methods_never_default(self, fake):
        fake.routes = bare_routes()
        items = gp.propose(gp.audit_posture(repo=R))
        for i in items:
            if i["id"] in ("merge-commit-only", "ruleset-main-pr", "forking-off"):
                assert i["group"] == "consider"

    def test_no_admin_no_proposal(self, fake):
        fake.routes = bare_routes(permissions={"admin": False, "push": True})
        audit = gp.audit_posture(repo=R)
        assert gp.propose(audit) == []
        assert gp.describe_proposal(audit, []) == (
            "Proposal: no proposal: your account does not administer this repo")

    def test_unreadable_check_not_proposed(self, fake):
        msg = "Upgrade to GitHub Pro or make this repository public to enable this feature."
        fake.routes = bare_routes(visibility="private")
        fake.routes[_get(f"repos/{R}/rulesets?per_page=100")] = (403, {"message": msg})
        items = gp.propose(gp.audit_posture(repo=R))
        assert "ruleset-main" not in _ids(items, "default")
        assert "ruleset-main" in _ids(items, "unreadable")
        out = gp.describe_proposal(gp.audit_posture(repo=R), items)
        assert "    ruleset-main: not available on this plan" in out

    def test_baseline_describe(self, fake):
        fake.routes = baseline_routes()
        audit = gp.audit_posture(repo=R)
        out = gp.describe_proposal(audit, gp.propose(audit))
        assert "  Default:\n    (none; already in place)" in out
        assert "    ruleset-main-pr: " in out


# ==========================================================================
# U3b: apply()
# ==========================================================================


def _make_applied(routes):
    """on_write handlers that move the fake repo toward the baseline, so the
    re-read after a write sees the new value."""
    def ruleset(fake, body):
        target = body["target"]
        rid = 1 if target == "branch" else 2
        stored = dict(body, id=rid)
        listing = fake.routes[_get(f"repos/{R}/rulesets?per_page=100")][1]
        fake.routes[_get(f"repos/{R}/rulesets?per_page=100")] = (200, listing + _listing(stored))
        fake.routes[_get(f"repos/{R}/rulesets/{rid}")] = (200, stored)

    def patch(fake, body):
        fake.routes[_get(f"repos/{R}")][1].update(body)

    routes[("POST", f"repos/{R}/rulesets")] = (201, {"id": 9})
    routes[("PATCH", f"repos/{R}")] = (200, {})
    routes[("PUT", f"repos/{R}/vulnerability-alerts")] = (204, None)
    return {("POST", f"repos/{R}/rulesets"): ruleset, ("PATCH", f"repos/{R}"): patch}


class TestApply:
    def test_unknown_id_writes_nothing(self, fake):
        fake.routes = bare_routes()
        out = gp.apply(R, ["wiki-off", "make-it-safe"])
        assert out["error"].startswith("unknown item id(s): make-it-safe; nothing applied.")
        assert fake.calls == []
        assert gp.describe_apply(out).startswith("Apply: unknown item id(s)")

    def test_no_ids_prints_proposal_writes_nothing(self, fake):
        fake.routes = bare_routes()
        out = gp.apply(R, [])
        assert fake.writes == []
        assert _ids(out["proposal"], "default") == list(gp.DEFAULT_IDS)
        text = gp.describe_apply(out)
        assert text.startswith("Apply: no item ids given; nothing applied.")
        assert "ruleset-main:" in text

    def test_two_ids_exact_writes_and_reread(self, fake):
        fake.routes = bare_routes()
        fake.on_write = _make_applied(fake.routes)
        # Given out of canonical order; written in canonical order.
        out = gp.apply(R, ["wiki-off", "ruleset-tags"])
        assert fake.writes == [
            ("POST", f"repos/{R}/rulesets", {
                "name": "protect release tags", "target": "tag", "enforcement": "active",
                "conditions": {"ref_name": {"include": ["refs/tags/v*"], "exclude": []}},
                "rules": [{"type": "deletion"}, {"type": "update"}],
            }),
            ("PATCH", f"repos/{R}", {"has_wiki": False}),
        ]
        by_id = {r["id"]: r for r in out["results"]}
        assert by_id["ruleset-tags"]["outcome"] == "applied"
        assert by_id["ruleset-tags"]["before"] == "0 active"
        assert by_id["ruleset-tags"]["after"] == "1 active (blocks updates and deletion)"
        assert (by_id["wiki-off"]["before"], by_id["wiki-off"]["after"]) == (ON, OFF)
        # Re-read through the audit's own GETs, after each write.
        gets = [e for m, e, _ in fake.calls if m == "GET"]
        post_i = fake.calls.index(fake.writes[0])
        assert f"repos/{R}/rulesets?per_page=100" in [
            e for m, e, _ in fake.calls[post_i + 1:] if m == "GET"]
        assert gets.count(f"repos/{R}") == 2  # audit, then re-read after PATCH

    def test_ruleset_main_exact_body(self, fake):
        fake.routes = bare_routes()
        fake.on_write = _make_applied(fake.routes)
        gp.apply(R, ["ruleset-main"])
        assert fake.writes == [("POST", f"repos/{R}/rulesets", {
            "name": "protect main", "target": "branch", "enforcement": "active",
            "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
            "rules": [{"type": "deletion"}, {"type": "non_fast_forward"}],
        })]
        assert not any(r["type"] == "pull_request" for r in fake.writes[0][2]["rules"])

    def test_every_default_write_call(self, fake):
        fake.routes = bare_routes()
        fake.on_write = _make_applied(fake.routes)
        for m, e in [("PUT", f"repos/{R}/automated-security-fixes"),
                     ("PUT", f"repos/{R}/actions/permissions"),
                     ("PUT", f"repos/{R}/actions/permissions/selected-actions")]:
            fake.routes[(m, e)] = (204, None)
        gp.apply(R, list(gp.DEFAULT_IDS))
        assert [(m, e) for m, e, _ in fake.writes] == [
            ("POST", f"repos/{R}/rulesets"),
            ("POST", f"repos/{R}/rulesets"),
            ("PUT", f"repos/{R}/vulnerability-alerts"),
            ("PUT", f"repos/{R}/automated-security-fixes"),
            ("PUT", f"repos/{R}/actions/permissions"),
            ("PUT", f"repos/{R}/actions/permissions/selected-actions"),
            ("PATCH", f"repos/{R}"),
            ("PATCH", f"repos/{R}"),
        ]
        bodies = [b for _, _, b in fake.writes]
        assert bodies[4] == {"enabled": True, "allowed_actions": "selected"}
        assert bodies[5] == {"github_owned_allowed": True, "verified_allowed": True,
                             "patterns_allowed": []}
        assert bodies[6] == {"delete_branch_on_merge": True}

    def test_already_set_is_noop(self, fake):
        fake.routes = baseline_routes()
        out = gp.apply(R, ["wiki-off"])
        assert fake.writes == []
        (r,) = out["results"]
        assert r["outcome"] == "already set" and r["before"] == r["after"] == OFF
        assert "already set; no change made" in gp.describe_apply(out)

    def test_baseline_default_set_six_noops(self, fake):
        fake.routes = baseline_routes()
        out = gp.apply(R, list(gp.DEFAULT_IDS))
        assert fake.writes == []
        assert {r["outcome"] for r in out["results"]} == {"already set"}

    def test_consider_item_only_when_named(self, fake):
        fake.routes = bare_routes()
        fake.on_write = _make_applied(fake.routes)
        gp.apply(R, ["wiki-off"])
        assert all(b != {"allow_merge_commit": True, "allow_squash_merge": False,
                         "allow_rebase_merge": False} for _, _, b in fake.writes)

    def test_failed_write_reported(self, fake):
        fake.routes = bare_routes()
        fake.routes[("PATCH", f"repos/{R}")] = (422, {"message": "Validation Failed"})
        out = gp.apply(R, ["wiki-off"])
        (r,) = out["results"]
        assert r["outcome"] == "not applied"
        assert r["message"] == f"PATCH repos/{R} returned HTTP 422: Validation Failed"
        assert r["after"] == ON

    def test_no_admin_applies_nothing(self, fake):
        fake.routes = bare_routes(permissions={"admin": False})
        out = gp.apply(R, ["wiki-off"])
        assert fake.writes == []
        assert out["error"] == "nothing applied: your account does not administer this repo"

    def test_forking_off_on_public_not_applicable(self, fake):
        fake.routes = bare_routes()
        out = gp.apply(R, ["forking-off"])
        assert fake.writes == []
        assert out["results"][0]["outcome"] == "not applied"


class TestNeverAtSessionStart:
    def test_session_start_does_not_import_audit_or_apply(self):
        import inspect
        import session_start
        src = inspect.getsource(session_start)
        for name in ("audit_posture", "apply(", "propose(", "_write_calls"):
            assert name not in src
