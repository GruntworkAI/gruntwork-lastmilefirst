#!/usr/bin/env python3
"""
Core secret scanning orchestration.

Runs gitleaks with merged config (default rules + custom formats).
Always uses --redact to avoid leaking secrets in output.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Add script directory to path for local imports
sys.path.insert(0, str(Path(__file__).parent))

from format_loader import write_merged_config

# Severity bump map for public repos
SEVERITY_BUMP = {
    "LOW": "MEDIUM",
    "MEDIUM": "HIGH",
    "HIGH": "CRITICAL",
    "CRITICAL": "CRITICAL",
}


def _check_gitleaks() -> Optional[str]:
    """Check if gitleaks is installed. Returns error message or None."""
    try:
        result = subprocess.run(
            ["gitleaks", "version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return None
    except FileNotFoundError:
        pass
    except subprocess.TimeoutExpired:
        pass
    return (
        "gitleaks is not installed.\n"
        "Install: brew install gitleaks  (macOS)\n"
        "         or see https://github.com/gitleaks/gitleaks#installing"
    )


def check_repo_visibility(repo_path: Optional[Path] = None) -> Optional[str]:
    """
    Check if current repo is public via gh CLI.
    Returns 'public', 'private', 'internal', or None if not determinable.
    """
    try:
        cmd = ["gh", "repo", "view", "--json", "visibility", "-q", ".visibility"]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10,
            cwd=str(repo_path) if repo_path else None,
        )
        if result.returncode == 0:
            return result.stdout.strip().upper()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


def _public_repo_banner(visibility: Optional[str]) -> List[str]:
    """Generate warning banner if repo is public."""
    if visibility != "PUBLIC":
        return []
    return [
        "",
        "!" * 70,
        "!  WARNING: This is a PUBLIC repository.",
        "!  Any committed secrets are exposed to the internet.",
        "!  Consider making this repo private if it contains sensitive code.",
        "!" * 70,
        "",
    ]


def _bump_severity(severity: str, is_public: bool) -> str:
    """Bump severity level for public repos."""
    if not is_public:
        return severity
    return SEVERITY_BUMP.get(severity.upper(), severity.upper())


def _run_gitleaks(
    args: List[str],
    config_path: Optional[Path] = None,
    cwd: Optional[str] = None,
) -> Tuple[int, str, str]:
    """
    Run gitleaks with given arguments.
    Returns (returncode, stdout, stderr).
    Exit codes: 0 = no leaks, 1 = leaks found, >1 = error.
    """
    cmd = ["gitleaks"]
    if config_path:
        cmd.extend(["--config", str(config_path)])
    cmd.extend(args)
    cmd.append("--redact")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minutes max
            cwd=cwd,
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return 2, "", "Scan timed out after 5 minutes"
    except FileNotFoundError:
        return 2, "", "gitleaks not found"


def _parse_findings(json_output: str, is_public: bool) -> List[Dict[str, Any]]:
    """Parse gitleaks JSON output and apply severity bumps."""
    if not json_output.strip():
        return []
    try:
        findings = json.loads(json_output)
    except json.JSONDecodeError:
        return []

    if not isinstance(findings, list):
        return []

    for finding in findings:
        original = finding.get("Severity", "MEDIUM")
        finding["Severity"] = _bump_severity(original, is_public)
        if is_public and original != finding["Severity"]:
            finding["_bumped"] = True

    return findings


def _format_findings(findings: List[Dict[str, Any]]) -> str:
    """Format findings for display."""
    if not findings:
        return "No secrets detected."

    lines = [f"\nFound {len(findings)} potential secret(s):\n"]
    lines.append(f"{'Severity':<10} {'Rule':<35} {'File':<40} Line")
    lines.append("-" * 90)

    for f in sorted(findings, key=lambda x: x.get("Severity", ""), reverse=True):
        severity = f.get("Severity", "?")
        rule = f.get("RuleID", f.get("Description", "unknown"))[:34]
        filepath = f.get("File", "?")
        # Truncate long paths
        if len(filepath) > 39:
            filepath = "..." + filepath[-36:]
        line = f.get("StartLine", "?")
        bumped = " *" if f.get("_bumped") else ""
        lines.append(f"{severity:<10}{bumped} {rule:<35} {filepath:<40} {line}")

    bumped_count = sum(1 for f in findings if f.get("_bumped"))
    if bumped_count:
        lines.append(f"\n* {bumped_count} finding(s) severity bumped due to PUBLIC repo")

    return "\n".join(lines)


def scan_repo(
    repo_path: Optional[Path] = None,
    report_format: str = "text",
) -> Tuple[int, str]:
    """
    Scan a single repo's full git history.
    Returns (exit_code, report_text).
    """
    # Pre-flight
    err = _check_gitleaks()
    if err:
        return 1, err

    cwd = str(repo_path) if repo_path else None

    # Check visibility
    visibility = check_repo_visibility(repo_path)
    is_public = visibility == "PUBLIC"

    config_path = write_merged_config()
    try:
        # Use JSON report to temp file
        import tempfile
        report_file = tempfile.mktemp(suffix=".json", prefix="gitleaks-report-")

        code, stdout, stderr = _run_gitleaks(
            ["detect", "--report-format", "json", "--report-path", report_file],
            config_path=config_path,
            cwd=cwd,
        )

        # Read findings
        findings = []
        report_path = Path(report_file)
        if report_path.exists():
            findings = _parse_findings(
                report_path.read_text(encoding="utf-8"), is_public
            )
            report_path.unlink(missing_ok=True)

        # Build report
        lines = _public_repo_banner(visibility)
        lines.append(_format_findings(findings))

        if stderr and code > 1:
            lines.append(f"\nErrors:\n{stderr}")

        return (1 if findings else 0), "\n".join(lines)
    finally:
        config_path.unlink(missing_ok=True)


def scan_staged(repo_path: Optional[Path] = None) -> Tuple[int, str]:
    """
    Pre-commit mode: scan only staged changes.
    Returns (exit_code, report_text).
    """
    err = _check_gitleaks()
    if err:
        return 1, err

    cwd = str(repo_path) if repo_path else None
    visibility = check_repo_visibility(repo_path)
    is_public = visibility == "PUBLIC"

    config_path = write_merged_config()
    try:
        import tempfile
        report_file = tempfile.mktemp(suffix=".json", prefix="gitleaks-staged-")

        code, stdout, stderr = _run_gitleaks(
            [
                "protect",
                "--staged",
                "--report-format", "json",
                "--report-path", report_file,
            ],
            config_path=config_path,
            cwd=cwd,
        )

        findings = []
        report_path = Path(report_file)
        if report_path.exists():
            findings = _parse_findings(
                report_path.read_text(encoding="utf-8"), is_public
            )
            report_path.unlink(missing_ok=True)

        lines = []
        if is_public:
            lines.append("Reminder: you are committing to a PUBLIC repository")

        if findings:
            lines.append(_format_findings(findings))
            return 1, "\n".join(lines)

        lines.append("No secrets detected in staged changes.")
        return 0, "\n".join(lines)
    finally:
        config_path.unlink(missing_ok=True)


def scan_workspace(workspace_path: Optional[Path] = None) -> Tuple[int, str]:
    """
    Walk workspace finding git repos and scan each.
    Returns (exit_code, combined_report).
    """
    err = _check_gitleaks()
    if err:
        return 1, err

    ws = workspace_path or Path.home() / "Code"
    if not ws.exists():
        return 1, f"Workspace not found: {ws}"

    # Find git repos (max 2 levels deep)
    repos: List[Path] = []
    for depth1 in sorted(ws.iterdir()):
        if not depth1.is_dir() or depth1.name.startswith("."):
            continue
        for depth2 in sorted(depth1.iterdir()):
            if not depth2.is_dir() or depth2.name.startswith("."):
                continue
            if (depth2 / ".git").exists():
                repos.append(depth2)

    if not repos:
        return 0, f"No git repos found in {ws}"

    lines = [f"Scanning {len(repos)} repos in {ws}...\n"]
    total_findings = 0

    for repo in repos:
        exit_code, report = scan_repo(repo)
        repo_name = f"{repo.parent.name}/{repo.name}"
        if exit_code == 0:
            lines.append(f"  {repo_name}: clean")
        else:
            lines.append(f"  {repo_name}: FINDINGS DETECTED")
            lines.append(report)
            total_findings += 1

    lines.append(f"\nScanned {len(repos)} repos. {total_findings} with findings.")
    return (1 if total_findings else 0), "\n".join(lines)


def update_scan_timestamp() -> None:
    """Update the overwatch state with current scan timestamp."""
    try:
        # Import overwatch utilities
        hooks_scripts = (
            Path(__file__).parent.parent.parent.parent / "hooks" / "scripts"
        )
        sys.path.insert(0, str(hooks_scripts))
        from overwatch import update_state_field

        update_state_field("last_secret_scan", int(time.time()))
    except (ImportError, Exception):
        pass  # Non-critical — don't fail scan over state update
