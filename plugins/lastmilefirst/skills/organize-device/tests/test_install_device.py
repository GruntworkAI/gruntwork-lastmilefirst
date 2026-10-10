"""Tests for the checklist renderer, the create-only `--apply` writers, and `--snapshot`.

Every test runs on the fake machine from conftest (a temp HOME, two invented
orgs, stub binaries on PATH). Fixtures specific to this file live here.
"""
from __future__ import annotations

import io
import os
import stat
import sys
from pathlib import Path

import pytest

import audit_device
import install_device
from audit_device import MISSING, missing, wrong
from device_manifest import default_manifest_path, load_manifest
from .conftest import CLIENT, GH_STUB, PLUGIN_ROOT, REAL_HOME, SSH_CONFIG

CLIENT_INCLUDE = '[includeIf "gitdir:~/Code/example-client/"]\n' \
                 "\tpath = ~/.gitconfig-example-client"
CLIENT_USER = f"[user]\n\tname = {CLIENT['git_user_name']}\n\temail = {CLIENT['git_email']}"
GLOBAL_ONLY = "[user]\n\tname = Example Studio\n\temail = studio@example.com\n" \
              "[credential]\n\thelper = osxkeychain\n"
SSH_WITHOUT_CLIENT = SSH_CONFIG.split("Host github-example-client")[0].rstrip() + "\n"

GH_RECORDING_STUB = GH_STUB.replace(
    "exit 0\n",
    'if [ "$1" = "repo" ]; then echo "$@" >> "$FAKE_GH_LOG"; fi\nexit 0\n', 1)


class FakeTTY(io.StringIO):
    """A stdin that answers as a terminal would."""

    def isatty(self) -> bool:
        return True


def answer(monkeypatch, text: str, tty: bool = True) -> None:
    monkeypatch.setattr(sys, "stdin", FakeTTY(text) if tty else io.StringIO(text))


def run(capsys, *argv):
    code = install_device.main(["--workspace-root", "~/Code", *argv])
    out = capsys.readouterr()
    return code, out.out, out.err


def step_lines(out: str) -> list[str]:
    return [l for l in out.splitlines() if l and l.lstrip()[:1].isdigit() and ". [" in l]


def tree(root: Path) -> dict[str, tuple]:
    """Every path under root with its content and mode, to prove nothing changed."""
    state = {}
    for dirpath, dirnames, filenames in os.walk(root):
        for name in dirnames:
            path = Path(dirpath) / name
            state[str(path)] = ("dir", stat.S_IMODE(path.lstat().st_mode))
        for name in filenames:
            path = Path(dirpath) / name
            state[str(path)] = (path.read_bytes(), stat.S_IMODE(path.lstat().st_mode))
    return state


@pytest.fixture(autouse=True)
def workspace_claude_md(device, monkeypatch):
    """A workspace CLAUDE.md with no project table, so the Workspace section is quiet.

    Also clears the AWS file overrides, so a value in the real environment can
    never point a test at the real home.
    """
    monkeypatch.delenv("AWS_CONFIG_FILE", raising=False)
    monkeypatch.delenv("AWS_SHARED_CREDENTIALS_FILE", raising=False)
    device.write("Code/CLAUDE.md", "# Example workspace\n")
    return device


def break_client_include(device) -> None:
    device.gitconfig(GLOBAL_ONLY)
    (device.home / ".gitconfig-example-client").unlink()


# --------------------------------------------------------------------------
# checklist
# --------------------------------------------------------------------------

def test_clean_machine_has_nothing_to_do(device, capsys):
    code, out, _ = run(capsys)
    assert code == 0
    assert "Nothing to do: the audit found nothing missing or wrong." in out
    assert step_lines(out) == []


def seed_problems(device, monkeypatch):
    device.stub("brew")
    device.unstub("jq")
    device.ssh_config(SSH_WITHOUT_CLIENT)
    monkeypatch.setenv("FAKE_GH_LOGINS", "ExampleStudio")
    device.gitconfig("[user]\n\tname = Someone Else\n\temail = studio@example.com\n")
    (device.home / ".gitconfig-example-client").unlink()


def test_checklist_orders_and_tags_steps(device, capsys, monkeypatch):
    seed_problems(device, monkeypatch)
    code, out, _ = run(capsys)
    assert code == 0
    lines = step_lines(out)
    tags = [(l.split("[")[1].split("]")[0], l.split("] ")[1].split(":")[0]) for l in lines]
    assert tags == [
        ("script", "Tools"),                         # packages first
        ("you", "SSH (example-client)"),             # the key, before the alias that uses it
        ("script", "SSH (example-client)"),          # the Host block
        ("you", "GitHub logins (example-client)"),   # gh auth login
        ("you", "GitHub logins (example-client)"),   # the browser half of the same finding
        ("script", "git identity (example-client)"),  # includeIf + include file
        ("you", "git identity (example-studio)"),    # a wrong global identity
    ]
    assert [l.split(".")[0].strip() for l in lines] == [str(n) for n in range(1, 8)]
    assert "brew install jq" in out
    assert "ssh-keygen -t ed25519" in out
    assert "gh auth login --hostname github.com" in out
    assert CLIENT_INCLUDE.replace("\n", "\n      ") in out
    assert "Replace the [user] section in ~/.gitconfig with:" in out
    assert "3 script steps, 4 you steps." in out
    assert "Run with --apply to perform the script steps." in out


