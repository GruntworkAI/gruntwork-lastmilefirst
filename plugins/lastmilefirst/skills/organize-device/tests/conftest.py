"""Pytest configuration for the organize-device scripts.

The skill ships as loose `scripts/*.py`, so this puts them (and the
organize-orgs and hooks scripts the audit reuses) on sys.path.

The `device` fixture builds a fake machine under tmp_path: a home directory
(HOME, XDG_CONFIG_HOME, and Path.home() all point at it), a workspace with two
invented orgs, an SSH config with keys on disk, a gitconfig with an include,
and a PATH holding only stub binaries. Out of the box the machine is clean;
each test breaks one thing.

The `real_home_guard` fixture is autouse: every test in this directory runs
under an audit hook that fails it if anything touches a path under the real
home (see the fixture for the events and the allowed prefixes).
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

_SKILL = Path(__file__).resolve().parent.parent
for _p in (_SKILL / "scripts",
           _SKILL.parent / "organize-orgs" / "scripts",
           _SKILL.parents[1] / "hooks" / "scripts"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

# Captured before any test patches HOME.
REAL_HOME = os.path.realpath(os.path.expanduser("~"))
PLUGIN_ROOT = str(_SKILL.parents[2])
WORKTREE_ROOT = str(_SKILL.parents[3])

STUDIO = {
    "github_account": "ExampleStudio",
    "git_user_name": "Example Studio",
    "git_email": "studio@example.com",
    "owns_remotes": ["ExampleStudio"],
}
CLIENT = {
    "github_account": "example-client-bot",
    "git_user_name": "example-client-bot",
    "git_email": "1234+example-client-bot@users.noreply.github.com",
    "owns_remotes": ["example-client-bot"],
    "ssh_host_alias": "github-example-client",
}

BASELINE = ("git", "gh", "jq", "python3", "node", "rg", "claude")

GH_STUB = """#!/bin/sh
if [ "$1" = "auth" ] && [ "$2" = "token" ] && [ "$3" = "--user" ]; then
  case ",$FAKE_GH_LOGINS," in
    *",$4,"*) echo "gho_FAKE_TOKEN_VALUE"; exit 0 ;;
  esac
  echo "no oauth token found for github.com account $4" >&2
  exit 1
fi
exit 0
"""

SSH_STUB = """#!/bin/sh
for last; do :; done
IFS=','
for pair in $FAKE_SSH_MAP; do
  host="${pair%%=*}"
  user="${pair#*=}"
  if [ "$host" = "$last" ]; then
    echo "Hi $user! You've successfully authenticated, but GitHub does not provide shell access." >&2
    exit 1
  fi
