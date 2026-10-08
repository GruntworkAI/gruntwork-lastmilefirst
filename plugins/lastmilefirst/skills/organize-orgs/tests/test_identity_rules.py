"""Pure identity rules and deliberate hook/bounded-audit policy differences."""
from pathlib import Path
import subprocess
import sys

import pytest

import check_identity as identity


CONTRACT = {
    "github_account": "example-dev",
    "git_user_name": "Example Developer",
    "git_email": "developer@example.invalid",
    "owns_remotes": ["ExampleOrg"],
}


@pytest.mark.parametrize(
    "text,default,strict",
    [
        ("type: Client # note\n", "client", "client"),
        ("type: future-type\n", "future-type", None),
        ("type: external\ntype: studio\n", "external", None),
        ("type: external\ntype: external\n", "external", None),
        ("type: \ntype: scratch\n", None, None),
        ('type: "external"\n', '"external"', None),
        ("# type: scratch\n  type: scratch\n\ttype: scratch\ntype: studio\n", "studio", "studio"),
        ("description: example\n", None, None),
    ],
)
def test_marker_policy_is_explicit(text, default, strict):
    assert identity.parse_workspace_type(text) == default
    assert identity.parse_workspace_type(text, strict=True) == strict


@pytest.mark.parametrize(
    "changes,default_status,strict_status,missing,invalid_enforcement,invalid_owners",
    [
        ({}, "valid", "valid", (), False, False),
        ({"github_account": 7}, "valid", "invalid", ("github_account",), False, False),
        ({"git_email": "  "}, "valid", "invalid", ("git_email",), False, False),
        ({"git_user_name": " REPLACE_ME "}, "valid", "invalid", ("git_user_name",), False, False),
        ({"git_user_name": 0}, "invalid", "invalid", ("git_user_name",), False, False),
        ({"enforcement": "future-mode"}, "valid", "invalid", (), True, False),
        ({"enforcement": None}, "valid", "invalid", (), True, False),
        ({"enforcement": " WARN "}, "valid", "invalid", (), True, False),
        ({"enforcement": "WARN"}, "valid", "valid", (), False, False),
        ({"owns_remotes": "org"}, "valid", "invalid", (), False, True),
        ({"owns_remotes": None}, "valid", "invalid", (), False, True),
        ({"owns_remotes": [3]}, "valid", "invalid", (), False, True),
        ({"owns_remotes": [""]}, "valid", "invalid", (), False, True),
        # Historical strict owner validation checks nonempty, not stripped text.
        ({"owns_remotes": [" "]}, "valid", "valid", (), False, False),
        ({"enforcement": "OFF", "git_email": None, "owns_remotes": 3},
         "disabled", "disabled", (), False, False),
    ],
)
def test_contract_policy_is_explicit(changes, default_status, strict_status, missing,
                                     invalid_enforcement, invalid_owners):
    config = {"identity": {**CONTRACT, **changes}}
    default = identity.inspect_identity_contract(config)
    strict = identity.inspect_identity_contract(config, strict=True)
    assert default.status == default_status
    assert strict == identity.ContractSummary(
        strict_status,
        (config["identity"].get("enforcement", "block").lower()
         if isinstance(config["identity"].get("enforcement", "block"), str) else None),
        missing, invalid_enforcement, invalid_owners,
    )
    assert default.enforcement == str(config["identity"].get("enforcement", "block")).lower()


@pytest.mark.parametrize("config", [None, {}, {"identity": {}}, {"identity": []}])
def test_missing_identity_block_in_both_policies(config):
    for strict in (False, True):
        assert identity.inspect_identity_contract(config, strict=strict) == identity.ContractSummary("missing", None)


def test_claims_retain_hook_coercion_but_strict_sources_are_rejected():
    configs = [
        ("valid", {"identity": CONTRACT}),
        ("same-account", {"identity": {**CONTRACT, "owns_remotes": ["exampleorg"]}}),
        ("numeric", {"identity": {"github_account": 7, "owns_remotes": [5]}}),
        ("iterable", {"identity": {"github_account": "second", "owns_remotes": "AB"}}),
        ("null-owners", {"identity": {"github_account": "third", "owns_remotes": None}}),
        ("missing-account", {"identity": {}}),
        ("no-identity", {}),
    ]
    permissive = identity.collect_claims(configs)
    assert permissive.claims == {"exampleorg": {"example-dev"}, "5": {"7"}, "a": {"second"}, "b": {"second"}}
    assert permissive.invalid_sources == ()
    strict = identity.collect_claims(configs, strict=True)
    assert strict.claims == {"exampleorg": {"example-dev"}}
    assert strict.invalid_sources == ("numeric", "iterable", "null-owners", "missing-account")


def test_claims_are_not_full_contract_validation():
    config = {"identity": {"github_account": "REPLACE_ME", "owns_remotes": [" "], "enforcement": "off"}}
    assert identity.collect_claims([("source", config)], strict=True).claims == {" ": {"REPLACE_ME"}}
    assert identity.collect_claims([("source", {"identity": {"github_account": "owner"}})], strict=True).invalid_sources == ()


def test_default_malformed_input_exceptions_are_not_silently_changed():
    with pytest.raises(AttributeError):
        identity.inspect_identity_contract([])
    with pytest.raises(AttributeError):
        identity.collect_claims([("bad-root", [1])])
    with pytest.raises(TypeError):
        identity.collect_claims([("bad-owners", {"identity": {"github_account": "account", "owns_remotes": 4}})])


