"""Tests for the Claude Code, AWS, Keychain, Network, and Workspace sections.

Same pattern as test_audit_device: the clean fake machine from conftest, one
broken thing per test, stub binaries on PATH driven by environment variables.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

import audit_device
import network
from audit_device import MISSING, WRONG
from .conftest import CLIENT, PLUGIN_ROOT, REAL_HOME, STUDIO


# --------------------------------------------------------------------------
# helpers and stubs
# --------------------------------------------------------------------------

def run(capsys, *argv):
    code = audit_device.main(["--workspace-root", "~/Code", *argv])
    out = capsys.readouterr()
    return code, out.out, out.err


def findings(capsys, *argv):
    code, out, _ = run(capsys, "--json", *argv)
    return code, json.loads(out)["findings"]


def in_section(found, section, cls="any"):
    return [f for f in found if f["section"] == section and (cls == "any" or f["class"] == cls)]


def problems(found, section):
    return [f for f in in_section(found, section) if f["class"] in (MISSING, WRONG)]


CLAUDE_STUB = """#!/bin/sh
[ -n "$FAKE_CLAUDE_LOG" ] && echo "$*" >> "$FAKE_CLAUDE_LOG"
if [ "$1" = "--version" ]; then echo "9.9.9 (Example Code)"; exit 0; fi
if [ "$1 $2 $3 $4" = "plugin marketplace list --json" ]; then
  echo "${FAKE_CLAUDE_MARKETPLACES:-[]}"; exit 0
fi
exit 0
"""

AWS_STUB = """#!/bin/sh
case "$1 $2" in
  "iam list-account-aliases")
    if [ -n "$FAKE_AWS_ALIASES" ]; then echo "$FAKE_AWS_ALIASES"
    else echo '{"AccountAliases": []}'; fi
    exit 0 ;;
  "sts get-caller-identity")
    echo '{"UserId": "AIDAEXAMPLEUSERID", "Account": "000000000000",'  # gitleaks:allow (all-zero fixture id)
    echo ' "Arn": "arn:aws:iam::000000000000:user/example-user-name"}'  # gitleaks:allow (all-zero fixture id)
    exit 0 ;;
esac
exit 0
"""

SECURITY_STUB = """#!/bin/sh
# find-generic-password -s <name>
case ",$FAKE_KEYCHAIN," in
  *",$3,"*) echo 'password: "EXAMPLEKEYCHAINVALUE"'; exit 0 ;;
esac
echo "security: SecKeychainSearchCopyNext: The specified item could not be found." >&2
exit 44
"""

SECRET_TOOL_STUB = """#!/bin/sh
# lookup service <name>
case ",$FAKE_KEYCHAIN," in
  *",$3,"*) printf 'EXAMPLEKEYCHAINVALUE'; exit 0 ;;
esac
exit 1
"""

TAILSCALE_STUB = """#!/bin/sh
if [ "$1" = "version" ]; then
  if [ -n "$FAKE_TS_BUNDLE" ]; then
    echo "Fatal error: BundleIdentifiers.swift:41: The current bundleIdentifier is unknown" >&2
    exit 1
  fi
  echo "${FAKE_TS_VERSION:-1.0.0}"
  echo "  tailscale commit: 0000000"
  exit 0
fi
if [ "$1" = "status" ]; then
  [ -n "$FAKE_TS_SLEEP" ] && /bin/sleep "$FAKE_TS_SLEEP"
  if [ -n "$FAKE_TS_STDERR" ]; then echo "$FAKE_TS_STDERR" >&2; fi
  [ -n "$FAKE_TS_STATUS_FILE" ] && /bin/cat "$FAKE_TS_STATUS_FILE"
  exit "${FAKE_TS_STATUS_EXIT:-0}"
