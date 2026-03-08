#!/usr/bin/env python3
"""
Repository auditing for secret hygiene.

Checks:
- .gitignore gap analysis against required patterns
- Dangerous committed files detection
- Repo visibility via gh CLI
- Full GitHub account audit (public repo inventory)
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Required .gitignore patterns for secret hygiene
REQUIRED_GITIGNORE_PATTERNS = [
    ".env",
    ".env.*",
    "*.pem",
    "*.key",
    "*.p12",
    "*.pfx",
    "*.tfstate",
    "*.tfstate.*",
    "terraform.tfvars",
    "terraform.tfvars.*",
    "*.credentials",
    "credentials.json",
    "service-account*.json",
]

# File patterns that should never be committed
DANGEROUS_FILE_PATTERNS = [
    ".env",
    "*.pem",
    "*.key",
    "*.p12",
    "*.pfx",
    "terraform.tfstate",
    "credentials.json",
    "service-account*.json",
    "*.keystore",
]

# Repo name patterns that suggest private content
SUSPICIOUS_PUBLIC_NAMES = [
    "internal",
    "private",
    "secret",
    "config",
    "credentials",
    "keys",
    "tokens",
    "env",
    "infra",
    "infrastructure",
]


def check_gitignore(repo_path: Optional[Path] = None) -> Tuple[List[str], List[str]]:
    """
    Check .gitignore for required secret-related patterns.
    Returns (missing_patterns, present_patterns).
    """
    path = (repo_path or Path.cwd()) / ".gitignore"
    if not path.exists():
        return REQUIRED_GITIGNORE_PATTERNS.copy(), []

    content = path.read_text(encoding="utf-8")
    lines = {line.strip() for line in content.splitlines() if line.strip() and not line.startswith("#")}

    missing = []
    present = []
    for pattern in REQUIRED_GITIGNORE_PATTERNS:
        if pattern in lines:
            present.append(pattern)
        else:
            missing.append(pattern)

    return missing, present


def check_dangerous_committed_files(repo_path: Optional[Path] = None) -> List[str]:
    """
    Check git history for files that should not have been committed.
    Returns list of dangerous file paths found in history.
    """
    cwd = str(repo_path) if repo_path else None
    dangerous = []

    for pattern in DANGEROUS_FILE_PATTERNS:
        try:
            result = subprocess.run(
                ["git", "log", "--all", "--name-only", "--pretty=format:", "--", pattern],
                capture_output=True,
                text=True,
                timeout=15,
                cwd=cwd,
            )
            if result.returncode == 0:
                files = {f.strip() for f in result.stdout.strip().split("\n") if f.strip()}
                dangerous.extend(sorted(files))
        except (subprocess.TimeoutExpired, FileNotFoundError):
            continue

    return list(set(dangerous))


def audit_repo(repo_path: Optional[Path] = None) -> str:
    """Run full audit on a single repo. Returns formatted report."""
    cwd = repo_path or Path.cwd()
    lines = [f"Audit: {cwd.name}", "=" * 50]

    # 1. Visibility
    try:
        result = subprocess.run(
            ["gh", "repo", "view", "--json", "visibility,nameWithOwner"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=str(cwd),
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            vis = data.get("visibility", "unknown").upper()
            name = data.get("nameWithOwner", "unknown")
            lines.append(f"\nVisibility: {vis}  ({name})")
            if vis == "PUBLIC":
                lines.append("  WARNING: This repo is publicly accessible!")
        else:
            lines.append("\nVisibility: Could not determine (no remote or gh not available)")
    except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError):
        lines.append("\nVisibility: Could not determine")

    # 2. .gitignore gaps
    missing, present = check_gitignore(cwd)
    lines.append(f"\n.gitignore coverage: {len(present)}/{len(REQUIRED_GITIGNORE_PATTERNS)} required patterns")
    if missing:
        lines.append("  Missing patterns (add these to .gitignore):")
        for p in missing:
            lines.append(f"    - {p}")
    else:
        lines.append("  All required patterns present.")

    # 3. Dangerous committed files
    dangerous = check_dangerous_committed_files(cwd)
    if dangerous:
        lines.append(f"\nDangerous files found in git history ({len(dangerous)}):")
        for f in dangerous[:20]:  # Cap display
            lines.append(f"  - {f}")
        if len(dangerous) > 20:
            lines.append(f"  ... and {len(dangerous) - 20} more")
        lines.append(
            "\n  To remove from history: git filter-branch or BFG Repo-Cleaner"
        )
    else:
        lines.append("\nNo dangerous files found in git history.")

    return "\n".join(lines)


def audit_github_account() -> str:
    """
    Audit all public repos across user's GitHub account and orgs.
    Uses gh CLI to enumerate repos.
    """
    lines = ["GitHub Account Public Repo Audit", "=" * 50]

    # Get all public repos
    try:
        result = subprocess.run(
            [
                "gh", "repo", "list",
                "--visibility", "public",
                "--limit", "200",
                "--json", "nameWithOwner,pushedAt,description,isArchived",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return f"Error: Could not list repos. Is gh CLI authenticated?\n{result.stderr}"

        repos = json.loads(result.stdout)
    except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError) as e:
        return f"Error: {e}"

    if not repos:
        lines.append("\nNo public repositories found.")
        return "\n".join(lines)

    lines.append(f"\nFound {len(repos)} public repo(s):\n")
    lines.append(f"{'Repository':<45} {'Last Push':<12} {'Flags'}")
    lines.append("-" * 80)

    flagged = []
    for repo in sorted(repos, key=lambda r: r.get("pushedAt", ""), reverse=True):
        name = repo.get("nameWithOwner", "unknown")
        pushed = repo.get("pushedAt", "")[:10]
        archived = repo.get("isArchived", False)

        # Check for suspicious names
        repo_lower = name.lower().split("/")[-1]
        flags = []
        if archived:
            flags.append("archived")
        for pattern in SUSPICIOUS_PUBLIC_NAMES:
            if pattern in repo_lower:
                flags.append(f"name contains '{pattern}'")
                flagged.append(name)
                break

        flag_str = ", ".join(flags) if flags else ""
        lines.append(f"  {name:<43} {pushed:<12} {flag_str}")

    if flagged:
        lines.append(f"\nFlagged repos ({len(flagged)}) - review visibility:")
        for name in flagged:
            lines.append(f"  - {name}")
        lines.append("\n  Change visibility: gh repo edit <repo> --visibility private")

    # Also check org repos
    try:
        result = subprocess.run(
            ["gh", "api", "user/orgs", "--jq", ".[].login"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode == 0 and result.stdout.strip():
            orgs = result.stdout.strip().split("\n")
            for org in orgs:
                org = org.strip()
                if not org:
                    continue
                try:
                    org_result = subprocess.run(
                        [
                            "gh", "repo", "list", org,
                            "--visibility", "public",
                            "--limit", "200",
                            "--json", "nameWithOwner,pushedAt",
                        ],
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )
                    if org_result.returncode == 0:
                        org_repos = json.loads(org_result.stdout)
                        if org_repos:
                            lines.append(f"\nOrg '{org}': {len(org_repos)} public repo(s)")
                            for repo in org_repos:
                                name = repo.get("nameWithOwner", "")
                                pushed = repo.get("pushedAt", "")[:10]
                                lines.append(f"  {name:<43} {pushed}")
                except (subprocess.TimeoutExpired, json.JSONDecodeError):
                    continue
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    return "\n".join(lines)
