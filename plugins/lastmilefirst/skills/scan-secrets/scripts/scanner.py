#!/usr/bin/env python3
"""
Core secret scanning orchestration.

Runs gitleaks with merged config (default rules + custom formats).
Always uses --redact to avoid leaking secrets in output.
"""
from __future__ import annotations

import json
import os
import re
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


# The 'git' subcommand (which replaced the deprecated 'detect'/'protect') was
# introduced in gitleaks v8.19.0. An older binary fails with a confusing
# "unknown command" error, so we detect it up front and surface an actionable one.
MIN_GITLEAKS_VERSION = (8, 19, 0)

_GITLEAKS_MISSING_MSG = (
    "gitleaks is not installed.\n"
    "Install: brew install gitleaks  (macOS)\n"
    "         or see https://github.com/gitleaks/gitleaks#installing"
)


def _parse_gitleaks_version(output: str) -> Optional[Tuple[int, int, int]]:
    """Extract a (major, minor, patch) tuple from `gitleaks version` output."""
    match = re.search(r"(\d+)\.(\d+)(?:\.(\d+))?", output)
    if not match:
        return None
    return (int(match.group(1)), int(match.group(2)), int(match.group(3) or 0))


def _check_gitleaks() -> Optional[str]:
    """
    Check gitleaks is installed and new enough. Returns an error message or None.

    Fail-closed by design: callers treat a returned message as a hard stop
    (blocked commit / errored scan), the same as missing gitleaks. "Too old to
    run the 'git' subcommand" is the same category as "not installed" — the
    scanner cannot run — so it blocks rather than warns.
    """
    try:
        result = subprocess.run(
            ["gitleaks", "version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return _GITLEAKS_MISSING_MSG

    if result.returncode != 0:
        return _GITLEAKS_MISSING_MSG

    version = _parse_gitleaks_version(f"{result.stdout} {result.stderr}")
    if version is None:
        # Ran cleanly but the version string didn't parse — most likely a future
        # format change on a newer (thus new-enough) binary. Don't brick the scan
        # on a parse miss; the report-file fail-closed check still catches a
        # genuinely broken binary.
        return None
    if version < MIN_GITLEAKS_VERSION:
        need = ".".join(str(n) for n in MIN_GITLEAKS_VERSION)
        have = ".".join(str(n) for n in version)
        return (
            f"gitleaks {have} is too old. This scanner uses the 'git' subcommand, "
            f"which requires gitleaks {need} or later.\n"
            f"Upgrade: brew upgrade gitleaks  (macOS)\n"
            f"         or see https://github.com/gitleaks/gitleaks#installing"
        )
    return None


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


# --- Archive scanning -------------------------------------------------------
#
# gitleaks reads every file as text. A committed archive is therefore invisible
# to it: the bytes are compressed, so no regex matches and the scan reports
# clean. This is not hypothetical — a Terraform plan file (`tfplan`) is a zip
# with a complete tfstate inside it, and two repos in this workspace carried one
# holding live credentials that every scan passed over.
#
# The fix is to expand recognised archives to a temp directory and scan that,
# attributing any finding back to the archive that contained it.

_ARCHIVE_MAGIC = {
    b"PK\x03\x04": "zip",
    b"PK\x05\x06": "zip",       # empty archive
    b"\x1f\x8b": "gzip",
    b"BZh": "bzip2",
    b"\xfd7zXZ": "xz",
}

# Guardrails: an archive bigger than this, or with more members than this, is
# reported as unscannable rather than expanded. Better a visible "we did not
# look inside this" than an unbounded extraction.
_MAX_ARCHIVE_BYTES = 100 * 1024 * 1024
_MAX_ARCHIVE_MEMBERS = 2000


def _sniff_archive(path: Path) -> Optional[str]:
    """Return an archive kind from magic bytes, or None."""
    try:
        with path.open("rb") as fh:
            head = fh.read(8)
    except OSError:
        return None
    for magic, kind in _ARCHIVE_MAGIC.items():
        if head.startswith(magic):
            return kind
    return None


def _candidate_files(cwd: Optional[str], staged_only: bool) -> List[str]:
    """Git-tracked (or staged) file paths, relative to the repo root."""
    args = (
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"]
        if staged_only
        else ["git", "ls-files"]
    )
    try:
        out = subprocess.run(
            args, capture_output=True, text=True, timeout=60, cwd=cwd
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []
    if out.returncode != 0:
        return []
    return [p for p in out.stdout.splitlines() if p.strip()]


def _extract_archive(path: Path, dest: Path) -> Tuple[bool, Optional[str]]:
    """
    Expand an archive into dest. Returns (extracted, reason_if_not).
    Member paths are flattened defensively — nothing is written outside dest.
    """
    import tarfile
    import zipfile

    try:
        if zipfile.is_zipfile(path):
            with zipfile.ZipFile(path) as zf:
                names = zf.namelist()
                if len(names) > _MAX_ARCHIVE_MEMBERS:
                    return False, f"{len(names)} members exceeds cap"
                for name in names:
                    if name.endswith("/"):
                        continue
                    safe = dest / name.replace("..", "_").lstrip("/")
                    safe.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(name) as src, safe.open("wb") as dst:
                        dst.write(src.read())
            return True, None

        if tarfile.is_tarfile(path):
            with tarfile.open(path) as tf:
                members = tf.getmembers()
                if len(members) > _MAX_ARCHIVE_MEMBERS:
                    return False, f"{len(members)} members exceeds cap"
                for m in members:
                    if not m.isfile():
                        continue
                    src = tf.extractfile(m)
                    if src is None:
                        continue
                    safe = dest / m.name.replace("..", "_").lstrip("/")
                    safe.parent.mkdir(parents=True, exist_ok=True)
                    with safe.open("wb") as dst:
                        dst.write(src.read())
            return True, None

        # gzip/bzip2/xz single-stream: decompress to one file
        import bz2
        import gzip
        import lzma

        openers = {"gzip": gzip.open, "bzip2": bz2.open, "xz": lzma.open}
        kind = _sniff_archive(path)
        if kind in openers:
            with openers[kind](path, "rb") as src:
                (dest / f"{path.name}.decompressed").write_bytes(src.read())
            return True, None
    except Exception as exc:  # noqa: BLE001 - report, never abort the scan
        return False, f"{type(exc).__name__}: {exc}"

    return False, "unrecognised archive"


def scan_archives(
    repo_path: Optional[Path],
    config_path: Optional[Path],
    is_public: bool,
    staged_only: bool = False,
) -> List[Dict[str, Any]]:
    """
    Find committed archives, expand them, and scan the contents.

    Findings are attributed as `<archive> -> <member>` so the report names the
    file that must actually be removed. An archive that cannot be expanded is
    itself reported, because an unscannable committed binary is a finding.
    """
    import shutil
    import tempfile

    cwd = str(repo_path) if repo_path else None
    root = Path(cwd) if cwd else Path.cwd()
    results: List[Dict[str, Any]] = []

    for rel in _candidate_files(cwd, staged_only):
        path = root / rel
        if not path.is_file():
            continue
        kind = _sniff_archive(path)
        if kind is None:
            continue

        size = path.stat().st_size
        if size > _MAX_ARCHIVE_BYTES:
            results.append(
                {
                    "RuleID": "lmf-unscannable-archive",
                    "Description": f"Committed {kind} archive too large to inspect",
                    "File": rel,
                    "StartLine": 0,
                    "Severity": _bump_severity("LOW", is_public),
                }
            )
            continue

        tmp = Path(tempfile.mkdtemp(prefix="lmf-archive-"))
        try:
            extracted, reason = _extract_archive(path, tmp)
            if not extracted:
                results.append(
                    {
                        "RuleID": "lmf-unscannable-archive",
                        "Description": f"Committed {kind} archive could not be inspected ({reason})",
                        "File": rel,
                        "StartLine": 0,
                        "Severity": _bump_severity("LOW", is_public),
                    }
                )
                continue

            report_file = tempfile.mktemp(suffix=".json", prefix="gitleaks-archive-")
            _run_gitleaks(
                ["dir", str(tmp), "--report-format", "json", "--report-path", report_file],
                config_path=config_path,
            )
            report = Path(report_file)
            if not report.exists():
                continue
            inner = _parse_findings(report.read_text(encoding="utf-8"), is_public)
            report.unlink(missing_ok=True)

            for f in inner:
                member = f.get("File", "?")
                try:
                    member = str(Path(member).relative_to(tmp))
                except ValueError:
                    member = Path(member).name
                f["File"] = f"{rel} -> {member}"
                f["_in_archive"] = True
                results.append(f)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    return results


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
            ["git", "--report-format", "json", "--report-path", report_file],
            config_path=config_path,
            cwd=cwd,
        )

        # Fail-closed on gitleaks abort. Exit codes alone are ambiguous (gitleaks
        # uses 1 for both "leaks found" and "config load failure"). The reliable
        # signal: if we requested --report-path and the file doesn't exist, the
        # scan never completed. Treating no-report as no-findings would silently
        # hide config errors.
        report_path = Path(report_file)
        if not report_path.exists():
            return 1, (
                f"gitleaks aborted before producing a report (exit {code}). "
                f"Scan did not complete.\nstderr:\n{stderr or '(none)'}"
            )

        findings = _parse_findings(
            report_path.read_text(encoding="utf-8"), is_public
        )
        report_path.unlink(missing_ok=True)

        # gitleaks cannot see inside archives, so scan them separately.
        findings.extend(scan_archives(repo_path, config_path, is_public))

        # Build report
        lines = _public_repo_banner(visibility)
        lines.append(_format_findings(findings))

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
                "git",
                "--pre-commit",
                "--staged",
                "--report-format", "json",
                "--report-path", report_file,
            ],
            config_path=config_path,
            cwd=cwd,
        )

        # Fail-closed on gitleaks abort. Gitleaks exit code 1 means either
        # "leaks found" or "config load failure" — ambiguous. The reliable
        # signal that the scan actually ran: the requested --report-path file
        # exists. If it doesn't, treat as a hard failure and block the commit.
        report_path = Path(report_file)
        if not report_path.exists():
            return 1, (
                f"gitleaks aborted before producing a report (exit {code}). "
                f"Pre-commit scan did not complete.\n"
                f"stderr:\n{stderr or '(none)'}\n\n"
                f"Commit blocked. If this is a config issue, run "
                f"/run-scan-secrets --list-formats to inspect rules."
            )

        findings = _parse_findings(
            report_path.read_text(encoding="utf-8"), is_public
        )
        report_path.unlink(missing_ok=True)

        # Staged archives are invisible to gitleaks; expand and scan them too.
        findings.extend(
            scan_archives(repo_path, config_path, is_public, staged_only=True)
        )

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

    Per-project state: each scanned repo's last_secret_scan timestamp is
    updated regardless of findings. Without this, Overwatch reports every
    just-scanned project as "Never scanned for secrets" because --all
    previously only touched a single global timestamp.
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

    # Lazy-import the per-project state updater. Soft-failure: if the
    # overwatch module can't be loaded, we still complete the scan.
    update_scoped_state = None
    try:
        hooks_scripts = (
            Path(__file__).parent.parent.parent.parent / "hooks" / "scripts"
        )
        sys.path.insert(0, str(hooks_scripts))
        from overwatch import update_scoped_state as _uss  # type: ignore
        update_scoped_state = _uss
    except (ImportError, Exception):
        pass

    lines = [f"Scanning {len(repos)} repos in {ws}...\n"]
    total_findings = 0
    now = int(time.time())

    for repo in repos:
        exit_code, report = scan_repo(repo)
        repo_name = f"{repo.parent.name}/{repo.name}"
        if exit_code == 0:
            lines.append(f"  {repo_name}: clean")
        else:
            lines.append(f"  {repo_name}: FINDINGS DETECTED")
            lines.append(report)
            total_findings += 1

        # Record per-project scan timestamp so Overwatch can see this repo
        # was scanned. Key shape matches what session_start.py reads from
        # state["projects"][f"{org}/{project_dir.name}"].
        if update_scoped_state is not None:
            try:
                update_scoped_state("projects", repo_name, "last_secret_scan", now)
            except Exception:
                pass  # Per-project update is best-effort; don't fail the scan

    lines.append(f"\nScanned {len(repos)} repos. {total_findings} with findings.")
    return (1 if total_findings else 0), "\n".join(lines)


