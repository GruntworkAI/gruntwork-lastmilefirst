#!/usr/bin/env python3
"""
GitHub secret-scanning posture checks.

Complements the content scan. The content scan asks "is there a secret in
this repo?"; this asks "is GitHub's own safety net switched on?" — namely
secret scanning (which feeds the partner program, and for many providers
means automatic revocation) and push protection (which blocks the push
server-side, where `--no-verify` cannot reach).

Both are free on public repositories. Repository-level push protection is
DISABLED by default; only user-level protection for personal accounts is on
by default, and that does not cover other contributors.

Lives in hooks/scripts/ rather than the skill because the latency-sensitive
consumer is session_start.py, which imports from here directly. The
scan-secrets scripts reach it with the same lazy path-insert idiom they
already use for `overwatch`.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional

ENABLED = "enabled"
DISABLED = "disabled"
UNKNOWN = "unknown"

# `security_and_analysis` is absent entirely for callers without admin on the
# repo. Reading that as "disabled" would fire on every contributor for every
# repo they do not own, so absence is UNKNOWN and stays silent.
_UNKNOWN_POSTURE = {"scanning": UNKNOWN, "push_protection": UNKNOWN}

# Tier-gated on free public repos; they read "disabled" permanently, so they
# are reported in --audit but never alerted on.
TIER_GATED_FIELDS = (
    "secret_scanning_non_provider_patterns",
    "secret_scanning_validity_checks",
)

# Repository settings read from the same payload at no extra cost. They are
# policy choices, not faults, so they are cached and shown in --audit and
# describe() but never alerted on (plan 2026-09-26-001, D2). Unlike
# security_and_analysis, these are visible to any caller who can read the
# repo, so they are parsed for private repos too.
ON = "on"
OFF = "off"

# (label, payload key), in the order they print.
MERGE_METHOD_FIELDS = (
    ("squash", "allow_squash_merge"),
    ("merge", "allow_merge_commit"),
    ("rebase", "allow_rebase_merge"),
)
FEATURE_FIELDS = (
    ("wiki", "has_wiki"),
    ("discussions", "has_discussions"),
    ("projects", "has_projects"),
)
SETTINGS_FIELDS = (
    "visibility",
    "merge_methods",
    "allow_auto_merge",
    "delete_branch_on_merge",
    "allow_forking",
    "features",
    "dependabot_security_updates",
    "web_commit_signoff_required",
)


def _run_gh(args, cwd: Optional[Path], timeout: int):
    """Run a gh command. Returns CompletedProcess, or None if gh is unusable."""
    try:
        return subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(cwd) if cwd else None,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None


def _on_off(value: Any) -> str:
    """A boolean payload field as on/off; anything else is UNKNOWN."""
    if value is True:
        return ON
    if value is False:
        return OFF
    return UNKNOWN


def parse_settings(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Repository settings from a repos/{owner}/{repo} payload.

    Every value is JSON-serializable (it is cached in Overwatch state).
    Absent or malformed fields are UNKNOWN, never a guessed default.
    `merge_methods` is the list of allowed methods, or UNKNOWN if any of the
    three flags is missing, because a partial list would misreport.
    """
    visibility = payload.get("visibility")
    flags = [payload.get(key) for _, key in MERGE_METHOD_FIELDS]
    if all(isinstance(f, bool) for f in flags):
        merge_methods: Any = [
            label for (label, _), f in zip(MERGE_METHOD_FIELDS, flags) if f
        ]
    else:
        merge_methods = UNKNOWN

    sa = payload.get("security_and_analysis")
    dependabot = UNKNOWN
    if isinstance(sa, dict):
        entry = sa.get("dependabot_security_updates")
        if isinstance(entry, dict) and entry.get("status") in (ENABLED, DISABLED):
            dependabot = entry["status"]

    return {
        "visibility": (
            visibility.upper() if isinstance(visibility, str) and visibility else UNKNOWN
        ),
        "merge_methods": merge_methods,
        "allow_auto_merge": _on_off(payload.get("allow_auto_merge")),
        "delete_branch_on_merge": _on_off(payload.get("delete_branch_on_merge")),
        "allow_forking": _on_off(payload.get("allow_forking")),
        "features": {
            label: _on_off(payload.get(key)) for label, key in FEATURE_FIELDS
        },
        "dependabot_security_updates": dependabot,
        "web_commit_signoff_required": _on_off(
            payload.get("web_commit_signoff_required")
        ),
    }


