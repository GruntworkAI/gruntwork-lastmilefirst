"""Tests for per-org git identity enforcement.

Each test builds a throwaway workspace on disk with real git repos, because the
behavior under test is mostly *resolution* — which contract governs which
directory, and what the remotes actually say. Mocking git out would test the
mocks.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

import check_identity


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def make_repo(path: Path, name: str | None = None, email: str | None = None,
              remotes: dict[str, str] | None = None) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    # Always set locally: the machine's global identity must not leak into tests.
    subprocess.run(["git", "config", "user.name", name or "unset"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", email or "unset@example.com"],
                   cwd=path, check=True)
    for remote_name, url in (remotes or {}).items():
        subprocess.run(["git", "remote", "add", remote_name, url], cwd=path, check=True)
    return path


def write_org(org_dir: Path, name: str, identity: dict | None) -> Path:
    (org_dir / ".claude").mkdir(parents=True, exist_ok=True)
    config: dict = {"name": name}
    if identity is not None:
        config["identity"] = identity
    (org_dir / ".claude" / "org.json").write_text(json.dumps(config), encoding="utf-8")
    return org_dir


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


def check(repo: Path, workspace: Path):
    return check_identity.evaluate(cwd=repo, workspace_root=workspace, check_gh=False)


# --------------------------------------------------------------------------
# remote URL parsing
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "url,expected",
    [
        ("git@github.com:GruntworkAI/repo.git", "GruntworkAI"),
        ("git@github-personal:outsideshot/repo.git", "outsideshot"),
        ("https://github.com/andyfish3/heather-thomason-2026.git", "andyfish3"),
        ("ssh://git@github.com/owner/repo.git", "owner"),
        ("https://github.com/owner/repo", "owner"),
        ("/some/local/path", None),
        ("", None),
    ],
)
def test_remote_owner_parsing(url, expected):
    assert check_identity.remote_owner(url) == expected


def test_host_alias_does_not_change_owner():
    """The alias picks an SSH key; it says nothing about who owns the repo."""
    via_alias = check_identity.remote_owner("git@github-personal:andyfish3/site.git")
    via_host = check_identity.remote_owner("git@github.com:andyfish3/site.git")
    assert via_alias == via_host == "andyfish3"


# --------------------------------------------------------------------------
# governance boundary
# --------------------------------------------------------------------------

def test_repo_outside_workspace_is_skipped(tmp_path, workspace):
    outside = make_repo(tmp_path / "elsewhere" / "repo")
    assert check(outside, workspace).status == "skipped"


def test_not_a_repo_is_skipped(workspace):
    plain = workspace / "notarepo"
    plain.mkdir()
    assert check(plain, workspace).status == "skipped"


def test_unregistered_org_blocks(workspace):
    """A repo inside the workspace with no org.json above it must not commit.

    This is the case the whole check exists for: making a new org directory and
    committing before registering it is how work lands under the wrong identity.
    """
    repo = make_repo(workspace / "brand-new-org" / "site")
    result = check(repo, workspace)
    assert result.status == "blocked"
    assert "No org identity contract" in result.problems[0]


def test_org_json_without_identity_block_blocks(workspace):
    write_org(workspace / "someorg", "someorg", identity=None)
    repo = make_repo(workspace / "someorg" / "proj")
    result = check(repo, workspace)
    assert result.status == "blocked"
    assert "no `identity` block" in result.problems[0]


def test_incomplete_contract_blocks(workspace):
    write_org(workspace / "someorg", "someorg",
              {"github_account": "someone", "owns_remotes": []})
    repo = make_repo(workspace / "someorg" / "proj")
    result = check(repo, workspace)
    assert result.status == "blocked"
    assert "incomplete" in result.problems[0]


# --------------------------------------------------------------------------
# identity matching
# --------------------------------------------------------------------------

def test_matching_identity_passes(workspace):
    write_org(workspace / "outsideshot", "outsideshot", CONTRACT)
    repo = make_repo(workspace / "outsideshot" / "site",
                     name="outsideshot", email="outsideshot@gmail.com")
    result = check(repo, workspace)
    assert result.status == "ok", result.problems


def test_wrong_email_blocks_and_gives_the_command(workspace):
    write_org(workspace / "outsideshot", "outsideshot", CONTRACT)
    repo = make_repo(workspace / "outsideshot" / "site",
                     name="outsideshot", email="admin@gruntwork.ai")
    result = check(repo, workspace)
    assert result.status == "blocked"
    assert any("admin@gruntwork.ai" in p for p in result.problems)
    assert any('git config user.email "outsideshot@gmail.com"' in r
               for r in result.remedies)


def test_wrong_name_blocks(workspace):
    write_org(workspace / "outsideshot", "outsideshot", CONTRACT)
    repo = make_repo(workspace / "outsideshot" / "site",
                     name="GruntworkAI", email="outsideshot@gmail.com")
    result = check(repo, workspace)
    assert result.status == "blocked"
    assert any("Commit name" in p for p in result.problems)


def test_enforcement_warn_does_not_block(workspace):
    contract = {**CONTRACT, "enforcement": "warn"}
    write_org(workspace / "outsideshot", "outsideshot", contract)
    repo = make_repo(workspace / "outsideshot" / "site",
                     name="wrong", email="wrong@example.com")
    result = check(repo, workspace)
    assert result.status == "warned"
    assert result.exit_code == 0
    assert result.problems  # still reported, just not fatal


def test_enforcement_off_skips_entirely(workspace):
    contract = {**CONTRACT, "enforcement": "off"}
    write_org(workspace / "outsideshot", "outsideshot", contract)
    repo = make_repo(workspace / "outsideshot" / "site",
                     name="wrong", email="wrong@example.com")
    assert check(repo, workspace).status == "skipped"


def test_nearest_contract_wins(workspace):
    """A project may override its org."""
    write_org(workspace / "outsideshot", "outsideshot", CONTRACT)
    project = workspace / "outsideshot" / "special"
    write_org(project, "special", STUDIO)
    repo = make_repo(project, name="GruntworkAI", email="admin@gruntwork.ai")
    result = check(repo, workspace)
    assert result.status == "ok", result.problems


# --------------------------------------------------------------------------
# the cross-context guard
# --------------------------------------------------------------------------

def test_unclaimed_remote_owner_is_allowed(workspace):
    """Collaborating on someone else's repo is normal and must stay silent.

    The campaign case: the repo is owned by andyfish3, nobody claims that
    owner, and the commit identity is correct. An allowlist would block this.
    """
    write_org(workspace / "outsideshot", "outsideshot", CONTRACT)
    repo = make_repo(
        workspace / "outsideshot" / "site",
        name="outsideshot", email="outsideshot@gmail.com",
        remotes={
            "origin": "git@github-personal:outsideshot/site.git",
            "upstream": "git@github-personal:andyfish3/site.git",
        },
    )
    result = check(repo, workspace)
    assert result.status == "ok", result.problems


def test_remote_claimed_by_another_account_blocks(workspace):
    """Cross-context leakage: a GruntworkAI-claimed remote inside outsideshot."""
    write_org(workspace / "outsideshot", "outsideshot", CONTRACT)
    write_org(workspace / "gruntwork", "gruntwork", STUDIO)
    repo = make_repo(
        workspace / "outsideshot" / "site",
        name="outsideshot", email="outsideshot@gmail.com",
        remotes={"origin": "git@github.com:GruntworkAI/thing.git"},
    )
    result = check(repo, workspace)
    assert result.status == "blocked"
    assert any("claimed by GruntworkAI" in p for p in result.problems)


def test_two_orgs_sharing_one_account_is_not_a_conflict(workspace):
    """gruntwork/ and lastmilefirst.ai/ both push to GruntworkAI. That is fine.

    Claims are keyed by GitHub account, not by org directory, precisely so this
    real-world arrangement does not read as cross-context leakage.
    """
    write_org(workspace / "gruntwork", "gruntwork", STUDIO)
    write_org(workspace / "lastmilefirst.ai", "lastmilefirst.ai", STUDIO)
    repo = make_repo(
        workspace / "lastmilefirst.ai" / "advisors",
        name="GruntworkAI", email="admin@gruntwork.ai",
        remotes={"origin": "git@github.com:GruntworkAI/LMF-Advisors.git"},
    )
    result = check(repo, workspace)
    assert result.status == "ok", result.problems


def test_no_remote_yet_is_fine(workspace):
    """A freshly `git init`-ed repo has no remote and must not be blocked."""
    write_org(workspace / "outsideshot", "outsideshot", CONTRACT)
    repo = make_repo(workspace / "outsideshot" / "fresh",
                     name="outsideshot", email="outsideshot@gmail.com")
    assert check(repo, workspace).status == "ok"


# --------------------------------------------------------------------------
# robustness
# --------------------------------------------------------------------------

def test_malformed_org_json_is_treated_as_absent(workspace):
    """A broken config must not wedge every commit in the org."""
    org = workspace / "someorg"
    (org / ".claude").mkdir(parents=True)
    (org / ".claude" / "org.json").write_text("{ not json", encoding="utf-8")
    repo = make_repo(org / "proj")
    result = check(repo, workspace)
    # Falls through to "unregistered", which blocks — but with the actionable
    # message, rather than raising.
    assert result.status == "blocked"
    assert "No org identity contract" in result.problems[0]


def test_override_env_short_circuits(workspace, monkeypatch, tmp_path):
    write_org(workspace / "outsideshot", "outsideshot", CONTRACT)
    repo = make_repo(workspace / "outsideshot" / "site",
                     name="wrong", email="wrong@example.com")
    monkeypatch.setenv(check_identity.OVERRIDE_ENV, "1")
    monkeypatch.chdir(repo)
    monkeypatch.setattr(check_identity, "OVERRIDE_LOG", tmp_path / "overrides.log")
    assert check_identity.main(["--pre-commit"]) == 0
    # An override that leaves no trace is not an override.
    assert (tmp_path / "overrides.log").exists()


def test_gh_check_is_advisory_only(workspace, monkeypatch):
    """A mismatched gh account warns but never blocks — it cannot affect the commit."""
    write_org(workspace / "outsideshot", "outsideshot", CONTRACT)
    repo = make_repo(workspace / "outsideshot" / "site",
                     name="outsideshot", email="outsideshot@gmail.com")
    monkeypatch.setattr(check_identity, "gh_active_account", lambda: "GruntworkAI")
    result = check_identity.evaluate(cwd=repo, workspace_root=workspace, check_gh=True)
    assert result.status == "warned"
    assert result.exit_code == 0
    assert any("gh's active account" in w for w in result.warnings)


# --------------------------------------------------------------------------
# workspace type markers (hook side)
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "text,expected",
    [
        ("type: external\n", "external"),
        ("# comment\ntype: scratch\n", "scratch"),
        ("type: Studio\n", "studio"),
        ("type: external  # inline note\n", "external"),
        ("note: no type here\n", None),
        ("", None),
        ("  type: indented-is-not-top-level\n", None),
    ],
)
def test_workspace_type_parsing(tmp_path, text, expected):
    (tmp_path / ".claude-workspace").write_text(text, encoding="utf-8")
    assert check_identity.workspace_type(tmp_path) == expected


def test_no_marker_is_none(tmp_path):
    assert check_identity.workspace_type(tmp_path) is None


@pytest.mark.parametrize("marker_type", ["external", "scratch"])
def test_marked_dir_skips_the_check(workspace, marker_type):
    """every/ and drafts/ must not block commits, and must not be 'unregistered'."""
    org = workspace / "third-party"
    org.mkdir()
    (org / ".claude-workspace").write_text(f"type: {marker_type}\n", encoding="utf-8")
    repo = make_repo(org / "cloned", name="whoever", email="whoever@example.com")
    assert check(repo, workspace).status == "skipped"


def test_studio_marker_is_still_governed(workspace):
    org = workspace / "mine"
    org.mkdir()
    (org / ".claude-workspace").write_text("type: studio\n", encoding="utf-8")
    repo = make_repo(org / "proj")
    assert check(repo, workspace).status == "blocked"


def test_marker_exemption_is_inherited_by_nested_repos(workspace):
    org = workspace / "third-party"
    (org / "nested").mkdir(parents=True)
    (org / ".claude-workspace").write_text("type: external\n", encoding="utf-8")
    repo = make_repo(org / "nested" / "deep")
    assert check(repo, workspace).status == "skipped"


def test_marker_outside_workspace_is_not_consulted(workspace, tmp_path):
    """The walk stops at the workspace root; a stray marker above it is ignored."""
    (tmp_path / ".claude-workspace").write_text("type: scratch\n", encoding="utf-8")
    org = write_org(workspace / "outsideshot", "outsideshot", CONTRACT)
    repo = make_repo(org / "site", name="wrong", email="wrong@example.com")
    assert check(repo, workspace).status == "blocked"


# --------------------------------------------------------------------------
# hook-mode output discipline
# --------------------------------------------------------------------------

def test_pre_commit_mode_suppresses_the_gh_advisory(workspace, monkeypatch, capsys):
    """A clean commit must print nothing from this check.

    The gh advisory is accurate but unactionable at commit time, and would
    otherwise fire on every commit in an org whose account isn't the active
    one — training the user to ignore the check's output entirely.
    """
    write_org(workspace / "outsideshot", "outsideshot", CONTRACT)
    repo = make_repo(workspace / "outsideshot" / "site",
                     name="outsideshot", email="outsideshot@gmail.com")
    monkeypatch.setattr(check_identity, "gh_active_account", lambda: "GruntworkAI")
    monkeypatch.chdir(repo)

    code = check_identity.main(["--pre-commit", "--workspace-root", str(workspace)])
    captured = capsys.readouterr()
    assert code == 0
    assert captured.out == ""
    assert captured.err == ""


def test_non_hook_mode_still_reports_the_gh_advisory(workspace, monkeypatch, capsys):
    """Read deliberately rather than mid-commit, the advisory is still useful."""
    write_org(workspace / "outsideshot", "outsideshot", CONTRACT)
    repo = make_repo(workspace / "outsideshot" / "site",
                     name="outsideshot", email="outsideshot@gmail.com")
    monkeypatch.setattr(check_identity, "gh_active_account", lambda: "GruntworkAI")
    monkeypatch.chdir(repo)

    code = check_identity.main(["--workspace-root", str(workspace)])
    assert code == 0
    assert "gh's active account" in capsys.readouterr().out


def test_blocking_problems_still_print_in_hook_mode(workspace, monkeypatch, capsys):
    """Suppressing the advisory must not mute real failures."""
    write_org(workspace / "outsideshot", "outsideshot", CONTRACT)
    repo = make_repo(workspace / "outsideshot" / "site",
                     name="GruntworkAI", email="admin@gruntwork.ai")
    monkeypatch.setattr(check_identity, "gh_active_account", lambda: "GruntworkAI")
    monkeypatch.chdir(repo)

    code = check_identity.main(["--pre-commit", "--workspace-root", str(workspace)])
    captured = capsys.readouterr()
    assert code == 1
    assert "BLOCKED" in captured.err
    assert "gh's active account" not in captured.err
