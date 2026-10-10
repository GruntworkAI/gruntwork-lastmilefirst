"""Overwatch's cheap device check (organize-device plan 3.6).

A fake HOME holds the workspace, ~/.gitconfig, and Overwatch state. A stub
`gh` on PATH answers `gh auth token --user <account>` from FAKE_GH_LOGINS
(comma-separated accounts that are logged in) and appends each account it is
asked about to FAKE_GH_LOG, so a test can tell whether the probe ran.

Two invented orgs: example-studio has no SSH host alias, so it is the default
org and needs no includeIf stanza; example-client has an alias and does.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

import device_check
import overwatch
import session_start

STUDIO, CLIENT = "example-studio", "example-client"
STUDIO_ACCOUNT, CLIENT_ACCOUNT = "ExampleStudio", "ExampleClient"
CLIENT_STANZA = f'[includeIf "gitdir:~/Code/{CLIENT}/"]\n\tpath = ~/.gitconfig-{CLIENT}\n'

GH_STUB = """#!/bin/sh
echo "$4" >> "$FAKE_GH_LOG"
case ",$FAKE_GH_LOGINS," in
  *",$4,"*) echo gho_not_a_real_token; exit 0 ;;
  *) echo "no oauth token found for $4" >&2; exit 1 ;;
esac
"""


def alert(account, org):
    return (f"ACTION REQUIRED: this machine cannot commit as {account} for {org}; "
            "run /run-organize-device")


class Device:
    def __init__(self, tmp_path: Path, monkeypatch):
        self.home = tmp_path / "home"
        self.workspace = self.home / "Code"
        self.workspace.mkdir(parents=True)
        self.bin = tmp_path / "bin"
        self.bin.mkdir()
        (self.bin / "gh").write_text(GH_STUB)
        (self.bin / "gh").chmod(0o755)
        self.log = tmp_path / "gh.log"
        self.log.write_text("")
        self.monkeypatch = monkeypatch
        self.state: dict = {}
        monkeypatch.setenv("HOME", str(self.home))
        monkeypatch.setenv("FAKE_GH_LOG", str(self.log))
        monkeypatch.setenv("PATH", f"{self.bin}{os.pathsep}/usr/bin{os.pathsep}/bin")
        self.logins(STUDIO_ACCOUNT, CLIENT_ACCOUNT)
        self.org(STUDIO, STUDIO_ACCOUNT)
        self.org(CLIENT, CLIENT_ACCOUNT, alias="github-example-client")
        self.gitconfig(CLIENT_STANZA)

    def org(self, name, account, alias=None):
        identity = {"github_account": account, "git_user_name": account,
                    "git_email": f"{account.lower()}@example.com"}
        if alias:
            identity["ssh_host_alias"] = alias
        (self.workspace / name / ".claude").mkdir(parents=True)
        (self.workspace / name / ".claude" / "org.json").write_text(
            json.dumps({"name": name, "identity": identity}))

    def logins(self, *accounts):
        self.monkeypatch.setenv("FAKE_GH_LOGINS", ",".join(accounts))

    def gitconfig(self, text):
        (self.home / ".gitconfig").write_text("[user]\n\tname = Example\n" + text)

    def no_gh(self):
        self.monkeypatch.setenv("PATH", f"/usr/bin{os.pathsep}/bin")

    def probes(self):
        return [line for line in self.log.read_text().splitlines() if line]

    def run(self, now=1_000_000):
        return device_check.device_alerts(
            {"workspace": str(self.workspace)},
            lambda: self.state,
            lambda field, value: self.state.__setitem__(field, value),
            now=now,
        )


@pytest.fixture
def device(tmp_path, monkeypatch):
    return Device(tmp_path, monkeypatch)


def test_all_present_is_silent(device):
    assert device.run() == []
    assert sorted(device.probes()) == sorted([STUDIO_ACCOUNT, CLIENT_ACCOUNT])


def test_missing_gh_login_names_account_and_org(device):
    device.logins(CLIENT_ACCOUNT)
    assert device.run() == [alert(STUDIO_ACCOUNT, STUDIO)]


def test_missing_include_for_aliased_org(device):
    device.gitconfig("")
    assert device.run() == [alert(CLIENT_ACCOUNT, CLIENT)]


def test_default_org_needs_no_stanza(device):
    # The fixture's gitconfig has no stanza for example-studio at all.
    assert STUDIO not in (device.home / ".gitconfig").read_text()
    assert device.run() == []


def test_wrong_stanza_is_not_absence(device):
    # An absolute home path is the full audit's `wrong` finding, not this one.
    device.gitconfig(f'[includeIf "gitdir:{device.workspace}/{CLIENT}"]\n\tpath = /nowhere\n')
    assert device.run() == []


def test_both_missing_for_one_org_is_one_line(device):
    device.logins(STUDIO_ACCOUNT)
    device.gitconfig("")
    assert device.run() == [alert(CLIENT_ACCOUNT, CLIENT)]


def test_two_orgs_failing_give_two_lines(device):
    device.logins()
    assert device.run() == [alert(CLIENT_ACCOUNT, CLIENT), alert(STUDIO_ACCOUNT, STUDIO)]


def test_missing_gh_binary_is_silent(device):
    device.no_gh()
    device.gitconfig("")
    assert device.run() == []
    assert device.state == {}


def test_no_workspace_or_no_contracts_is_silent(device, tmp_path):
    assert device_check.device_alerts({}, lambda: {}, lambda f, v: None) == []
    empty = tmp_path / "empty"
    empty.mkdir()
    assert device_check.device_alerts({"workspace": str(empty)},
                                      lambda: {}, lambda f, v: None) == []
    assert device.probes() == []


def test_clean_result_is_cached_for_a_day(device):
    assert device.run(now=1_000_000) == []
    assert len(device.probes()) == 2
    device.logins()  # would fail now, but the clean answer is still fresh
    assert device.run(now=1_000_000 + 23 * 3600) == []
    assert len(device.probes()) == 2
    assert device.run(now=1_000_000 + 25 * 3600) == [
        alert(CLIENT_ACCOUNT, CLIENT), alert(STUDIO_ACCOUNT, STUDIO)]
    assert len(device.probes()) == 4


def test_new_contract_invalidates_the_cache(device):
    assert device.run() == []
    device.org("example-other", "ExampleOther", alias="github-example-other")
    assert device.run(now=1_000_100) == [alert("ExampleOther", "example-other")]


def test_failing_result_is_not_cached(device):
    device.logins(CLIENT_ACCOUNT)
    assert device.run(now=1_000_000) == [alert(STUDIO_ACCOUNT, STUDIO)]
    assert device_check.DEVICE_CACHE_FIELD not in device.state
    device.logins(STUDIO_ACCOUNT, CLIENT_ACCOUNT)  # the fix
    assert device.run(now=1_000_060) == []
    assert len(device.probes()) == 4  # re-probed, not served from cache


def test_exception_inside_the_check_is_silent(device, monkeypatch):
    ad = device_check._audit_device()

    def boom(*a, **kw):
        raise RuntimeError("broken audit")

    monkeypatch.setattr(ad, "load_contracts", boom)
    assert device.run() == []


def test_unimportable_audit_is_silent(device, monkeypatch):
    monkeypatch.setattr(device_check, "_audit_device", lambda: None)
    device.gitconfig("")
    assert device.run() == []


def test_session_start_check_uses_overwatch_state(device, tmp_path, monkeypatch):
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    monkeypatch.setattr(overwatch, "get_state_dir", lambda: state_dir)
    config = {"workspace": str(device.workspace)}
    assert session_start.check_device(config) == []
    cached = overwatch.get_scoped_state("global", None)[device_check.DEVICE_CACHE_FIELD]
    assert isinstance(cached["checked_at"], int)
    device.gitconfig("")
    assert session_start.check_device(config) == []  # served from the cache


def test_session_start_check_survives_a_raising_check(monkeypatch):
    def boom(*a, **kw):
        raise RuntimeError("broken")

    monkeypatch.setattr(session_start, "_device_alerts", boom)
    assert session_start.check_device({"workspace": "/nowhere"}) == []