fi
exit 0
"""


def ts_status(device, monkeypatch, backend="Running", tailnet="example-tailnet",
              ssh_on=False, dns="example-host.example-tailnet.ts.net.", raw=None):
    """Write a status JSON for the tailscale stub. Only fields the provider reads,
    plus one key-shaped field to prove it is never echoed."""
    data = {
        "BackendState": backend,
        "Self": {"DNSName": dns, "PublicKey": "nodekey:EXAMPLENODEKEY"},
        "CurrentTailnet": {"Name": tailnet, "MagicDNSSuffix": "example-tailnet.ts.net",
                           "MagicDNSEnabled": True},
    }
    if ssh_on:
        data["Self"]["sshHostKeys"] = ["ssh-ed25519 EXAMPLEHOSTKEY"]
    if backend == "NeedsLogin":
        data.pop("CurrentTailnet")
    path = device.home / "ts-status.json"
    path.write_text(raw if raw is not None else json.dumps(data), encoding="utf-8")
    monkeypatch.setenv("FAKE_TS_STATUS_FILE", str(path))


@pytest.fixture
def mac(monkeypatch):
    monkeypatch.setattr(audit_device, "_system", lambda: "Darwin")


@pytest.fixture
def linux(monkeypatch):
    monkeypatch.setattr(audit_device, "_system", lambda: "Linux")


@pytest.fixture
def tailscale_device(device, monkeypatch, mac):
    """A Mac with the Tailscale app and a working brew CLI, running and clean."""
    import network.tailscale as ts
    app = device.home / "Applications" / "Tailscale.app"
    (app / "Contents").mkdir(parents=True)
    import plistlib
    (app / "Contents" / "Info.plist").write_bytes(
        plistlib.dumps({"CFBundleShortVersionString": "1.0.0"}))
    monkeypatch.setattr(ts, "MAC_APP", app)
    monkeypatch.setattr(ts, "TIMEOUT", 5.0)
    for name in ("FAKE_TS_BUNDLE", "FAKE_TS_SLEEP", "FAKE_TS_STDERR", "FAKE_TS_STATUS_EXIT",
                 "FAKE_TS_VERSION"):
        monkeypatch.delenv(name, raising=False)
    device.stub("tailscale", TAILSCALE_STUB)
    ts_status(device, monkeypatch)
    device.manifest('[network]\nprovider = "tailscale"\n\n'
                    '[network.tailscale]\ntailnet = "example-tailnet"\nssh = false\n')
    device.ts = ts
    device.app = app
    return device


def table(device, body: str) -> None:
    device.write("Code/CLAUDE.md",
                 "# Example workspace\n\n## Project Directory Mapping\n\n" + body + "\n"
                 "## Something Else\n\n| not | ~/Code/elsewhere/ignored |\n")


# --------------------------------------------------------------------------
# section order and the clean machine
# --------------------------------------------------------------------------

def test_report_order(device, capsys):
    _, out, _ = run(capsys)
    heads = ["Device manifest", "Platform", "Tools", "GitHub logins", "SSH", "git identity",
             "Claude Code", "AWS", "Keychain", "Network", "Workspace"]
    positions = [out.index(f"\n{h}\n") for h in heads]
    assert positions == sorted(positions)


def test_clean_machine_still_clean_with_new_sections(device, capsys):
    code, found = findings(capsys)
    assert code == 0
    for section in ("Claude Code", "AWS", "Keychain", "Network", "Workspace"):
        assert problems(found, section) == []


# --------------------------------------------------------------------------
# Claude Code
# --------------------------------------------------------------------------

MARKETS = {
    "example-market": {"source": {"source": "github", "repo": "ExampleStudio/example-market"}},
    "local-market": {"source": {"source": "directory", "path": "/opt/example-local"}},
}


def test_claude_version_is_a_note(device, capsys):
    device.stub("claude", CLAUDE_STUB)
    _, found = findings(capsys)
    notes = in_section(found, "Claude Code", None)
    assert [n["message"] for n in notes] == ["claude --version: 9.9.9 (Example Code)."]


def test_missing_claude_binary_is_not_repeated(device, capsys):
    device.unstub("claude")
    device.manifest('[claude]\nplugins = ["example@example-market"]\n')
    _, found = findings(capsys)
    assert [f["message"] for f in in_section(found, "Tools", MISSING)] == \
        ["claude is not installed (baseline)."]
    claude = in_section(found, "Claude Code")
    assert all("claude is not installed" not in f["message"] for f in claude)
    assert all("--version" not in f["message"] for f in claude)


def test_marketplace_known_by_repo_key_or_path(device, capsys):
    device.write(".claude/plugins/known_marketplaces.json", json.dumps(MARKETS))
    device.manifest('[claude]\nmarketplaces = ["ExampleStudio/example-market", '
                    '"example-market", "/opt/example-local"]\n')
    _, found = findings(capsys)
    assert problems(found, "Claude Code") == []


def test_missing_marketplace(device, capsys):
    device.write(".claude/plugins/known_marketplaces.json", json.dumps(MARKETS))
    device.manifest('[claude]\nmarketplaces = ["ExampleStudio/other-market"]\n')
    code, found = findings(capsys)
    [f] = problems(found, "Claude Code")
    assert f["class"] == MISSING
    assert f["remedy"] == "claude plugin marketplace add ExampleStudio/other-market"
    assert code == 2


def test_marketplace_list_fallback_only_under_full(device, capsys, monkeypatch):
    log = device.home / "claude.log"
    device.stub("claude", CLAUDE_STUB)
    monkeypatch.setenv("FAKE_CLAUDE_LOG", str(log))
    monkeypatch.setenv("FAKE_CLAUDE_MARKETPLACES", json.dumps(
        [{"name": "example-market", "source": "github", "repo": "ExampleStudio/example-market"}]))
    device.write(".claude/plugins/known_marketplaces.json", "{not json")
    device.manifest('[claude]\nmarketplaces = ["ExampleStudio/example-market"]\n')

    _, found = findings(capsys)
    assert "plugin marketplace list" not in log.read_text(encoding="utf-8")
    assert problems(found, "Claude Code") == []
    assert any("Could not read" in f["message"] for f in in_section(found, "Claude Code"))

    _, found = findings(capsys, "--full", "--no-liveness")
    assert "plugin marketplace list --json" in log.read_text(encoding="utf-8")
    assert problems(found, "Claude Code") == []
    assert not any("Could not read" in f["message"] for f in in_section(found, "Claude Code"))


def test_missing_plugin(device, capsys):
    device.write(".claude/settings.json", json.dumps(
        {"enabledPlugins": {"example@example-market": True}}))
    device.manifest('[claude]\nplugins = ["example@example-market", "other@example-market"]\n')
    _, found = findings(capsys)
    [f] = problems(found, "Claude Code")
    assert f["class"] == MISSING
    assert f["remedy"] == "claude plugin install other@example-market"


def test_disabled_plugin_is_missing_with_enable(device, capsys):
    device.write(".claude/settings.json", json.dumps(
        {"enabledPlugins": {"example@example-market": False}}))
    device.manifest('[claude]\nplugins = ["example@example-market"]\n')
    _, found = findings(capsys)
    [f] = problems(found, "Claude Code")
    assert f["class"] == MISSING
    assert f["remedy"] == "claude plugin enable example@example-market"


def _hooks(device, *names):
    for name in names:
        device.write(f".claude/lastmilefirst/git-hooks/{name}", "#!/bin/sh\n")


def test_scan_hooks_present_and_active_is_clean(device, capsys):
    _hooks(device, "pre-commit", "pre-push")
    device.write(".gitconfig", (device.home / ".gitconfig").read_text()
                 + "[core]\n\thooksPath = ~/.claude/lastmilefirst/git-hooks\n")
    device.manifest('[claude]\nhooks = ["pre-commit", "pre-push"]\n')
    _, found = findings(capsys)
    assert problems(found, "Claude Code") == []


def test_missing_scan_hooks(device, capsys):
    _hooks(device, "pre-commit")
    device.manifest('[claude]\nhooks = ["pre-commit", "pre-push"]\n')
    _, found = findings(capsys)
    [f] = problems(found, "Claude Code")
    assert f["class"] == MISSING
    assert "pre-push" in f["message"] and "pre-commit" not in f["message"]
    assert f["remedy"] == "/run-scan-secrets --install-hooks"


def test_scan_hooks_without_hooks_path_is_missing(device, capsys):
    _hooks(device, "pre-commit", "pre-push")
    device.manifest('[claude]\nhooks = ["pre-commit"]\n')
    _, found = findings(capsys)
    [f] = problems(found, "Claude Code")
    assert f["class"] == MISSING and "core.hooksPath is not set" in f["message"]
    assert f["remedy"] == "/run-scan-secrets --install-hooks"


def test_hooks_path_pointing_elsewhere_is_wrong(device, capsys):
    _hooks(device, "pre-commit")
    device.write(".gitconfig", (device.home / ".gitconfig").read_text()
                 + "[core]\n\thooksPath = ~/example-other-hooks\n")
    device.manifest('[claude]\nhooks = ["pre-commit"]\n')
    _, found = findings(capsys)
    [f] = problems(found, "Claude Code")
    assert f["class"] == WRONG
    assert "hooksPath = ~/.claude/lastmilefirst/git-hooks" in f["remedy"]


def test_hooks_path_matches_the_installer():
    sys.path.insert(0, str(Path(audit_device.__file__).resolve().parents[2]
                           / "scan-secrets" / "scripts"))
    import hook_installer
    assert hook_installer.HOOKS_DIR.parts[-3:] == audit_device.SCAN_HOOKS_RELATIVE.parts
    assert hook_installer.HOOK_FILE.name == "pre-commit"
    assert hook_installer.PRE_PUSH_HOOK_FILE.name == "pre-push"


# --------------------------------------------------------------------------
# AWS
# --------------------------------------------------------------------------

FAKE_AWS_SECRET = "EXAMPLEAWSSECRETVALUE0000"


@pytest.fixture
def aws_device(device):
    device.stub("aws", AWS_STUB)
    device.write(".aws/config", "[default]\nregion = us-example-1\n"
                                "[profile example-dev]\nregion = us-example-1\n")
    device.write(".aws/credentials",
                 f"[example-ci]\naws_secret_access_key = {FAKE_AWS_SECRET}\n")
    return device


def test_aws_profiles_found_in_config_and_credentials(aws_device, capsys):
    aws_device.manifest('[aws]\nprofiles = ["default", "example-dev", "example-ci"]\n')
    _, out, _ = run(capsys)
    _, found = findings(capsys)
    assert problems(found, "AWS") == []
    assert FAKE_AWS_SECRET not in out


def test_missing_aws_profile_is_a_you_step(aws_device, capsys):
    aws_device.manifest('[aws]\nprofiles = ["example-prod"]\n')
    _, found = findings(capsys)
    [f] = problems(found, "AWS")
    assert f["class"] == MISSING
    assert f["remedy"] is None
    assert f["you"] == "aws configure --profile example-prod"


def test_default_profile_label_note(aws_device, capsys):
    aws_device.manifest('[aws]\nprofiles = ["default"]\ndefault_profile_is = "studio"\n')
    _, found = findings(capsys)
    assert [n["message"] for n in in_section(found, "AWS", None)] == \
        ["Profile default is labeled studio (aws.default_profile_is)."]


def test_specify_label_is_not_repeated(aws_device, capsys):
    aws_device.manifest('[aws]\nprofiles = ["default"]\ndefault_profile_is = "(specify)"\n')
    _, found = findings(capsys)
    assert in_section(found, "AWS") == []


def test_missing_aws_binary_is_one_finding(device, capsys):
    device.manifest('[aws]\nprofiles = ["default", "example-dev"]\n')
    _, found = findings(capsys)
    [f] = in_section(found, "AWS")
    assert f["class"] == MISSING and "aws is not installed" in f["message"]


def test_missing_aws_binary_already_in_tools_is_not_repeated(device, capsys):
    device.manifest('[tools]\nextra = ["awscli"]\n[aws]\nprofiles = ["default"]\n')
    _, found = findings(capsys)
    assert len(in_section(found, "Tools", MISSING)) == 1
    assert problems(found, "AWS") == []


def test_full_reports_alias_only(aws_device, capsys, monkeypatch):
    monkeypatch.setenv("FAKE_AWS_ALIASES", '{"AccountAliases": ["example-alias"]}')
    aws_device.manifest('[aws]\nprofiles = ["default"]\ndefault_profile_is = "studio"\n')
    _, out, _ = run(capsys, "--full")
    assert "Profile default answers as account example-alias." in out
    assert "example-user-name" not in out and "AIDAEXAMPLE" not in out


def test_full_falls_back_to_account_id(aws_device, capsys):
    aws_device.manifest('[aws]\nprofiles = ["default"]\n')
    _, out, _ = run(capsys, "--full")
    assert "Profile default answers as account 000000000000." in out  # gitleaks:allow (all-zero fixture id)
    assert "arn:" not in out and "example-user-name" not in out


def test_cheap_and_no_liveness_never_call_sts(aws_device, capsys, monkeypatch):
    calls = []
    monkeypatch.setattr(audit_device, "aws_account", lambda p: calls.append(p))
    aws_device.manifest('[aws]\nprofiles = ["default"]\n')
    run(capsys)
    run(capsys, "--full", "--no-liveness")
    assert calls == []


# --------------------------------------------------------------------------
# Keychain
# --------------------------------------------------------------------------

def test_keychain_mac_present_and_absent(device, capsys, monkeypatch, mac):
    device.stub("security", SECURITY_STUB)
    monkeypatch.setenv("FAKE_KEYCHAIN", "example-present")
    device.manifest('[keychain]\nitems = ["example-present", "example-absent"]\n')
    _, out, _ = run(capsys)
    _, found = findings(capsys)
    [f] = problems(found, "Keychain")
    assert f["class"] == MISSING and "example-absent" in f["message"]
    assert f["remedy"] is None
    assert "prompts for the value" in f["you"]
    assert "EXAMPLEKEYCHAINVALUE" not in out


def test_keychain_linux_secret_tool(device, capsys, monkeypatch, linux):
    device.stub("secret-tool", SECRET_TOOL_STUB)
    monkeypatch.setenv("FAKE_KEYCHAIN", "example-present")
    device.manifest('[keychain]\nitems = ["example-present", "example-absent"]\n')
    _, out, _ = run(capsys)
    _, found = findings(capsys)
    [f] = problems(found, "Keychain")
    assert f["class"] == MISSING and "example-absent" in f["message"]
    assert "EXAMPLEKEYCHAINVALUE" not in out


def test_keychain_unsupported_platform_is_one_note(device, capsys, linux):
    device.manifest('[keychain]\nitems = ["a", "b"]\n')
    _, found = findings(capsys)
    assert [(f["class"], f["message"]) for f in in_section(found, "Keychain")] == \
        [(None, "Cannot check keychain items on this platform.")]


def test_keychain_never_captures_output(monkeypatch):
    seen = {}

    def fake_run(cmd, **kwargs):
        seen.update(kwargs)

        class R:
            returncode = 0
        return R()

    monkeypatch.setattr(audit_device.subprocess, "run", fake_run)
    assert audit_device.keychain_has(["security", "find-generic-password", "-s", "x"]) is True
    assert seen["stdout"] is audit_device.subprocess.DEVNULL
    assert seen["stderr"] is audit_device.subprocess.DEVNULL
    assert "capture_output" not in seen


# --------------------------------------------------------------------------
# Network
# --------------------------------------------------------------------------

def test_none_provider_is_one_note_and_imports_no_provider(device, capsys, monkeypatch):
    for name in [m for m in sys.modules if m == "network" or m.startswith("network.")]:
        monkeypatch.delitem(sys.modules, name)
    _, found = findings(capsys)
    net = in_section(found, "Network")
    assert len(net) == 1 and net[0]["class"] is None
    assert "No network provider is configured" in net[0]["message"]
    assert "[network]" in net[0]["message"]
    assert not [m for m in sys.modules if m == "network" or m.startswith("network.")]


def test_explicit_none_matches_the_default(device, capsys, monkeypatch):
    monkeypatch.delitem(sys.modules, "network.tailscale", raising=False)
    device.manifest('[network]\nprovider = "none"\n')
    _, found = findings(capsys)
    assert len(in_section(found, "Network")) == 1
    assert "network.tailscale" not in sys.modules


def test_unknown_provider_is_wrong(device, capsys):
    device.manifest('[network]\nprovider = "example-mesh"\n')
    code, found = findings(capsys)
    [f] = in_section(found, "Network")
    assert f["class"] == WRONG and "example-mesh" in f["message"]
    assert '"none", "tailscale"' in f["remedy"]
    assert code == 1


def test_provider_package_interface():
    assert network.available() == ["tailscale"]
    module = network.load("tailscale")
    for fn in ("detect", "audit", "handoff"):
        assert callable(getattr(module, fn))
    assert "tailnet" in module.__doc__ and "ssh" in module.__doc__
    with pytest.raises(KeyError):
        network.load("os")


def test_a_crashing_provider_is_one_wrong(tailscale_device, capsys, monkeypatch):
    monkeypatch.setattr(tailscale_device.ts, "audit",
                        lambda table, ctx: (_ for _ in ()).throw(RuntimeError("boom")))
    _, found = findings(capsys)
    [f] = in_section(found, "Network")
    assert f["class"] == WRONG and "RuntimeError" in f["message"]


def test_tailscale_running_clean(tailscale_device, capsys):
    code, found = findings(capsys)
    net = in_section(found, "Network")
    assert problems(found, "Network") == []
    assert [n["message"] for n in net] == \
        ["MagicDNS name: example-host.example-tailnet.ts.net."]
    _, out, _ = run(capsys)
    assert "EXAMPLENODEKEY" not in out


def test_tailscale_stopped_is_a_note_with_up(tailscale_device, capsys, monkeypatch):
    ts_status(tailscale_device, monkeypatch, backend="Stopped")
    code, found = findings(capsys)
    assert problems(found, "Network") == []
    stopped = [f for f in in_section(found, "Network") if "stopped" in f["message"]]
    assert stopped[0]["class"] is None and stopped[0]["you"] == "tailscale up"
    assert code == 0


def test_tailscale_needs_login_is_missing(tailscale_device, capsys, monkeypatch):
    ts_status(tailscale_device, monkeypatch, backend="NeedsLogin")
    _, found = findings(capsys)
    [f] = problems(found, "Network")
    assert f["class"] == MISSING and "tailscale up" in f["you"]
    assert f["remedy"] is None


def test_tailscale_status_timeout_is_one_wrong(tailscale_device, capsys, monkeypatch):
    monkeypatch.setattr(tailscale_device.ts, "TIMEOUT", 0.5)
    monkeypatch.setenv("FAKE_TS_SLEEP", "3")
    # `tailscale version` must answer; only status sleeps.
    _, found = findings(capsys)
    [f] = problems(found, "Network")
    assert f["class"] == WRONG and "did not answer in time" in f["message"]


def test_tailscale_bad_json_is_one_wrong(tailscale_device, capsys, monkeypatch):
    ts_status(tailscale_device, monkeypatch, raw="{this is not json")
    _, found = findings(capsys)
    [f] = problems(found, "Network")
    assert f["class"] == WRONG and "not status JSON" in f["message"]


def test_tailscale_daemon_not_running_is_missing(tailscale_device, capsys, monkeypatch):
    monkeypatch.delenv("FAKE_TS_STATUS_FILE")
    monkeypatch.setenv("FAKE_TS_STDERR", "failed to connect to local tailscaled; it doesn't "
                                         "appear to be running")
    monkeypatch.setenv("FAKE_TS_STATUS_EXIT", "1")
    _, found = findings(capsys)
    [f] = problems(found, "Network")
    assert f["class"] == MISSING and "background service" in f["message"]
    assert "Open the Tailscale app." in f["you"]


def test_tailscale_not_installed_mac(tailscale_device, capsys):
    tailscale_device.unstub("tailscale")
    import shutil
    shutil.rmtree(tailscale_device.app)
    _, found = findings(capsys)
    [f] = problems(found, "Network")
    assert f["class"] == MISSING and f["remedy"] == "brew install --cask tailscale-app"


def test_tailscale_not_installed_linux(tailscale_device, capsys, monkeypatch):
    monkeypatch.setattr(audit_device, "_system", lambda: "Linux")
    tailscale_device.unstub("tailscale")
    _, found = findings(capsys)
    [f] = problems(found, "Network")
    assert f["class"] == MISSING
    assert f["remedy"] == "curl -fsSL https://tailscale.com/install.sh | sh"
    assert "sudo tailscale up" in f["you"]


def test_tailscale_linux_running_skips_the_app_checks(tailscale_device, capsys, monkeypatch):
    monkeypatch.setattr(audit_device, "_system", lambda: "Linux")
    monkeypatch.setenv("FAKE_TS_BUNDLE", "1")  # would fail the macOS version check
    _, found = findings(capsys)
    assert problems(found, "Network") == []


def test_app_without_cli_on_path_is_wrong(tailscale_device, capsys):
    tailscale_device.unstub("tailscale")
    _, found = findings(capsys)
    [f] = problems(found, "Network")
    assert f["class"] == WRONG and "not on PATH" in f["message"]
    assert "brew install tailscale" in f["remedy"]


def test_bundle_mismatch_is_wrong_with_the_repair(tailscale_device, capsys, monkeypatch):
    monkeypatch.setenv("FAKE_TS_BUNDLE", "1")
    _, found = findings(capsys)
    [f] = problems(found, "Network")
    assert f["class"] == WRONG and "bundle mismatch" in f["message"]
    assert "rm /usr/local/bin/tailscale" in f["remedy"]
    assert "brew install tailscale" in f["remedy"]


def test_app_and_cli_version_difference_is_a_note(tailscale_device, capsys, monkeypatch):
    monkeypatch.setenv("FAKE_TS_VERSION", "1.0.1")
    _, found = findings(capsys)
    assert problems(found, "Network") == []
    assert any("app is 1.0.0 and the command-line tool is 1.0.1" in f["message"]
               for f in in_section(found, "Network"))


def test_tailnet_mismatch_is_wrong(tailscale_device, capsys, monkeypatch):
    ts_status(tailscale_device, monkeypatch, tailnet="example-other-tailnet")
    _, found = findings(capsys)
    [f] = problems(found, "Network")
    assert f["class"] == WRONG
    assert f["remedy"] == "tailscale switch example-tailnet"


def test_specify_tailnet_is_not_compared(tailscale_device, capsys, monkeypatch):
    tailscale_device.manifest('[network]\nprovider = "tailscale"\n\n'
                              '[network.tailscale]\ntailnet = "(specify)"\n')
    ts_status(tailscale_device, monkeypatch, tailnet="anything")
    _, found = findings(capsys)
    assert problems(found, "Network") == []


def test_ssh_expected_and_off_is_missing(tailscale_device, capsys):
    tailscale_device.manifest('[network]\nprovider = "tailscale"\n\n'
                              '[network.tailscale]\nssh = true\n')
    _, found = findings(capsys)
    [f] = problems(found, "Network")
    assert f["class"] == MISSING and f["remedy"] == "tailscale set --ssh"


def test_ssh_expected_and_on_is_clean(tailscale_device, capsys, monkeypatch):
    tailscale_device.manifest('[network]\nprovider = "tailscale"\n\n'
                              '[network.tailscale]\nssh = true\n')
    ts_status(tailscale_device, monkeypatch, ssh_on=True)
    _, out, _ = run(capsys)
    _, found = findings(capsys)
    assert problems(found, "Network") == []
    assert "EXAMPLEHOSTKEY" not in out


def test_bad_tailscale_table_is_wrong(tailscale_device, capsys):
    tailscale_device.manifest('[network]\nprovider = "tailscale"\n\n'
                              '[network.tailscale]\nssh = "yes"\n')
    _, found = findings(capsys)
    [f] = problems(found, "Network")
    assert f["class"] == WRONG and "true or false" in f["message"]


def test_tailscale_detect_and_handoff(tailscale_device, monkeypatch):
    ts = tailscale_device.ts
    ts_status(tailscale_device, monkeypatch, ssh_on=True)
    assert ts.detect() == {"installed": True, "running": True, "tailnet": "example-tailnet",
                           "ssh": True}
    ts_status(tailscale_device, monkeypatch, backend="Stopped")
    assert ts.detect()["running"] is False
    assert ts.handoff({}) == ["tailscale up"]
    assert ts.handoff({"ssh": True}) == ["tailscale up", "tailscale set --ssh"]
    monkeypatch.setattr(audit_device, "_system", lambda: "Linux")
    assert ts.handoff({})[0] == "sudo tailscale up"


# --------------------------------------------------------------------------
# Workspace
# --------------------------------------------------------------------------

ROWS = """### Example Studio

