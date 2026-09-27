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

import fnmatch
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


def _run_gh(args, cwd: Optional[Path], timeout: int, input_text: Optional[str] = None):
    """Run a gh command. Returns CompletedProcess, or None if gh is unusable.

    `input_text` is fed to stdin; only the gated apply uses it, to pass a
    JSON request body with `--input -`.
    """
    try:
        return subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(cwd) if cwd else None,
            input=input_text,
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


# ---------------------------------------------------------------------------
# Per-call checks (--audit only; plan 2026-09-26-001, U3)
#
# Each check costs its own API call, so none runs at session start (D3).
# Every check returns a small dict whose "status" is OK, UNKNOWN, or
# NOT_AVAILABLE. UNKNOWN covers any non-2xx the API contract does not give a
# meaning to (usually: no admin on the repo); it prints one line and is never
# a finding. NOT_AVAILABLE is a 403 whose message says the feature needs a
# paid plan (rulesets on a private user repo), so it is not read as a gap.
# Seven checks is the ceiling for this plan (Risks, "rules engine").
# ---------------------------------------------------------------------------

OK = "ok"
NOT_AVAILABLE = "not available on this plan"

DEFAULT_BRANCH_TOKEN = "~DEFAULT_BRANCH"
ALL_TOKEN = "~ALL"
RELEASE_TAG_PATTERN = "refs/tags/v*"
# A representative release tag. A tag ruleset "covers release tags" when one
# of its include patterns matches this ref (so refs/tags/* and ~ALL count).
_SAMPLE_RELEASE_TAG = "refs/tags/v0.0.0"
MARKETPLACE_PATH = ".claude-plugin/marketplace.json"


def _api(
    method: str,
    endpoint: str,
    body: Optional[Dict[str, Any]] = None,
    cwd: Optional[Path] = None,
    timeout: int = 15,
):
    """One `gh api -i` call. Returns (status, payload, message).

    `-i` puts the HTTP status line ahead of the body, so a 404 that means
    "off" (vulnerability-alerts) can be told apart from gh being unusable.
    status is None when gh could not run or printed no status line. payload
    is the parsed JSON body, or None for an empty body (e.g. 204). message
    is the API's "message" field, when there is one.
    """
    args = ["gh", "api", "-i", "-X", method, endpoint]
    if body is None:
        result = _run_gh(args, cwd, timeout)
    else:
        args += ["--input", "-"]
        result = _run_gh(args, cwd, timeout, input_text=json.dumps(body))
    if result is None:
        return None, None, "gh unavailable or timed out"

    out = (result.stdout or "").replace("\r\n", "\n")
    head, _, raw = out.partition("\n\n")
    first = head.split("\n", 1)[0].split()
    if len(first) < 2 or not first[0].startswith("HTTP/") or not first[1].isdigit():
        return None, None, "no HTTP status in gh output"
    status = int(first[1])

    payload: Any = None
    if raw.strip():
        try:
            payload = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            payload = None
    message = payload.get("message") if isinstance(payload, dict) else None
    return status, payload, message


def _is_2xx(status: Optional[int]) -> bool:
    return status is not None and 200 <= status < 300


def _is_plan_gated(status: Optional[int], message: Optional[str]) -> bool:
    if status != 403 or not message:
        return False
    text = message.lower()
    return "upgrade" in text or "plan" in text


def _failed(status: Optional[int], message: Optional[str]) -> Dict[str, Any]:
    """The result dict for a non-2xx the API contract gives no meaning to."""
    if _is_plan_gated(status, message):
        return {"status": NOT_AVAILABLE, "reason": message}
    reason = f"HTTP {status}" if status is not None else (message or "no response")
    return {"status": UNKNOWN, "reason": reason}


def _include_patterns(ruleset: Dict[str, Any]):
    ref = (ruleset.get("conditions") or {}).get("ref_name") or {}
    include = ref.get("include") or []
    exclude = ref.get("exclude") or []
    return [p for p in include if isinstance(p, str)], [p for p in exclude if isinstance(p, str)]


def _targets_ref(ruleset: Dict[str, Any], ref: str, tokens) -> bool:
    """Whether a ruleset's ref_name condition covers `ref`. `tokens` are the
    ~SPECIAL values that count as a match (e.g. ~DEFAULT_BRANCH)."""
    include, exclude = _include_patterns(ruleset)
    prefix = "/".join(ref.split("/")[:2])  # refs/heads or refs/tags

    def matches(pattern: str) -> bool:
        if pattern in tokens:
            return True
        if pattern.startswith("~"):
            return False
        full = pattern if pattern.startswith("refs/") else f"{prefix}/{pattern}"
        return fnmatch.fnmatchcase(ref, full)

    if any(matches(p) for p in exclude):
        return False
    return any(matches(p) for p in include)


