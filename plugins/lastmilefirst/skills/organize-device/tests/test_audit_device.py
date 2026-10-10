"""Tests for the device audit's cheap checks and its output contract.

Each test starts from the clean fake machine in conftest and breaks one thing,
so every `missing` and `wrong` case has exactly one test that produces it.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import audit_device
from audit_device import MISSING, WRONG
from .conftest import CLIENT, SSH_CONFIG, SSH_STUB, STUDIO


def run(capsys, *argv):
    code = audit_device.main(["--workspace-root", "~/Code", *argv])
    out = capsys.readouterr()
    return code, out.out, out.err


def findings(capsys, *argv):
    code, out, _ = run(capsys, "--json", *argv)
    return code, json.loads(out)["findings"]


def only(found, cls, section=None):
    return [f for f in found if f["class"] == cls and (section is None or f["section"] == section)]


def problems(found):
    return [f for f in found if f["class"] in (MISSING, WRONG)]


# --------------------------------------------------------------------------
# clean, manifest, output contract
# --------------------------------------------------------------------------

def test_clean_machine_has_no_findings(device, capsys):
    code, found = findings(capsys)
    assert problems(found) == []
    assert code == 0
    code, out, _ = run(capsys)
    assert "Result: clean." in out


def test_no_manifest_prints_one_informational_line(device, capsys):
    code, out, _ = run(capsys)
    assert code == 0
    lines = [l for l in out.splitlines() if "No device manifest" in l]
    assert len(lines) == 1
    assert "~/.config/lastmilefirst/device.toml" in lines[0]
    assert "--snapshot" in lines[0]


def test_manifest_found_is_reported(device, capsys):
    device.manifest('[tools]\nextra = []\n')
    _, out, _ = run(capsys)
    assert "Read ~/.config/lastmilefirst/device.toml." in out


def test_invalid_manifest_exits_3_with_a_clear_message(device, capsys):
    device.manifest('[secrets]\ntoken = "x"\n')
    code, out, err = run(capsys)
    assert code == 3
    assert "unknown top-level table" in err and "secrets" in err
    assert out == ""


def test_manifest_flag_overrides_location(device, capsys, tmp_path):
    elsewhere = tmp_path / "carried.toml"
    elsewhere.write_text('[tools]\nextra = ["example-tool"]\n', encoding="utf-8")
    code, found = findings(capsys, "--manifest", str(elsewhere))
    assert [f["message"] for f in only(found, MISSING, "Tools")] == \
        ["example-tool is not installed (manifest tools.extra)."]
    assert code == 2


def test_json_shape(device, capsys):
    device.unstub("jq")
    code, out, _ = run(capsys, "--json")
    data = json.loads(out)
    assert set(data) == {"mode", "manifest", "workspace_root", "findings", "summary",
                         "exit_code"}
    assert data["mode"] == "cheap"
    assert data["manifest"] is None
    assert data["workspace_root"] == "~/Code"
    assert data["summary"] == {"wrong": 0, "missing": 1}
    assert data["exit_code"] == code == 2
    for finding in data["findings"]:
        assert set(finding) == {"severity", "org", "message", "remedy", "class", "section",
                                "you", "action"}
    jq = only(data["findings"], MISSING)[0]
    assert jq["severity"] == "warning" and jq["section"] == "Tools"


def test_text_shape_matches_audit_identity(device, capsys):
    device.unstub("jq")
    device.gitconfig("[user]\n\tname = Someone Else\n\temail = studio@example.com\n")
    _, out, _ = run(capsys)
    assert "WARNING: jq is not installed (baseline)." in out
    assert "ACTION REQUIRED: Global git identity is wrong" in out
    assert "       → " in out
    assert "Result: 1 action required, 2 warnings." in out  # jq + client includeIf


def test_exit_codes(device, capsys):
    assert run(capsys)[0] == 0
    device.unstub("jq")
    assert run(capsys)[0] == 2
    device.gitconfig("[user]\n\tname = Someone Else\n\temail = studio@example.com\n")
    assert run(capsys)[0] == 1


def test_help_documents_exit_codes(capsys):
    with pytest.raises(SystemExit) as exc:
        audit_device.main(["--help"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    for line in ("0  clean", "1  at least one `wrong`", "2  only `missing`", "3  the audit"):
        assert line in out


def test_bad_argument_exits_3_not_2(capsys):
    with pytest.raises(SystemExit) as exc:
        audit_device.main(["--no-such-flag"])
    assert exc.value.code == 3


def test_old_python_is_refused_with_one_line(capsys):
    assert audit_device.require_python((3, 9)) is False
    err = capsys.readouterr().err
    assert err.count("\n") == 1 and "3.11" in err
    assert audit_device.require_python((3, 11)) is True


def test_no_real_home_path_is_read(device, capsys, real_home_guard):
    """Nothing under the real home is opened or listed, apart from the
    interpreter and this plugin's own source (the conftest guard enforces it)."""
    audit_device.main(["--json"])
    capsys.readouterr()
    assert real_home_guard.seen, "the audit hook recorded nothing; the test is not observing"