def test_identity_absent_local_keys_and_unset_effective_values_are_distinct():
    assert identity.compare_identity_fields(CONTRACT, {}) == identity.IdentityComparison((), ("user.name", "user.email"))
    assert identity.compare_identity_fields(CONTRACT, {"user.name": None, "user.email": None}) == identity.IdentityComparison(("user.name", "user.email"), ())
    assert identity.compare_identity_fields(CONTRACT, {"user.name": CONTRACT["git_user_name"], "user.email": "wrong"}) == identity.IdentityComparison(("user.email",), ())


@pytest.mark.parametrize(
    "url,account,claims,expected",
    [
        ("git@host-alias:ExampleOrg/repo.git", "example-dev", {"exampleorg": {"example-dev"}},
         identity.RemoteClaim("ExampleOrg", ("example-dev",), False)),
        ("https://github.com/ExampleOrg/repo.git", "example-dev", {"exampleorg": {"other", "example-dev"}},
         identity.RemoteClaim("ExampleOrg", ("example-dev", "other"), False)),
        ("ssh://git@github.com/ExampleOrg/repo.git", "Example-Dev", {"exampleorg": {"example-dev"}},
         identity.RemoteClaim("ExampleOrg", ("example-dev",), True)),
        ("https://github.com/unclaimed/repo.git", "example-dev", {},
         identity.RemoteClaim("unclaimed", (), False)),
        ("/local/repo", "example-dev", {}, identity.RemoteClaim(None, (), False)),
    ],
)
def test_remote_claim_rules(url, account, claims, expected):
    assert identity.inspect_remote_claim(url, account, claims) == expected


def test_governing_selection_uses_only_supplied_nearest_first_candidates():
    project, org = Path("/unread/project"), Path("/unread")
    candidates = [(project, True, None), (org, True, {"identity": CONTRACT})]
    assert identity.select_governing_org(candidates) == (org, candidates[1][2])
    assert identity.select_governing_org(candidates, stop_on_malformed=True) == (project, None)
    assert identity.select_governing_org([(project, False, None)]) == (None, None)
    # An empty parsed config governs and reports a missing identity block.
    assert identity.select_governing_org([(project, True, {})]) == (project, {})


def test_governing_and_marker_selection_stop_reading_after_the_first_match():
    first = Path("/not-accessed")

    def candidates():
        yield first, True, {}
        raise AssertionError("Read beyond the governing candidate")

    def markers():
        yield first, "scratch"
        raise AssertionError("Read beyond the exemption")

    assert identity.select_governing_org(candidates()) == (first, {})
    assert identity.select_ungoverned_ancestor(markers()) == first
    assert identity.select_ungoverned_ancestor([(first, "client"), (first.parent, "external")]) == first.parent


def test_pure_helpers_never_read_or_resolve_paths(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Pure rules must not access the filesystem")

    for name in ("read_text", "resolve", "is_file", "is_dir", "exists", "iterdir"):
        monkeypatch.setattr(Path, name, forbidden)
    path = Path("/not-read")
    assert identity.parse_workspace_type("type: external", strict=True) == "external"
    assert identity.inspect_identity_contract({"identity": CONTRACT}).status == "valid"
    claims = identity.collect_claims([(path, {"identity": CONTRACT})]).claims
    assert not identity.inspect_remote_claim("git@github.com:ExampleOrg/repo", "example-dev", claims).conflict
    assert identity.select_governing_org([(path, True, {})]) == (path, {})
    assert identity.select_ungoverned_ancestor([(path, "external")]) == path


def test_hook_remains_runnable_as_a_single_stdlib_script(tmp_path):
    script = tmp_path / "check_identity.py"
    script.write_text(Path(identity.__file__).read_text(), encoding="utf-8")
    completed = subprocess.run(
        [sys.executable, "-S", str(script), "--json", "--workspace-root", str(tmp_path)],
        cwd=tmp_path, text=True, capture_output=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert '"status": "skipped"' in completed.stdout


def test_evaluate_preserves_unset_messages_order_and_unknown_enforcement(monkeypatch):
    root, org = Path("/workspace/org/project"), Path("/workspace/org")
    monkeypatch.setattr(identity, "repo_root", lambda cwd: root)
    monkeypatch.setattr(identity, "is_under", lambda *args: True)
    monkeypatch.setattr(identity, "ungoverned_ancestor", lambda *args: None)
    monkeypatch.setattr(identity, "find_governing_org", lambda *args: (org, {"name": "example", "identity": {**CONTRACT, "enforcement": "future"}}))
    monkeypatch.setattr(identity, "effective_identity", lambda cwd: (None, None))
    monkeypatch.setattr(identity, "collect_account_claims", lambda root: {"elsewhere": {"second"}})
    monkeypatch.setattr(identity, "remotes", lambda cwd: {"origin": "git@github.com:Elsewhere/repo"})
    result = identity.evaluate(cwd=root, workspace_root=Path("/workspace"), check_gh=False)
    assert result.to_dict() == {
        "status": "warned", "org": "example", "enforcement": "future",
        "problems": [
            "Commit email is (unset), but org 'example' requires developer@example.invalid.",
            "Commit name is (unset), but org 'example' requires Example Developer.",
            "Remote 'origin' points at Elsewhere/, which is claimed by second — but this directory is governed by example-dev.",
        ],
        "warnings": [],
        "remedies": [
            'git config user.email "developer@example.invalid"',
            'git config user.name "Example Developer"',
            "Move the repo under the second org, or fix the remote for 'origin'.",
        ],
    }