def fetch_rulesets(repo: str, cwd: Optional[Path] = None) -> Dict[str, Dict[str, Any]]:
    """Branch and tag rulesets, with their rules, from one list call.

    The list endpoint returns no rules, so each branch or tag ruleset is
    then read by id. Returns {"branch": r, "tag": r} where each r is
    {"status": OK, "rulesets": [...]} or a _failed() dict. A failed detail
    read makes that target's result unreadable rather than partial.
    """
    status, payload, message = _api("GET", f"repos/{repo}/rulesets?per_page=100", cwd=cwd)
    if not _is_2xx(status) or not isinstance(payload, list):
        failed = _failed(status, message)
        return {"branch": dict(failed), "tag": dict(failed)}
    out: Dict[str, Dict[str, Any]] = {
        "branch": {"status": OK, "rulesets": []},
        "tag": {"status": OK, "rulesets": []},
    }
    for entry in payload:
        if not isinstance(entry, dict) or entry.get("target") not in out:
            continue
        bucket = out[entry["target"]]
        if bucket.get("status") != OK:
            continue
        status, detail, message = _api(
            "GET", f"repos/{repo}/rulesets/{entry.get('id')}", cwd=cwd
        )
        if _is_2xx(status) and isinstance(detail, dict):
            bucket["rulesets"].append(detail)
        else:
            out[entry["target"]] = _failed(status, message)
    return out


def _rule_types(ruleset: Dict[str, Any]) -> set:
    return {
        r.get("type") for r in (ruleset.get("rules") or [])
        if isinstance(r, dict) and r.get("type")
    }


def check_branch_rulesets(
    repo: str,
    default_branch: str,
    rulesets: Optional[Dict[str, Any]] = None,
    cwd: Optional[Path] = None,
) -> Dict[str, Any]:
    """Check 1: rulesets and classic protection on the default branch."""
    if rulesets is None:
        rulesets = fetch_rulesets(repo, cwd)["branch"]
    ref = f"refs/heads/{default_branch}"

    if rulesets.get("status") == OK:
        targeting = [
            r for r in rulesets["rulesets"]
            if _targets_ref(r, ref, (DEFAULT_BRANCH_TOKEN, ALL_TOKEN))
        ]
        active = [r for r in targeting if r.get("enforcement") == "active"]
        types = set().union(*(_rule_types(r) for r in active)) if active else set()
        result: Dict[str, Any] = {
            "status": OK,
            "branch": default_branch,
            "count": len(targeting),
            "active": len(active),
            "names": [r.get("name") for r in active],
            "pull_request": "pull_request" in types,
            "non_fast_forward": "non_fast_forward" in types,
            "deletion": "deletion" in types,
        }
    else:
        result = {**rulesets, "branch": default_branch}
        result.pop("rulesets", None)

    # Classic branch protection. The API answers an unprotected branch with a
    # 404 whose message is "Branch not protected"; any other 404 is a
    # permissions answer and stays UNKNOWN.
    status, _, message = _api(
        "GET", f"repos/{repo}/branches/{default_branch}/protection", cwd=cwd
    )
    if _is_2xx(status):
        result["classic_protection"] = ON
    elif status == 404 and message == "Branch not protected":
        result["classic_protection"] = OFF
    elif _is_plan_gated(status, message):
        result["classic_protection"] = NOT_AVAILABLE
    else:
        result["classic_protection"] = UNKNOWN
    return result


def _has_marketplace(repo: str, repo_path: Optional[Path], cwd: Optional[Path]) -> Any:
    """True/False when known, UNKNOWN otherwise. Reads the working tree when
    the audit runs inside the repo, else one contents call."""
    if repo_path is not None:
        for d in (repo_path, *repo_path.parents):
            if (d / ".git").exists():
                return (d / MARKETPLACE_PATH).is_file()
    status, _, _ = _api("GET", f"repos/{repo}/contents/{MARKETPLACE_PATH}", cwd=cwd)
    if _is_2xx(status):
        return True
    if status == 404:
        return False
    return UNKNOWN