def test_unknown_package_manager_is_a_you_step(device, capsys):
    device.unstub("jq")  # no brew or apt stub, so the remedy is prose
    _, out, _ = run(capsys)
    assert step_lines(out) == ["1. [you] Tools: jq is not installed (baseline)."]


def test_checklist_writes_nothing(device, capsys, monkeypatch):
    seed_problems(device, monkeypatch)
    before = tree(device.home)
    run(capsys)
    assert tree(device.home) == before


def test_invalid_manifest_exits_3(device, capsys):
    device.manifest('[secrets]\ntoken = "x"\n')
    code, out, err = run(capsys)
    assert code == 3 and "unknown top-level table" in err and out == ""


def test_force_without_snapshot_is_a_bad_argument(device, capsys):
    with pytest.raises(SystemExit) as exc:
        install_device.main(["--force"])
    assert exc.value.code == 3


# --------------------------------------------------------------------------
# --apply: confirmation
# --------------------------------------------------------------------------

def test_apply_answered_no_writes_nothing(device, capsys, monkeypatch):
    break_client_include(device)
    before = tree(device.home)
    answer(monkeypatch, "n\n")
    code, out, _ = run(capsys, "--apply")
    assert code == 0
    assert "[script] git identity" in out
    assert "Nothing was changed." in out
    assert tree(device.home) == before


def test_apply_on_non_interactive_stdin_is_a_no(device, capsys, monkeypatch):
    break_client_include(device)
    before = tree(device.home)
    answer(monkeypatch, "y\n", tty=False)
    code, out, _ = run(capsys, "--apply")
    assert code == 0
    assert "stdin is not a terminal" in out
    assert tree(device.home) == before


def test_apply_with_no_script_steps_does_not_ask(device, capsys, monkeypatch):
    device.gitconfig("[user]\n\tname = Someone Else\n\temail = studio@example.com\n"
                     + CLIENT_INCLUDE + "\n")
    answer(monkeypatch, "")
    code, out, _ = run(capsys, "--apply")
    assert code == 0 and "No script steps to run." in out and "[y/N]" not in out


# --------------------------------------------------------------------------
# --apply: git identity
# --------------------------------------------------------------------------

def backups(directory: Path, name: str) -> list[Path]:
    return sorted(directory.glob(f"{name}.bak-*"))


def test_apply_creates_include_and_appends_stanza_with_backup(device, capsys, monkeypatch):
    break_client_include(device)
    answer(monkeypatch, "y\n")
    code, out, _ = run(capsys, "--apply")
    assert code == 0, out
    assert "done: created ~/.gitconfig-example-client; appended the includeIf" in out

    gitconfig = (device.home / ".gitconfig").read_text(encoding="utf-8")
    assert gitconfig.startswith(GLOBAL_ONLY)            # original lines intact
    assert gitconfig == GLOBAL_ONLY + "\n" + CLIENT_INCLUDE + "\n"
    assert "/Users/" not in gitconfig and str(device.home) not in gitconfig
    include = (device.home / ".gitconfig-example-client").read_text(encoding="utf-8")
    assert include == CLIENT_USER + "\n"

    saved = backups(device.home, ".gitconfig")
    assert len(saved) == 1 and saved[0].read_text(encoding="utf-8") == GLOBAL_ONLY

    # the audit now agrees, and a rerun has nothing to do
    assert audit_device.main(["--workspace-root", "~/Code"]) == 0
    capsys.readouterr()
    _, out, _ = run(capsys)
    assert "Nothing to do" in out


def test_apply_keeps_an_existing_matching_include_file(device, capsys, monkeypatch):
    device.gitconfig(GLOBAL_ONLY)  # the include file from conftest stays
    original = (device.home / ".gitconfig-example-client").read_bytes()
    answer(monkeypatch, "y\n")
    code, out, _ = run(capsys, "--apply")
    assert code == 0
    assert "created" not in out.split("done:")[1].split("\n")[0]
    assert (device.home / ".gitconfig-example-client").read_bytes() == original
    assert (device.home / ".gitconfig").read_text(encoding="utf-8").endswith(
        CLIENT_INCLUDE + "\n")


def test_apply_refuses_stanza_when_include_file_disagrees(device, capsys, monkeypatch):
    device.gitconfig(GLOBAL_ONLY)
    device.write(".gitconfig-example-client",
                 "[user]\n\tname = example-client-bot\n\temail = other@example.com\n")
    before = tree(device.home)
    answer(monkeypatch, "y\n")
    code, out, _ = run(capsys, "--apply")
    assert code == 1
    assert "failed: ~/.gitconfig-example-client already exists with a different" in out
    assert tree(device.home) == before