def rules_fingerprint() -> str:
    """
    Short digest of the ruleset a scan actually used.

    Recorded alongside the scan timestamp so a later session can tell whether a
    project was last scanned with rules that have since improved. Freshness by
    date alone is not enough: a repo with no new commits looks "recently
    scanned" forever, even after the scanner gains the ability to detect
    something it previously walked straight past.
    """
    import hashlib

    h = hashlib.sha256()
    try:
        from format_loader import ensure_format_dir

        formats_dir = Path(ensure_format_dir())
    except Exception:
        formats_dir = Path.home() / ".claude" / "lastmilefirst" / "secret-formats"

    try:
        for name in sorted(p.name for p in formats_dir.glob("*.toml")):
            h.update(name.encode())
            h.update((formats_dir / name).read_bytes())
    except Exception:
        h.update(b"formats-unreadable")

    # Scanner behaviour matters as much as the rules — archive inspection
    # changed what a scan can see without changing a single rule.
    try:
        plugin_json = Path(__file__).parents[3] / ".claude-plugin" / "plugin.json"
        h.update(json.loads(plugin_json.read_text()).get("version", "?").encode())
    except Exception:
        h.update(b"version-unknown")

    return h.hexdigest()[:16]


def update_scan_timestamp(workspace: bool = False) -> None:
    """
    Record that a scan ran, with the ruleset it used.

    When `workspace` is set the sweep covered every repo, so a workspace-scoped
    marker is written too — a per-project timestamp cannot express "the whole
    estate was swept", and a dormant repo nobody opens is exactly the one that
    needs that guarantee.
    """
    try:
        hooks_scripts = (
            Path(__file__).parent.parent.parent.parent / "hooks" / "scripts"
        )
        sys.path.insert(0, str(hooks_scripts))
        from overwatch import update_project_state, update_state_field

        now = int(time.time())
        fingerprint = rules_fingerprint()

        update_project_state("last_secret_scan", now)
        update_project_state("last_scan_rules", fingerprint)

        if workspace:
            update_state_field("last_workspace_scan", now)
            update_state_field("last_workspace_scan_rules", fingerprint)
    except (ImportError, Exception):
        pass  # Non-critical — don't fail scan over state update
