"""Pytest configuration for the organize-device scripts.

The skill ships as loose `scripts/*.py`, so this puts them (and the
organize-orgs and hooks scripts the audit reuses) on sys.path.

The `device` fixture builds a fake machine under tmp_path: a home directory
(HOME, XDG_CONFIG_HOME, and Path.home() all point at it), a workspace with two
invented orgs, an SSH config with keys on disk, a gitconfig with an include,
and a PATH holding only stub binaries. Out of the box the machine is clean;
each test breaks one thing.
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