def test_apply_never_touches_a_wrong_finding(device, capsys, monkeypatch):
    wrong_global = "[user]\n\tname = Someone Else\n\temail = studio@example.com\n"
    device.gitconfig(wrong_global)
    (device.home / ".gitconfig-example-client").unlink()
    ssh_wrong = SSH_CONFIG.replace(
        "IdentityFile ~/.ssh/id_ed25519_example-client\n    IdentitiesOnly yes\n",
        "IdentityFile ~/.ssh/id_ed25519_example-client\n")
    device.ssh_config(ssh_wrong)
    answer(monkeypatch, "y\n")
    code, out, _ = run(capsys, "--apply")
    assert code == 0, out
    assert "[you] git identity (example-studio): Global git identity is wrong" in out
    assert "[you] SSH (example-client): `Host github-example-client` in ~/.ssh/config is wrong" \
        in out
    # the wrong [user] lines are exactly as they were; only the missing stanza was added
    assert (device.home / ".gitconfig").read_text(encoding="utf-8") == \
        wrong_global + "\n" + CLIENT_INCLUDE + "\n"
    assert (device.home / ".ssh" / "config").read_text(encoding="utf-8") == ssh_wrong
    assert backups(device.home / ".ssh", "config") == []


# --------------------------------------------------------------------------
# --apply: SSH
# --------------------------------------------------------------------------

def test_apply_appends_ssh_block_with_backup_and_mode_600(device, capsys, monkeypatch):
    config = device.ssh_config(SSH_WITHOUT_CLIENT)
    config.chmod(0o644)
    answer(monkeypatch, "y\n")
    code, out, _ = run(capsys, "--apply")
    assert code == 0, out
    text = config.read_text(encoding="utf-8")
    assert text.startswith(SSH_WITHOUT_CLIENT)
    assert text.endswith("Host github-example-client\n    HostName github.com\n"
                         "    IdentityFile ~/.ssh/id_ed25519_example-client\n"
                         "    IdentitiesOnly yes\n")
    assert stat.S_IMODE(config.stat().st_mode) == 0o600
    saved = backups(device.home / ".ssh", "config")
    assert len(saved) == 1
    assert saved[0].read_text(encoding="utf-8") == SSH_WITHOUT_CLIENT
    assert stat.S_IMODE(saved[0].stat().st_mode) == 0o600
    assert "done: appended Host github-example-client" in out


def test_apply_refuses_ssh_block_defined_in_an_included_file(device, capsys, monkeypatch):
    """The audit does not follow Include; the writer does, and refuses."""
    device.ssh_config(SSH_WITHOUT_CLIENT)
    device.write(".ssh/config.d/extra", "Host github-example-client\n    HostName example.com\n")
    before = tree(device.home)
    answer(monkeypatch, "y\n")
    code, out, _ = run(capsys, "--apply")
    assert code == 1
    assert "failed: refused: a Host github-example-client block already exists in " \
           "~/.ssh/config.d/extra" in out
    assert tree(device.home) == before


@pytest.mark.parametrize("existing", [
    "host GITHUB-EXAMPLE-CLIENT\n    HostName github.com\n",
    "Host=other github-example-client\n",
    'Host "github-example-client"\n',
    "Match host github-example-client\n    User git\n",
])
def test_ssh_writer_refuses_any_existing_form(device, existing):
    config = device.ssh_config(existing)
    state = install_device.ApplyState(stamp="20260101T000000", workspace_root=device.workspace)
    ok, detail = install_device.apply_ssh_block(
        state, "github-example-client", "Host github-example-client\n    HostName github.com")
    assert not ok and "refused" in detail
    assert config.read_text(encoding="utf-8") == existing
    assert backups(device.home / ".ssh", "config") == []


def test_ssh_writer_creates_dot_ssh_when_absent(device):
    import shutil
    shutil.rmtree(device.home / ".ssh")
    state = install_device.ApplyState(stamp="20260101T000000", workspace_root=device.workspace)
    ok, _ = install_device.apply_ssh_block(state, "github-example-client",
                                           "Host github-example-client\n    HostName github.com")
    assert ok
    assert stat.S_IMODE((device.home / ".ssh").stat().st_mode) == 0o700
    assert stat.S_IMODE((device.home / ".ssh" / "config").stat().st_mode) == 0o600


# --------------------------------------------------------------------------
# --apply: packages, clones, manifest copy
# --------------------------------------------------------------------------

