"""The pre-push scan (plan 2026-10-09-001, section 3.4, U3).

Git hands a pre-push hook one line per ref on stdin:
`<local ref> <local sha> <remote ref> <remote sha>`. A deleted ref is skipped,
a new remote ref is a first push (everything reachable from the local sha,
plus the first-push audit), and an existing ref scans `remote..local` only.

The unit tests replace gitleaks, the merged config, `gh`, and the hygiene
checks with stand-ins, the same way test_visibility_policy.py does. One
end-to-end test at the bottom performs a real `git push` between two tmp_path
repos through the generated dispatcher, with HOME and the git config pointed
into tmp_path so nothing on this machine is read or changed.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

import hook_installer
import scanner

ZERO = "0" * 40
LOCAL = "a" * 40
REMOTE = "b" * 40
OTHER = "c" * 40

ORDINARY = {"RuleID": "generic-api-key", "File": "config.py", "StartLine": 9,
            "Severity": "HIGH", "Tags": [], "Fingerprint": "f1"}
PII = {"RuleID": "lmf-pii-personal-email", "File": "notes.md", "StartLine": 5,
       "Severity": "LOW", "Tags": ["pii"], "Fingerprint": "f2"}


def line(local_ref, local_sha, remote_ref, remote_sha):
    return f"{local_ref} {local_sha} {remote_ref} {remote_sha}\n"


# --- stdin parsing -------------------------------------------------------------

def test_new_remote_ref_is_a_first_push():
    [ref] = scanner.parse_pre_push_lines(line("refs/heads/main", LOCAL, "refs/heads/main", ZERO))
    assert ref["kind"] == "new"
    assert ref["local_sha"] == LOCAL


def test_existing_remote_ref_is_a_range():
    [ref] = scanner.parse_pre_push_lines(line("refs/heads/main", LOCAL, "refs/heads/main", REMOTE))
    assert ref["kind"] == "existing"
    assert ref["remote_sha"] == REMOTE


def test_deleted_ref_is_marked_deleted():
    [ref] = scanner.parse_pre_push_lines(line("(delete)", ZERO, "refs/heads/old", REMOTE))
    assert ref["kind"] == "deleted"


def test_several_lines_and_blank_lines():
    text = (line("refs/heads/main", LOCAL, "refs/heads/main", REMOTE)
            + "\n"
            + line("refs/heads/feature", OTHER, "refs/heads/feature", ZERO)
            + line("(delete)", ZERO, "refs/heads/old", REMOTE))
    kinds = [r["kind"] for r in scanner.parse_pre_push_lines(text)]
    assert kinds == ["existing", "new", "deleted"]


def test_malformed_line_is_refused():
    with pytest.raises(ValueError):
        scanner.parse_pre_push_lines("refs/heads/main only-two\n")


# --- the scan, with stand-ins ----------------------------------------------------

@pytest.fixture
def push_env(tmp_path, monkeypatch):
    """Stand-ins for gitleaks, config, gh, and the hygiene checks.

    `state["rows"]` is what gitleaks reports; `state["log_opts"]` records the
    range each gitleaks call was handed; the extras record their calls.
    """
    config = tmp_path / "merged.toml"
    state = {"rows": [], "log_opts": [], "args": [], "posture_calls": 0,
             "hygiene_calls": 0, "declared": None, "github": None,
             "hygiene": [], "known": {LOCAL, REMOTE, OTHER}, "floor": [],
             "by_repo": {}, "posture_repos": [], "reason": None}

    def write_config(*_a, **_k):
        config.write_text("")
        return config

    def run(args, config_path=None, cwd=None):
        state["args"].append(list(args))
        state["log_opts"].append(args[args.index("--log-opts") + 1])
        Path(args[args.index("--report-path") + 1]).write_text(json.dumps(state["rows"]))
        return (1 if state["rows"] else 0), "", ""

    def posture(_repo_path=None, repo=None):
        """The clone's default repo answers `state["github"]`; a named repo
        answers from `state["by_repo"]` (absent means no answer)."""
        state["posture_calls"] += 1
        state["posture_repos"].append(repo)
        visibility = state["by_repo"].get(repo) if repo else state["github"]
        reason = None if visibility else (state["reason"] or "no remote, no access, or repo not found")
        return {"visibility": visibility, "repo": repo or "example/repo",
                "scanning": "unknown", "push_protection": "unknown", "reason": reason}

    def hygiene(_repo=None):
        state["hygiene_calls"] += 1
        return list(state["hygiene"])

    def check(*args, **_kwargs):
        state["floor"].append(args)
        return None

    monkeypatch.setattr(scanner, "_check_gitleaks", check)
    monkeypatch.setattr(scanner, "write_merged_config", write_config)
    monkeypatch.setattr(scanner, "consume_sync_note", lambda: None)
    monkeypatch.setattr(scanner, "_run_gitleaks", run)
    monkeypatch.setattr(scanner, "declared_visibility", lambda _repo=None: state["declared"])
    monkeypatch.setattr(scanner, "check_repo_visibility",
                        lambda _repo=None: state["declared"] or state["github"])
    monkeypatch.setattr(scanner, "_fetch_github_posture", posture)
    monkeypatch.setattr(scanner, "_hygiene_warnings", hygiene)
    monkeypatch.setattr(scanner, "_describe_github_posture", lambda p: "GitHub protections: (stand-in)")
    monkeypatch.setattr(scanner, "_commit_exists", lambda sha, _cwd=None: sha in state["known"])
    return state


def test_existing_ref_hands_gitleaks_the_range(push_env, tmp_path):
    code, _ = scanner.scan_pushed(line("refs/heads/main", LOCAL, "refs/heads/main", REMOTE), tmp_path)
    assert code == 0
    assert push_env["log_opts"] == [f"{REMOTE}..{LOCAL}"]
    assert push_env["args"][0][0] == "git"


def test_new_ref_scans_only_commits_not_already_on_a_remote(push_env, tmp_path):
    scanner.scan_pushed(line("refs/heads/main", LOCAL, "refs/heads/main", ZERO), tmp_path)
    assert push_env["log_opts"] == [f"{LOCAL} --not --remotes"]


def test_several_new_refs_share_one_gitleaks_run(push_env, tmp_path):
    text = (line("refs/heads/main", LOCAL, "refs/heads/main", ZERO)
            + line("refs/heads/feature", OTHER, "refs/heads/feature", ZERO))
    scanner.scan_pushed(text, tmp_path)
    assert push_env["log_opts"] == [f"{LOCAL} {OTHER} --not --remotes"]


def test_one_finding_from_the_batched_run_is_reported_once(push_env, tmp_path):
    push_env["rows"].extend([dict(ORDINARY), dict(ORDINARY)])
    text = (line("refs/heads/main", LOCAL, "refs/heads/main", ZERO)
            + line("refs/heads/feature", OTHER, "refs/heads/feature", ZERO))
    _, report = scanner.scan_pushed(text, tmp_path)
    assert "1 blocking finding(s)" in report


def test_deleted_ref_is_not_scanned(push_env, tmp_path):
    code, _ = scanner.scan_pushed(line("(delete)", ZERO, "refs/heads/old", REMOTE), tmp_path)
    assert code == 0
    assert push_env["log_opts"] == []


def test_each_line_gets_its_own_range(push_env, tmp_path):
    text = (line("refs/heads/main", LOCAL, "refs/heads/main", REMOTE)
            + line("refs/heads/feature", OTHER, "refs/heads/feature", ZERO)
            + line("(delete)", ZERO, "refs/heads/old", REMOTE))
    scanner.scan_pushed(text, tmp_path)
    assert push_env["log_opts"] == [f"{REMOTE}..{LOCAL}", f"{OTHER} --not --remotes"]


def test_unknown_remote_sha_widens_to_the_local_history(push_env, tmp_path):
    """gitleaks exits 0 with an empty report on an invalid range (8.30.1), so a
    remote sha this clone never fetched would otherwise scan nothing."""
    push_env["known"] = {LOCAL}
    scanner.scan_pushed(line("refs/heads/main", LOCAL, "refs/heads/main", REMOTE), tmp_path)
    assert push_env["log_opts"] == [f"{LOCAL} --not --remotes"]


def test_the_log_opts_floor_is_requested(push_env, tmp_path):
    scanner.scan_pushed(line("refs/heads/main", LOCAL, "refs/heads/main", REMOTE), tmp_path)
    assert push_env["floor"] and push_env["floor"][0][0] == scanner.LOG_OPTS_MIN_GITLEAKS_VERSION


def test_blocking_finding_blocks_the_push(push_env, tmp_path):
    push_env["rows"].append(dict(ORDINARY))
    push_env["declared"] = "PRIVATE"
    code, report = scanner.scan_pushed(line("refs/heads/main", LOCAL, "refs/heads/main", REMOTE), tmp_path)
    assert code == 1
    assert "1 blocking finding(s)" in report


def test_warnings_only_push_is_allowed(push_env, tmp_path):
    push_env["rows"].append(dict(PII))
    push_env["declared"] = "PRIVATE"
    code, report = scanner.scan_pushed(line("refs/heads/main", LOCAL, "refs/heads/main", REMOTE), tmp_path)
    assert code == 0
    assert "WARNING" in report
    assert "1 warning(s)" in report


def test_the_same_finding_across_two_refs_is_reported_once(push_env, tmp_path):
    push_env["rows"].append(dict(ORDINARY))
    text = (line("refs/heads/main", LOCAL, "refs/heads/main", REMOTE)
            + line("refs/heads/feature", OTHER, "refs/heads/feature", REMOTE))
    _, report = scanner.scan_pushed(text, tmp_path)
    assert "1 blocking finding(s)" in report


def test_missing_report_fails_closed(push_env, tmp_path, monkeypatch):
    monkeypatch.setattr(scanner, "_run_gitleaks", lambda *a, **k: (1, "", "config error"))
    code, report = scanner.scan_pushed(line("refs/heads/main", LOCAL, "refs/heads/main", REMOTE), tmp_path)
    assert code == 1
    assert "did not complete" in report


def test_gitleaks_unavailable_blocks(push_env, tmp_path, monkeypatch):
    monkeypatch.setattr(scanner, "_check_gitleaks", lambda *a, **k: "gitleaks is not installed.")
    code, report = scanner.scan_pushed(line("refs/heads/main", LOCAL, "refs/heads/main", REMOTE), tmp_path)
    assert code == 1
    assert "not installed" in report


def test_malformed_stdin_blocks(push_env, tmp_path):
    code, _ = scanner.scan_pushed("garbage\n", tmp_path)
    assert code == 1


def test_empty_stdin_allows(push_env, tmp_path):
    code, _ = scanner.scan_pushed("", tmp_path)
    assert code == 0
    assert push_env["log_opts"] == []


# --- first-push extras -------------------------------------------------------------

def test_extras_run_only_on_a_new_ref(push_env, tmp_path):
    scanner.scan_pushed(line("refs/heads/main", LOCAL, "refs/heads/main", REMOTE), tmp_path)
    assert push_env["posture_calls"] == 0
    assert push_env["hygiene_calls"] == 0
    scanner.scan_pushed(line("refs/heads/main", LOCAL, "refs/heads/main", ZERO), tmp_path)
    assert push_env["posture_calls"] == 1
    assert push_env["hygiene_calls"] == 1


def test_extras_run_once_for_several_new_refs(push_env, tmp_path):
    text = (line("refs/heads/main", LOCAL, "refs/heads/main", ZERO)
            + line("refs/heads/feature", OTHER, "refs/heads/feature", ZERO))
    scanner.scan_pushed(text, tmp_path)
    assert push_env["posture_calls"] == 1
    assert push_env["hygiene_calls"] == 1


def test_hygiene_gaps_warn_without_blocking(push_env, tmp_path):
    push_env["hygiene"] = ["WARNING: .gitignore is missing 2 required pattern(s): .env, *.pem"]
    code, report = scanner.scan_pushed(line("refs/heads/main", LOCAL, "refs/heads/main", ZERO), tmp_path)
    assert code == 0
    assert ".gitignore is missing" in report


def test_declared_private_but_github_public_blocks_with_the_remedy(push_env, tmp_path):
    push_env["declared"] = "PRIVATE"
    push_env["github"] = "PUBLIC"
    code, report = scanner.scan_pushed(line("refs/heads/main", LOCAL, "refs/heads/main", ZERO), tmp_path)
    assert code == 1
    assert "declared PRIVATE" in report
    assert "GitHub reports PUBLIC" in report
    assert "gh repo edit --visibility private" in report
    assert "git config lastmilefirst.visibility public" in report


def test_declared_public_but_github_private_warns(push_env, tmp_path):
    push_env["declared"] = "PUBLIC"
    push_env["github"] = "PRIVATE"
    code, report = scanner.scan_pushed(line("refs/heads/main", LOCAL, "refs/heads/main", ZERO), tmp_path)
    assert code == 0
    assert "WARNING" in report
    assert "declared PUBLIC" in report


@pytest.mark.parametrize("declared,github", [(None, "PUBLIC"), (None, None),
                                             ("PRIVATE", "PRIVATE"), ("PUBLIC", "PUBLIC")])
def test_no_mismatch_is_not_a_finding(push_env, tmp_path, declared, github):
    push_env["declared"] = declared
    push_env["github"] = github
    code, report = scanner.scan_pushed(line("refs/heads/main", LOCAL, "refs/heads/main", ZERO), tmp_path)
    assert code == 0
    assert "declared" not in report


def test_unconfirmed_declaration_warns_without_blocking(push_env, tmp_path):
    push_env["declared"] = "PRIVATE"
    push_env["github"] = None
    push_env["reason"] = "gh unavailable or timed out"
    code, report = scanner.scan_pushed(line("refs/heads/main", LOCAL, "refs/heads/main", ZERO), tmp_path)
    assert code == 0
    assert ("WARNING: declared PRIVATE; GitHub could not confirm it (gh unavailable or timed out), "
            "so the declaration was not verified.") in report


def test_unconfirmed_declaration_without_a_posture_module_says_no_answer(push_env, tmp_path, monkeypatch):
    push_env["declared"] = "INTERNAL"
    monkeypatch.setattr(scanner, "_fetch_github_posture", lambda *_a, **_k: None)
    code, report = scanner.scan_pushed(line("refs/heads/main", LOCAL, "refs/heads/main", ZERO), tmp_path)
    assert code == 0
    assert "GitHub could not confirm it (no answer)" in report


def test_mismatch_is_not_checked_on_a_range_push(push_env, tmp_path):
    push_env["declared"] = "PRIVATE"
    push_env["github"] = "PUBLIC"
    code, _ = scanner.scan_pushed(line("refs/heads/main", LOCAL, "refs/heads/main", REMOTE), tmp_path)
    assert code == 0


def test_public_repo_first_push_shows_posture_as_a_warning(push_env, tmp_path):
    push_env["github"] = "PUBLIC"
    code, report = scanner.scan_pushed(line("refs/heads/main", LOCAL, "refs/heads/main", ZERO), tmp_path)
    assert code == 0
    assert "GitHub protections: (stand-in)" in report
    assert "WARNING" in report


def test_private_repo_first_push_does_not_show_posture(push_env, tmp_path):
    push_env["github"] = "PRIVATE"
    _, report = scanner.scan_pushed(line("refs/heads/main", LOCAL, "refs/heads/main", ZERO), tmp_path)
    assert "GitHub protections" not in report


# --- the remote being pushed to ------------------------------------------------------

@pytest.mark.parametrize("url,expected", [
    ("https://github.com/example-org/example-repo.git", "example-org/example-repo"),
    ("https://github.com/example-org/example-repo", "example-org/example-repo"),
    ("git@github.com:example-org/example-repo.git", "example-org/example-repo"),
    ("ssh://git@github.com/example-org/example-repo.git", "example-org/example-repo"),
    ("git@github-work:example-org/example-repo.git", "example-org/example-repo"),
    ("git@gitlab.com:example-org/example-repo.git", None),
    ("https://gitlab.com/example-org/example-repo.git", None),
    ("/tmp/remote.git", None),
    ("file:///tmp/remote.git", None),
    ("", None),
    (None, None),
])
def test_github_repo_is_read_from_the_remote_url(url, expected):
    assert scanner.github_repo_from_url(url) == expected


PUSHED_URL = "git@github.com:example-org/pushed-repo.git"


def test_public_pushed_remote_overrides_a_private_declaration(push_env, tmp_path):
    """The clone's default repo is private; the remote being pushed to is public."""
    push_env["declared"] = "PRIVATE"
    push_env["github"] = "PRIVATE"
    push_env["by_repo"] = {"example-org/pushed-repo": "PUBLIC"}
    push_env["rows"].append(dict(PII))
    code, report = scanner.scan_pushed(line("refs/heads/main", LOCAL, "refs/heads/main", ZERO),
                                       tmp_path, remote_url=PUSHED_URL)
    assert code == 1
    assert "example-org/pushed-repo" in push_env["posture_repos"]
    assert "declared PRIVATE" in report
    assert "GitHub reports PUBLIC" in report
    assert "gh repo edit --visibility private" in report
    # Public rules: personal data blocks rather than warns.
    assert "1 blocking finding(s)" in report
    assert "Reminder: you are pushing to a PUBLIC repository" in report


