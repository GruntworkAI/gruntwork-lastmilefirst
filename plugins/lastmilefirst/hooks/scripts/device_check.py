"""Overwatch's cheap device check (organize-device plan 3.6).

For each org identity contract under the workspace root, can this machine
commit as the contract's account? Two local probes answer that:

    a `gh` login for `github_account`   exit code of `gh auth token --user`
                                         (local keyring, no network, 5 s)
    an `includeIf` stanza for the org    ~/.gitconfig, parsed by organize-device
                                         (the default org, the one contract
                                         with no SSH host alias, rides the
                                         global identity and needs none)

Either absence is one ACTION REQUIRED line per org. A stanza that exists but is
wrong (absolute home path and so on) is the full audit's business, not this
check's. Tools and the network provider never alert at session start.

The probes and the contract discovery belong to organize-device's
`audit_device.py`, imported lazily so a broken or too-old sibling costs this
check and nothing else. A clean answer is cached for a day in Overwatch state;
a failing one is not, so the session after the fix stops alerting at once.
Every failure path is silent: this runs inside session start, which must not
crash.
"""

from __future__ import annotations

import shutil
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

DEVICE_CACHE_FIELD = "device_check"
DEVICE_CACHE_TTL = 24 * 60 * 60
# audit_device.py exits the interpreter at import on anything older.
_MIN_PYTHON = (3, 11)
_DEVICE_SCRIPTS = Path(__file__).resolve().parent.parent.parent / "skills" / "organize-device" / "scripts"

ALERT = ("ACTION REQUIRED: this machine cannot commit as {account} for {org}; "
         "run /run-organize-device")


def _audit_device():
    """organize-device's audit module, or None when it cannot be imported."""
    if tuple(sys.version_info[:2]) < _MIN_PYTHON:
        return None
    if str(_DEVICE_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(_DEVICE_SCRIPTS))
    try:
        import audit_device  # noqa: PLC0415 - lazy on purpose
    except BaseException:  # includes the SystemExit an old interpreter raises
        return None
    return audit_device


def _fingerprint(workspace_root: Path, contracts) -> List[Any]:
    """What a cached clean answer was about. A new or changed contract re-probes."""
    return [str(workspace_root)] + sorted(
        [c.org, c.github_account, c.ssh_host_alias or ""] for c in contracts
    )


def _has_stanza(ad, stanzas, contract, home: Path) -> bool:
    for stanza in stanzas:
        target = ad._gitdir_target(stanza)
        if target is not None and ad._gitdir_matches(target, contract.org_dir, home):
            return True
    return False


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
    ad = _audit_device()
    if ad is None:
        return []

    root = Path(workspace).expanduser()
    contracts = ad.load_contracts(root)
    if not contracts:
        return []

    now = int(time.time()) if now is None else now
    fingerprint = _fingerprint(root, contracts)
    cached = get_state().get(DEVICE_CACHE_FIELD)
    if (isinstance(cached, dict) and cached.get("fingerprint") == fingerprint
            and isinstance(cached.get("checked_at"), int)
            and now - cached["checked_at"] <= DEVICE_CACHE_TTL):
        return []

    home = Path.home()
    # AuditContext owns the default-org rule; the manifest is not consulted here.
    ctx = ad.AuditContext(home=home, workspace_root=root, manifest=None,
                          manifest_path=Path(), contracts=contracts)
    stanzas = ad.read_git_config(home / ".gitconfig") or []

    alerts: List[str] = []
    undetermined = False
    login_cache: Dict[str, Optional[bool]] = {}
    for contract in contracts:
        account = contract.github_account
        if account not in login_cache:
            login_cache[account] = ad.gh_login_present(account)
        login = login_cache[account]
        if login is None:
            undetermined = True  # timed out; neither alert nor cache
        stanza_ok = ctx.is_default(contract) or _has_stanza(ad, stanzas, contract, home)
        if login is False or not stanza_ok:
            alerts.append(ALERT.format(account=account, org=contract.org))

    if not alerts and not undetermined:
        try:
            set_state(DEVICE_CACHE_FIELD, {"checked_at": now, "fingerprint": fingerprint})
        except Exception:
            pass  # the cache is an optimization, never a correctness requirement
    return alerts