# --------------------------------------------------------------------------
# platform
# --------------------------------------------------------------------------

def test_platform_is_informational(device, capsys):
    _, found = findings(capsys)
    platform = [f for f in found if f["section"] == "Platform"]
    assert len(platform) == 1 and platform[0]["class"] is None
    assert "shell: zsh" in platform[0]["message"]
    assert "package manager: none found" in platform[0]["message"]


def test_windows_is_wrong_and_stops_the_audit(device, capsys, monkeypatch):
    monkeypatch.setattr(audit_device, "_system", lambda: "MINGW64_NT-10.0")
    code, found = findings(capsys)
    assert code == 1
    assert [f["section"] for f in found] == ["Device manifest", "Platform"]
    assert "unsupported" in found[1]["message"]
    assert "WSL2" in found[1]["remedy"]


# --------------------------------------------------------------------------
# tools
# --------------------------------------------------------------------------

def test_missing_baseline_tool_with_no_package_manager(device, capsys):
    device.unstub("jq")
    _, found = findings(capsys)
    [jq] = only(found, MISSING, "Tools")
    assert jq["message"] == "jq is not installed (baseline)."
    assert "no brew or apt found" in jq["remedy"]


def test_missing_tool_remedy_uses_brew(device, capsys):
    device.stub("brew")
    device.unstub("rg")
    _, found = findings(capsys)
    assert only(found, MISSING, "Tools")[0]["remedy"] == "brew install ripgrep"


def test_missing_tool_remedy_uses_apt(device, capsys):
    device.stub("apt-get")
    device.unstub("node")
    _, found = findings(capsys)
    assert only(found, MISSING, "Tools")[0]["remedy"] == "sudo apt-get install -y nodejs"


def test_missing_claude_uses_native_installer(device, capsys):
    device.unstub("claude")
    _, found = findings(capsys)
    assert "claude.ai/install.sh" in only(found, MISSING, "Tools")[0]["remedy"]


def test_manifest_extra_tool_maps_package_to_binary(device, capsys):
    device.manifest('[tools]\nextra = ["awscli"]\n')
    device.stub("brew")
    _, found = findings(capsys)
    [aws] = only(found, MISSING, "Tools")
    assert aws["remedy"] == "brew install awscli"
    device.stub("aws")
    _, found = findings(capsys)
    assert only(found, MISSING, "Tools") == []


# --------------------------------------------------------------------------
# GitHub logins
# --------------------------------------------------------------------------

def test_missing_gh_login(device, capsys, monkeypatch):
    monkeypatch.setenv("FAKE_GH_LOGINS", "ExampleStudio")
    code, out, _ = run(capsys)
    assert code == 2
    _, found = findings(capsys)
    [login] = only(found, MISSING, "GitHub logins")
    assert login["org"] == "example-client"
    assert "example-client-bot" in login["message"]
    assert login["remedy"].startswith("gh auth login")
    assert "Browser step" in login["you"] and "example-client-bot" in login["you"]


def test_token_is_never_printed(device, capsys):
    _, out, _ = run(capsys)
    assert "gho_FAKE_TOKEN_VALUE" not in out
    _, out, _ = run(capsys, "--json")
    assert "gho_FAKE_TOKEN_VALUE" not in out


def test_present_logins_and_active_account_are_reported(device, capsys):
    _, out, _ = run(capsys)
    assert "gh logins present: example-client-bot, ExampleStudio." in out
    assert "gh's active account is ExampleStudio" in out
    assert "machine-global" in out