def test_private_pushed_remote_is_the_answer_used(push_env, tmp_path):
    push_env["declared"] = "PRIVATE"
    push_env["github"] = "PUBLIC"
    push_env["by_repo"] = {"example-org/pushed-repo": "PRIVATE"}
    code, report = scanner.scan_pushed(line("refs/heads/main", LOCAL, "refs/heads/main", ZERO),
                                       tmp_path, remote_url=PUSHED_URL)
    assert code == 0
    assert "declared" not in report


def test_no_answer_for_the_pushed_remote_falls_back_to_the_default_repo(push_env, tmp_path):
    push_env["declared"] = "PRIVATE"
    push_env["github"] = "PUBLIC"
    code, report = scanner.scan_pushed(line("refs/heads/main", LOCAL, "refs/heads/main", ZERO),
                                       tmp_path, remote_url=PUSHED_URL)
    assert code == 1
    assert push_env["posture_repos"] == ["example-org/pushed-repo", None]
    assert "GitHub reports PUBLIC" in report


def test_unparseable_remote_keeps_the_default_resolution(push_env, tmp_path):
    push_env["declared"] = "PRIVATE"
    push_env["github"] = "PRIVATE"
    code, _ = scanner.scan_pushed(line("refs/heads/main", LOCAL, "refs/heads/main", ZERO),
                                  tmp_path, remote_url="/tmp/remote.git")
    assert code == 0
    assert push_env["posture_repos"] == [None]