done
echo "$last: Permission denied (publickey)." >&2
exit 255
"""

SSH_CONFIG = """# test ssh config
Include ~/.ssh/config.d/*

Host github.com
    HostName github.com
    User git
    IdentityFile ~/.ssh/id_ed25519
    IdentitiesOnly yes

Host github-example-client
    HostName github.com
    User git
    IdentityFile ~/.ssh/id_ed25519_example-client
    IdentitiesOnly yes
"""


class Device:
    def __init__(self, root: Path) -> None:
        self.home = root / "home"
        self.workspace = self.home / "Code"
        self.bin = root / "bin"
        self.config = self.home / ".config"

    # --- writers -----------------------------------------------------------

    def write(self, relative: str, text: str) -> Path:
        path = self.home / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def org(self, name: str, identity: dict) -> Path:
        org_dir = self.workspace / name
        (org_dir / ".claude").mkdir(parents=True, exist_ok=True)
        (org_dir / ".claude" / "org.json").write_text(
            json.dumps({"name": name, "identity": identity}), encoding="utf-8")
        return org_dir

    def stub(self, name: str, body: str = "#!/bin/sh\nexit 0\n") -> Path:
        path = self.bin / name
        path.write_text(body, encoding="utf-8")
        path.chmod(0o755)
        return path

    def unstub(self, name: str) -> None:
        (self.bin / name).unlink()

    def gitconfig(self, text: str) -> Path:
        return self.write(".gitconfig", text)

    def ssh_config(self, text: str) -> Path:
        return self.write(".ssh/config", text)

    def manifest(self, text: str) -> Path:
        return self.write(".config/lastmilefirst/device.toml", text)

    def repo(self, org: str, name: str, origin: str) -> Path:
        repo = self.workspace / org / name
        (repo / ".git").mkdir(parents=True, exist_ok=True)
        (repo / ".git" / "config").write_text(
            f'[remote "origin"]\n\turl = {origin}\n', encoding="utf-8")
        return repo


@pytest.fixture
def device(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Device:
    dev = Device(tmp_path.resolve())
    dev.home.mkdir()
    dev.bin.mkdir()
    monkeypatch.setenv("HOME", str(dev.home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(dev.config))
    monkeypatch.setenv("PATH", str(dev.bin))
    monkeypatch.setenv("SHELL", "/bin/zsh")
    monkeypatch.setenv("FAKE_GH_LOGINS", "ExampleStudio,example-client-bot")
    monkeypatch.delenv("FAKE_SSH_MAP", raising=False)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: dev.home))

    for tool in BASELINE:
        dev.stub(tool)
    dev.stub("gh", GH_STUB)

    dev.org("example-studio", STUDIO)
    dev.org("example-client", CLIENT)

    dev.ssh_config(SSH_CONFIG)
    dev.write(".ssh/id_ed25519", "fake private key\n")
    dev.write(".ssh/id_ed25519_example-client", "fake private key\n")

    dev.gitconfig(
        "[user]\n\tname = Example Studio\n\temail = studio@example.com\n"
        "[credential]\n\thelper = osxkeychain\n"
        '[includeIf "gitdir:~/Code/example-client/"]\n'
        "\tpath = ~/.gitconfig-example-client\n"
    )
    dev.write(".gitconfig-example-client",
              f"[user]\n\tname = {CLIENT['git_user_name']}\n\temail = {CLIENT['git_email']}\n")
    dev.write(".config/gh/hosts.yml",
              "github.com:\n    users:\n        ExampleStudio:\n    user: ExampleStudio\n")
    return dev


# --- U4 additions -----------------------------------------------------------

@pytest.fixture(autouse=True)
def _workspace_claude_md(request):
    """Give every `device` a workspace CLAUDE.md with no project table.

    The Workspace section reports a missing workspace CLAUDE.md, so without
    this the clean fake machine would no longer be clean. Tests that do not
    use `device` are untouched.
    """
    if "device" in request.fixturenames:
        request.getfixturevalue("device").write("Code/CLAUDE.md", "# Example workspace\n")


# --- no real home -------------------------------------------------------------

# Path arguments to watch, by audit event: the positions that name a path.
_PATH_EVENTS = {
    "open": (0,),
    "os.listdir": (0,),
    "os.scandir": (0,),
    "os.mkdir": (0,),
    "os.rename": (0, 1),
    "os.chmod": (0,),
    "os.remove": (0,),
    "os.rmdir": (0,),
    "shutil.copyfile": (0, 1),
    "shutil.copymode": (0, 1),
}


def _under(path: str, root: str) -> bool:
    return path == root or path.startswith(root.rstrip(os.sep) + os.sep)


class RealHomeGuard:
    """Records every watched path; `leaks` are the ones under the real home that are
    not allowed. The fake HOME, /tmp and /private/tmp are outside the real home, so
    they pass without an entry; the worktree, the venv, and the Python prefixes are
    inside it on a developer machine, so they are listed."""

    allowed = tuple(dict.fromkeys(os.path.realpath(p) for p in (
        WORKTREE_ROOT, PLUGIN_ROOT, sys.prefix, sys.base_prefix, sys.exec_prefix,
        sys.base_exec_prefix, "/private/tmp", "/tmp")))

    def __init__(self) -> None:
        self.seen: list[tuple[str, str]] = []
        self.leaks: list[tuple[str, str]] = []
        self._busy = False

    def _check(self, event: str, raw: object, argv_element: bool = False) -> None:
        if isinstance(raw, int) or raw is None:
            return  # a file descriptor, or no path
        if not isinstance(raw, (str, bytes, os.PathLike)):
            return
        text = os.fsdecode(raw)
        if argv_element:
            text = os.path.expanduser(text) if text.startswith("~") else text
            if not os.path.isabs(text):
                return  # a word, not a path (relative paths resolve in an allowed cwd)
        path = os.path.realpath(text)
        self.seen.append((event, path))
        if _under(path, REAL_HOME) and not any(_under(path, a) for a in self.allowed):
            self.leaks.append((event, path))

    def __call__(self, event: str, args: tuple) -> None:
        if self._busy or not args:
            return
        self._busy = True
        try:
            if event in _PATH_EVENTS:
                for i in _PATH_EVENTS[event]:
                    if i < len(args):
                        self._check(event, args[i])
            elif event == "subprocess.Popen":
                executable, argv, cwd = args[0], args[1], args[2]
                self._check(event, executable, argv_element=True)
                if isinstance(argv, (str, bytes, os.PathLike)):
                    argv = [argv]
                for element in argv or ():
                    self._check(event, element, argv_element=True)
                self._check(event, cwd)
        finally:
            self._busy = False


_GUARD: dict = {"current": None}


def _dispatch(event: str, args: tuple) -> None:
    guard = _GUARD["current"]
    if guard is not None:
        guard(event, args)


sys.addaudithook(_dispatch)  # audit hooks cannot be removed; this one is a no-op between tests


def _leak_report(guard: RealHomeGuard) -> str:
    shown = "\n".join(f"  {event}: {path}" for event, path in dict.fromkeys(guard.leaks))
    guard.leaks.clear()  # reported once
    return f"touched the real home ({REAL_HOME}):\n{shown}"


@pytest.hookimpl(wrapper=True)
def pytest_runtest_call(item):
    """Report a leak in the test body as a test failure, not a teardown error."""
    result = yield
    guard = _GUARD["current"]
    if guard is not None and guard.leaks:
        pytest.fail(_leak_report(guard), pytrace=False)
    return result


@pytest.fixture(autouse=True)
def real_home_guard():
    """Fail any test in this directory that opens, lists, creates, renames, chmods,
    removes, or copies a path under the real home, or starts a process whose
    executable, argv, or cwd names one. Request it by name to read `.seen`."""
    guard = RealHomeGuard()
    _GUARD["current"] = guard
    try:
        yield guard
    finally:
        _GUARD["current"] = None
    if guard.leaks:  # from fixture setup or teardown
        pytest.fail(_leak_report(guard), pytrace=False)