def test_missing_gh_binary_is_one_note_not_a_crash(device, capsys):
    device.unstub("gh")
    _, found = findings(capsys)
    github = [f for f in found if f["section"] == "GitHub logins"]
    assert len(github) == 1 and github[0]["class"] is None
    assert len(only(found, MISSING, "Tools")) == 1


def test_gh_timeout_is_a_note(device, capsys, monkeypatch):
    monkeypatch.setattr(audit_device, "gh_login_present", lambda account: None)
    _, found = findings(capsys)
    notes = [f for f in found if f["section"] == "GitHub logins" and "did not answer" in
             f["message"]]
    assert len(notes) == 2
    assert only(found, MISSING, "GitHub logins") == []


OLD_GH_STUB = """#!/bin/sh
if [ "$1" = "auth" ] && [ "$2" = "token" ]; then
  echo "unknown flag: --user" >&2
  exit 1
fi
exit 0
"""


def test_gh_without_user_flag_is_a_note_not_missing(device, capsys, monkeypatch):
    device.stub("gh", OLD_GH_STUB)
    assert audit_device.gh_login_present("ExampleStudio") is None
    monkeypatch.setattr(audit_device, "_system", lambda: "Darwin")
    _, found = findings(capsys)
    assert only(found, MISSING, "GitHub logins") == []
    notes = [f for f in found if f["section"] == "GitHub logins" and "2.40.0" in f["message"]]
    assert len(notes) == 2
    assert all("brew upgrade gh" in f["message"] for f in notes)


def test_gh_upgrade_remedy_names_the_apt_repository_on_linux():
    assert "apt repository" in audit_device.gh_upgrade_remedy("Linux")
    assert "brew upgrade gh" in audit_device.gh_upgrade_remedy("Darwin")


def test_gh_probe_timeout_yields_none(monkeypatch):
    monkeypatch.setattr(audit_device, "_run", lambda args, timeout: None)
    assert audit_device.gh_login_present("ExampleStudio") is None


# --------------------------------------------------------------------------
# SSH
# --------------------------------------------------------------------------

def test_missing_alias_block(device, capsys):
    device.ssh_config(SSH_CONFIG.split("Host github-example-client")[0])
    _, found = findings(capsys)
    [block] = only(found, MISSING, "SSH")
    assert block["org"] == "example-client"
    assert block["remedy"].splitlines()[1:] == [
        "Host github-example-client",
        "    HostName github.com",
        "    IdentityFile ~/.ssh/id_ed25519_example-client",
        "    IdentitiesOnly yes",
    ]
    assert "ssh-keygen -t ed25519" in block["you"]
    assert CLIENT["git_email"] in block["you"]


def test_missing_ssh_config_file_reports_each_alias(device, capsys):
    (device.home / ".ssh" / "config").unlink()
    _, found = findings(capsys)
    assert len(only(found, MISSING, "SSH")) == 1


def test_alias_with_wrong_hostname(device, capsys):
    device.ssh_config(SSH_CONFIG.replace(
        "Host github-example-client\n    HostName github.com",
        "Host github-example-client\n    HostName gitlab.example.com"))
    _, found = findings(capsys)
    [bad] = only(found, WRONG, "SSH")
    assert "HostName is gitlab.example.com" in bad["message"]
    assert "    HostName github.com" in bad["remedy"]
    assert "    User git" in bad["remedy"]  # other options are kept
    assert bad["you"] is None


def test_alias_with_key_missing_on_disk(device, capsys):
    (device.home / ".ssh" / "id_ed25519_example-client").unlink()
    _, found = findings(capsys)
    [bad] = only(found, WRONG, "SSH")
    assert "is not on disk" in bad["message"]
    assert "ssh-keygen" in bad["you"]


def test_alias_without_identities_only(device, capsys):
    device.ssh_config(SSH_CONFIG.replace(
        "IdentityFile ~/.ssh/id_ed25519_example-client\n    IdentitiesOnly yes",
        "IdentityFile ~/.ssh/id_ed25519_example-client"))
    _, found = findings(capsys)
    [bad] = only(found, WRONG, "SSH")
    assert "IdentitiesOnly yes is absent" in bad["message"]
    assert bad["remedy"].rstrip().endswith("IdentitiesOnly yes")


def test_ssh_keys_are_case_insensitive(device, capsys):
    device.ssh_config(SSH_CONFIG.replace("HostName", "hostname").replace(
        "IdentitiesOnly", "identitiesonly").replace("IdentityFile", "IDENTITYFILE"))
    _, found = findings(capsys)
    assert only(found, WRONG, "SSH") == [] and only(found, MISSING, "SSH") == []


