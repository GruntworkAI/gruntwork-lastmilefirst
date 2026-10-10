"""
Network providers for the device audit (plan 3.8).

A provider is one module in this directory, `<name>.py`, chosen by
`network.provider` in the device manifest. It exposes:

    detect() -> dict
        At least `installed: bool` and `running: bool`. `--snapshot` uses it to
        decide whether to write the provider into a new manifest. It may add
        names it can read safely (a tailnet name), never a key or token.

    audit(table: dict, ctx) -> list[Finding]
        Checks the machine against the provider's `[network.<name>]` manifest
        table. `ctx` is audit_device's AuditContext. Findings use the
        `missing` / `wrong` / `note` constructors from audit_device.

    handoff(table: dict) -> list[str]
        The sign-in or join commands `--install` prints as `you` steps.

The module docstring documents the provider's manifest keys; the SKILL.md
provider table is built from it. A provider reads names and states only and
never a key, token, or auth key.

Nothing here imports a provider until `load()` is called, so a manifest with
`provider = "none"` runs no provider code at all.
"""
from __future__ import annotations

import importlib
from pathlib import Path
from types import ModuleType

NONE = "none"
_HERE = Path(__file__).resolve().parent


def available() -> list[str]:
    """Shipped provider names, sorted. Lists files; imports nothing."""
    return sorted(p.stem for p in _HERE.glob("*.py")
                  if p.stem != "__init__" and not p.stem.startswith("_"))


def load(name: str) -> ModuleType:
    """Import the named provider. KeyError when it is not shipped.

    The name is checked against `available()` first, so a manifest value can
    never become an arbitrary import.
    """
    if name not in available():
        raise KeyError(name)
    return importlib.import_module(f"{__name__}.{name}")
