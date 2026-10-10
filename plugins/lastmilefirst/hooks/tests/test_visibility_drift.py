"""Overwatch visibility drift: declared visibility vs what GitHub reports.

Session start asks GitHub once (`_github_posture`) and hands the answer to
both the drift check and Check 8 (`_visibility_checks`, which `main` calls).
Every external call goes through `subprocess.run` (git for the repo root,
the remote, and the `lastmilefirst.visibility` declaration; `gh api` for
GitHub's answer), so one stand-in drives the whole check. State is written to
a tmp_path state dir, never the real one.
"""

from __future__ import annotations

import json
import subprocess
import time

import pytest

import overwatch
import session_start

REPO_ROOT = "/tmp/example-repo"
EXPECTED_PREFIX = "ACTION REQUIRED: this repo is declared"


class FakeEnv:
    """Answers the git and gh calls the drift check makes."""

    def __init__(self):
        self.in_repo = True
        self.remote = "git@github.com:example-org/example-repo.git"
        self.declared = None  # e.g. "private"
        self.github = None  # e.g. "public"; None with gh_missing False = no access
        self.gh_missing = False
        self.gh_calls = 0

    def run(self, args, *a, **kw):
        if args[:2] == ["git", "rev-parse"]:
            if not self.in_repo:
                return subprocess.CompletedProcess(args, 128, "", "not a git repo")
            return subprocess.CompletedProcess(args, 0, REPO_ROOT + "\n", "")
        if args[:2] == ["git", "remote"]:
            out = "origin\n" if self.remote else ""
            return subprocess.CompletedProcess(args, 0, out, "")
        if args[:2] == ["git", "config"]:
            if self.declared is None:
                return subprocess.CompletedProcess(args, 1, "", "")
            return subprocess.CompletedProcess(args, 0, self.declared + "\n", "")
        if args[:1] == ["gh"]:
            self.gh_calls += 1
            if self.gh_missing:
                raise FileNotFoundError("gh")
            if self.github is None:
                return subprocess.CompletedProcess(args, 1, "", "HTTP 404")
            payload = {"full_name": "example-org/example-repo",
                       "visibility": self.github}
            return subprocess.CompletedProcess(args, 0, json.dumps(payload), "")
        raise AssertionError(f"unexpected subprocess call: {args}")


@pytest.fixture
def env(tmp_path, monkeypatch):
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    monkeypatch.setattr(overwatch, "get_state_dir", lambda: state_dir)
    fake = FakeEnv()
    # subprocess is one module object, so this reaches scanner.py and
    # github_protections.py too.
    monkeypatch.setattr(session_start.subprocess, "run", fake.run)
    return fake


PROJECT = "example-org/example-repo"
PUBLIC_WARNING = "WARNING: PUBLIC repo"


def drift(alerts):
    """The drift alert among session start's visibility alerts, or None."""
    found = [a for a in alerts if a.startswith(EXPECTED_PREFIX)]
    assert len(found) <= 1
    return found[0] if found else None


def cache_entry(project_key=None):
    scope, key = ("projects", project_key) if project_key else ("repos", REPO_ROOT)
    return overwatch.get_scoped_state(scope, key).get("github_protections")


def seed_cache(visibility, project_key=None, age=0):
    scope, key = ("projects", project_key) if project_key else ("repos", REPO_ROOT)
    overwatch.update_scoped_state(scope, key, "github_protections", {
        "posture": {"repo": PROJECT, "visibility": visibility, "reason": None,
                    "scanning": "unknown", "push_protection": "unknown"},
        "checked_at": int(time.time()) - age,
    })


# --- the comparison -------------------------------------------------------------

def test_match_is_silent(env):
    env.declared, env.github = "private", "private"
    assert drift(session_start._visibility_checks(None)) is None
    assert env.gh_calls == 1


def test_declared_private_github_public_alerts(env):
    env.declared, env.github = "private", "public"
    assert drift(session_start._visibility_checks(None)) == (
        "ACTION REQUIRED: this repo is declared private but GitHub reports public; "
        "run /run-scan-secrets --audit"
    )