def test_default_host_with_missing_key_is_wrong(device, capsys):
    (device.home / ".ssh" / "id_ed25519").unlink()
    _, found = findings(capsys)
    [bad] = only(found, WRONG, "SSH")
    assert bad["org"] == "example-studio"
    assert "Host github.com" in bad["remedy"]


def test_absent_default_host_block_is_only_a_note(device, capsys):
    device.ssh_config(SSH_CONFIG.replace(
        "Host github.com\n    HostName github.com\n    User git\n"
        "    IdentityFile ~/.ssh/id_ed25519\n    IdentitiesOnly yes\n", ""))
    _, found = findings(capsys)
    assert problems([f for f in found if f["section"] == "SSH"]) == []
    assert any("No `Host github.com` block" in f["message"] for f in found)


def test_two_accounts_without_alias_is_wrong(device, capsys):
    device.org("example-other", {**STUDIO, "github_account": "example-other",
                                 "git_email": "other@example.com"})
    _, found = findings(capsys)
    [bad] = only(found, WRONG, "SSH")
    assert "More than one GitHub account has no ssh_host_alias" in bad["message"]
    # one account keeps the plain host; the other gets the alias line to add
    assert bad["remedy"].count('"ssh_host_alias": "github-example-') == 1


def test_two_orgs_sharing_the_default_account_is_fine(device, capsys):
    device.org("example-lab", STUDIO)
    _, found = findings(capsys)
    assert problems(found) == []


# --------------------------------------------------------------------------
# git identity
# --------------------------------------------------------------------------

GLOBAL_USER = "[user]\n\tname = Example Studio\n\temail = studio@example.com\n"


def test_missing_include_stanza(device, capsys):
    device.gitconfig(GLOBAL_USER)
    _, found = findings(capsys)
    [stanza] = only(found, MISSING, "git identity")
    assert stanza["org"] == "example-client"
    assert '[includeIf "gitdir:~/Code/example-client/"]' in stanza["remedy"]
    assert "\tpath = ~/.gitconfig-example-client" in stanza["remedy"]
    assert f"\temail = {CLIENT['git_email']}" in stanza["remedy"]
    assert str(device.home) not in stanza["remedy"]


def test_default_org_needs_no_stanza(device, capsys):
    _, found = findings(capsys)
    assert not any(f["org"] == "example-studio" for f in problems(found))


def _stanza(gitdir: str, path: str) -> str:
    return GLOBAL_USER + f'[includeIf "gitdir:{gitdir}"]\n\tpath = {path}\n'


def test_absolute_home_gitdir_is_wrong(device, capsys):
    device.gitconfig(_stanza(f"{device.home}/Code/example-client/",
                             "~/.gitconfig-example-client"))
    _, found = findings(capsys)
    [bad] = only(found, WRONG, "git identity")
    assert "gitdir uses an absolute home path" in bad["message"]
    assert '[includeIf "gitdir:~/Code/example-client/"]' in bad["remedy"]


def test_absolute_home_include_path_is_wrong(device, capsys):
    device.gitconfig(_stanza("~/Code/example-client/",
                             f"{device.home}/.gitconfig-example-client"))
    _, found = findings(capsys)
    [bad] = only(found, WRONG, "git identity")
    assert "path uses an absolute home path" in bad["message"]
    assert "\tpath = ~/.gitconfig-example-client" in bad["remedy"]
    assert "[user]" not in bad["remedy"]  # the include file itself is right


def test_users_prefix_counts_as_absolute_home(device, capsys):
    # Only this login's real home counts, as given or resolved.
    assert audit_device.is_absolute_home_path(f"{device.home}/.gitconfig-x", device.home)
    assert audit_device.is_absolute_home_path(str(device.home), device.home)
    assert not audit_device.is_absolute_home_path("~/.gitconfig-x", device.home)
    # A /Users/ or /home/ path outside this home is a chosen location.
    assert not audit_device.is_absolute_home_path("/Users/Shared/code/x/", device.home)
    assert not audit_device.is_absolute_home_path("/home/someone/.gitconfig-x", device.home)


