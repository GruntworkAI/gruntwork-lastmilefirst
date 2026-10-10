"""Tests for the device manifest loader and the shipped template."""
from __future__ import annotations

import tomllib

import pytest

from device_manifest import (
    NETWORK_NONE,
    TEMPLATE_PATH,
    ManifestError,
    default_manifest_path,
    load_manifest,
    parse_manifest,
)


def test_default_path_honors_xdg_config_home(tmp_path):
    env = {"XDG_CONFIG_HOME": str(tmp_path / "xdg")}
    assert default_manifest_path(env, home=tmp_path) == \
        tmp_path / "xdg" / "lastmilefirst" / "device.toml"


def test_default_path_falls_back_to_dot_config(tmp_path):
    assert default_manifest_path({}, home=tmp_path) == \
        tmp_path / ".config" / "lastmilefirst" / "device.toml"


def test_missing_default_manifest_is_not_an_error(device):
    manifest = load_manifest()
    assert not manifest.found
    assert manifest.workspace_root == "~/Code"
    assert manifest.network_provider == NETWORK_NONE


def test_explicit_path_that_does_not_exist_is_an_error(tmp_path):
    with pytest.raises(ManifestError, match="no manifest"):
        load_manifest(tmp_path / "absent.toml")


def test_template_loads_with_every_key():
    data = tomllib.loads(TEMPLATE_PATH.read_text(encoding="utf-8"))
    assert set(data) == {"workspace", "tools", "claude", "aws", "keychain", "network"}
    assert set(data["claude"]) == {"marketplaces", "plugins", "hooks"}
    assert set(data["aws"]) == {"profiles", "default_profile_is"}
    assert set(data["network"]["tailscale"]) == {"tailnet", "ssh"}
    manifest = load_manifest(TEMPLATE_PATH)
    assert manifest.network_provider == "none"
    assert manifest.network_options["tailscale"]["ssh"] is True


def test_full_manifest_parses(tmp_path):
    path = tmp_path / "device.toml"
    path.write_text(
        '[workspace]\nroot = "~/Work"\n'
        '[tools]\nextra = ["uv", "awscli"]\n'
        '[aws]\nprofiles = ["default", "example"]\ndefault_profile_is = "studio"\n'
        '[keychain]\nitems = ["example-item"]\n'
        '[network]\nprovider = "tailscale"\n[network.tailscale]\ntailnet = "example.ts.net"\n',
        encoding="utf-8",
    )
    manifest = load_manifest(path)
    assert manifest.found and manifest.path == path
    assert manifest.workspace_root == "~/Work"
    assert manifest.tools_extra == ["uv", "awscli"]
    assert manifest.aws_default_profile_is == "studio"
    assert manifest.keychain_items == ["example-item"]
    assert manifest.network_options == {"tailscale": {"tailnet": "example.ts.net"}}


def test_unknown_top_level_table_is_rejected():
    with pytest.raises(ManifestError, match="unknown top-level table.*secrets"):
        parse_manifest({"secrets": {"token": "x"}})


def test_unknown_key_in_known_table_is_rejected():
    with pytest.raises(ManifestError, match="unknown key tools.extras"):
        parse_manifest({"tools": {"extras": ["uv"]}})


@pytest.mark.parametrize("data, where", [
    ({"tools": {"extra": "uv"}}, "tools.extra"),
    ({"tools": {"extra": ["uv", 3]}}, "tools.extra"),
    ({"workspace": {"root": 7}}, "workspace.root"),
    ({"network": {"provider": ""}}, "network.provider"),
    ({"claude": "yes"}, r"\[claude\]"),
    ({"network": {"tailscale": "on"}}, "network.tailscale"),
])
def test_wrong_types_are_rejected(data, where):
    with pytest.raises(ManifestError, match=where):
        parse_manifest(data)


def test_invalid_toml_is_a_manifest_error(tmp_path):
    path = tmp_path / "device.toml"
    path.write_text("[tools\nextra = 1\n", encoding="utf-8")
    with pytest.raises(ManifestError, match="not valid TOML"):
        load_manifest(path)
