#!/usr/bin/env python3
"""
Audit identity contracts across the workspace.

The pre-commit hook (check_identity.py) answers one question fast and offline:
does *this* commit match? This audit answers the questions the hook structurally
cannot — is every org configured, does the declared account exist, and are there
repos already sitting on the wrong identity.

Split by budget, because the three surfaces have very different constraints:

    check_identity.py   instant, offline, blocking   this commit
    session-start       sub-second, offline          is a contract missing
    this script         seconds, network allowed     does everything comply

Overwatch calls `cheap_findings()` directly — it must stay filesystem-only, no
subprocesses, because it shares a 10-second session-start budget with every
other check. `full_findings()` adds the per-repo drift walk and the optional
account-liveness probe, and is only ever run on explicit invocation.

Exit codes: 0 = clean or advisory-only, 1 = at least one error-severity finding.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable, Optional

sys.path.insert(0, str(Path(__file__).parent))

from check_identity import (  # noqa: E402
    DEFAULT_WORKSPACE_ROOT,
    REQUIRED_FIELDS,
    collect_account_claims,
    effective_identity,
    load_org_config,
    remote_owner,
    remotes,
    workspace_type,
    UNGOVERNED_TYPES,
)

ERROR = "error"
WARNING = "warning"
INFO = "info"

# Deliberately permissive: GitHub's own rule is alphanumeric-or-hyphen, no
# leading/trailing hyphen, 39 max. The audit should catch a typo, not relitigate
# GitHub's validation.
GITHUB_ACCOUNT_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class Finding:
    def __init__(self, severity: str, org: Optional[str], message: str,
                 remedy: Optional[str] = None) -> None:
        self.severity = severity
        self.org = org
        self.message = message
        self.remedy = remedy

    def to_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity,
            "org": self.org,
            "message": self.message,
            "remedy": self.remedy,
        }

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Finding {self.severity} {self.org}: {self.message}>"


# --------------------------------------------------------------------------
# discovery
# --------------------------------------------------------------------------

def iter_org_dirs(workspace_root: Path) -> Iterable[Path]:
    """Direct children of the workspace root that could hold an org contract.

    Filesystem-driven rather than reading the configured org list, and that is
    deliberate: a newly created org directory is absent from the config exactly
    when it is most dangerous — before anyone has registered it.
    """
    if not workspace_root.is_dir():
        return []
    try:
        children = sorted(workspace_root.iterdir())
    except OSError:
        return []
    return [c for c in children if c.is_dir() and not c.name.startswith(".")]


def is_git_repo(path: Path) -> bool:
    return (path / ".git").exists()


def iter_repos(org_dir: Path) -> Iterable[Path]:
    """Git repos directly under an org. One level only — repos don't nest."""
    try:
        children = sorted(org_dir.iterdir())
    except OSError:
        return []
    return [c for c in children if c.is_dir() and is_git_repo(c)]


# --------------------------------------------------------------------------
# checks 1, 2, 6 — cheap enough for session start
# --------------------------------------------------------------------------