def test_apply_runs_the_package_install(device, capsys, monkeypatch):
    log = device.home.parent / "brew.log"
    device.stub("brew", f'#!/bin/sh\necho "$@" >> {log}\nexit 0\n')
    device.unstub("jq")
    answer(monkeypatch, "y\n")
    code, out, _ = run(capsys, "--apply")
    assert code == 0
    assert log.read_text(encoding="utf-8") == "install jq\n"
    assert "done: brew install jq" in out


def test_failed_package_install_is_reported_and_exits_1(device, capsys, monkeypatch):
    device.stub("brew", "#!/bin/sh\nexit 7\n")
    device.unstub("jq")
    answer(monkeypatch, "y\n")
    code, out, _ = run(capsys, "--apply")
    assert code == 1 and "failed: brew install jq exited 7" in out


def workspace_section(ctx):
    return [
        missing("Workspace", "example-studio", "example-alpha is not cloned.",
                "gh repo clone ExampleStudio/example-alpha ~/Code/example-studio/example-alpha"),
        missing("Workspace", "example-studio", "example-beta is not cloned.",
                "gh repo clone ExampleStudio/example-beta ~/Code/example-studio/example-beta"),
    ]


def test_clones_are_confirmed_one_row_at_a_time(device, capsys, monkeypatch):
    log = device.home.parent / "gh.log"
    monkeypatch.setenv("FAKE_GH_LOG", str(log))
    device.stub("gh", GH_RECORDING_STUB)
    device.gitconfig(GLOBAL_ONLY)  # one non-clone script step, so ordering shows too
    monkeypatch.setattr(audit_device, "SECTIONS",
                        [*audit_device.SECTIONS, ("Workspace", workspace_section)])
    answer(monkeypatch, "y\ny\nn\n")
    code, out, _ = run(capsys, "--apply")
    assert code == 0, out
    lines = step_lines(out)
    assert [l.split("] ")[1].split(":")[0] for l in lines] == \
        ["git identity (example-client)", "Workspace (example-studio)",
         "Workspace (example-studio)"]
    assert all("[script]" in l for l in lines)
    assert out.count("[y/N]") == 3  # the one confirmation plus one per clone
    assert "3. skipped" in out
    alpha = device.home / "Code" / "example-studio" / "example-alpha"
    assert log.read_text(encoding="utf-8") == \
        f"repo clone ExampleStudio/example-alpha {alpha}\n"


def test_declining_the_first_question_skips_every_clone(device, capsys, monkeypatch):
    log = device.home.parent / "gh.log"
    monkeypatch.setenv("FAKE_GH_LOG", str(log))
    device.stub("gh", GH_RECORDING_STUB)
    monkeypatch.setattr(audit_device, "SECTIONS",
                        [*audit_device.SECTIONS, ("Workspace", workspace_section)])
    answer(monkeypatch, "n\ny\ny\n")
    run(capsys, "--apply")
    assert not log.exists()


def test_clone_remedy_shapes(device, capsys, monkeypatch):
    def section(ctx):
        return [
            missing("Workspace", "example-client", "example-gamma is not cloned.",
                    "git clone git@github-example-client:example-client-bot/example-gamma.git "
                    "~/Code/example-client/example-gamma"),
            missing("Workspace", "example-side", "example-delta is not cloned.",
                    "gh repo clone (specify)/example-delta ~/Code/example-side/example-delta",
                    you="The owner is unknown; run /run-organize-orgs first."),
        ]

    monkeypatch.setattr(audit_device, "SECTIONS", [*audit_device.SECTIONS, ("Workspace", section)])
    _, out, _ = run(capsys)
    assert step_lines(out) == [
        "1. [script] Workspace (example-client): example-gamma is not cloned.",
        "2. [you] Workspace (example-side): example-delta is not cloned.",
        "3. [you] Workspace (example-side): example-delta is not cloned.",
    ]


def test_a_note_with_a_handoff_is_an_optional_you_step(device, capsys, monkeypatch):
    def section(ctx):
        return [audit_device.Finding(audit_device.INFO, None, "Example network is stopped.",
                                     None, section="Network", you="example-net up")]

    monkeypatch.setattr(audit_device, "SECTIONS", [*audit_device.SECTIONS, ("Network", section)])
    _, out, _ = run(capsys)
    assert step_lines(out) == ["1. [you] Network: Example network is stopped. (optional)"]
    assert "      example-net up" in out


def test_claude_plugin_remedy_is_a_script_step(device, capsys, monkeypatch):
    log = device.home.parent / "claude.log"
    device.stub("claude", f'#!/bin/sh\necho "$@" >> {log}\nexit 0\n')

    def claude_section(ctx):
        return [
            missing("Claude Code", None, "Marketplace example/market is not known.",
                    "claude plugin marketplace add example/market"),
            missing("Claude Code", None, "Plugin example@market is not enabled.",
                    "claude plugin install example@market"),
            wrong("Claude Code", None, "Something exists and is wrong.",
                  "claude plugin install example-other@market"),
        ]

    monkeypatch.setattr(audit_device, "SECTIONS",
                        [*audit_device.SECTIONS, ("Claude Code", claude_section)])
    answer(monkeypatch, "y\n")
    code, out, _ = run(capsys, "--apply")
    assert code == 0
    assert "2 script steps, 1 you step." in out
    calls = [l for l in log.read_text(encoding="utf-8").splitlines() if l.startswith("plugin")]
    assert calls == ["plugin marketplace add example/market", "plugin install example@market"]