def test_pushed_remote_is_not_asked_on_a_range_push(push_env, tmp_path):
    push_env["by_repo"] = {"example-org/pushed-repo": "PUBLIC"}
    scanner.scan_pushed(line("refs/heads/main", LOCAL, "refs/heads/main", REMOTE),
                        tmp_path, remote_url=PUSHED_URL)
    assert push_env["posture_calls"] == 0


# --- CLI ------------------------------------------------------------------------

def test_cli_pre_push_reads_stdin_and_returns_the_scan_code(monkeypatch, capsys):
    import io
    import scan_secrets

    seen = {}

    def fake_scan(text, repo_path=None, remote_url=None):
        seen["text"] = text
        seen["remote_url"] = remote_url
        return 1, "report text"

    monkeypatch.setattr(scanner, "scan_pushed", fake_scan)
    monkeypatch.setattr("sys.argv", ["scan_secrets.py", "--pre-push"])
    stdin = line("refs/heads/main", LOCAL, "refs/heads/main", ZERO)
    monkeypatch.setattr("sys.stdin", io.StringIO(stdin))
    assert scan_secrets.main() == 1
    assert seen["text"] == stdin
    assert seen["remote_url"] is None
    assert "report text" in capsys.readouterr().err


def test_cli_pre_push_passes_the_hook_remote_url_through(monkeypatch, capsys):
    import io
    import scan_secrets

    seen = {}

    def fake_scan(text, repo_path=None, remote_url=None):
        seen["remote_url"] = remote_url
        return 0, ""

    monkeypatch.setattr(scanner, "scan_pushed", fake_scan)
    monkeypatch.setattr("sys.argv", ["scan_secrets.py", "--pre-push", "origin", PUSHED_URL])
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    assert scan_secrets.main() == 0
    assert seen["remote_url"] == PUSHED_URL