def test_declared_public_github_private_alerts(env):
    env.declared, env.github = "public", "private"
    assert drift(session_start._visibility_checks(None)) == (
        "ACTION REQUIRED: this repo is declared public but GitHub reports private; "
        "run /run-scan-secrets --audit"
    )


def test_no_remote_is_silent(env):
    env.declared, env.github, env.remote = "private", "public", None
    assert drift(session_start._visibility_checks(None)) is None
    assert env.gh_calls == 0


def test_not_a_repo_is_silent(env):
    env.declared, env.github, env.in_repo = "private", "public", False
    assert drift(session_start._visibility_checks(None)) is None
    assert env.gh_calls == 0


def test_no_declaration_is_silent(env):
    env.declared, env.github = None, "public"
    assert drift(session_start._visibility_checks(None)) is None


def test_no_declaration_compares_nothing(env):
    env.declared = None
    assert session_start.check_visibility_drift(github_visibility="PUBLIC") is None


def test_gh_unavailable_is_silent(env):
    env.declared, env.gh_missing = "private", True
    assert drift(session_start._visibility_checks(None)) is None


def test_gh_without_access_is_silent(env):
    env.declared, env.github = "private", None
    assert drift(session_start._visibility_checks(None)) is None


# --- one fetch, shared ------------------------------------------------------------

@pytest.mark.parametrize("project_key", [None, PROJECT])
def test_one_gh_call_serves_both_checks(env, project_key):
    env.declared, env.github = "private", "public"
    alerts = session_start._visibility_checks(project_key)
    assert drift(alerts) is not None
    assert any(a.startswith(PUBLIC_WARNING) for a in alerts)
    assert env.gh_calls == 1


@pytest.mark.parametrize("project_key", [None, PROJECT])
def test_cache_hit_skips_gh(env, project_key):
    env.declared, env.github = "private", "private"
    seed_cache("PUBLIC", project_key)
    out = drift(session_start._visibility_checks(project_key))
    assert env.gh_calls == 0
    assert out is not None and out.startswith(EXPECTED_PREFIX)


def test_inside_a_project_the_check8_cache_is_the_one_used(env):
    """Check 8's per-project posture cache is the only cache in a project."""
    env.declared, env.github = "private", "private"
    session_start._visibility_checks(PROJECT)
    assert session_start._cached_posture(PROJECT, int(time.time()))["visibility"] == "PRIVATE"
    assert cache_entry(None) is None


@pytest.mark.parametrize("project_key", [None, PROJECT])
def test_stale_cache_refetches(env, project_key):
    env.declared, env.github = "private", "private"
    seed_cache("PUBLIC", project_key, age=2 * 86400)
    assert drift(session_start._visibility_checks(project_key)) is None
    assert env.gh_calls == 1


@pytest.mark.parametrize("project_key", [None, PROJECT])
def test_matching_answer_is_cached(env, project_key):
    env.declared, env.github = "private", "private"
    session_start._visibility_checks(project_key)
    entry = cache_entry(project_key)
    assert entry["posture"]["visibility"] == "PRIVATE"
    assert isinstance(entry["checked_at"], int)


@pytest.mark.parametrize("project_key", [None, PROJECT])
def test_mismatching_answer_is_not_cached(env, project_key):
    """After the remedy, the next session re-checks instead of alerting for a day."""
    env.declared, env.github = "private", "public"
    assert drift(session_start._visibility_checks(project_key)) is not None
    assert cache_entry(project_key) is None
    env.github = "private"
    assert drift(session_start._visibility_checks(project_key)) is None
    assert env.gh_calls == 2


@pytest.mark.parametrize("project_key", [None, PROJECT])
def test_unknown_answer_is_not_cached_when_declared(env, project_key):
    env.declared, env.gh_missing = "private", True
    session_start._visibility_checks(project_key)
    assert cache_entry(project_key) is None