def check_tag_rulesets(
    repo: str,
    rulesets: Optional[Dict[str, Any]] = None,
    repo_path: Optional[Path] = None,
    cwd: Optional[Path] = None,
) -> Dict[str, Any]:
    """Check 2: rulesets whose pattern covers release tags (v*)."""
    if rulesets is None:
        rulesets = fetch_rulesets(repo, cwd)["tag"]
    marketplace = _has_marketplace(repo, repo_path, cwd)
    if rulesets.get("status") != OK:
        result = {**rulesets, "marketplace": marketplace}
        result.pop("rulesets", None)
        return result

    def covers(r):
        include, _ = _include_patterns(r)
        return RELEASE_TAG_PATTERN in include or _targets_ref(
            r, _SAMPLE_RELEASE_TAG, (ALL_TOKEN,)
        )

    matching = [r for r in rulesets["rulesets"] if covers(r)]
    active = [r for r in matching if r.get("enforcement") == "active"]
    types = set().union(*(_rule_types(r) for r in active)) if active else set()
    return {
        "status": OK,
        "count": len(matching),
        "active": len(active),
        "names": [r.get("name") for r in active],
        "update": "update" in types,
        "deletion": "deletion" in types,
        "marketplace": marketplace,
    }


def check_dependabot_alerts(repo: str, cwd: Optional[Path] = None) -> Dict[str, Any]:
    """Check 3. Per the API contract, 204 means on and 404 means off."""
    status, _, message = _api("GET", f"repos/{repo}/vulnerability-alerts", cwd=cwd)
    if _is_2xx(status):
        return {"status": OK, "alerts": ON}
    if status == 404:
        return {"status": OK, "alerts": OFF}
    return _failed(status, message)


def check_actions_policy(repo: str, cwd: Optional[Path] = None) -> Dict[str, Any]:
    """Check 4: whether Actions is enabled and which actions may run."""
    status, payload, message = _api("GET", f"repos/{repo}/actions/permissions", cwd=cwd)
    if not _is_2xx(status) or not isinstance(payload, dict):
        return _failed(status, message)
    result: Dict[str, Any] = {
        "status": OK,
        "enabled": payload.get("enabled"),
        "allowed_actions": payload.get("allowed_actions", UNKNOWN),
    }
    if payload.get("allowed_actions") == "selected":
        status, sel, message = _api(
            "GET", f"repos/{repo}/actions/permissions/selected-actions", cwd=cwd
        )
        if _is_2xx(status) and isinstance(sel, dict):
            patterns = sel.get("patterns_allowed") or []
            result.update({
                "github_owned_allowed": sel.get("github_owned_allowed"),
                "verified_allowed": sel.get("verified_allowed"),
                "patterns_allowed": len(patterns),
                "patterns": list(patterns),
            })
        else:
            result.update({
                "github_owned_allowed": UNKNOWN,
                "verified_allowed": UNKNOWN,
                "patterns_allowed": UNKNOWN,
            })
    return result


def check_workflow_token(repo: str, cwd: Optional[Path] = None) -> Dict[str, Any]:
    """Check 5: the default GITHUB_TOKEN permissions for workflows."""
    status, payload, message = _api(
        "GET", f"repos/{repo}/actions/permissions/workflow", cwd=cwd
    )
    if not _is_2xx(status) or not isinstance(payload, dict):
        return _failed(status, message)
    return {
        "status": OK,
        "default_workflow_permissions": payload.get("default_workflow_permissions", UNKNOWN),
        "can_approve_pull_request_reviews": payload.get(
            "can_approve_pull_request_reviews", UNKNOWN
        ),
    }


def check_webhooks(repo: str, cwd: Optional[Path] = None) -> Dict[str, Any]:
    """Check 6: webhook count, and counts with no secret or SSL checks off.
    Counts only; whether a hook is suspicious is the user's call."""
    status, payload, message = _api("GET", f"repos/{repo}/hooks?per_page=100", cwd=cwd)
    if not _is_2xx(status) or not isinstance(payload, list):
        return _failed(status, message)
    hooks = [h for h in payload if isinstance(h, dict)]
    configs = [h.get("config") or {} for h in hooks]
    return {
        "status": OK,
        "count": len(hooks),
        "no_secret": sum(1 for c in configs if not c.get("secret")),
        "insecure_ssl": sum(1 for c in configs if str(c.get("insecure_ssl")) == "1"),
    }


def check_deploy_keys(repo: str, cwd: Optional[Path] = None) -> Dict[str, Any]:
    """Check 7: deploy key count and how many can write."""
    status, payload, message = _api("GET", f"repos/{repo}/keys?per_page=100", cwd=cwd)
    if not _is_2xx(status) or not isinstance(payload, list):
        return _failed(status, message)
    keys = [k for k in payload if isinstance(k, dict)]
    return {
        "status": OK,
        "count": len(keys),
        "writable": sum(1 for k in keys if k.get("read_only") is False),
    }