# --- end to end: a real git push through the generated dispatcher ------------------

PLUGIN_ROOT = Path(__file__).resolve().parents[3]

# Built at runtime so this file never carries the token shape itself. The value
# is invented; it matches gitleaks' default GitHub personal access token rule.
SYNTHETIC_TOKEN = "gh" + "p_" + "aB3dE5fG7hI9jK1lM3nO5pQ7rS9tU1vW3xY5"


needs_gitleaks = pytest.mark.skipif(shutil.which("gitleaks") is None,
                                    reason="gitleaks is not on PATH")


def _e2e_repo(tmp_path):
    """A working repo and a bare remote in tmp_path, with the pre-push hook.

    HOME, the global git config, and the gh config all point into tmp_path,
    and the plugin is found through the real marketplace path pattern via a
    symlink. Returns (git, work, bare)."""
    home = tmp_path / "home"
    marketplace = home / ".claude" / "plugins" / "marketplaces" / "gruntwork-test" / "plugins"
    marketplace.mkdir(parents=True)
    (marketplace / "lastmilefirst").symlink_to(PLUGIN_ROOT)
    gitconfig = home / ".gitconfig"
    gitconfig.write_text("")

    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("GIT_", "GH_", "GITHUB_"))}
    env.update({
        "HOME": str(home),
        "GIT_CONFIG_GLOBAL": str(gitconfig),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GH_CONFIG_DIR": str(home / ".config" / "gh"),
        "GIT_AUTHOR_NAME": "Test Author",
        "GIT_AUTHOR_EMAIL": "author@example.com",
        "GIT_COMMITTER_NAME": "Test Author",
        "GIT_COMMITTER_EMAIL": "author@example.com",
    })

    work = tmp_path / "work"
    bare = tmp_path / "remote.git"

    def git(*args, cwd=work, check=True):
        return subprocess.run(["git", *args], cwd=cwd, env=env, capture_output=True,
                              text=True, check=check, timeout=120)

    git("init", "-q", "--bare", str(bare), cwd=tmp_path)
    work.mkdir()
    git("init", "-q", "-b", "main")
    git("remote", "add", "origin", str(bare))
    hook = work / ".git" / "hooks" / "pre-push"
    hook.write_text(hook_installer.build_hook_script("pre-push"), encoding="utf-8")
    hook.chmod(0o755)
    return git, work, bare