def test_workspace_outside_home_stanza_is_accepted(device, capsys, tmp_path):
    shared = tmp_path / "Shared" / "code"
    (shared / "example-client" / ".claude").mkdir(parents=True)
    (shared / "example-client" / ".claude" / "org.json").write_text(
        json.dumps({"name": "example-client", "identity": CLIENT}), encoding="utf-8")
    (shared / "example-studio" / ".claude").mkdir(parents=True)
    (shared / "example-studio" / ".claude" / "org.json").write_text(
        json.dumps({"name": "example-studio", "identity": STUDIO}), encoding="utf-8")
    device.gitconfig(_stanza(f"{shared}/example-client/", "~/.gitconfig-example-client"))
    audit_device.main(["--workspace-root", str(shared), "--json"])
    found = json.loads(capsys.readouterr().out)["findings"]
    assert only(found, WRONG, "git identity") == []
    assert only(found, MISSING, "git identity") == []


def test_user_git_config_paths(device, monkeypatch):
    assert audit_device.user_git_config_paths(device.home) == [
        device.home / ".gitconfig", device.home / ".config" / "git" / "config"]
    monkeypatch.delenv("XDG_CONFIG_HOME")
    assert audit_device.user_git_config_paths(device.home)[1] == \
        device.home / ".config" / "git" / "config"
    monkeypatch.setenv("XDG_CONFIG_HOME", "/example/xdg")
    assert audit_device.user_git_config_paths(device.home)[1] == Path("/example/xdg/git/config")


def test_stanza_only_in_xdg_git_config_audits_clean(device, capsys, monkeypatch):
    monkeypatch.delenv("XDG_CONFIG_HOME")
    device.gitconfig(GLOBAL_USER)
    device.write(".config/git/config", '[includeIf "gitdir:~/Code/example-client/"]\n'
                                       "\tpath = ~/.gitconfig-example-client\n")
    _, found = findings(capsys)
    assert only(found, WRONG, "git identity") == []
    assert only(found, MISSING, "git identity") == []
    assert audit_device.has_include_for(audit_device.read_user_git_stanzas(device.home),
                                        device.workspace / "example-client", device.home)


def test_stanza_under_custom_xdg_config_home_audits_clean(device, capsys, monkeypatch,
                                                          tmp_path):
    xdg = tmp_path / "elsewhere-xdg"
    (xdg / "git").mkdir(parents=True)
    (xdg / "git" / "config").write_text('[includeIf "gitdir:~/Code/example-client/"]\n'
                                        "\tpath = ~/.gitconfig-example-client\n",
                                        encoding="utf-8")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))
    device.gitconfig(GLOBAL_USER)
    _, found = findings(capsys)
    assert only(found, WRONG, "git identity") == []
    assert only(found, MISSING, "git identity") == []


def test_both_user_git_configs_merge(device, capsys):
    device.org("example-third", {**CLIENT, "github_account": "example-third-bot",
                                 "git_user_name": "example-third-bot",
                                 "git_email": "5678+example-third-bot@users.noreply.github.com",
                                 "owns_remotes": ["example-third-bot"],
                                 "ssh_host_alias": "github-example-client"})
    device.write(".config/git/config", '[includeIf "gitdir:~/Code/example-third/"]\n'
                                       "\tpath = ~/.gitconfig-example-third\n")
    device.write(".gitconfig-example-third", "[user]\n\tname = example-third-bot\n"
                 "\temail = 5678+example-third-bot@users.noreply.github.com\n")
    stanzas = audit_device.read_user_git_stanzas(device.home)
    assert [audit_device.gitdir_target(s) for s in stanzas] == [
        "~/Code/example-client/", "~/Code/example-third/"]
    _, found = findings(capsys)
    assert only(found, WRONG, "git identity") == []
    assert only(found, MISSING, "git identity") == []


def test_wrong_stanza_in_xdg_file_names_that_file(device, capsys):
    device.gitconfig(GLOBAL_USER)
    device.write(".config/git/config", '[includeIf "gitdir:~/Code/example-client"]\n'
                                       "\tpath = ~/.gitconfig-example-client\n")
    _, found = findings(capsys)
    [bad] = only(found, WRONG, "git identity")
    assert bad["remedy"].startswith("Replace the stanza in ~/.config/git/config with:")


def test_private_gitdir_names_remain_aliases():
    assert audit_device._gitdir_target is audit_device.gitdir_target
    assert audit_device._gitdir_matches is audit_device.gitdir_matches


