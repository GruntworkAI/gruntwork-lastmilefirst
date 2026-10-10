#!/usr/bin/env python3
"""
The device manifest: the few facts about a machine that have no other home.

Org identity (accounts, emails, SSH host aliases) lives in each org's
`.claude/org.json` and is never copied here. The manifest records only names of
things the contracts cannot know about: extra tools, expected Claude Code
marketplaces and plugins, AWS profile names, keychain item names, and an
optional network provider. It never holds a key, token, or credential value.

Location: `$XDG_CONFIG_HOME/lastmilefirst/device.toml`, defaulting to
`~/.config/lastmilefirst/device.toml`. It describes the device, so it lives
outside every workspace. A missing manifest is not an error: the audit runs on
the contracts alone and every manifest field takes its default.

The commented template ships beside this file as `device_template.toml`.

Standard library only; `tomllib` needs Python 3.11+.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Optional

try:
    import tomllib
except ImportError:  # pragma: no cover - Python < 3.11; audit_device exits first
    tomllib = None  # type: ignore[assignment]

TEMPLATE_PATH = Path(__file__).parent / "device_template.toml"
MANIFEST_RELATIVE = Path("lastmilefirst") / "device.toml"
DEFAULT_WORKSPACE_ROOT = "~/Code"
NETWORK_NONE = "none"


class ManifestError(ValueError):
    """The manifest exists but cannot be used. The message says why."""


# Fixed tables: table -> key -> expected type. `list` means a list of strings.
# `network` is handled separately because it also carries one subtable per
# provider, which the provider module validates (plan 3.8).
_SCHEMA: dict[str, dict[str, type]] = {
    "workspace": {"root": str},
    "tools": {"extra": list},
    "claude": {"marketplaces": list, "plugins": list, "hooks": list},
    "aws": {"profiles": list, "default_profile_is": str},
    "keychain": {"items": list},
    "network": {"provider": str},
}


@dataclass
class Manifest:
    """Parsed manifest with every default filled in.

    `path` is where it was read from, or None when no manifest was found.
    `network_options` maps a provider name to its `[network.<name>]` table,
    passed through unvalidated for the provider to check.
    """

    path: Optional[Path] = None
    workspace_root: str = DEFAULT_WORKSPACE_ROOT
    tools_extra: list[str] = field(default_factory=list)
    claude_marketplaces: list[str] = field(default_factory=list)
    claude_plugins: list[str] = field(default_factory=list)
    claude_hooks: list[str] = field(default_factory=list)
    aws_profiles: list[str] = field(default_factory=list)
    aws_default_profile_is: Optional[str] = None
    keychain_items: list[str] = field(default_factory=list)
    network_provider: str = NETWORK_NONE
    network_options: dict[str, dict[str, Any]] = field(default_factory=dict)

    @property
    def found(self) -> bool:
        return self.path is not None


def default_manifest_path(env: Optional[Mapping[str, str]] = None,
                          home: Optional[Path] = None) -> Path:
    """Where the manifest lives on this machine, honoring `$XDG_CONFIG_HOME`.

    Resolved at call time so a test (or a second user) gets its own home.
    """
    env = os.environ if env is None else env
    home = home or Path.home()
    xdg = env.get("XDG_CONFIG_HOME")
    base = Path(xdg).expanduser() if xdg else home / ".config"
    return base / MANIFEST_RELATIVE


def _check_value(where: str, value: Any, expected: type) -> None:
    if expected is list:
        if not isinstance(value, list) or not all(isinstance(v, str) and v for v in value):
            raise ManifestError(f"{where} must be a list of non-empty strings.")
    elif expected is str:
        if not isinstance(value, str) or not value.strip():
            raise ManifestError(f"{where} must be a non-empty string.")


def parse_manifest(data: Mapping[str, Any], path: Optional[Path] = None) -> Manifest:
    """Validate a parsed TOML document and return a Manifest.

    Unknown top-level tables and unknown keys inside a known table are
    rejected, because a misspelled key would otherwise be silently ignored and
    the audit would quietly check less than the user thinks.
    """
    unknown = sorted(set(data) - set(_SCHEMA))
    if unknown:
        raise ManifestError(
            f"unknown top-level table(s): {', '.join(unknown)}. "
            f"Known tables: {', '.join(sorted(_SCHEMA))}."
        )

    manifest = Manifest(path=path)
    for table, keys in _SCHEMA.items():
        section = data.get(table)
        if section is None:
            continue
        if not isinstance(section, dict):
            raise ManifestError(f"[{table}] must be a table.")
        for key, value in section.items():
            if table == "network" and key not in keys:
                if not isinstance(value, dict):
                    raise ManifestError(
                        f"network.{key} is not a known key; provider settings "
                        f"belong in a [network.{key}] table."
                    )
                manifest.network_options[key] = dict(value)
                continue
            if key not in keys:
                raise ManifestError(
                    f"unknown key {table}.{key}. Known keys in [{table}]: "
                    f"{', '.join(sorted(keys))}."
                )
            _check_value(f"{table}.{key}", value, keys[key])

    workspace = data.get("workspace", {})
    tools = data.get("tools", {})
    claude = data.get("claude", {})
    aws = data.get("aws", {})
    keychain = data.get("keychain", {})
    network = data.get("network", {})

    manifest.workspace_root = workspace.get("root", DEFAULT_WORKSPACE_ROOT)
    manifest.tools_extra = list(tools.get("extra", []))
    manifest.claude_marketplaces = list(claude.get("marketplaces", []))
    manifest.claude_plugins = list(claude.get("plugins", []))
    manifest.claude_hooks = list(claude.get("hooks", []))
    manifest.aws_profiles = list(aws.get("profiles", []))
    manifest.aws_default_profile_is = aws.get("default_profile_is")
    manifest.keychain_items = list(keychain.get("items", []))
    manifest.network_provider = network.get("provider", NETWORK_NONE)
    return manifest


def load_manifest(path: Optional[Path] = None) -> Manifest:
    """Read the manifest at `path` (or the default location).

    Returns a default Manifest with `path=None` when the file does not exist.
    Raises ManifestError when it exists but is unreadable, not TOML, or fails
    validation. An explicitly named path that does not exist is an error,
    because the user asked for that file.
    """
    explicit = path is not None
    path = path or default_manifest_path()
    if not path.is_file():
        if explicit:
            raise ManifestError(f"no manifest at {path}.")
        return Manifest()
    if tomllib is None:  # pragma: no cover
        raise ManifestError("reading the manifest needs Python 3.11 or newer.")
    try:
        with path.open("rb") as handle:
            data = tomllib.load(handle)
    except OSError as exc:
        raise ManifestError(f"cannot read {path}: {exc.strerror or exc}.") from exc
    except tomllib.TOMLDecodeError as exc:
        raise ManifestError(f"{path} is not valid TOML: {exc}.") from exc
    return parse_manifest(data, path=path)