def _commit(git, work, name, text, message):
    (work / name).write_text(text)
    git("add", name)
    git("commit", "-q", "-m", message)


@needs_gitleaks
def test_real_push_is_blocked_then_allowed(tmp_path):
    git, work, bare = _e2e_repo(tmp_path)

    (work / "README.md").write_text("A scratch repo.\n")
    git("add", "README.md")
    git("commit", "-q", "-m", "init")
    base = git("rev-parse", "HEAD").stdout.strip()

    (work / "settings.py").write_text(f'github_token = "{SYNTHETIC_TOKEN}"\n')
    git("add", "settings.py")
    git("commit", "-q", "-m", "add settings")

    blocked = git("push", "origin", "main", check=False)
    assert blocked.returncode != 0, blocked.stderr
    assert "github-pat" in blocked.stderr
    assert "blocking finding(s)" in blocked.stderr
    assert git("rev-parse", "--verify", "-q", "refs/heads/main", cwd=bare, check=False).returncode != 0

    # Drop the secret commit, commit something clean, and push again.
    git("reset", "-q", "--hard", base)
    (work / "notes.md").write_text("Nothing sensitive here.\n")
    git("add", "notes.md")
    git("commit", "-q", "-m", "notes")
    allowed = git("push", "origin", "main", check=False)
    assert allowed.returncode == 0, allowed.stderr
    head = git("rev-parse", "HEAD").stdout.strip()
    assert git("rev-parse", "refs/heads/main", cwd=bare).stdout.strip() == head

    # A later push scans only the range, and a secret in it still blocks.
    (work / "later.py").write_text(f'github_token = "{SYNTHETIC_TOKEN}"\n')
    git("add", "later.py")
    git("commit", "-q", "-m", "later")
    again = git("push", "origin", "main", check=False)
    assert again.returncode != 0
    assert "github-pat" in again.stderr