def test_gitdir_without_trailing_slash_is_wrong(device, capsys):
    device.gitconfig(_stanza("~/Code/example-client", "~/.gitconfig-example-client"))
    _, found = findings(capsys)
    [bad] = only(found, WRONG, "git identity")
    assert "trailing slash" in bad["message"]
    assert '"gitdir:~/Code/example-client/"' in bad["remedy"]


def test_missing_include_file_is_wrong(device, capsys):
    (device.home / ".gitconfig-example-client").unlink()
    _, found = findings(capsys)
    [bad] = only(found, WRONG, "git identity")
    assert "does not exist" in bad["message"]
    assert f"\temail = {CLIENT['git_email']}" in bad["remedy"]


def test_include_file_with_wrong_email_is_wrong(device, capsys):
    device.write(".gitconfig-example-client",
                 f"[user]\n\tname = {CLIENT['git_user_name']}\n\temail = studio@example.com\n")
    _, found = findings(capsys)
    [bad] = only(found, WRONG, "git identity")
    assert "user.email is studio@example.com" in bad["message"]
    assert f"\temail = {CLIENT['git_email']}" in bad["remedy"]


def test_include_file_with_wrong_name_is_wrong(device, capsys):
    device.write(".gitconfig-example-client",
                 f"[user]\n\tname = Someone\n\temail = {CLIENT['git_email']}\n")
    _, found = findings(capsys)
    [bad] = only(found, WRONG, "git identity")
    assert "user.name is Someone" in bad["message"]


def test_global_identity_different_is_wrong(device, capsys):
    device.gitconfig(device.home.joinpath(".gitconfig").read_text().replace(
        "studio@example.com", "elsewhere@example.com"))
    _, found = findings(capsys)
    [bad] = only(found, WRONG, "git identity")
    assert bad["org"] == "example-studio"
    assert "user.email is elsewhere@example.com" in bad["message"]
    assert "\temail = studio@example.com" in bad["remedy"]


def test_global_identity_unset_is_missing(device, capsys):
    device.gitconfig('[includeIf "gitdir:~/Code/example-client/"]\n'
                     "\tpath = ~/.gitconfig-example-client\n")
    _, found = findings(capsys)
    [unset] = only(found, MISSING, "git identity")
    assert 'git config --global user.email "studio@example.com"' in unset["remedy"]


def test_signing_is_reported_never_flagged(device, capsys):
    device.write(".ssh/example_signing.pub", "ssh-ed25519 AAAA fake\n")
    device.write(".gitconfig-example-client",
                 f"[user]\n\tname = {CLIENT['git_user_name']}\n\temail = {CLIENT['git_email']}\n"
                 "\tsigningkey = ~/.ssh/example_signing.pub\n"
                 "[commit]\n\tgpgsign = true\n[gpg]\n\tformat = ssh\n")
    _, found = findings(capsys)
    assert problems(found) == []
    [signing] = [f for f in found if f["message"].startswith("Commit signing")]
    assert "example-studio off" in signing["message"]
    assert "example-client on (ssh, key ~/.ssh/example_signing.pub, present)" in \
        signing["message"]


def test_credential_helper_is_reported(device, capsys):
    _, out, _ = run(capsys)
    assert "credential.helper is osxkeychain" in out


def test_inline_credential_helper_is_never_echoed(device, capsys):
    device.gitconfig(GLOBAL_USER
                     + '[credential]\n\thelper = "!f() { echo password=example-value; }; f"\n'
                     + '[includeIf "gitdir:~/Code/example-client/"]\n'
                     + "\tpath = ~/.gitconfig-example-client\n")
    _, out, _ = run(capsys)
    assert "example-value" not in out
    assert "credential.helper is a custom command (!...)" in out
    _, out, _ = run(capsys, "--json")
    assert "example-value" not in out


def test_credential_helper_arguments_are_dropped(device, capsys):
    device.gitconfig(device.home.joinpath(".gitconfig").read_text().replace(
        "helper = osxkeychain", "helper = store --file ~/example-secret-store"))
    _, out, _ = run(capsys)
    assert "credential.helper is store " in out
    assert "example-secret-store" not in out


def test_insteadof_url_is_never_echoed(device, capsys):
    device.gitconfig(device.home.joinpath(".gitconfig").read_text()
                     + '[url "https://user:example-token@example.invalid/"]\n'
                     + "\tinsteadOf = https://example.invalid/\n")
    _, out, _ = run(capsys)
    assert "example-token" not in out
    _, out, _ = run(capsys, "--json")
    assert "example-token" not in out