def test_manifest_copy_only_when_none_exists(device, capsys, monkeypatch, tmp_path):
    carried = tmp_path / "carried.toml"
    carried.write_text('[tools]\nextra = []\n', encoding="utf-8")
    answer(monkeypatch, "y\n")
    code, out, _ = run(capsys, "--apply", "--manifest", str(carried))
    assert code == 0, out
    assert "[script] Device manifest" in out
    target = default_manifest_path(home=device.home)
    assert target.read_text(encoding="utf-8") == '[tools]\nextra = []\n'

    target.write_text("[tools]\nextra = [\"uv\"]\n", encoding="utf-8")
    _, out, _ = run(capsys, "--manifest", str(carried))
    assert "Device manifest" not in out  # one is there, so nothing is offered
    assert target.read_text(encoding="utf-8") == "[tools]\nextra = [\"uv\"]\n"


# --------------------------------------------------------------------------
# --snapshot
# --------------------------------------------------------------------------

CLAUDE_STUB = """#!/bin/sh
if [ "$1 $2 $3" = "plugin marketplace list" ]; then
  echo '[{"name": "example-market", "source": "github", "repo": "ExampleStudio/example-market",'
  echo '  "installLocation": "/nowhere"},'
  echo ' {"name": "local-market", "source": "directory", "path": "/opt/example-market"}]'
  exit 0
fi
if [ "$1 $2" = "plugin list" ]; then
  echo '[{"id": "example@example-market", "enabled": true, "scope": "user"},'
  echo ' {"id": "off@example-market", "enabled": false, "scope": "user"},'
  echo ' {"id": "proj@example-market", "enabled": true, "scope": "project"}]'
  exit 0
fi
exit 0
"""

FAKE_SECRET = "EXAMPLEFAKESECRETVALUE0000"


def seed_snapshot_machine(device):
    for tool in ("uv", "aws", "docker"):
        device.stub(tool)
    device.stub("claude", CLAUDE_STUB)
    device.write(".aws/config", "[default]\nregion = us-example-1\n"
                                "[profile example-dev]\nregion = us-example-1\n"
                                "[sso-session example-sso]\nsso_region = us-example-1\n")
    device.write(".aws/credentials", f"[default]\naws_secret_access_key = {FAKE_SECRET}\n"
                                     f"[example-ci]\naws_secret_access_key = {FAKE_SECRET}\n")
    device.write(".claude/lastmilefirst/git-hooks/pre-commit", "#!/bin/sh\n")
    # the settings files agree with what the claude stub reports, so the round trip is clean
    device.write(".claude/plugins/known_marketplaces.json",
                 '{"example-market": {"source": {"source": "github",'
                 ' "repo": "ExampleStudio/example-market"}},'
                 ' "local-market": {"source": {"source": "directory",'
                 ' "path": "/opt/example-market"}}}')
    device.write(".claude/settings.json", '{"enabledPlugins": {"example@example-market": true}}')
    gitconfig = device.home / ".gitconfig"
    gitconfig.write_text(gitconfig.read_text(encoding="utf-8")
                         + "[core]\n\thooksPath = ~/.claude/lastmilefirst/git-hooks\n",
                         encoding="utf-8")


def test_snapshot_writes_a_manifest_that_loads_and_holds_names_only(device, capsys):
    seed_snapshot_machine(device)
    code, out, err = run(capsys, "--snapshot")
    assert code == 0, err
    path = default_manifest_path(home=device.home)
    text = path.read_text(encoding="utf-8")
    manifest = load_manifest(path)
    assert manifest.workspace_root == "~/Code"
    assert manifest.tools_extra == ["uv", "awscli", "docker"]
    assert manifest.claude_marketplaces == ["ExampleStudio/example-market",
                                            "/opt/example-market"]
    assert manifest.claude_plugins == ["example@example-market"]
    assert manifest.claude_hooks == ["pre-commit"]
    assert manifest.aws_profiles == ["default", "example-dev", "example-ci"]
    assert manifest.aws_default_profile_is == "(specify)"
    assert manifest.keychain_items == []
    assert manifest.network_provider == "none"
    assert FAKE_SECRET not in text and "region" not in text and "us-example-1" not in text
    assert "[keychain]\n# Left empty on purpose" in text
    assert "Wrote ~/.config/lastmilefirst/device.toml" in out

    # round trip: the audit reads it and the tools it lists are all present
    assert audit_device.main(["--workspace-root", "~/Code"]) == 0
    assert "Read ~/.config/lastmilefirst/device.toml." in capsys.readouterr().out