@needs_gitleaks
def test_new_branch_skips_a_finding_already_on_the_remote(tmp_path):
    """A first push of a branch scans only commits no remote already holds."""
    git, work, bare = _e2e_repo(tmp_path)
    _commit(git, work, "README.md", "A scratch repo.\n", "init")
    _commit(git, work, "settings.py", f'github_token = "{SYNTHETIC_TOKEN}"\n', "add settings")
    landed = git("push", "--no-verify", "origin", "main", check=False)
    assert landed.returncode == 0, landed.stderr

    git("checkout", "-q", "-b", "feature")
    _commit(git, work, "notes.md", "Nothing sensitive here.\n", "notes")
    pushed = git("push", "origin", "feature", check=False)
    assert pushed.returncode == 0, pushed.stderr
    assert "github-pat" not in pushed.stderr
    head = git("rev-parse", "HEAD").stdout.strip()
    assert git("rev-parse", "refs/heads/feature", cwd=bare).stdout.strip() == head


@needs_gitleaks
def test_range_push_skips_a_finding_already_on_the_remote(tmp_path):
    """An existing branch scans only the pushed range, not what is under it."""
    git, work, bare = _e2e_repo(tmp_path)
    _commit(git, work, "README.md", "A scratch repo.\n", "init")
    _commit(git, work, "settings.py", f'github_token = "{SYNTHETIC_TOKEN}"\n', "add settings")
    landed = git("push", "--no-verify", "origin", "main", check=False)
    assert landed.returncode == 0, landed.stderr

    _commit(git, work, "notes.md", "Nothing sensitive here.\n", "notes")
    pushed = git("push", "origin", "main", check=False)
    assert pushed.returncode == 0, pushed.stderr
    assert "github-pat" not in pushed.stderr
    head = git("rev-parse", "HEAD").stdout.strip()
    assert git("rev-parse", "refs/heads/main", cwd=bare).stdout.strip() == head
