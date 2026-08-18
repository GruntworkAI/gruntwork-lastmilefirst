#!/usr/bin/env python3
"""
Per-org git identity enforcement.

Every workspace org may declare an identity contract in `<org>/.claude/org.json`
under `identity`. This script resolves the contract governing the current repo
and verifies that the commit about to be made carries the right identity.

Two ideas do the work:

1. **The directory is the governance signal, not the remote.** You declared the
   context when you chose where the repo lives. Remotes owned by other people are
   normal — forks have an `upstream`, OSS contributions push to someone else's
   org, clients own their repos. So the blocking check is commit identity;
   remote ownership is only a cross-context guard.

2. **`owns_remotes` is a claim registry, not an allowlist.** An owner nobody
   claims is fine. An owner claimed by a *different GitHub account* than the one
   governing this directory is a real mistake — that is the only remote-side
   condition that blocks. Note the comparison is by account, not by org
   directory: two workspace orgs legitimately share one GitHub account.

Run modes:
    check_identity.py                 human-readable resolution for the cwd repo
    check_identity.py --pre-commit    hook mode; terse, exit 1 blocks the commit
    check_identity.py --json          machine-readable, for organize-orgs

Exit codes: 0 = allowed, 1 = blocked.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# Workspace root. Overridable for tests and for the pending ~/work/ migration
# (see the LMF-stack architecture plan).
DEFAULT_WORKSPACE_ROOT = Path.home() / "Code"

OVERRIDE_ENV = "LMF_IDENTITY_OVERRIDE"
OVERRIDE_LOG = Path.home() / ".claude" / "lastmilefirst" / "identity-overrides.log"

ENFORCEMENT_BLOCK = "block"
ENFORCEMENT_WARN = "warn"
ENFORCEMENT_OFF = "off"

REQUIRED_FIELDS = ("github_account", "git_user_name", "git_email")

# Workspace directory types (see the workspace-types spec). Only two matter
# here: directories holding work that isn't first-party carry no identity
# obligation, because there is no "our account" for them to be wrong about.
WORKSPACE_MARKER = ".claude-workspace"
UNGOVERNED_TYPES = {"external", "scratch"}


# --------------------------------------------------------------------------
# git helpers
# --------------------------------------------------------------------------

def _git(*args: str, cwd: Optional[Path] = None) -> Optional[str]:
    """Run a git command, returning stripped stdout or None on any failure."""
    try:
        result = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=str(cwd) if cwd else None,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None
    if result.returncode != 0:
        return None
    out = result.stdout.strip()
    return out or None


def repo_root(cwd: Optional[Path] = None) -> Optional[Path]:
    """Top level of the containing work tree, or None if not in a repo."""
    top = _git("rev-parse", "--show-toplevel", cwd=cwd)
    return Path(top).resolve() if top else None


def effective_identity(cwd: Optional[Path] = None) -> tuple[Optional[str], Optional[str]]:
    """The user.name / user.email git would actually stamp on a commit here."""
    return _git("config", "--get", "user.name", cwd=cwd), _git(
        "config", "--get", "user.email", cwd=cwd
    )


def remotes(cwd: Optional[Path] = None) -> dict[str, str]:
    """Map of remote name -> fetch URL. Empty when the repo has no remotes."""
    raw = _git("remote", "-v", cwd=cwd)
    if not raw:
        return {}
    found: dict[str, str] = {}
    for line in raw.splitlines():
        parts = line.split()
        if len(parts) >= 2:
            found.setdefault(parts[0], parts[1])
    return found


# Matches the owner segment of the URL forms git actually produces:
#   git@github.com:owner/repo.git         (scp-like, incl. host aliases)
#   ssh://git@github.com/owner/repo.git
#   https://github.com/owner/repo.git
_SCP_LIKE = re.compile(r"^[^/]+@[^:/]+:(?P<path>.+)$")
_URL_LIKE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*://[^/]+/(?P<path>.+)$")


def remote_owner(url: str) -> Optional[str]:
    """Owner (user or org) a remote URL points at, independent of host alias.

    Host aliases are deliberately ignored: `github-personal` and `github.com`
    both resolve to GitHub, and the alias says which *key* to use, not which
    account owns the repo.
    """
    url = url.strip()
    match = _SCP_LIKE.match(url) or _URL_LIKE.match(url)
    if not match:
        return None
    path = match.group("path").lstrip("/")
    segments = [s for s in path.split("/") if s]
    return segments[0] if segments else None


# --------------------------------------------------------------------------
# contract resolution
# --------------------------------------------------------------------------

def load_org_config(org_dir: Path) -> Optional[dict[str, Any]]:
    """Parse `<org_dir>/.claude/org.json`, or None if absent/unreadable.

    A malformed org.json is treated as absent rather than fatal: a broken config
    should not wedge every commit in the org.
    """
    config_path = org_dir / ".claude" / "org.json"
    if not config_path.is_file():
        return None
    try:
        return json.loads(config_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return None


def workspace_type(directory: Path) -> Optional[str]:
    """Declared type from a `.claude-workspace` marker, lowercased.

    Deliberately not a YAML parse: this runs in a pre-commit hook, which must
    not depend on PyYAML being installed. Only the top-level `type:` key is
    needed, and a malformed marker returns None so the caller falls back to the
    default (governed) behavior rather than silently exempting a directory.
    """
    marker = directory / WORKSPACE_MARKER
    if not marker.is_file():
        return None
    try:
        text = marker.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    for line in text.splitlines():
        if line.startswith(("#", " ", "\t")) or ":" not in line:
            continue
        key, _, value = line.partition(":")
        if key.strip() == "type":
            return value.split("#")[0].strip().lower() or None
    return None


def ungoverned_ancestor(start: Path, workspace_root: Path) -> Optional[Path]:
    """Nearest ancestor marked as a type carrying no identity obligation."""
    try:
        start = start.resolve()
        workspace_root = workspace_root.resolve()
    except OSError:
        return None
    for candidate in [start, *start.parents]:
        if workspace_type(candidate) in UNGOVERNED_TYPES:
            return candidate
        if candidate == workspace_root:
            break
    return None


def find_governing_org(
    start: Path, workspace_root: Path
) -> tuple[Optional[Path], Optional[dict[str, Any]]]:
    """Nearest ancestor (inclusive) holding an org.json, walking up to the root.

    Nearest wins, so a project may override its org. Returns the org directory
    and its parsed config; the config may lack an `identity` block, which is a
    different state from having no org.json at all.
    """
    try:
        start = start.resolve()
        workspace_root = workspace_root.resolve()
    except OSError:
        return None, None

    for candidate in [start, *start.parents]:
        config = load_org_config(candidate)
        if config is not None:
            return candidate, config
        if candidate == workspace_root:
            break
    return None, None


def collect_account_claims(workspace_root: Path) -> dict[str, set[str]]:
    """Map remote owner -> set of GitHub accounts claiming it, across all orgs.

    Keyed by account rather than org directory on purpose: `gruntwork/` and
    `lastmilefirst.ai/` are separate workspace orgs that both push to the
    `GruntworkAI` account, and that is not a conflict.
    """
    claims: dict[str, set[str]] = {}
    if not workspace_root.is_dir():
        return claims
    try:
        children = sorted(workspace_root.iterdir())
    except OSError:
        return claims

    for child in children:
        if not child.is_dir():
            continue
        config = load_org_config(child)
        if not config:
            continue
        identity = config.get("identity")
        if not isinstance(identity, dict):
            continue
        account = identity.get("github_account")
        if not account:
            continue
        for owner in identity.get("owns_remotes") or []:
            claims.setdefault(str(owner).lower(), set()).add(str(account))
    return claims


def is_under(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except (ValueError, OSError):
        return False


# --------------------------------------------------------------------------
# the check itself
# --------------------------------------------------------------------------

class Result:
    """Outcome of one evaluation: a status, plus problems and advisories."""

    def __init__(self, status: str) -> None:
        self.status = status          # ok | blocked | warned | skipped
        self.problems: list[str] = []  # blocking
        self.warnings: list[str] = []  # advisory only
        self.remedies: list[str] = []
        self.org: Optional[str] = None
        self.enforcement: Optional[str] = None

    @property
    def exit_code(self) -> int:
        return 1 if self.status == "blocked" else 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "org": self.org,
            "enforcement": self.enforcement,
            "problems": self.problems,
            "warnings": self.warnings,
            "remedies": self.remedies,
        }


def gh_active_account() -> Optional[str]:
    """Active `gh` account, read from local config only. Never hits the network."""
    hosts = Path.home() / ".config" / "gh" / "hosts.yml"
    if not hosts.is_file():
        return None
    try:
        text = hosts.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    # Deliberately not a YAML parse: the hook must not require PyYAML, and the
    # only field needed is the top-level `user:` key that gh maintains.
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("user:") and not line.startswith(" " * 8):
            value = stripped.split(":", 1)[1].strip()
            if value:
                return value
    return None


def evaluate(
    cwd: Optional[Path] = None,
    workspace_root: Optional[Path] = None,
    check_gh: bool = True,
) -> Result:
    workspace_root = workspace_root or DEFAULT_WORKSPACE_ROOT

    root = repo_root(cwd)
    if root is None:
        return Result("skipped")

    # The workspace root is the governance boundary. Repos outside it are none
    # of our business — cloned tools, other checkouts, anything transient.
    if not is_under(root, workspace_root):
        return Result("skipped")

    # External / scratch directories hold work that isn't ours to attribute:
    # third-party clones and throwaway artifacts. Checked before contract
    # resolution so a marked directory never reports as "unregistered".
    if ungoverned_ancestor(root, workspace_root):
        return Result("skipped")

    org_dir, config = find_governing_org(root, workspace_root)

    # Governed but unregistered: a repo sits inside the workspace with no
    # org.json anywhere above it. This is the case that matters — creating a new
    # org directory and committing before registering it is exactly how work
    # lands under the wrong identity.
    if config is None:
        result = Result("blocked")
        result.problems.append(
            f"No org identity contract governs {root}."
        )
        result.remedies.append(
            "Register the org:  /run-organize-orgs"
        )
        result.remedies.append(
            f"Or exempt it once:  {OVERRIDE_ENV}=1 git commit ..."
        )
        return result

    identity = config.get("identity")
    org_name = config.get("name") or (org_dir.name if org_dir else None)

    if not isinstance(identity, dict) or not identity:
        result = Result("blocked")
        result.org = org_name
        result.problems.append(
            f"Org '{org_name}' has an org.json but no `identity` block."
        )
        result.remedies.append(
            f"Add one to {org_dir / '.claude' / 'org.json'} (github_account, "
            "git_user_name, git_email, owns_remotes)."
        )
        result.remedies.append(f"Or exempt it once:  {OVERRIDE_ENV}=1 git commit ...")
        return result

    enforcement = str(identity.get("enforcement", ENFORCEMENT_BLOCK)).lower()
    if enforcement == ENFORCEMENT_OFF:
        result = Result("skipped")
        result.org = org_name
        result.enforcement = enforcement
        return result

    missing = [f for f in REQUIRED_FIELDS if not identity.get(f)]
    if missing:
        result = Result("blocked")
        result.org = org_name
        result.enforcement = enforcement
        result.problems.append(
            f"Org '{org_name}' identity contract is incomplete: missing "
            + ", ".join(missing)
        )
        result.remedies.append(f"Fix {org_dir / '.claude' / 'org.json'}")
        return result

    result = Result("ok")
    result.org = org_name
    result.enforcement = enforcement

    # --- commit identity: the check that actually matters -----------------
    actual_name, actual_email = effective_identity(cwd)
    expected_name = identity["git_user_name"]
    expected_email = identity["git_email"]

    if actual_email != expected_email:
        result.problems.append(
            f"Commit email is {actual_email or '(unset)'}, but org '{org_name}' "
            f"requires {expected_email}."
        )
        result.remedies.append(f'git config user.email "{expected_email}"')

    if actual_name != expected_name:
        result.problems.append(
            f"Commit name is {actual_name or '(unset)'}, but org '{org_name}' "
            f"requires {expected_name}."
        )
        result.remedies.append(f'git config user.name "{expected_name}"')

    # --- cross-context guard ---------------------------------------------
    # Only an owner claimed by a *different account* blocks. Unclaimed owners
    # are normal collaboration and must stay silent, or the check earns a
    # reputation for false positives and gets overridden reflexively.
    account = str(identity["github_account"])
    claims = collect_account_claims(workspace_root)
    for name, url in sorted(remotes(cwd).items()):
        owner = remote_owner(url)
        if not owner:
            continue
        claiming = claims.get(owner.lower())
        if claiming and account not in claiming:
            other = ", ".join(sorted(claiming))
            result.problems.append(
                f"Remote '{name}' points at {owner}/, which is claimed by "
                f"{other} — but this directory is governed by {account}."
            )
            result.remedies.append(
                f"Move the repo under the {other} org, or fix the remote for '{name}'."
            )

    # --- advisory: gh's active account ------------------------------------
    # Cannot block: gh's active account has no bearing on the commit being made,
    # only on later `gh` commands.
    if check_gh:
        active = gh_active_account()
        if active and active != account:
            result.warnings.append(
                f"gh's active account is {active}, not {account}. "
                f"Commits are unaffected; `gh` commands will target {active}."
            )
            result.remedies.append(f"gh auth switch --user {account}")

    if result.problems:
        result.status = ENFORCEMENT_BLOCK if enforcement == ENFORCEMENT_BLOCK else "warned"
    elif result.warnings:
        result.status = "warned"

    if result.status == ENFORCEMENT_BLOCK:
        result.status = "blocked"
    return result


def log_override(root: Optional[Path]) -> None:
    """Record a bypass. An override that leaves no trace is not an override."""
    try:
        OVERRIDE_LOG.parent.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with OVERRIDE_LOG.open("a", encoding="utf-8") as handle:
            handle.write(f"{stamp}\t{root or os.getcwd()}\n")
    except OSError:
        pass  # never let logging failure block a commit


# --------------------------------------------------------------------------
# entry point
# --------------------------------------------------------------------------

def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify the git identity matches the governing org contract."
    )
    parser.add_argument(
        "--pre-commit", action="store_true", help="hook mode: terse output"
    )
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument(
        "--workspace-root", type=Path, default=None, help="override the workspace root"
    )
    args = parser.parse_args(argv)

    if os.environ.get(OVERRIDE_ENV):
        root = repo_root()
        log_override(root)
        if not args.json:
            print(
                f"lastmilefirst: identity check overridden via {OVERRIDE_ENV} "
                f"(logged to {OVERRIDE_LOG})",
                file=sys.stderr,
            )
        return 0

    # The gh advisory is deliberately absent in hook mode. It is accurate but
    # unactionable at commit time — gh's active account cannot affect the commit
    # being made — and it would otherwise print on *every* commit in an org
    # whose account isn't the currently active one. A per-commit nag about
    # unrelated state is how a check trains people to stop reading it.
    # audit_identity.py still reports it, where it is read deliberately.
    result = evaluate(
        workspace_root=args.workspace_root,
        check_gh=not args.pre_commit,
    )

    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
        return result.exit_code

    if result.status == "skipped":
        if not args.pre_commit:
            print("Identity check does not apply here.")
        return 0

    if result.status == "ok":
        if not args.pre_commit:
            print(f"Identity OK — org '{result.org}' ({result.enforcement}).")
        return 0

    stream = sys.stderr if result.status == "blocked" else sys.stdout
    label = "BLOCKED" if result.status == "blocked" else "warning"
    print("", file=stream)
    print(f"lastmilefirst identity check — {label}", file=stream)
    for problem in result.problems:
        print(f"  ✗ {problem}", file=stream)
    for warning in result.warnings:
        print(f"  ! {warning}", file=stream)
    if result.remedies:
        print("", file=stream)
        print("  Fix:", file=stream)
        for remedy in dict.fromkeys(result.remedies):
            print(f"    {remedy}", file=stream)
    print("", file=stream)

    return result.exit_code


if __name__ == "__main__":
    sys.exit(main())