def test_snapshot_refuses_to_overwrite_without_force(device, capsys):
    seed_snapshot_machine(device)
    path = device.manifest("[tools]\nextra = []\n")
    code, _, err = run(capsys, "--snapshot")
    assert code == 3 and "pass --force" in err
    assert path.read_text(encoding="utf-8") == "[tools]\nextra = []\n"
    code, _, _ = run(capsys, "--snapshot", "--force")
    assert code == 0
    assert load_manifest(path).tools_extra == ["uv", "awscli", "docker"]


def test_snapshot_to_an_explicit_path(device, capsys, tmp_path):
    target = tmp_path / "out" / "device.toml"
    code, _, _ = run(capsys, "--snapshot", "--manifest", str(target))
    assert code == 0
    assert load_manifest(target).found
    assert not default_manifest_path(home=device.home).exists()


def test_snapshot_falls_back_to_settings_files(device, capsys):
    device.stub("claude", "#!/bin/sh\nexit 1\n")
    device.write(".claude/settings.json",
                 '{"enabledPlugins": {"example@example-market": true, "off@x": false},'
                 ' "env": {"EXAMPLE_TOKEN": "' + FAKE_SECRET + '"}}')
    device.write(".claude/plugins/known_marketplaces.json",
                 '{"example-market": {"source": {"source": "github",'
                 ' "repo": "ExampleStudio/example-market"}}}')
    code, _, _ = run(capsys, "--snapshot")
    assert code == 0
    path = default_manifest_path(home=device.home)
    manifest = load_manifest(path)
    assert manifest.claude_marketplaces == ["ExampleStudio/example-market"]
    assert manifest.claude_plugins == ["example@example-market"]
    assert FAKE_SECRET not in path.read_text(encoding="utf-8")


def test_snapshot_records_a_running_network_provider(device, capsys, monkeypatch, tmp_path):
    scripts = tmp_path / "fake-scripts"
    package = scripts / "network"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "aaa_stopped.py").write_text("def detect():\n    return False\n",
                                            encoding="utf-8")
    (package / "example_net.py").write_text(
        "def detect():\n"
        "    return {'installed': True, 'running': True, 'tailnet': 'example-net', "
        "'ssh': True}\n",
        encoding="utf-8")
    for name in [m for m in sys.modules if m == "network" or m.startswith("network.")]:
        monkeypatch.delitem(sys.modules, name)
    monkeypatch.setattr(install_device, "_HERE", scripts)
    monkeypatch.syspath_prepend(str(scripts))
    try:
        code, _, err = run(capsys, "--snapshot")
    finally:
        for name in [m for m in sys.modules if m == "network" or m.startswith("network.")]:
            del sys.modules[name]
    assert code == 0, err
    manifest = load_manifest(default_manifest_path(home=device.home))
    assert manifest.network_provider == "example_net"
    assert manifest.network_options == {"example_net": {"tailnet": "example-net", "ssh": True}}


def test_snapshot_without_a_network_package_writes_none(device, monkeypatch, tmp_path):
    monkeypatch.setattr(install_device, "_HERE", tmp_path)
    assert install_device.snapshot_network() == ("none", None, None)


# --------------------------------------------------------------------------
# no real HOME, every mode
# --------------------------------------------------------------------------

_HOOK_STATE: dict = {"fn": None}


def _dispatch(event, args):
    fn = _HOOK_STATE["fn"]
    if fn is not None:
        fn(event, args)


sys.addaudithook(_dispatch)


def watch_real_home(action) -> None:
    seen: list[str] = []
    allowed = tuple(os.path.realpath(p) for p in
                    {PLUGIN_ROOT, sys.prefix, sys.base_prefix, sys.exec_prefix})

    def hook(event, args):
        if event in ("open", "os.listdir", "os.scandir", "subprocess.Popen") and args:
            target = args[0]
            if isinstance(target, (str, bytes, os.PathLike)):
                seen.append(os.path.realpath(os.fsdecode(target)))

    _HOOK_STATE["fn"] = hook
    try:
        action()
    finally:
        _HOOK_STATE["fn"] = None
    leaked = [p for p in seen
              if (p == REAL_HOME or p.startswith(REAL_HOME + os.sep))
              and not p.startswith(allowed)]
    assert seen, "the audit hook recorded nothing; the test is not observing"
    assert leaked == []


@pytest.mark.parametrize("mode", ["checklist", "apply-no", "apply-yes", "snapshot"])
def test_no_real_home_path_is_read_or_written(device, capsys, monkeypatch, mode):
    break_client_include(device)
    device.ssh_config(SSH_WITHOUT_CLIENT)
    seed_snapshot_machine(device)
    argv = {"checklist": [], "apply-no": ["--apply"], "apply-yes": ["--apply"],
            "snapshot": ["--snapshot"]}[mode]
    answer(monkeypatch, "n\n" if mode == "apply-no" else "y\n")
    watch_real_home(lambda: install_device.main(argv))
    capsys.readouterr()
    if mode == "apply-yes":
        assert (device.home / ".gitconfig-example-client").is_file()