def parse_posture(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Extract posture from a repos/{owner}/{repo} payload.

    Absent or malformed `security_and_analysis` yields UNKNOWN for every
    security field rather than DISABLED — see module docstring. The
    repository settings from parse_settings() are included alongside; the
    security keys and their values are unchanged by that addition.
    """
    settings = parse_settings(payload)
    sa = payload.get("security_and_analysis")
    if not isinstance(sa, dict):
        return {**_UNKNOWN_POSTURE, **settings}

    def status_of(key: str) -> str:
        entry = sa.get(key)
        if not isinstance(entry, dict):
            return UNKNOWN
        value = entry.get("status")
        return value if value in (ENABLED, DISABLED) else UNKNOWN

    posture = {
        "scanning": status_of("secret_scanning"),
        "push_protection": status_of("secret_scanning_push_protection"),
    }
    for field in TIER_GATED_FIELDS:
        posture[field] = status_of(field)
    posture.update(settings)
    return posture


def fetch_posture(
    repo_path: Optional[Path] = None,
    repo: Optional[str] = None,
    timeout: int = 10,
) -> Dict[str, Any]:
    """Fetch visibility + protection posture in a single API call.

    `gh api` resolves the {owner}/{repo} placeholders from the working
    directory's remote, so no remote parsing is needed. Pass `repo` as
    "owner/name" to check a repo that is not checked out locally.

    Private repos short-circuit before any posture is reported: secret
    scanning there requires paid GitHub Secret Protection, so flagging it
    would be a permanent, unfixable alert.

    Returns a dict that is always safe to read:
        {repo, visibility, scanning, push_protection, reason}
    plus the parse_settings() fields whenever the payload was readable
    (callers reading an older cached entry must tolerate their absence).
    """
    endpoint = f"repos/{repo}" if repo else "repos/{owner}/{repo}"
    result = _run_gh(["gh", "api", endpoint], repo_path, timeout)

    base: Dict[str, Any] = {
        "repo": repo,
        "visibility": None,
        "reason": None,
        **_UNKNOWN_POSTURE,
    }

    if result is None:
        base["reason"] = "gh unavailable or timed out"
        return base
    if result.returncode != 0:
        base["reason"] = "no remote, no access, or repo not found"
        return base

    try:
        payload = json.loads(result.stdout)
    except (json.JSONDecodeError, ValueError):
        base["reason"] = "unreadable API response"
        return base

    base["repo"] = payload.get("full_name") or repo
    # Settings are readable at any visibility, so record them before the
    # private short-circuit; the visibility key keeps its existing
    # None-when-absent semantics below.
    settings = parse_settings(payload)
    settings.pop("visibility")
    base.update(settings)
    visibility = str(payload.get("visibility", "")).upper() or None
    base["visibility"] = visibility

    if visibility != "PUBLIC":
        base["reason"] = "private repo — GitHub secret scanning requires a paid tier"
        return base

    posture = parse_posture(payload)
    posture.pop("visibility")
    base.update(posture)
    if base["scanning"] == UNKNOWN and base["push_protection"] == UNKNOWN:
        base["reason"] = "no admin access to this repo"
    return base


def enable_command(repo: str) -> str:
    """The one-liner that fixes it. Scanning must be enabled for push
    protection to be accepted; a single PATCH carrying both keys works."""
    return (
        f"gh api -X PATCH repos/{repo} \\\n"
        "  -F 'security_and_analysis[secret_scanning][status]=enabled' \\\n"
        "  -F 'security_and_analysis[secret_scanning_push_protection][status]=enabled'"
    )


def is_exposed(posture: Dict[str, Any]) -> bool:
    """True when a PUBLIC repo we can administer has a protection switched off."""
    if posture.get("visibility") != "PUBLIC":
        return False
    return DISABLED in (posture.get("scanning"), posture.get("push_protection"))


def posture_alert(posture: Dict[str, Any]) -> Optional[str]:
    """Session-start alert text, or None when there is nothing to say.

    ACTION REQUIRED is justified here because the condition is rare,
    unambiguous, fixed by one pasteable command, and self-extinguishing —
    once fixed it cannot fire again, so it will not become background noise.
    """
    if not is_exposed(posture):
        return None

    repo = posture.get("repo") or "this repo"
    off = [
        label
        for label, key in (("secret scanning", "scanning"),
                           ("push protection", "push_protection"))
        if posture.get(key) == DISABLED
    ]
    return (
        f"ACTION REQUIRED: PUBLIC repo ({repo}) has {' and '.join(off)} disabled. "
        f"Enable with:\n{enable_command(repo)}"
    )


def describe_settings(posture: Dict[str, Any]) -> str:
    """Repository-settings block for --audit. Measurements only; empty when
    nothing was read (gh failed, or an older cache entry without them)."""
    def shown(value: Any) -> str:
        return UNKNOWN if value is None else str(value)

    methods = posture.get("merge_methods")
    features = posture.get("features")
    if not isinstance(features, dict):
        features = {}

    values = [
        methods,
        posture.get("allow_auto_merge"),
        posture.get("delete_branch_on_merge"),
        posture.get("allow_forking"),
        *features.values(),
        posture.get("dependabot_security_updates"),
        posture.get("web_commit_signoff_required"),
    ]
    if all(v in (None, UNKNOWN) for v in values):
        return ""

    if isinstance(methods, list):
        methods_text = ", ".join(methods) if methods else "none"
    else:
        methods_text = shown(methods)

    lines = [
        "Repository settings (--audit only, not alerted on):",
        f"  Merge methods allowed:         {methods_text}",
        f"  Auto-merge:                    {shown(posture.get('allow_auto_merge'))}",
        f"  Delete branch on merge:        {shown(posture.get('delete_branch_on_merge'))}",
        f"  Forking:                       {shown(posture.get('allow_forking'))}",
    ]
    for label, _ in FEATURE_FIELDS:
        name = f"{label.capitalize()}:"
        lines.append(f"  {name:<30} {shown(features.get(label))}")
    lines.append(
        f"  Dependabot security updates:   {shown(posture.get('dependabot_security_updates'))}"
    )
    lines.append(
        f"  Web commit sign-off required:  {shown(posture.get('web_commit_signoff_required'))}"
    )
    return "\n".join(lines)


def describe(posture: Dict[str, Any]) -> str:
    """Multi-line human-readable block for --audit output: the protection
    block, then the repository-settings block when any setting was read."""
    head = _describe_protections(posture)
    settings = describe_settings(posture)
    return f"{head}\n{settings}" if settings else head


def _describe_protections(posture: Dict[str, Any]) -> str:
    if posture.get("visibility") != "PUBLIC":
        return f"GitHub protections: not applicable ({posture.get('reason')})"

    if posture.get("scanning") == UNKNOWN and posture.get("push_protection") == UNKNOWN:
        return f"GitHub protections: unknown ({posture.get('reason')})"

    lines = [
        "GitHub protections:",
        f"  Secret scanning:  {posture.get('scanning')}",
        f"  Push protection:  {posture.get('push_protection')}",
    ]
    if is_exposed(posture):
        lines.append("  WARNING: this public repo is missing a free protection.")
        lines.append(f"  Enable: {enable_command(posture.get('repo', ''))}")

    gated = [
        f"{field.replace('secret_scanning_', '')}={posture.get(field)}"
        for field in TIER_GATED_FIELDS
        if posture.get(field) and posture.get(field) != UNKNOWN
    ]
    if gated:
        lines.append(f"  Tier-gated (not alerted on): {', '.join(gated)}")
        lines.append(
            "  Generic patterns are what this plugin's own lmf-* rules cover."
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Account-wide sweep
#
# Posture is a property of the repo on GitHub, not of the working copy, so a
# sweep that only visits cloned repos can miss an unguarded public repo
# entirely. `--all` therefore checks every public repo on every account the
# workspace claims.
# ---------------------------------------------------------------------------

def discover_accounts(workspace: Path) -> list:
    """GitHub accounts claimed by the workspace's per-org identity contracts.

    Reads <workspace>/<org>/.claude/org.json -> identity.github_account.
    Derived rather than hardcoded so a new org is picked up automatically.
    """
    accounts = []
    try:
        org_files = sorted(workspace.glob("*/.claude/org.json"))
    except OSError:
        return accounts

    for path in org_files:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, ValueError):
            continue
        identity = data.get("identity")
        if not isinstance(identity, dict):
            continue
        account = identity.get("github_account")
        if isinstance(account, str) and account and account not in accounts:
            accounts.append(account)
    return accounts


def list_public_repos(account: str, timeout: int = 30) -> Optional[list]:
    """Public, non-fork repos for an account. None if the listing failed.

    Listing another account's *public* repos succeeds from any authenticated
    identity, so this never needs `gh auth switch` — which is machine-global
    and must not be called from a scan.
    """
    result = _run_gh(
        [
            "gh", "repo", "list", account,
            "--visibility", "public",
            "--no-archived",
            "--limit", "200",
            "--json", "nameWithOwner,isFork",
        ],
        None,
        timeout,
    )
    if result is None or result.returncode != 0:
        return None
    try:
        entries = json.loads(result.stdout)
    except (json.JSONDecodeError, ValueError):
        return None
    return [
        e["nameWithOwner"]
        for e in entries
        if isinstance(e, dict) and not e.get("isFork") and e.get("nameWithOwner")
    ]


def sweep_accounts(workspace: Path) -> list:
    """Report lines for every public repo missing a free protection.

    Forks are excluded: their settings belong to the upstream owner. Repos
    without admin access resolve to UNKNOWN and stay silent.
    """
    accounts = discover_accounts(workspace)
    if not accounts:
        return ["\nGitHub protections: no org identity contracts found — skipped."]

    lines = [f"\nGitHub protections — {len(accounts)} account(s): {', '.join(accounts)}"]
    exposed, checked, unreadable = [], 0, []

    for account in accounts:
        repos = list_public_repos(account)
        if repos is None:
            unreadable.append(account)
            continue
        for repo in repos:
            posture = fetch_posture(repo=repo)
            checked += 1
            if is_exposed(posture):
                off = [
                    label
                    for label, key in (("scanning", "scanning"),
                                       ("push protection", "push_protection"))
                    if posture.get(key) == DISABLED
                ]
                exposed.append((repo, ", ".join(off)))

    if unreadable:
        lines.append(f"  Could not list: {', '.join(unreadable)}")

    if not exposed:
        lines.append(f"  {checked} public repo(s) checked — all protected.")
        return lines

    lines.append(f"  {checked} public repo(s) checked, {len(exposed)} MISSING protections:")
    for repo, off in exposed:
        lines.append(f"    {repo}: {off} disabled")
    lines.append("\n  Enable with:")
    lines.append("  " + enable_command(exposed[0][0]).replace("\n", "\n  "))
    return lines