def cheap_findings(workspace_root: Optional[Path] = None) -> list[Finding]:
    """Filesystem-only checks. No subprocesses, no network.

    Called from the session-start hook, so its cost must stay proportional to
    the number of orgs (a handful of small JSON reads), never to the number of
    repos.
    """
    workspace_root = workspace_root or DEFAULT_WORKSPACE_ROOT
    findings: list[Finding] = []
    claims: dict[str, set[str]] = {}

    for org_dir in iter_org_dirs(workspace_root):
        name = org_dir.name

        if workspace_type(org_dir) in UNGOVERNED_TYPES:
            continue

        config = load_org_config(org_dir)

        if config is None:
            # Check 6: an unregistered org. Only worth reporting if there is
            # something in it that could actually receive a commit — an empty
            # or repo-less directory is not yet a problem.
            if any(iter_repos(org_dir)):
                findings.append(Finding(
                    ERROR, name,
                    f"Org '{name}' has git repos but no identity contract — "
                    f"commits there are blocked.",
                    "/run-organize-orgs",
                ))
            continue

        identity = config.get("identity")

        # Check 1: presence and completeness.
        if not isinstance(identity, dict) or not identity:
            findings.append(Finding(
                ERROR, name,
                f"Org '{name}' has org.json but no `identity` block — "
                f"commits there are blocked.",
                f"Add `identity` to {org_dir / '.claude' / 'org.json'}",
            ))
            continue

        missing = [f for f in REQUIRED_FIELDS if not identity.get(f)]
        if missing:
            findings.append(Finding(
                ERROR, name,
                f"Org '{name}' identity contract is missing: {', '.join(missing)}",
                f"Fix {org_dir / '.claude' / 'org.json'}",
            ))
            continue

        # Check 2: well-formedness.
        account = str(identity["github_account"])
        if not GITHUB_ACCOUNT_RE.match(account):
            findings.append(Finding(
                ERROR, name,
                f"Org '{name}' declares github_account '{account}', which is not "
                f"a valid GitHub username.",
                f"Fix {org_dir / '.claude' / 'org.json'}",
            ))
        email = str(identity["git_email"])
        if not EMAIL_RE.match(email):
            findings.append(Finding(
                ERROR, name,
                f"Org '{name}' declares git_email '{email}', which is not a "
                f"valid address.",
                f"Fix {org_dir / '.claude' / 'org.json'}",
            ))

        if not identity.get("owns_remotes"):
            findings.append(Finding(
                INFO, name,
                f"Org '{name}' claims no remotes, so cross-context leakage into "
                f"it cannot be detected.",
                "Add `owns_remotes` if this org owns a GitHub account.",
            ))

        for owner in identity.get("owns_remotes") or []:
            claims.setdefault(str(owner).lower(), set()).add(account)

        # Check 5: the prose mirror must not contradict the machine copy.
        # Substring presence, not prose parsing — this catches the real failure
        # (edited one file, forgot the other), and nothing more is claimed.
        claude_md = org_dir / "CLAUDE.md"
        if claude_md.is_file():
            try:
                text = claude_md.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                text = ""
            absent = [v for v in (account, email) if v and v not in text]
            if absent:
                findings.append(Finding(
                    WARNING, name,
                    f"Org '{name}' CLAUDE.md does not mention "
                    f"{', '.join(absent)} — prose and org.json may have drifted.",
                    f"Update {claude_md}",
                ))

    # Check 2b: one owner claimed by two different accounts makes the
    # cross-context check ambiguous — it cannot tell which org is correct.
    for owner, accounts in sorted(claims.items()):
        if len(accounts) > 1:
            findings.append(Finding(
                ERROR, None,
                f"Remote owner '{owner}' is claimed by more than one account: "
                f"{', '.join(sorted(accounts))}.",
                "Remove the duplicate from one org's `owns_remotes`.",
            ))

    return findings


# --------------------------------------------------------------------------
# checks 3, 4 — explicit invocation only
# --------------------------------------------------------------------------