# --------------------------------------------------------------------------
# --apply --yes and --clone
# --------------------------------------------------------------------------

def yes_machine(device, monkeypatch):
    log = device.home.parent / "gh.log"
    monkeypatch.setenv("FAKE_GH_LOG", str(log))
    device.stub("gh", GH_RECORDING_STUB)
    device.gitconfig(GLOBAL_ONLY)  # a non-clone script step: the client includeIf
    monkeypatch.setattr(audit_device, "SECTIONS",
                        [*audit_device.SECTIONS, ("Workspace", workspace_section)])
    answer(monkeypatch, "", tty=False)
    return log


def test_apply_yes_runs_non_clone_steps_and_skips_clones(device, capsys, monkeypatch):
    log = yes_machine(device, monkeypatch)
    code, out, _ = run(capsys, "--apply", "--yes")
    assert code == 0, out
    assert "[y/N]" not in out and "stdin is not a terminal" not in out
    assert (device.home / ".gitconfig").read_text(encoding="utf-8") == \
        GLOBAL_ONLY + "\n" + CLIENT_INCLUDE + "\n"
    assert not log.exists()
    skipped = [l for l in out.splitlines() if "skipped:" in l]
    assert skipped == [
        "2. skipped: clones run under --yes only when named; pass --clone example-alpha to "
        "run this one",
        "3. skipped: clones run under --yes only when named; pass --clone example-beta to "
        "run this one",
    ]


def test_apply_yes_with_clone_runs_only_that_clone(device, capsys, monkeypatch):
    log = yes_machine(device, monkeypatch)
    code, out, _ = run(capsys, "--apply", "--yes", "--clone", "example-beta")
    assert code == 0, out
    beta = device.home / "Code" / "example-studio" / "example-beta"
    assert log.read_text(encoding="utf-8") == f"repo clone ExampleStudio/example-beta {beta}\n"
    assert "pass --clone example-alpha" in out and "example-beta to run" not in out


@pytest.mark.parametrize("argv", [["--yes"], ["--apply", "--clone", "example-alpha"],
                                  ["--snapshot", "--yes"]])
def test_yes_and_clone_need_apply_yes(device, capsys, argv):
    with pytest.raises(SystemExit) as exc:
        install_device.main(argv)
    assert exc.value.code == 3


# --------------------------------------------------------------------------
# structured actions (Finding.action)
# --------------------------------------------------------------------------

def with_action(finding, action):
    finding.action = action
    return finding


def test_structured_actions_are_script_whatever_the_prose(device, capsys, monkeypatch):
    brew_log = device.home.parent / "brew.log"
    device.stub("brew", f'#!/bin/sh\necho "$@" >> {brew_log}\nexit 0\n')
    claude_log = device.home.parent / "claude.log"
    device.stub("claude", f'#!/bin/sh\necho "$@" >> {claude_log}\nexit 0\n')
    gh_log = device.home.parent / "gh.log"
    monkeypatch.setenv("FAKE_GH_LOG", str(gh_log))
    device.stub("gh", GH_RECORDING_STUB)
    config = device.ssh_config(SSH_WITHOUT_CLIENT)
    device.gitconfig(GLOBAL_ONLY)
    (device.home / ".gitconfig-example-client").unlink()
    block = ("Host github-example-side\n    HostName github.com\n"
             "    IdentityFile ~/.ssh/id_ed25519_example-side\n    IdentitiesOnly yes")
    side_user = "[user]\n\tname = Example Side\n\temail = side@example.com"
    side_stanza = '[includeIf "gitdir:~/Code/example-side/"]\n\tpath = ~/.gitconfig-example-side'

    def section(ctx):
        return [
            with_action(missing("Extra", None, "A tool is absent.", "Get the tool somehow."),
                        {"kind": "package", "manager": "brew", "name": "example-tool"}),
            with_action(missing("Extra", None, "An alias is absent.", "Add a host entry."),
                        {"kind": "ssh_block", "host": "github-example-side", "block": block,
                         "key_path": "~/.ssh/id_ed25519_example-side"}),
            with_action(missing("Extra", "example-side", "No identity include.",
                                "Set up the include however you like."),
                        {"kind": "git_include", "org_dir": "~/Code/example-side",
                         "include_path": "~/.gitconfig-example-side", "stanza": side_stanza,
                         "file_text": side_user}),
            with_action(missing("Extra", None, "Marketplace absent.", "Add the marketplace."),
                        {"kind": "plugin_marketplace_add", "entry": "example/market"}),
            with_action(missing("Extra", None, "Plugin absent.", None),
                        {"kind": "plugin_install", "entry": "example@market"}),
            with_action(missing("Extra", "example-studio", "Repo absent.", "Clone it."),
                        {"kind": "clone", "dest": "~/Code/example-studio/example-zeta",
                         "command": "gh repo clone ExampleStudio/example-zeta "
                                    "~/Code/example-studio/example-zeta"}),
            with_action(missing("Extra", None, "Malformed action.", "Do a thing."),
                        {"kind": "package", "manager": "brew", "name": "bad name; rm"}),
            with_action(wrong("Extra", None, "Wrong, with an action.", "Fix by hand."),
                        {"kind": "plugin_install", "entry": "example-other@market"}),
        ]

    monkeypatch.setattr(audit_device, "SECTIONS",
                        [*audit_device.SECTIONS, ("Extra", section)])
    answer(monkeypatch, "", tty=False)
    code, out, _ = run(capsys, "--apply", "--yes", "--clone", "example-zeta")
    assert code == 0, out
    tags = {l.split(": ", 1)[1]: l.split("[")[1].split("]")[0] for l in step_lines(out)
            if "Extra" in l}
    assert tags == {
        "A tool is absent.": "script", "An alias is absent.": "script",
        "No identity include.": "script", "Marketplace absent.": "script",
        "Plugin absent.": "script", "Repo absent.": "script",
        "Malformed action.": "you", "Wrong, with an action.": "you",
    }
    # packages and clones keep their places in the order
    numbered = [l for l in step_lines(out)]
    assert "A tool is absent." in numbered[0] and "Repo absent." in numbered[-1]

    assert brew_log.read_text(encoding="utf-8") == "install example-tool\n"
    assert [l for l in claude_log.read_text(encoding="utf-8").splitlines()
            if l.startswith("plugin")] == ["plugin marketplace add example/market",
                                           "plugin install example@market"]
    zeta = device.home / "Code" / "example-studio" / "example-zeta"
    assert f"repo clone ExampleStudio/example-zeta {zeta}" in gh_log.read_text(encoding="utf-8")
    assert config.read_text(encoding="utf-8").endswith(block + "\n")
    assert (device.home / ".gitconfig-example-side").read_text(encoding="utf-8") == \
        side_user + "\n"
    assert (device.home / ".gitconfig").read_text(encoding="utf-8").endswith(side_stanza + "\n")