| Project Name | Directory Path |
|-------------|---------------|
| alpha | ~/Code/example-studio/example-alpha |
| beta | ~/Code/example-studio/example-beta |

### Example Client

| Project Name | Directory Path |
|-------------|---------------|
| gamma | ~/Code/example-client/example-gamma |
| old-thing (paused) | ~/Code/example-client/example-paused |
"""


def test_workspace_root_missing_is_wrong(device, capsys):
    code = audit_device.main(["--json", "--workspace-root", "~/NoSuchWorkspace"])
    found = json.loads(capsys.readouterr().out)["findings"]
    [f] = in_section(found, "Workspace")
    assert f["class"] == WRONG and "does not exist" in f["message"]
    assert code == 1


def test_workspace_claude_md_missing(device, capsys):
    (device.workspace / "CLAUDE.md").unlink()
    _, found = findings(capsys)
    [f] = in_section(found, "Workspace")
    assert f["class"] == MISSING and f["remedy"] is None and "Clone" in f["you"]


def test_dangling_claude_md_link_is_wrong(device, capsys):
    md = device.workspace / "CLAUDE.md"
    md.unlink()
    md.symlink_to(device.home / "seed" / "CLAUDE.md")
    _, found = findings(capsys)
    [f] = in_section(found, "Workspace")
    assert f["class"] == WRONG and "does not exist" in f["message"]
    assert "ln -sfn" in f["remedy"]


def test_resolving_claude_md_link_is_a_note(device, capsys):
    real = device.write("seed/CLAUDE.md", "# seed\n")
    md = device.workspace / "CLAUDE.md"
    md.unlink()
    md.symlink_to(real)
    _, found = findings(capsys)
    ws = in_section(found, "Workspace")
    assert problems(found, "Workspace") == []
    assert any("links to ~/seed/CLAUDE.md" in f["message"] for f in ws)


def test_no_table_is_a_note(device, capsys):
    _, found = findings(capsys)
    [f] = in_section(found, "Workspace")
    assert f["class"] is None and "Project Directory Mapping" in f["message"]


def test_clone_remedies_for_alias_and_non_alias_orgs(device, capsys):
    table(device, ROWS)
    (device.workspace / "example-studio" / "example-alpha").mkdir()
    code, found = findings(capsys)
    clones = {f["message"]: f for f in problems(found, "Workspace")}
    assert set(clones) == {"beta is not cloned at ~/Code/example-studio/example-beta.",
                           "gamma is not cloned at ~/Code/example-client/example-gamma."}
    beta = clones["beta is not cloned at ~/Code/example-studio/example-beta."]
    gamma = clones["gamma is not cloned at ~/Code/example-client/example-gamma."]
    assert beta["class"] == gamma["class"] == MISSING
    assert beta["org"] == "example-studio" and gamma["org"] == "example-client"
    assert beta["remedy"] == (f"gh repo clone {STUDIO['github_account']}/example-beta "
                              f"~/Code/example-studio/example-beta")
    assert gamma["remedy"] == (f"git clone git@{CLIENT['ssh_host_alias']}:"
                               f"{CLIENT['github_account']}/example-gamma.git "
                               f"~/Code/example-client/example-gamma")
    for f in clones.values():
        assert f["remedy"].startswith(("gh repo clone ", "git clone "))
    assert code == 2


def test_paused_row_is_skipped_and_rows_are_counted(device, capsys):
    table(device, ROWS)
    _, found = findings(capsys)
    notes = [f["message"] for f in in_section(found, "Workspace", None)]
    assert any("example-paused" in m and "skipped" in m for m in notes)
    assert "0 of 3 project rows present (3 not cloned)." in notes
    assert not any("ignored" in f["message"] for f in in_section(found, "Workspace"))


def test_org_directory_missing(device, capsys):
    table(device, "| delta | ~/Code/example-absent/example-delta |\n")
    _, found = findings(capsys)
    org = [f for f in problems(found, "Workspace") if "Org directory" in f["message"]]
    assert len(org) == 1 and org[0]["class"] == MISSING
    assert org[0]["remedy"] == "mkdir -p ~/Code/example-absent"
    clone = [f for f in problems(found, "Workspace") if "delta" in f["message"]][0]
    assert clone["remedy"].startswith("gh repo clone (specify)/example-delta ")
    assert "/run-organize-orgs" in clone["you"]


def test_org_directory_without_org_json_is_wrong(device, capsys):
    (device.workspace / "example-bare").mkdir()
    table(device, "| delta | ~/Code/example-bare/example-delta |\n")
    _, found = findings(capsys)
    [org] = [f for f in problems(found, "Workspace") if "org.json" in f["message"]]
    assert org["class"] == WRONG and org["remedy"] == "run /run-organize-orgs"


def test_project_rows_parser():
    rows = audit_device.project_rows(
        "## Project Directory Mapping\n\n| a | `~/Code/x/a/` |\n| b (removed) | ~/Code/x/b |\n"
        "| no path | here |\n", Path("/h"))
    assert [(r.name, r.path_text, r.skipped) for r in rows] == \
        [("a", "~/Code/x/a", False), ("b (removed)", "~/Code/x/b", True)]
    assert audit_device.project_rows("# nothing\n", Path("/h")) is None


# --------------------------------------------------------------------------
# public surface for the Overwatch device check (U5)
# --------------------------------------------------------------------------

def test_import_has_no_side_effects_on_old_python(monkeypatch, capsys):
    monkeypatch.setattr(sys, "version_info", (3, 10, 0, "final", 0))
    spec = importlib.util.spec_from_file_location(
        "audit_device_old_python", Path(audit_device.__file__))
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, "audit_device_old_python", module)  # dataclasses need it
    spec.loader.exec_module(module)  # must not raise SystemExit
    assert module.main(["--json"]) == 3
    assert "3.11" in capsys.readouterr().err


def test_has_include_for(device):
    stanzas = audit_device.parse_git_config(
        '[includeIf "gitdir:~/Code/example-client/"]\n\tpath = x\n'
        f'[includeIf "gitdir:{device.home}/Code/example-wrong-but-present/"]\n\tpath = y\n')
    home = device.home
    assert audit_device.has_include_for(stanzas, device.workspace / "example-client", home)
    assert audit_device.has_include_for(
        stanzas, device.workspace / "example-wrong-but-present", home)
    assert not audit_device.has_include_for(stanzas, device.workspace / "example-studio", home)


def test_is_default_module_level(device):
    contracts = audit_device.load_contracts(device.workspace)
    by_org = {c.org: c for c in contracts}
    assert audit_device.is_default(by_org["example-studio"], contracts)
    assert not audit_device.is_default(by_org["example-client"], contracts)
    second = audit_device.Contract("example-other", device.workspace / "x", "OtherAccount",
                                   "Other", "other@example.com")
    assert not audit_device.is_default(by_org["example-studio"], [*contracts, second])
    assert callable(audit_device.gh_login_present)


# --------------------------------------------------------------------------
# no real home
# --------------------------------------------------------------------------

_HOOK_STATE: dict = {"fn": None}


def _dispatch(event, args):
    fn = _HOOK_STATE["fn"]
    if fn is not None:
        fn(event, args)


sys.addaudithook(_dispatch)


def test_no_real_home_path_is_read_by_the_new_sections(tailscale_device, capsys, monkeypatch):
    device = tailscale_device
    device.stub("claude", CLAUDE_STUB)
    device.stub("aws", AWS_STUB)
    device.stub("security", SECURITY_STUB)
    device.write(".aws/config", "[default]\n")
    device.write(".claude/settings.json", "{}")
    device.write(".claude/plugins/known_marketplaces.json", "{}")
    device.manifest(
        '[claude]\nmarketplaces = ["ExampleStudio/m"]\nplugins = ["p@m"]\n'
        'hooks = ["pre-commit"]\n[aws]\nprofiles = ["default"]\n'
        '[keychain]\nitems = ["example-item"]\n'
        '[network]\nprovider = "tailscale"\n[network.tailscale]\nssh = true\n')
    table(device, ROWS)
    seen: list[str] = []
    allowed = tuple(os.path.realpath(p) for p in
                    {PLUGIN_ROOT, sys.prefix, sys.base_prefix, sys.exec_prefix})

    def hook(event, args):
        if event in ("open", "os.listdir", "os.scandir") and args:
            target = args[0]
            if isinstance(target, (str, bytes, os.PathLike)):
                seen.append(os.path.realpath(os.fsdecode(target)))

    _HOOK_STATE["fn"] = hook
    try:
        audit_device.main(["--json", "--full"])
    finally:
        _HOOK_STATE["fn"] = None
    out = capsys.readouterr().out
    sections = {f["section"] for f in json.loads(out)["findings"]}
    assert {"Claude Code", "AWS", "Keychain", "Network", "Workspace"} <= sections
    leaked = [p for p in seen
              if (p == REAL_HOME or p.startswith(REAL_HOME + os.sep))
              and not p.startswith(allowed)]
    assert seen
    assert leaked == []


# --------------------------------------------------------------------------
# structured actions for the installer
# --------------------------------------------------------------------------

def _actions(found, kind):
    return [f["action"] for f in found if f["action"] and f["action"]["kind"] == kind]


def test_package_action(device, capsys, monkeypatch):
    monkeypatch.setattr(audit_device, "package_manager", lambda: "brew")
    device.unstub("rg")
    _, found = findings(capsys)
    assert _actions(found, "package") == [{"kind": "package", "manager": "brew",
                                           "name": "ripgrep"}]
    device.unstub("claude")  # the native installer is not a package
    _, found = findings(capsys)
    assert len(_actions(found, "package")) == 1


def test_git_include_action(device, capsys):
    device.gitconfig("[user]\n\tname = Example Studio\n\temail = studio@example.com\n")
    _, found = findings(capsys)
    [action] = _actions(found, "git_include")
    assert action == {
        "kind": "git_include",
        "org_dir": "~/Code/example-client/",
        "include_path": "~/.gitconfig-example-client",
        "stanza": '[includeIf "gitdir:~/Code/example-client/"]\n'
                  "\tpath = ~/.gitconfig-example-client",
        "file_text": f"[user]\n\tname = {CLIENT['git_user_name']}\n"
                     f"\temail = {CLIENT['git_email']}\n",
    }


def test_ssh_block_action(device, capsys):
    device.ssh_config("Host github.com\n    HostName github.com\n"
                      "    IdentityFile ~/.ssh/id_ed25519\n    IdentitiesOnly yes\n")
    _, found = findings(capsys)
    [action] = _actions(found, "ssh_block")
    assert action == {
        "kind": "ssh_block",
        "host": "github-example-client",
        "block": "Host github-example-client\n    HostName github.com\n"
                 "    IdentityFile ~/.ssh/id_ed25519_example-client\n    IdentitiesOnly yes",
        "key_path": "~/.ssh/id_ed25519_example-client",
    }


def test_claude_actions(device, capsys):
    device.write(".claude/plugins/known_marketplaces.json", json.dumps(MARKETS))
    device.write(".claude/settings.json", json.dumps(
        {"enabledPlugins": {"off@example-market": False}}))
    device.manifest('[claude]\nmarketplaces = ["ExampleStudio/other-market"]\n'
                    'plugins = ["new@example-market", "off@example-market"]\n')
    _, found = findings(capsys)
    assert _actions(found, "plugin_marketplace_add") == \
        [{"kind": "plugin_marketplace_add", "entry": "ExampleStudio/other-market"}]
    assert _actions(found, "plugin_install") == \
        [{"kind": "plugin_install", "entry": "new@example-market"}]
    assert _actions(found, "plugin_enable") == \
        [{"kind": "plugin_enable", "entry": "off@example-market"}]


def test_clone_action(device, capsys):
    table(device, ROWS + "| delta | ~/Code/example-absent/example-delta |\n")
    _, found = findings(capsys)
    clones = {a["dest"]: a for a in _actions(found, "clone")}
    assert clones == {
        "~/Code/example-studio/example-alpha": {
            "kind": "clone", "dest": "~/Code/example-studio/example-alpha",
            "command": "gh repo clone ExampleStudio/example-alpha "
                       "~/Code/example-studio/example-alpha"},
        "~/Code/example-studio/example-beta": {
            "kind": "clone", "dest": "~/Code/example-studio/example-beta",
            "command": "gh repo clone ExampleStudio/example-beta "
                       "~/Code/example-studio/example-beta"},
        "~/Code/example-client/example-gamma": {
            "kind": "clone", "dest": "~/Code/example-client/example-gamma",
            "command": "git clone git@github-example-client:example-client-bot/"
                       "example-gamma.git ~/Code/example-client/example-gamma"},
    }
    # No owner is known for an org with no contract, so that row has no action.
    [delta] = [f for f in found if "delta" in f["message"] and f["class"] == MISSING]
    assert delta["action"] is None


def test_wrong_findings_and_notes_never_carry_an_action(device, capsys, monkeypatch):
    device.gitconfig(
        "[user]\n\tname = Someone Else\n\temail = studio@example.com\n"
        '[includeIf "gitdir:/Users/example/Code/example-client/"]\n'
        "\tpath = ~/.gitconfig-example-client\n[core]\n\thooksPath = ~/elsewhere\n")
    device.write(".claude/lastmilefirst/git-hooks/pre-commit", "#!/bin/sh\n")
    device.manifest('[claude]\nhooks = ["pre-commit"]\n[network]\nprovider = "nope"\n')
    (device.workspace / "example-bare").mkdir()
    table(device, "| delta | ~/Code/example-bare/example-delta |\n")
    _, found = findings(capsys)
    wrongs = [f for f in found if f["class"] == WRONG]
    assert {f["section"] for f in wrongs} >= {"git identity", "Claude Code", "Network",
                                              "Workspace"}
    assert all(f["action"] is None for f in wrongs)
    assert all(f["action"] is None for f in found if f["class"] is None)
    forced = audit_device.Finding(audit_device.ERROR, None, "x", "y",
                                  finding_class=WRONG, action={"kind": "package"})
    assert forced.action is None


def test_build_context_is_what_main_uses(device, capsys, monkeypatch):
    ctx = audit_device.build_context(workspace_root="~/Code", full=True)
    assert ctx.home == device.home and ctx.workspace_root == device.workspace
    assert ctx.full and ctx.liveness and not ctx.manifest.found
    assert {c.org for c in ctx.contracts} == {"example-studio", "example-client"}
    assert audit_device.build_context(full=True, no_liveness=True).liveness is False
    with pytest.raises(TypeError):
        audit_device.build_context(bogus=1)
    seen = []
    real = audit_device.build_context
    monkeypatch.setattr(audit_device, "build_context",
                        lambda args=None, **kw: seen.append(args) or real(args, **kw))
    run(capsys)
    assert len(seen) == 1 and seen[0].workspace_root is not None
