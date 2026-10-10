"""Overwatch's cheap device check (organize-device plan 3.6).

For each org identity contract under the workspace root, can this machine
commit as the contract's account? Two local probes answer that:

    a `gh` login for `github_account`   exit code of `gh auth token --user`
                                         (local keyring, no network)
    an `includeIf` stanza for the org    ~/.gitconfig and the XDG git config,
                                         read by organize-device (the default
                                         org, the one contract with no SSH host
                                         alias, rides the global identity and
                                         needs none)

Either absence is one ACTION REQUIRED line per org. A stanza that exists but is
wrong (absolute home path and so on) is the full audit's business, not this
check's. Tools and the network provider never alert at session start.

The probes and the contract discovery belong to organize-device's
`audit_device.py`, imported lazily so a broken sibling costs this check and
nothing else. The gh probes share one budget (DEVICE_BUDGET_SECS), because the
whole SessionStart hook has 10 s and a locked keyring can hang each probe.

Caching, under one Overwatch state field:

    clean          no alert, every login answered      24 h
    undetermined   no alert, a probe timed out or the  1 h
                   budget ran out first
    python_floor   the hook's python is below 3.11     24 h (the WARNING line
                                                        prints once a day)
    alert          never cached, so the session after the fix stops alerting

Every other failure path is silent: this runs inside session start, which must
not crash.
"""

from __future__ import annotations

import shutil
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

DEVICE_CACHE_FIELD = "device_check"
DEVICE_CACHE_TTL = 24 * 60 * 60
DEVICE_UNDETERMINED_TTL = 60 * 60
# Total wall time for every gh probe in one run, well inside the hook's 10 s.
DEVICE_BUDGET_SECS = 3.0
_TTLS = {"clean": DEVICE_CACHE_TTL, "undetermined": DEVICE_UNDETERMINED_TTL,
         "python_floor": DEVICE_CACHE_TTL}
# audit_device.py exits the interpreter at import on anything older.
_MIN_PYTHON = (3, 11)
_DEVICE_SCRIPTS = Path(__file__).resolve().parent.parent.parent / "skills" / "organize-device" / "scripts"

ALERT = ("ACTION REQUIRED: this machine cannot commit as {account} for {org}; "
         "run /run-organize-device")
PYTHON_FLOOR_WARNING = ("WARNING: device check skipped: python3 is {version}, "
                        "organize-device needs {floor} or newer")

# The budget clock, the same monotonic deadline session_start uses for the
# plugin-update refresh. A module name so tests can drive it.
_clock = time.monotonic


def _python_version() -> tuple:
    return tuple(sys.version_info[:2])


def _audit_device():
    """organize-device's audit module, or None when it cannot be imported."""
    if _python_version() < _MIN_PYTHON:
        return None
    if str(_DEVICE_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(_DEVICE_SCRIPTS))
    try:
        import audit_device  # noqa: PLC0415 - lazy on purpose
    except BaseException:  # includes the SystemExit an old interpreter raises
        return None
    return audit_device


def _fingerprint(workspace_root: Path, contracts) -> List[Any]:
    """What a cached answer was about. A new or changed contract re-probes."""
    return [str(workspace_root)] + sorted(
        [c.org, c.github_account, c.ssh_host_alias or ""] for c in contracts
    )


def _fresh(cached: Any, fingerprint: List[Any], now: int) -> bool:
    if not (isinstance(cached, dict) and cached.get("fingerprint") == fingerprint
            and isinstance(cached.get("checked_at"), int)):
        return False
    # An entry without a status predates the field and was a clean run.
    ttl = _TTLS.get(cached.get("status", "clean"))
    return ttl is not None and now - cached["checked_at"] <= ttl


def _cache(set_state, status: str, now: int, fingerprint: List[Any]) -> None:
    try:
        set_state(DEVICE_CACHE_FIELD,
                  {"checked_at": now, "fingerprint": fingerprint, "status": status})
    except Exception:
        pass  # the cache is an optimization, never a correctness requirement


def device_alerts(
    config: Dict[str, Any],
    get_state: Callable[[], Dict[str, Any]],
    set_state: Callable[[str, Any], None],
    now: Optional[int] = None,
) -> List[str]:
    """ACTION REQUIRED lines, one per org this machine cannot commit for.

    `get_state` returns the global Overwatch scope; `set_state(field, value)`
    writes one field to it. Never raises.
    """
    try:
        return _device_alerts(config, get_state, set_state, now)
    except Exception:
        return []


def _device_alerts(config, get_state, set_state, now) -> List[str]:
    workspace = (config or {}).get("workspace")
    if not workspace:
        return []
    if shutil.which("gh") is None:
        return []  # the Tools section of the audit reports a missing gh
    root = Path(workspace).expanduser()
    now = int(time.time()) if now is None else now

    version = _python_version()
    if version < _MIN_PYTHON:
        fingerprint = [str(root), "python", "%d.%d" % version]
        if _fresh(get_state().get(DEVICE_CACHE_FIELD), fingerprint, now):
            return []
        _cache(set_state, "python_floor", now, fingerprint)
        return [PYTHON_FLOOR_WARNING.format(version="%d.%d" % version,
                                            floor="%d.%d" % _MIN_PYTHON)]

    ad = _audit_device()
    if ad is None:
        return []
    contracts = ad.load_contracts(root)
    if not contracts:
        return []

    fingerprint = _fingerprint(root, contracts)
    if _fresh(get_state().get(DEVICE_CACHE_FIELD), fingerprint, now):
        return []

    home = Path.home()
    stanzas = ad.read_user_git_stanzas(home)
    deadline = _clock() + DEVICE_BUDGET_SECS

    alerts: List[str] = []
    undetermined = False
    login_cache: Dict[str, Optional[bool]] = {}
    for contract in contracts:
        account = contract.github_account
        if account not in login_cache:
            remaining = deadline - _clock()
            if undetermined or remaining <= 0:
                # A probe already hung or the budget is spent: stop asking gh.
                login_cache[account] = None
            else:
                login_cache[account] = ad.gh_login_present(
                    account, timeout=min(ad.GH_TIMEOUT, remaining))
        login = login_cache[account]
        if login is None:
            undetermined = True  # neither alert nor a clean answer
        stanza_ok = (ad.is_default(contract, contracts)
                     or ad.has_include_for(stanzas, contract.org_dir, home))
        if login is False or not stanza_ok:
            alerts.append(ALERT.format(account=account, org=contract.org))

    if not alerts:
        _cache(set_state, "undetermined" if undetermined else "clean", now, fingerprint)
    return alerts