def account_exists(account: str, timeout: float = 5.0) -> Optional[bool]:
    """Whether GitHub knows this account. None when it cannot be determined.

    Never blocking: a typo'd github_account degrades to a silent no-match in the
    hook rather than wedging commits, so this is worth reporting and not worth
    gating on. Also returns None when offline or `gh` is absent, so a plane
    ride does not manufacture findings.
    """
    try:
        result = subprocess.run(
            ["gh", "api", f"users/{account}", "--jq", ".login"],
            capture_output=True, text=True, timeout=timeout,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None
    if result.returncode == 0:
        return True
    stderr = (result.stderr or "").lower()
    if "404" in stderr or "not found" in stderr:
        return False
    return None


def drift_findings(workspace_root: Optional[Path] = None) -> list[Finding]:
    """Check 4: repos already sitting on the wrong identity.

    The retroactive half of the story. The hook can only stop the next commit;
    nothing stops a repo configured before the contract existed, or one cloned
    with a stale global default.
    """
    workspace_root = workspace_root or DEFAULT_WORKSPACE_ROOT
    findings: list[Finding] = []
    claims = collect_account_claims(workspace_root)

    for org_dir in iter_org_dirs(workspace_root):
        if workspace_type(org_dir) in UNGOVERNED_TYPES:
            continue
        config = load_org_config(org_dir)
        if not config:
            continue
        identity = config.get("identity")
        if not isinstance(identity, dict):
            continue
        if str(identity.get("enforcement", "block")).lower() == "off":
            continue
        if any(not identity.get(f) for f in REQUIRED_FIELDS):
            continue

        name = config.get("name") or org_dir.name
        account = str(identity["github_account"])

        for repo in iter_repos(org_dir):
            actual_name, actual_email = effective_identity(repo)
            if actual_email != identity["git_email"]:
                findings.append(Finding(
                    ERROR, name,
                    f"{org_dir.name}/{repo.name} commits as "
                    f"{actual_email or '(unset)'}, expected {identity['git_email']}.",
                    f'git -C {repo} config user.email "{identity["git_email"]}"',
                ))
            if actual_name != identity["git_user_name"]:
                findings.append(Finding(
                    ERROR, name,
                    f"{org_dir.name}/{repo.name} commits as name "
                    f"{actual_name or '(unset)'}, expected {identity['git_user_name']}.",
                    f'git -C {repo} config user.name "{identity["git_user_name"]}"',
                ))

            for remote_name, url in sorted(remotes(repo).items()):
                owner = remote_owner(url)
                if not owner:
                    continue
                claiming = claims.get(owner.lower())
                if claiming and account not in claiming:
                    findings.append(Finding(
                        ERROR, name,
                        f"{org_dir.name}/{repo.name} remote '{remote_name}' points "
                        f"at {owner}/, claimed by {', '.join(sorted(claiming))}, "
                        f"but the org is governed by {account}.",
                        "Move the repo, or correct the remote.",
                    ))

    return findings


def liveness_findings(workspace_root: Optional[Path] = None,
                      probe=account_exists) -> list[Finding]:
    """Check 3: does each declared account actually exist on GitHub."""
    workspace_root = workspace_root or DEFAULT_WORKSPACE_ROOT
    findings: list[Finding] = []
    seen: set[str] = set()

    for org_dir in iter_org_dirs(workspace_root):
        if workspace_type(org_dir) in UNGOVERNED_TYPES:
            continue
        config = load_org_config(org_dir)
        identity = (config or {}).get("identity")
        if not isinstance(identity, dict):
            continue
        account = identity.get("github_account")
        if not account or account in seen:
            continue
        seen.add(str(account))
        if probe(str(account)) is False:
            findings.append(Finding(
                WARNING, config.get("name") or org_dir.name,
                f"GitHub does not recognize the declared account '{account}'.",
                "Check for a typo in github_account.",
            ))
    return findings


def full_findings(workspace_root: Optional[Path] = None,
                  check_liveness: bool = True) -> list[Finding]:
    findings = cheap_findings(workspace_root)
    findings.extend(drift_findings(workspace_root))
    if check_liveness:
        findings.extend(liveness_findings(workspace_root))
    return findings


# --------------------------------------------------------------------------
# entry point
# --------------------------------------------------------------------------

def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Audit per-org identity contracts across the workspace."
    )
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--cheap", action="store_true",
                        help="filesystem-only checks (what session start runs)")
    parser.add_argument("--no-liveness", action="store_true",
                        help="skip the GitHub account probe")
    parser.add_argument("--workspace-root", type=Path, default=None)
    args = parser.parse_args(argv)

    if args.cheap:
        findings = cheap_findings(args.workspace_root)
    else:
        findings = full_findings(args.workspace_root,
                                 check_liveness=not args.no_liveness)

    if args.json:
        print(json.dumps([f.to_dict() for f in findings], indent=2))
    else:
        errors = [f for f in findings if f.severity == ERROR]
        warnings = [f for f in findings if f.severity == WARNING]
        infos = [f for f in findings if f.severity == INFO]
        if not findings:
            print("Identity contracts: all orgs clean.")
        for group, label in ((errors, "ERROR"), (warnings, "WARNING"), (infos, "note")):
            for finding in group:
                print(f"{label}: {finding.message}")
                if finding.remedy:
                    print(f"       → {finding.remedy}")

    return 1 if any(f.severity == ERROR for f in findings) else 0


if __name__ == "__main__":
    sys.exit(main())