def test_https_origins_are_counted_not_named(device, capsys):
    device.repo("example-client", "site", "https://github.com/example-client-bot/site.git")
    device.repo("example-client", "tool", "git@github-example-client:example-client-bot/tool.git")
    device.repo("example-studio", "app", "https://github.com/ExampleStudio/app.git")
    _, found = findings(capsys)
    [line] = [f for f in found if "HTTPS origin" in f["message"]]
    assert line["class"] is None
    assert "example-client 1 of 2" in line["message"]
    assert "site" not in line["message"] and "example-studio" not in line["message"]


def test_includeif_on_a_second_section_line_and_comments(device, capsys):
    device.gitconfig(
        "# global\n[user]\n\tname = Example Studio ; trailing comment\n"
        '\temail = "studio@example.com"\n'
        '[includeIf "gitdir/i:~/Code/example-client/**"] path = ~/.gitconfig-example-client\n'
    )
    _, found = findings(capsys)
    assert problems(found) == []


# --------------------------------------------------------------------------
# --full liveness
# --------------------------------------------------------------------------

def test_cheap_mode_never_runs_ssh(device, capsys, monkeypatch):
    calls = []
    monkeypatch.setattr(audit_device, "ssh_greeting",
                        lambda host: calls.append(host) or (True, None))
    run(capsys)
    run(capsys, "--full", "--no-liveness")
    assert calls == []


def test_full_mode_greeting_matches(device, capsys, monkeypatch):
    device.stub("ssh", SSH_STUB)
    monkeypatch.setenv("FAKE_SSH_MAP",
                       "git@github-example-client=example-client-bot,git@github.com=ExampleStudio")
    code, out, _ = run(capsys, "--json", "--full")
    data = json.loads(out)
    assert data["mode"] == "full"
    assert problems(data["findings"]) == [] and code == 0


def test_full_mode_wrong_account_greeting(device, capsys, monkeypatch):
    device.stub("ssh", SSH_STUB)
    monkeypatch.setenv("FAKE_SSH_MAP",
                       "git@github-example-client=ExampleStudio,git@github.com=ExampleStudio")
    code, found = findings(capsys, "--full")
    [bad] = only(found, WRONG, "SSH")
    assert "authenticates as ExampleStudio, not example-client-bot" in bad["message"]
    assert code == 1


def test_full_mode_no_greeting_is_missing(device, capsys, monkeypatch):
    device.stub("ssh", SSH_STUB)
    monkeypatch.setenv("FAKE_SSH_MAP", "git@github.com=ExampleStudio")
    _, found = findings(capsys, "--full")
    [unauth] = only(found, MISSING, "SSH")
    assert "did not authenticate" in unauth["message"]
    assert "browser step" in unauth["you"]


# --------------------------------------------------------------------------
# parsers
# --------------------------------------------------------------------------

def test_git_parser_handles_legacy_subsections_and_quotes():
    stanzas = audit_device.parse_git_config(
        '[remote.Origin]\n\turl = x\n[remote "up\\"s"]\n\turl = "a # b" # c\n[core]\n\tbare\n')
    assert audit_device.git_get(stanzas, "remote", "url", subsection="origin") == "x"
    assert audit_device.git_get(stanzas, "remote", "url", subsection='up"s') == "a # b"
    assert audit_device.git_get(stanzas, "core", "bare") == "true"


def test_ssh_parser_ignores_include_and_match():
    blocks = audit_device.parse_ssh_config(
        "Include ~/.ssh/extra\nIdentityFile ~/.ssh/global\n"
        "Match host foo\n    User x\nHost=a b\n    HostName=github.com\n")
    assert audit_device.find_ssh_block(blocks, "b").get("hostname") == "github.com"
    assert audit_device.find_ssh_block(blocks, "foo") is None


def test_sections_are_an_extensible_list():
    titles = [t for t, _ in audit_device.SECTIONS]
    assert titles == ["Device manifest", "Platform", "Tools", "GitHub logins", "SSH",
                      "git identity", "Claude Code", "AWS", "Keychain", "Network",
                      "Workspace"]
    assert all(callable(fn) for _, fn in audit_device.SECTIONS)