def audit_posture(
    repo: Optional[str] = None,
    repo_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Run the repo read plus the seven per-call checks.

    `repo` is "owner/name"; when None, gh resolves {owner}/{repo} from
    `repo_path`'s remote and the full name from the first response is used
    for every later call. Returns:
        {status, repo, reason, default_branch, admin, settings, checks}
    where settings is parse_posture() of the repo payload (the source for
    the repo-level proposal items) and checks maps check name to its dict.
    """
    cwd = repo_path
    status, payload, message = _api(
        "GET", f"repos/{repo}" if repo else "repos/{owner}/{repo}", cwd=cwd
    )
    if not _is_2xx(status) or not isinstance(payload, dict):
        reason = f"HTTP {status}" if status is not None else message
        return {"status": UNKNOWN, "repo": repo, "reason": reason, "checks": {}}

    full = payload.get("full_name") or repo
    branch = payload.get("default_branch") or "main"
    perms = payload.get("permissions")
    admin = perms.get("admin") if isinstance(perms, dict) else UNKNOWN

    rulesets = fetch_rulesets(full, cwd)
    checks = {
        "branch_rulesets": check_branch_rulesets(full, branch, rulesets["branch"], cwd),
        "tag_rulesets": check_tag_rulesets(full, rulesets["tag"], repo_path, cwd),
        "dependabot_alerts": check_dependabot_alerts(full, cwd),
        "actions": check_actions_policy(full, cwd),
        "workflow_token": check_workflow_token(full, cwd),
        "webhooks": check_webhooks(full, cwd),
        "deploy_keys": check_deploy_keys(full, cwd),
    }
    return {
        "status": OK,
        "repo": full,
        "reason": None,
        "default_branch": branch,
        "admin": admin,
        "settings": parse_posture(payload),
        "checks": checks,
    }


def _unread(label: str, check: Dict[str, Any]) -> Optional[str]:
    """The one line for a check that could not be read, else None."""
    status = check.get("status")
    if status == NOT_AVAILABLE:
        return f"  {label}: not available on this plan"
    if status != OK:
        return f"  {label}: unknown ({check.get('reason') or 'not readable'})"
    return None


def _yes_no(value: Any) -> str:
    if value is True:
        return "yes"
    if value is False:
        return "no"
    return UNKNOWN


def describe_audit(audit: Dict[str, Any]) -> str:
    """Per-call block for --audit. Measurements only (D4): counts and
    values, plus one consequence clause where the user may not know it."""
    if audit.get("status") != OK:
        return f"Per-call checks: unknown ({audit.get('reason')})"
    checks = audit["checks"]
    lines = ["Per-call checks (--audit only, not alerted on):"]

    b = checks["branch_rulesets"]
    label = f"Rulesets on {b.get('branch')}"
    line = _unread(label, b)
    if line is None:
        if b["active"]:
            rules = [
                "blocks force pushes" if b["non_fast_forward"] else "force pushes not blocked",
                "blocks deletion" if b["deletion"] else "deletion not blocked",
            ]
            pr = "requires a pull request" if b["pull_request"] else "no pull request requirement"
            line = f"  {label}: {b['active']} active ({', '.join(rules)}; {pr})"
        else:
            line = f"  {label}: {b['active']} active"
        if b["count"] != b["active"]:
            line += f", {b['count'] - b['active']} not enforced"
    lines.append(line)
    classic = b.get("classic_protection", UNKNOWN)
    classic_text = {ON: "on", OFF: "none"}.get(classic, classic)
    lines.append(f"  Classic branch protection on {b.get('branch')}: {classic_text}")

    t = checks["tag_rulesets"]
    label = "Rulesets on release tags (v*)"
    line = _unread(label, t)
    if line is None:
        if t["active"]:
            rules = [
                "blocks updates" if t["update"] else "updates not blocked",
                "blocks deletion" if t["deletion"] else "deletion not blocked",
            ]
            line = f"  {label}: {t['active']} active ({', '.join(rules)})"
        else:
            line = f"  {label}: {t['active']} active"
        if t["count"] != t["active"]:
            line += f", {t['count'] - t['active']} not enforced"
    if t.get("marketplace") is True:
        line += "; this repo ships a marketplace.json, and consumer installs resolve from this tag"
    lines.append(line)

    d = checks["dependabot_alerts"]
    lines.append(_unread("Dependabot alerts", d) or f"  Dependabot alerts: {d['alerts']}")

    a = checks["actions"]
    line = _unread("Actions", a)
    if line is None:
        if a.get("enabled") is False:
            line = "  Actions: disabled"
        else:
            line = f"  Actions: enabled, allowed actions {a.get('allowed_actions')}"
            if a.get("allowed_actions") == "selected":
                line += (
                    f" (GitHub-owned allowed: {_yes_no(a.get('github_owned_allowed'))},"
                    f" verified allowed: {_yes_no(a.get('verified_allowed'))},"
                    f" patterns: {a.get('patterns_allowed')})"
                )
    lines.append(line)

    w = checks["workflow_token"]
    lines.append(_unread("Workflow token", w) or (
        f"  Workflow token default: {w['default_workflow_permissions']};"
        f" can approve pull requests: {_yes_no(w['can_approve_pull_request_reviews'])}"
    ))

    h = checks["webhooks"]
    lines.append(_unread("Webhooks", h) or (
        f"  Webhooks: {h['count']} ({h['no_secret']} without a secret,"
        f" {h['insecure_ssl']} with SSL verification off)"
    ))

    k = checks["deploy_keys"]
    lines.append(_unread("Deploy keys", k) or (
        f"  Deploy keys: {k['count']} ({k['writable']} writable)"
    ))
    return "\n".join(lines)


def deep_audit(repos, progress=None) -> list:
    """Per-call checks for each repo in an account sweep (--audit --github
    --deep). About eight calls per repo, plus one per ruleset. `progress`,
    when given, is called with (index, total, repo) before each repo."""
    lines = []
    total = len(repos)
    for i, repo in enumerate(repos, 1):
        if progress:
            progress(i, total, repo)
        lines.append(f"\n[{i}/{total}] {repo}")
        lines.append(describe_audit(audit_posture(repo=repo)))
    return lines


# ---------------------------------------------------------------------------
# Gated apply (plan 2026-09-26-001, U3b; D1)
#
# propose() turns an audit into an itemized delta; apply() writes exactly the
# ids the user named, then re-reads each setting through the same GET the
# audit uses. The default group is the six-part baseline from the plan.
# Anything that changes who can push or merge is "consider" and is written
# only when named. Nothing here is reachable from session start.
# ---------------------------------------------------------------------------

DEFAULT_GROUP = "default"
CONSIDER_GROUP = "consider"
UNREADABLE_GROUP = "unreadable"

# Canonical order; apply() writes in this order regardless of how the ids
# were given (Dependabot alerts must be on before security updates).
DEFAULT_IDS = (
    "ruleset-main",
    "ruleset-tags",
    "dependabot-alerts",
    "dependabot-updates",
    "actions-selected",
    "delete-branch-on-merge",
    "wiki-off",
)
CONSIDER_IDS = (
    "ruleset-main-pr",
    "merge-commit-only",
    "forking-off",
)
ITEM_IDS = DEFAULT_IDS + CONSIDER_IDS

RULESET_MAIN = {
    "name": "protect main",
    "target": "branch",
    "enforcement": "active",
    "conditions": {"ref_name": {"include": [DEFAULT_BRANCH_TOKEN], "exclude": []}},
    "rules": [{"type": "deletion"}, {"type": "non_fast_forward"}],
}
RULESET_TAGS = {
    "name": "protect release tags",
    "target": "tag",
    "enforcement": "active",
    "conditions": {"ref_name": {"include": [RELEASE_TAG_PATTERN], "exclude": []}},
    "rules": [{"type": "deletion"}, {"type": "update"}],
}
RULESET_MAIN_PR = {
    "name": "require pull request on main",
    "target": "branch",
    "enforcement": "active",
    "conditions": {"ref_name": {"include": [DEFAULT_BRANCH_TOKEN], "exclude": []}},
    "rules": [{
        "type": "pull_request",
        "parameters": {
            "required_approving_review_count": 0,
            "dismiss_stale_reviews_on_push": False,
            "require_code_owner_review": False,
            "require_last_push_approval": False,
            "required_review_thread_resolution": False,
        },
    }],
}


def _item(id_, group, setting, current, proposed, reason, consequence, in_place,
          unreadable=None):
    return {
        "id": id_,
        "group": UNREADABLE_GROUP if unreadable else group,
        "setting": setting,
        "current": current,
        "proposed": proposed,
        "reason": reason,
        "consequence": consequence,
        "in_place": in_place,
        "unreadable": unreadable,
    }


def _check_unreadable(check: Dict[str, Any]) -> Optional[str]:
    status = check.get("status")
    if status == OK:
        return None
    if status == NOT_AVAILABLE:
        return NOT_AVAILABLE
    return f"unknown ({check.get('reason') or 'not readable'})"


def _all_items(audit: Dict[str, Any], settings: Dict[str, Any]) -> list:
    """Every item, including the ones already in place (apply needs them to
    report a no-op). propose() filters."""
    checks = audit.get("checks") or {}
    branch = audit.get("default_branch") or "main"
    items = []

    b = checks.get("branch_rulesets") or {"status": UNKNOWN}
    bu = _check_unreadable(b)
    main_ok = bool(b.get("non_fast_forward") and b.get("deletion"))
    items.append(_item(
        "ruleset-main", DEFAULT_GROUP, f"Ruleset on {branch}",
        "unreadable" if bu else (
            f"{b.get('active', 0)} active"
            + (" (blocks force pushes and deletion)" if main_ok else "")
        ),
        "'protect main': blocks force pushes and deletion; no pull request requirement",
        "force pushes and deletion rewrite or remove the history everyone builds on",
        f"blocks force pushes to {branch} and its deletion; direct pushes still work",
        main_ok, bu,
    ))

    t = checks.get("tag_rulesets") or {"status": UNKNOWN}
    tu = _check_unreadable(t)
    tags_ok = bool(t.get("update") and t.get("deletion"))
    reason = "a release tag that can be moved changes what it points to after release"
    if t.get("marketplace") is True:
        reason += "; consumer installs resolve from this tag"
    items.append(_item(
        "ruleset-tags", DEFAULT_GROUP, "Ruleset on release tags (v*)",
        "unreadable" if tu else (
            f"{t.get('active', 0)} active"
            + (" (blocks updates and deletion)" if tags_ok else "")
        ),
        "'protect release tags': refs/tags/v*, blocks updates and deletion",
        reason,
        "existing v* tags can no longer be moved or deleted; new tags can still be created",
        tags_ok, tu,
    ))

    d = checks.get("dependabot_alerts") or {"status": UNKNOWN}
    du = _check_unreadable(d)
    items.append(_item(
        "dependabot-alerts", DEFAULT_GROUP, "Dependabot alerts",
        "unreadable" if du else d.get("alerts"), ON,
        "known vulnerabilities in dependencies are reported on the repo",
        "alerts appear in the Security tab and notifications; no code changes",
        d.get("alerts") == ON, du,
    ))

    dep = settings.get("dependabot_security_updates", UNKNOWN)
    items.append(_item(
        "dependabot-updates", DEFAULT_GROUP, "Dependabot security updates",
        dep, ENABLED,
        "a vulnerable dependency gets a fix proposed as a pull request",
        "Dependabot opens pull requests; nothing merges without a person",
        dep == ENABLED,
        None if dep in (ENABLED, DISABLED) else "unknown (needs admin)",
    ))

    a = checks.get("actions") or {"status": UNKNOWN}
    au = _check_unreadable(a)
    if a.get("enabled") is False:
        cur, actions_ok = "Actions disabled", True
    elif a.get("allowed_actions") == "selected":
        cur = (f"selected (GitHub-owned: {_yes_no(a.get('github_owned_allowed'))},"
               f" verified: {_yes_no(a.get('verified_allowed'))})")
        actions_ok = a.get("github_owned_allowed") is True and a.get("verified_allowed") is True
    else:
        cur, actions_ok = str(a.get("allowed_actions")), False
    items.append(_item(
        "actions-selected", DEFAULT_GROUP, "Actions allowed actions",
        "unreadable" if au else cur,
        "selected: GitHub-owned and verified creators allowed",
        "a workflow cannot pull in an action from an unverified publisher",
        "workflows using an action outside that set stop running until it is allowed",
        actions_ok, au,
    ))

    dbm = settings.get("delete_branch_on_merge", UNKNOWN)
    items.append(_item(
        "delete-branch-on-merge", DEFAULT_GROUP, "Delete branch on merge",
        dbm, ON,
        "merged head branches do not pile up",
        "the head branch is deleted after a pull request merges; it can be restored",
        dbm == ON, None if dbm in (ON, OFF) else UNKNOWN,
    ))

    wiki = (settings.get("features") or {}).get("wiki", UNKNOWN)
    items.append(_item(
        "wiki-off", DEFAULT_GROUP, "Wiki",
        wiki, OFF,
        "a wiki is a surface that can carry content nobody reviewed",
        "the Wiki tab is hidden; existing wiki content is kept and returns if turned back on",
        wiki == OFF, None if wiki in (ON, OFF) else UNKNOWN,
    ))

    # consider: changes who can push or merge; applied only when named.
    pr = b.get("pull_request") is True
    items.append(_item(
        "ruleset-main-pr", CONSIDER_GROUP, f"Pull request requirement on {branch}",
        "unreadable" if bu else ("required" if pr else "not required"),
        "'require pull request on main': pull_request rule, 0 approvals",
        "every change to the default branch passes through a pull request",
        f"direct pushes to {branch} are blocked, including doc commits",
        pr, bu,
    ))

    methods = settings.get("merge_methods", UNKNOWN)
    items.append(_item(
        "merge-commit-only", CONSIDER_GROUP, "Merge methods",
        ", ".join(methods) if isinstance(methods, list) else methods,
        "merge only",
        "a merge commit keeps the original author line; a squash writes a new commit"
        " stamped with the pull request author's primary email",
        "squash and rebase merges are no longer offered",
        methods == ["merge"], None if isinstance(methods, list) else UNKNOWN,
    ))

    # GitHub does not allow forking to be turned off on a public repo, so
    # the item exists only where the setting has an effect.
    if settings.get("visibility") not in ("PUBLIC", None, UNKNOWN):
        fork = settings.get("allow_forking", UNKNOWN)
        items.append(_item(
            "forking-off", CONSIDER_GROUP, "Forking",
            fork, OFF,
            "a fork of a private repo is a second copy under someone else's control",
            "no new forks; collaborators who work from a fork switch to branches",
            fork == OFF, None if fork in (ON, OFF) else UNKNOWN,
        ))
    return items


def propose(audit: Dict[str, Any], settings: Optional[Dict[str, Any]] = None) -> list:
    """The itemized delta: every item not already in place.

    `settings` defaults to the audit's own repo settings. A repo the caller
    does not administer gets no proposal (see proposal_blocker()).
    """
    if proposal_blocker(audit):
        return []
    if settings is None:
        settings = audit.get("settings") or {}
    return [i for i in _all_items(audit, settings) if not i["in_place"]]


def proposal_blocker(audit: Dict[str, Any]) -> Optional[str]:
    """One-line reason there is no proposal at all, else None."""
    if audit.get("status") != OK:
        return f"no proposal: the repo could not be read ({audit.get('reason')})"
    if audit.get("admin") is not True:
        return "no proposal: your account does not administer this repo"
    return None


def describe_proposal(audit: Dict[str, Any], items: list) -> str:
    blocker = proposal_blocker(audit)
    if blocker:
        return f"Proposal: {blocker}"
    lines = [f"Proposal for {audit.get('repo')} (nothing is applied without --apply <id>):"]
    for group, title in (
        (DEFAULT_GROUP, "Default"),
        (CONSIDER_GROUP, "Consider (changes who can push or merge; applied only if named)"),
    ):
        chosen = [i for i in items if i["group"] == group]
        lines.append(f"\n  {title}:")
        if not chosen:
            lines.append("    (none; already in place)" if group == DEFAULT_GROUP
                         else "    (none)")
        for i in chosen:
            lines.append(f"    {i['id']}: {i['setting']}: {i['current']} -> {i['proposed']}")
            lines.append(f"      why: {i['reason']}")
            lines.append(f"      consequence: {i['consequence']}")
    unread = [i for i in items if i["group"] == UNREADABLE_GROUP]
    if unread:
        lines.append("\n  Not proposed (current value could not be read):")
        for i in unread:
            lines.append(f"    {i['id']}: {i['unreadable']}")
    return "\n".join(lines)


def _write_calls(item_id: str, repo: str, audit: Dict[str, Any]) -> list:
    """The (method, endpoint, body) calls that apply one item."""
    if item_id == "ruleset-main":
        return [("POST", f"repos/{repo}/rulesets", RULESET_MAIN)]
    if item_id == "ruleset-tags":
        return [("POST", f"repos/{repo}/rulesets", RULESET_TAGS)]
    if item_id == "ruleset-main-pr":
        return [("POST", f"repos/{repo}/rulesets", RULESET_MAIN_PR)]
    if item_id == "dependabot-alerts":
        return [("PUT", f"repos/{repo}/vulnerability-alerts", None)]
    if item_id == "dependabot-updates":
        return [("PUT", f"repos/{repo}/automated-security-fixes", None)]
    if item_id == "actions-selected":
        actions = (audit.get("checks") or {}).get("actions") or {}
        return [
            ("PUT", f"repos/{repo}/actions/permissions",
             {"enabled": True, "allowed_actions": "selected"}),
            ("PUT", f"repos/{repo}/actions/permissions/selected-actions",
             {"github_owned_allowed": True, "verified_allowed": True,
              "patterns_allowed": list(actions.get("patterns") or [])}),
        ]
    if item_id == "delete-branch-on-merge":
        return [("PATCH", f"repos/{repo}", {"delete_branch_on_merge": True})]
    if item_id == "wiki-off":
        return [("PATCH", f"repos/{repo}", {"has_wiki": False})]
    if item_id == "merge-commit-only":
        return [("PATCH", f"repos/{repo}", {
            "allow_merge_commit": True, "allow_squash_merge": False,
            "allow_rebase_merge": False})]
    if item_id == "forking-off":
        return [("PATCH", f"repos/{repo}", {"allow_forking": False})]
    raise KeyError(item_id)


def _reread(item_id: str, repo: str, audit: Dict[str, Any]) -> Any:
    """The current value of one item, read through the audit's own GET."""
    fresh = dict(audit)
    checks = dict(audit.get("checks") or {})
    settings = audit.get("settings") or {}
    if item_id in ("ruleset-main", "ruleset-main-pr"):
        checks["branch_rulesets"] = check_branch_rulesets(
            repo, audit.get("default_branch") or "main")
    elif item_id == "ruleset-tags":
        checks["tag_rulesets"] = check_tag_rulesets(repo)
    elif item_id == "dependabot-alerts":
        checks["dependabot_alerts"] = check_dependabot_alerts(repo)
    elif item_id == "actions-selected":
        checks["actions"] = check_actions_policy(repo)
    else:
        status, payload, _ = _api("GET", f"repos/{repo}")
        if _is_2xx(status) and isinstance(payload, dict):
            settings = parse_posture(payload)
        else:
            return UNKNOWN
    fresh["checks"] = checks
    for i in _all_items(fresh, settings):
        if i["id"] == item_id:
            return i["current"]
    return UNKNOWN


def apply(
    repo: Optional[str],
    ids,
    repo_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Apply exactly the named items, then re-read each one.

    Unknown ids are an error and nothing is written (checked before any
    call). No ids returns the proposal and writes nothing. Returns
    {error, audit, proposal, results}; each result is
    {id, outcome, before, after, message} with outcome one of
    "applied", "already set", "not applied".
    """
    ids = list(ids or [])
    unknown = [i for i in ids if i not in ITEM_IDS]
    if unknown:
        return {
            "error": f"unknown item id(s): {', '.join(unknown)}; nothing applied."
                     f" Known ids: {', '.join(ITEM_IDS)}",
            "audit": None, "proposal": [], "results": [],
        }

    audit = audit_posture(repo=repo, repo_path=repo_path)
    if not ids:
        return {"error": None, "audit": audit, "proposal": propose(audit), "results": []}

    blocker = proposal_blocker(audit)
    if blocker:
        return {"error": blocker.replace("no proposal", "nothing applied"),
                "audit": audit, "proposal": [], "results": []}

    full = audit["repo"]
    by_id = {i["id"]: i for i in _all_items(audit, audit.get("settings") or {})}
    results = []
    for item_id in [i for i in ITEM_IDS if i in ids]:
        item = by_id.get(item_id)
        if item is None:
            results.append({"id": item_id, "outcome": "not applied", "before": None,
                            "after": None,
                            "message": "not applicable to this repo (e.g. forking on a public repo)"})
            continue
        before = item["current"]
        if item["unreadable"]:
            results.append({"id": item_id, "outcome": "not applied", "before": before,
                            "after": before,
                            "message": f"current value could not be read: {item['unreadable']}"})
            continue
        if item["in_place"]:
            results.append({"id": item_id, "outcome": "already set", "before": before,
                            "after": before, "message": "already set; no change made"})
            continue
        failure = None
        for method, endpoint, body in _write_calls(item_id, full, audit):
            status, _, message = _api(method, endpoint, body)
            if not _is_2xx(status):
                failure = (f"{method} {endpoint} returned "
                           f"{'HTTP ' + str(status) if status else 'no response'}"
                           + (f": {message}" if message else ""))
                break
        after = _reread(item_id, full, audit)
        results.append({
            "id": item_id,
            "outcome": "not applied" if failure else "applied",
            "before": before,
            "after": after,
            "message": failure or "applied and re-read",
        })
    return {"error": None, "audit": audit, "proposal": [], "results": results}


def describe_apply(outcome: Dict[str, Any]) -> str:
    if outcome.get("error"):
        return f"Apply: {outcome['error']}"
    if not outcome.get("results"):
        audit = outcome.get("audit") or {}
        return ("Apply: no item ids given; nothing applied.\n\n"
                + describe_proposal(audit, outcome.get("proposal") or []))
    repo = (outcome.get("audit") or {}).get("repo")
    lines = [f"Apply to {repo}:"]
    for r in outcome["results"]:
        lines.append(f"  {r['id']}: {r['outcome']}")
        lines.append(f"    before: {r['before']}")
        lines.append(f"    after:  {r['after']}")
        if r["outcome"] != "applied":
            lines.append(f"    {r['message']}")
    return "\n".join(lines)
