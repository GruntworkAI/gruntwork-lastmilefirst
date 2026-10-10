"""Overwatch visibility drift: declared visibility vs what GitHub reports.

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


def test_match_is_silent(env):
    env.declared, env.github = "private", "private"
    assert session_start.check_visibility_drift() is None
    assert env.gh_calls == 1


def test_declared_private_github_public_alerts(env):
    env.declared, env.github = "private", "public"
    assert session_start.check_visibility_drift() == (
        "ACTION REQUIRED: this repo is declared private but GitHub reports public; "
        "run /run-scan-secrets --audit"
    )


def test_declared_public_github_private_alerts(env):
    env.declared, env.github = "public", "private"
    assert session_start.check_visibility_drift() == (
        "ACTION REQUIRED: this repo is declared public but GitHub reports private; "
        "run /run-scan-secrets --audit"
    )


def test_no_remote_is_silent(env):
    env.declared, env.github, env.remote = "private", "public", None
    assert session_start.check_visibility_drift() is None
    assert env.gh_calls == 0


def test_not_a_repo_is_silent(env):
    env.declared, env.github, env.in_repo = "private", "public", False
    assert session_start.check_visibility_drift() is None
    assert env.gh_calls == 0


def test_no_declaration_is_silent(env):
    env.declared, env.github = None, "public"
    assert session_start.check_visibility_drift() is None
    assert env.gh_calls == 0


def test_gh_unavailable_is_silent(env):
    env.declared, env.gh_missing = "private", True
    assert session_start.check_visibility_drift() is None


def test_gh_without_access_is_silent(env):
    env.declared, env.github = "private", None
    assert session_start.check_visibility_drift() is None


def test_answer_is_cached(env):
    env.declared, env.github = "private", "public"
    session_start.check_visibility_drift()
    entry = overwatch.get_scoped_state("repos", REPO_ROOT).get("github_visibility")
    assert entry["visibility"] == "PUBLIC"
    assert isinstance(entry["checked_at"], int)


def test_cache_hit_skips_gh(env):
    env.declared, env.github = "private", "private"
    overwatch.update_scoped_state(
        "repos", REPO_ROOT, "github_visibility",
        {"visibility": "PUBLIC", "checked_at": int(time.time())},
    )
    out = session_start.check_visibility_drift()
    assert env.gh_calls == 0
    assert out is not None and out.startswith(EXPECTED_PREFIX)


def test_stale_cache_refetches(env):
    env.declared, env.github = "private", "private"
    overwatch.update_scoped_state(
        "repos", REPO_ROOT, "github_visibility",
        {"visibility": "PUBLIC", "checked_at": int(time.time()) - 2 * 86400},
    )
    assert session_start.check_visibility_drift() is None
    assert env.gh_calls == 1


def test_unknown_answer_is_not_cached(env):
    env.declared, env.gh_missing = "private", True
    session_start.check_visibility_drift()
    assert overwatch.get_scoped_state("repos", REPO_ROOT).get("github_visibility") is None