def test_structured_ssh_action_still_refuses_an_existing_host(device, capsys, monkeypatch):
    def section(ctx):
        return [with_action(missing("Extra", None, "Alias absent.", "Add a host entry."),
                            {"kind": "ssh_block", "host": "github-example-client",
                             "block": "Host github-example-client\n    HostName github.com",
                             "key_path": "~/.ssh/id_ed25519_example-client"})]

    monkeypatch.setattr(audit_device, "SECTIONS", [*audit_device.SECTIONS, ("Extra", section)])
    before = tree(device.home)
    answer(monkeypatch, "", tty=False)
    code, out, _ = run(capsys, "--apply", "--yes")
    assert code == 1 and "refused: a Host github-example-client block already exists" in out
    assert tree(device.home) == before


def test_snapshot_honors_aws_file_overrides(device, capsys, monkeypatch, tmp_path):
    seed_snapshot_machine(device)  # ~/.aws holds default, example-dev, example-ci
    config = tmp_path / "aws-elsewhere" / "config"
    creds = tmp_path / "aws-elsewhere" / "credentials"
    config.parent.mkdir()
    config.write_text("[profile example-moved]\nregion = us-example-1\n"
                      "[sso-session example-sso]\n", encoding="utf-8")
    creds.write_text(f"[example-moved-ci]\naws_secret_access_key = {FAKE_SECRET}\n",
                     encoding="utf-8")
    monkeypatch.setenv("AWS_CONFIG_FILE", str(config))
    monkeypatch.setenv("AWS_SHARED_CREDENTIALS_FILE", str(creds))
    code, _, err = run(capsys, "--snapshot")
    assert code == 0, err
    path = default_manifest_path(home=device.home)
    assert load_manifest(path).aws_profiles == ["example-moved", "example-moved-ci"]
    assert FAKE_SECRET not in path.read_text(encoding="utf-8")


def test_snapshot_force_keeps_the_existing_workspace_root(device, capsys):
    path = device.manifest('[workspace]\nroot = "~/Work"\n')
    code = install_device.main(["--snapshot", "--force"])
    capsys.readouterr()
    assert code == 0
    assert 'root = "~/Work"' in path.read_text(encoding="utf-8")
    assert install_device.main(["--snapshot", "--force", "--workspace-root", "~/Other"]) == 0
    capsys.readouterr()
    assert 'root = "~/Other"' in path.read_text(encoding="utf-8")


def test_snapshot_force_over_an_invalid_manifest_uses_the_default_root(device, capsys):
    path = device.manifest('[secrets]\ntoken = "x"\n')
    assert install_device.main(["--snapshot", "--force"]) == 0
    capsys.readouterr()
    assert load_manifest(path).workspace_root == "~/Code"
