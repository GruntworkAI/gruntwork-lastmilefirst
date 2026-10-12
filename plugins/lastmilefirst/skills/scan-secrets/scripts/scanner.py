#!/usr/bin/env python3
"""
Core secret scanning orchestration.

Runs gitleaks with merged config (default rules + custom formats).
Uses --redact to avoid leaking secrets in output. The one exception is the
pass that fetches the matched text for people-rule findings in a repo marked
approvable: it runs only those rules, unredacted, into a temp directory that
is removed afterwards.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import urlparse
from typing import Any, Dict, List, Optional, Tuple

# Add script directory to path for local imports
sys.path.insert(0, str(Path(__file__).parent))

from format_loader import write_merged_config, consume_sync_note

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

# The pre-push scan hands the pushed range to `gitleaks git --log-opts`. That
# flag shipped with the 'git' subcommand itself in v8.19.0 (cmd/git.go at the
# v8.19.0 tag defines "staged", "pre-commit", and "log-opts"), so the floor is
# the same release; it is named separately so the two can diverge.
LOG_OPTS_MIN_GITLEAKS_VERSION = (8, 19, 0)

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


def _check_gitleaks(
    min_version: Tuple[int, int, int] = MIN_GITLEAKS_VERSION,
    feature: str = "the 'git' subcommand",
) -> Optional[str]:
    """
    Check gitleaks is installed and new enough. Returns an error message or None.

    `min_version` and `feature` let a mode that needs a later flag raise the
    floor (the pre-push scan passes LOG_OPTS_MIN_GITLEAKS_VERSION).

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
    if version < min_version:
        need = ".".join(str(n) for n in min_version)
        have = ".".join(str(n) for n in version)
        return (
            f"gitleaks {have} is too old. This scanner uses {feature}, "
            f"which requires gitleaks {need} or later.\n"
            f"Upgrade: brew upgrade gitleaks  (macOS)\n"
            f"         or see https://github.com/gitleaks/gitleaks#installing"
        )
    return None


VISIBILITY_CONFIG_KEY = "lastmilefirst.visibility"
VISIBILITY_VALUES = {"PUBLIC", "PRIVATE", "INTERNAL"}


def declared_visibility(repo_path: Optional[Path] = None) -> Optional[str]:
    """Visibility declared in the repo's own git config, if any.

    `git config lastmilefirst.visibility private` is a local claim that does
    not depend on which account `gh` has active. The `gh` CLI's active account
    is machine-global, so a private repo owned by one account reads as
    "not found" while another account is active; the declared value settles it.
    Returns 'PUBLIC', 'PRIVATE', 'INTERNAL', or None when unset or invalid.
    """
    try:
        result = subprocess.run(
            ["git", "config", "--get", VISIBILITY_CONFIG_KEY],
            capture_output=True, text=True, timeout=5,
            cwd=str(repo_path) if repo_path else None,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None
    value = result.stdout.strip().upper()
    return value if result.returncode == 0 and value in VISIBILITY_VALUES else None


APPROVABLE_CONFIG_KEY = "lastmilefirst.approvable"


def approvable_rules(repo_path: Optional[Path] = None) -> set:
    """Rule ids the repo is marked approvable for, lower-cased.

    `git config --add lastmilefirst.approvable <rule>` marks a repo whose
    subject is a listed person, so a people-rule finding is shown with its
    matched text and asked about instead of only blocking. Local scope only:
    a global value would mark every repo on the machine. Unset, unreadable,
    or outside a repo is the empty set.
    """
    try:
        result = subprocess.run(
            ["git", "config", "--local", "--get-all", APPROVABLE_CONFIG_KEY],
            capture_output=True, text=True, timeout=5,
            cwd=str(repo_path) if repo_path else None,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return set()
    if result.returncode != 0:
        return set()
    return {line.strip().lower() for line in result.stdout.splitlines() if line.strip()}


def is_approvable(finding: Dict[str, Any], approvable: set) -> bool:
    """A finding is approvable when its rule is marked and the rule is a people rule.

    Eligibility is decided per finding, so a marker naming a secret, an
    organization, or a PII rule never matches anything.
    """
    rule = str(finding.get("RuleID") or "").strip().lower()
    return bool(rule) and rule in approvable and _finding_kind(finding) == "person"


def marker_warnings(approvable: set, config_path: Optional[Path]) -> List[str]:
    """One line per marker key that does not name a people rule in the merged config.

    Such a key never matches a finding (see is_approvable); the line makes the
    misconfiguration visible. An unreadable config gives no lines rather than
    calling every key wrong.
    """
    if not approvable or not config_path:
        return []
    try:
        from format_loader import _read_toml
        rules = _read_toml(Path(config_path)).get("rules") or []
    except Exception:  # noqa: BLE001 - a warning helper never aborts the scan
        return []
    people = {
        str(rule.get("id") or "").strip().lower()
        for rule in rules
        if isinstance(rule, dict) and _finding_kind({"Tags": rule.get("tags") or []}) == "person"
    }
    return [f"lastmilefirst.approvable names {key}, which is not a people rule; ignored"
            for key in sorted(approvable) if key not in people]


def check_repo_visibility(repo_path: Optional[Path] = None) -> Optional[str]:
    """
    Visibility of the repo: the value declared in git config wins, then what
    the gh CLI reports for the active account.
    Returns 'PUBLIC', 'PRIVATE', 'INTERNAL', or None if not determinable
    (no GitHub remote, gh missing, not logged in, or the active account
    cannot see the repo).
    """
    declared = declared_visibility(repo_path)
    if declared:
        return declared
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
            return result.stdout.strip().upper() or None
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
    redact: bool = True,
    enable_rules: Optional[List[str]] = None,
) -> Tuple[int, str, str]:
    """
    Run gitleaks with given arguments.
    Returns (returncode, stdout, stderr).
    Exit codes: 0 = no leaks, 1 = leaks found, >1 = error.

    `redact=False` is only for the approvable pass, which always passes
    `enable_rules` so no rule other than a people rule runs unredacted.
    An unknown id in `enable_rules` makes gitleaks abort before writing a
    report, so callers pass ids taken from findings, never raw config.
    """
    cmd = ["gitleaks"]
    if config_path:
        cmd.extend(["--config", str(config_path)])
    cmd.extend(args)
    for rule in enable_rules or []:
        cmd.extend(["--enable-rule", rule])
    if redact:
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


SEVERITY_TAG_PREFIX = "severity-"


def _declared_severity(finding: Dict[str, Any]) -> str:
    """gitleaks reports no severity, so a rule declares one with a `severity-<level>` tag.

    A tagged level wins over the report's (always absent) Severity field; the default stays MEDIUM.
    """
    for tag in finding.get("Tags") or []:
        text = str(tag).strip().lower()
        if text.startswith(SEVERITY_TAG_PREFIX):
            level = text[len(SEVERITY_TAG_PREFIX):].upper()
            if level in SEVERITY_BUMP:
                return level
    return str(finding.get("Severity") or "MEDIUM").upper()


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
        original = _declared_severity(finding)
        finding["Severity"] = _bump_severity(original, is_public)
        if is_public and original != finding["Severity"]:
            finding["_bumped"] = True

    return findings


# Three kinds of tagged rule, one policy.
#
# - `public-only`: an organization's name (e.g. a client's), fine inside a
#   private repo and a finding in a public one. Dropped in PRIVATE/INTERNAL.
# - `pii`: generic personal data (a personal email, a phone number). Kept in
#   every repo; in PRIVATE/INTERNAL it is a WARNING that does not block.
# - `private-name` without `public-only`: a person from the user's people
#   list. Kept and blocking in every repo.
#
# Everything else is an ordinary secret and always blocks. The names
# themselves live in the user's org rules file, never in the plugin.
PUBLIC_ONLY_TAG = "public-only"
PII_TAG = "pii"
PRIVATE_NAME_TAG = "private-name"

_VISIBILITY_UNKNOWN_NOTE = (
    "public-only rules applied because visibility could not be determined; "
    "push the repo or run `gh auth login`"
)


def _tags(finding: Dict[str, Any]) -> set:
    tags = finding.get("Tags") or []
    if isinstance(tags, str):
        tags = [tags]
    return {str(t).strip().lower() for t in tags}


def _finding_kind(finding: Dict[str, Any]) -> str:
    """One of "organization", "person", "pii", "ordinary"."""
    tags = _tags(finding)
    if PUBLIC_ONLY_TAG in tags:
        return "organization"
    if PRIVATE_NAME_TAG in tags:
        return "person"
    if PII_TAG in tags:
        return "pii"
    return "ordinary"


def apply_visibility_policy(
    findings: List[Dict[str, Any]], visibility: Optional[str]
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Decide, per finding, whether it is kept and whether it blocks.

    PUBLIC, or unknown visibility (no remote, `gh` missing or not logged in):
    every finding is kept and blocks; when unknown and a public-only rule
    fired, one line says why it was applied. PRIVATE or INTERNAL: public-only
    findings are dropped with one summary line, pii findings are kept with
    Blocking False, everything else blocks.

    A pii finding on the same File and StartLine as a person finding is
    dropped, so the line is reported once, as the person.

    Returns (kept_findings, report_lines). Kept findings are copies carrying a
    `Blocking` boolean; the input is not modified.
    """
    kinds = [(f, _finding_kind(f)) for f in findings]
    person_lines = {(f.get("File"), f.get("StartLine")) for f, k in kinds if k == "person"}
    kinds = [(f, k) for f, k in kinds
             if not (k == "pii" and (f.get("File"), f.get("StartLine")) in person_lines)]

    vis = (visibility or "").upper()
    private = vis in ("PRIVATE", "INTERNAL")
    organization_count = sum(1 for _, k in kinds if k == "organization")

    kept: List[Dict[str, Any]] = []
    for finding, kind in kinds:
        if private and kind == "organization":
            continue
        kept.append(dict(finding, Blocking=not (private and kind == "pii")))

    lines: List[str] = []
    if organization_count:
        if private:
            where = "a private" if vis == "PRIVATE" else "an internal"
            lines.append(f"{organization_count} finding(s) from public-only rules "
                         f"suppressed in {where} repo")
        elif vis != "PUBLIC":
            lines.append(_VISIBILITY_UNKNOWN_NOTE)
    return kept, lines


def apply_public_only(
    findings: List[Dict[str, Any]], visibility: Optional[str]
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Deprecated alias of apply_visibility_policy, kept for one release.

    Returns the kept findings without the `Blocking` flag.
    """
    kept, lines = apply_visibility_policy(findings, visibility)
    return [{k: v for k, v in f.items() if k != "Blocking"} for f in kept], lines


def _is_blocking(finding: Dict[str, Any]) -> bool:
    """A finding that never went through the policy blocks."""
    return finding.get("Blocking", True) is not False


def _summary_counts(findings: List[Dict[str, Any]]) -> str:
    blocking = sum(1 for f in findings if _is_blocking(f))
    warnings = len(findings) - blocking
    parts = []
    if blocking:
        parts.append(f"{blocking} blocking finding(s)")
    if warnings:
        parts.append(f"{warnings} warning(s)")
    return " and ".join(parts)


# Display order, most severe first; an unknown severity sorts last.
_SEVERITY_RANK = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}


def _format_findings(findings: List[Dict[str, Any]]) -> str:
    """Format findings for display. Non-blocking findings read WARNING."""
    if not findings:
        return "No secrets detected."

    lines = [f"\nFound {_summary_counts(findings)}:\n"]
    lines.append(f"{'Severity':<10} {'Rule':<35} {'File':<40} Line")
    lines.append("-" * 90)

    ordered = sorted(findings, key=lambda x: _SEVERITY_RANK.get(
        str(x.get("Severity", "")).upper(), len(_SEVERITY_RANK)))
    # Stable regroup: blocking first, keeping the severity order within each group.
    ordered.sort(key=lambda x: not _is_blocking(x))
    for f in ordered:
        severity = f.get("Severity", "?") if _is_blocking(f) else "WARNING"
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
    if any(not _is_blocking(f) for f in findings):
        lines.append("\nWARNING rows are personal data in a private repo: reported, not blocking.")

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


def _scan_expanded_archive(
    tmp: Path,
    rel: str,
    config_path: Optional[Path],
    is_public: bool,
    redact: bool = True,
    enable_rules: Optional[List[str]] = None,
) -> Optional[List[Dict[str, Any]]]:
    """Run `gitleaks dir` over an expanded archive and attribute each finding.

    Returns None when gitleaks wrote no report. The unredacted pass writes its
    report inside its own temp directory, removed before returning.
    """
    import shutil

    kwargs: Dict[str, Any] = {}
    if not redact:
        kwargs["redact"] = False
    if enable_rules:
        kwargs["enable_rules"] = list(enable_rules)
    report_dir = None if redact else Path(tempfile.mkdtemp(prefix="lmf-approvable-"))
    try:
        if report_dir is None:
            report_file = tempfile.mktemp(suffix=".json", prefix="gitleaks-archive-")
        else:
            report_file = str(report_dir / "report.json")
        _run_gitleaks(
            ["dir", str(tmp), "--report-format", "json", "--report-path", report_file],
            config_path=config_path,
            **kwargs,
        )
        report = Path(report_file)
        if not report.exists():
            return None
        inner = _parse_findings(report.read_text(encoding="utf-8"), is_public)
        report.unlink(missing_ok=True)
    finally:
        if report_dir is not None:
            shutil.rmtree(report_dir, ignore_errors=True)

    for f in inner:
        member = f.get("File", "?")
        try:
            member = str(Path(member).relative_to(tmp))
        except ValueError:
            member = Path(member).name
        f["File"] = f"{rel} -> {member}"
        f["_in_archive"] = True
    return inner


def scan_archives(
    repo_path: Optional[Path],
    config_path: Optional[Path],
    is_public: bool,
    staged_only: bool = False,
    approvable: Optional[set] = None,
) -> List[Dict[str, Any]]:
    """
    Find committed archives, expand them, and scan the contents.

    Findings are attributed as `<archive> -> <member>` so the report names the
    file that must actually be removed. An archive that cannot be expanded is
    itself reported, because an unscannable committed binary is a finding.

    With `approvable` (the repo's marker), approvable findings get their
    matched text from an unredacted pass over the same expanded directory,
    run before it is removed (see _attach_matches).
    """
    import shutil

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

            inner = _scan_expanded_archive(tmp, rel, config_path, is_public)
            if inner is None:
                continue
            if approvable:
                # The fingerprint carries this run's temp path, so the join
                # uses the rewritten File, the line, and the rule.
                _attach_matches(
                    inner, approvable,
                    lambda ids: _scan_expanded_archive(
                        tmp, rel, config_path, is_public,
                        redact=False, enable_rules=ids),
                    _archive_join_key,
                )
            results.extend(inner)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    return results


def _gitleaks_report(
    args: List[str],
    prefix: str,
    config_path: Path,
    cwd: Optional[str],
    is_public: bool,
    redact: bool = True,
    enable_rules: Optional[List[str]] = None,
    approvable: Optional[set] = None,
) -> Tuple[Optional[List[Dict[str, Any]]], int, str]:
    """Run gitleaks with a JSON report and parse it.

    Returns (findings, exit_code, stderr). findings is None when gitleaks
    aborted before writing the report, so the caller can fail closed with its
    own message. Exit codes alone are ambiguous (gitleaks uses 1 for both
    "leaks found" and "config load failure"); the reliable signal that the
    scan completed is that the requested --report-path file exists. Treating
    no-report as no-findings would silently hide config errors.

    With `approvable` (the repo's marker), approvable findings get their
    matched text from a second, unredacted pass over the same target that
    runs only their rules (see _attach_matches). `redact=False` writes the
    report inside a temp directory removed in a `finally`.
    """
    import shutil

    kwargs: Dict[str, Any] = {}
    if not redact:
        kwargs["redact"] = False
    if enable_rules:
        kwargs["enable_rules"] = list(enable_rules)
    report_dir = None if redact else Path(tempfile.mkdtemp(prefix="lmf-approvable-"))
    try:
        if report_dir is None:
            report_file = tempfile.mktemp(suffix=".json", prefix=prefix)
        else:
            report_file = str(report_dir / f"{prefix}report.json")
        code, _stdout, stderr = _run_gitleaks(
            args + ["--report-format", "json", "--report-path", report_file],
            config_path=config_path,
            cwd=cwd,
            **kwargs,
        )
        report_path = Path(report_file)
        if not report_path.exists():
            return None, code, stderr
        findings = _parse_findings(report_path.read_text(encoding="utf-8"), is_public)
        report_path.unlink(missing_ok=True)
    finally:
        if report_dir is not None:
            shutil.rmtree(report_dir, ignore_errors=True)

    if approvable:
        def unredacted(ids: List[str]) -> Optional[List[Dict[str, Any]]]:
            rows, pass_code, pass_stderr = _gitleaks_report(
                args, prefix, config_path, cwd, is_public,
                redact=False, enable_rules=ids)
            if rows is None:
                unredacted.error = (f"no report from the unredacted pass (exit {pass_code})"
                                    + (f": {pass_stderr.strip()}" if pass_stderr.strip() else ""))
            return rows
        unredacted.error = None
        _attach_matches(findings, approvable, unredacted, _diff_join_key)
    return findings, code, stderr


# --- Approvable findings: the matched text, the grouped block, the approval ---
#
# A repo marked approvable (approvable_rules) shows each people-rule finding
# with what it matched, grouped by term, so the approval is given against the
# text rather than a rule name and a line number. The first pass stays
# redacted; _attach_matches fetches the text from a second pass that runs only
# the approvable rules.

def _diff_join_key(finding: Dict[str, Any]) -> Tuple[Any, ...]:
    """Join key for a diff or history finding: the fingerprint, else file, line, rule.

    gitleaks' fingerprint names file, rule, and line but not the column, so two
    matches on one line share it; the column keeps them apart.
    """
    base = finding.get("Fingerprint") or (
        finding.get("File"), finding.get("StartLine"), finding.get("RuleID"))
    return (base, finding.get("StartColumn"))


def _archive_join_key(finding: Dict[str, Any]) -> Tuple[Any, ...]:
    """Join key for an archive finding, whose fingerprint carries a per-run temp path."""
    return (finding.get("File"), finding.get("StartLine"), finding.get("RuleID"),
            finding.get("StartColumn"))


def _attach_matches(
    findings: List[Dict[str, Any]],
    approvable: set,
    run_unredacted,
    join_key,
) -> None:
    """Copy the unredacted Match and Secret onto each approvable finding, in place.

    `run_unredacted(rule_ids)` runs the second pass over the first pass's
    target and returns its findings, or None when it wrote no report. The ids
    are the distinct RuleIDs of the approvable findings, never the marker's
    keys: those are eligible by construction and exist in the merged config,
    whereas an unknown id makes gitleaks abort.

    A joined finding carries `_unredacted: True`. One left unjoined (no report,
    or no matching row) carries `_match_error` instead, so the caller can fail
    closed (see unmatched_rules); an approval is never taken against a blank term.
    """
    targets = [f for f in findings if is_approvable(f, approvable)]
    if not targets:
        return
    ids = sorted({str(f.get("RuleID")) for f in targets})
    rows = run_unredacted(ids)
    if rows is None:
        error = getattr(run_unredacted, "error", None) or "no report from the unredacted pass"
        for f in targets:
            f["_match_error"] = error
        return
    index: Dict[Tuple[Any, ...], List[Dict[str, Any]]] = {}
    for row in rows:
        index.setdefault(join_key(row), []).append(row)
    for f in targets:
        candidates = index.get(join_key(f))
        if not candidates:
            f["_match_error"] = "no matching row in the unredacted pass"
            continue
        row = candidates.pop(0)
        f["Match"] = row.get("Match", "")
        f["Secret"] = row.get("Secret", "")
        f["_unredacted"] = True
        f.pop("_match_error", None)


def unmatched_rules(findings: List[Dict[str, Any]], approvable: set) -> List[str]:
    """Rules with an approvable finding that has no matched text; empty when all joined."""
    return sorted({str(f.get("RuleID")) for f in findings
                   if is_approvable(f, approvable) and not f.get("_unredacted")})


def _term(finding: Dict[str, Any]) -> str:
    """The matched term: the rule's capture group (Secret) when present, else Match.

    Lower-cased and whitespace-collapsed, so two casings of one name are one row.
    """
    text = str(finding.get("Secret") or "").strip() or str(finding.get("Match") or "")
    return " ".join(text.split()).lower()


APPROVABLE_FILE_CAP = 5


def _format_approvable(findings: List[Dict[str, Any]]) -> str:
    """Render approvable findings grouped by rule, then by matched term.

    One header per rule (`<rule> in N files (M lines)`), then one row per term
    with its count and the files it appears in, most lines first, capped at
    five with `... and N more files`. Callers pass approvable findings only.
    """
    by_rule: Dict[str, List[Dict[str, Any]]] = {}
    for f in findings:
        by_rule.setdefault(str(f.get("RuleID") or "unknown"), []).append(f)

    lines: List[str] = []
    for rule in sorted(by_rule):
        rows = by_rule[rule]
        files = {str(f.get("File") or "?") for f in rows}
        lines.append(f"{rule} in {len(files)} file{'s' if len(files) != 1 else ''} "
                     f"({len(rows)} line{'s' if len(rows) != 1 else ''})")

        by_term: Dict[str, Dict[str, int]] = {}
        for f in rows:
            per_file = by_term.setdefault(_term(f), {})
            path = str(f.get("File") or "?")
            per_file[path] = per_file.get(path, 0) + 1

        ordered_terms = sorted(by_term.items(), key=lambda kv: (-sum(kv[1].values()), kv[0]))
        term_width = max(len(term) for term in by_term) + 2
        count_width = max(len(f"{sum(c.values())}×") for c in by_term.values()) + 2
        for term, per_file in ordered_terms:
            ordered_files = sorted(per_file.items(), key=lambda kv: (-kv[1], kv[0]))
            shown = ordered_files[:APPROVABLE_FILE_CAP]
            count = f"{sum(per_file.values())}×"
            for i, (path, n) in enumerate(shown):
                if i == 0:
                    lines.append(f"  {term:<{term_width}}{count:<{count_width}}{path} ({n})")
                else:
                    lines.append(f"  {'':<{term_width}}{'':<{count_width}}{path} ({n})")
            hidden = len(ordered_files) - len(shown)
            if hidden:
                lines.append(f"  {'':<{term_width}}{'':<{count_width}}"
                             f"... and {hidden} more file{'s' if hidden != 1 else ''}")
    return "\n".join(lines)


def apply_approvals(
    findings: List[Dict[str, Any]], approvable: set, approved: bool
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Mark approvable findings approved, after apply_visibility_policy.

    Returns (findings, approvable_subset). When `approved`, each approvable
    finding becomes a copy with `Blocking` False and `Approved` True; every
    other finding is passed through unchanged. The subset is always returned,
    so the caller can render it whether or not it was approved. The input is
    not modified.
    """
    out: List[Dict[str, Any]] = []
    subset: List[Dict[str, Any]] = []
    for f in findings:
        if is_approvable(f, approvable):
            if approved:
                f = dict(f, Blocking=False, Approved=True)
            subset.append(f)
        out.append(f)
    return out, subset


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
        findings, code, stderr = _gitleaks_report(
            ["git"], "gitleaks-report-", config_path, cwd, is_public
        )
        # Fail-closed on gitleaks abort (see _gitleaks_report).
        if findings is None:
            return 1, (
                f"gitleaks aborted before producing a report (exit {code}). "
                f"Scan did not complete.\nstderr:\n{stderr or '(none)'}"
            )

        # gitleaks cannot see inside archives, so scan them separately.
        findings.extend(scan_archives(repo_path, config_path, is_public))
        findings, policy_lines = apply_visibility_policy(findings, visibility)

        # Build report
        lines = _public_repo_banner(visibility)
        sync_note = consume_sync_note()
        if sync_note:
            lines.append(sync_note)
        lines.extend(policy_lines)
        lines.append(_format_findings(findings))

        blocked = any(_is_blocking(f) for f in findings)
        return (1 if blocked else 0), "\n".join(lines)
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
        findings, code, stderr = _gitleaks_report(
            ["git", "--pre-commit", "--staged"],
            "gitleaks-staged-", config_path, cwd, is_public,
        )
        # Fail-closed on gitleaks abort (see _gitleaks_report): block the commit.
        if findings is None:
            return 1, (
                f"gitleaks aborted before producing a report (exit {code}). "
                f"Pre-commit scan did not complete.\n"
                f"stderr:\n{stderr or '(none)'}\n\n"
                f"Commit blocked. If this is a config issue, run "
                f"/run-scan-secrets --list-formats to inspect rules."
            )

        # Staged archives are invisible to gitleaks; expand and scan them too.
        findings.extend(
            scan_archives(repo_path, config_path, is_public, staged_only=True)
        )
        # Same visibility answer as the full scan (check_repo_visibility above).
        findings, policy_lines = apply_visibility_policy(findings, visibility)

        lines = []
        sync_note = consume_sync_note()
        if sync_note:
            lines.append(sync_note)
        if is_public:
            lines.append("Reminder: you are committing to a PUBLIC repository")
        lines.extend(policy_lines)

        if any(_is_blocking(f) for f in findings):
            lines.append(_format_findings(findings))
            return 1, "\n".join(lines)
        if findings:
            # Warnings only (personal data in a private repo): shown, not blocking.
            lines.append(_format_findings(findings))
            lines.append("No blocking findings; commit allowed.")
            return 0, "\n".join(lines)

        lines.append("No secrets detected in staged changes.")
        return 0, "\n".join(lines)
    finally:
        config_path.unlink(missing_ok=True)


# --- Pre-push scan -------------------------------------------------------

_ZERO_SHA = re.compile(r"^0+$")


def parse_pre_push_lines(text: str) -> List[Dict[str, str]]:
    """Parse the ref lines git writes to a pre-push hook's stdin.

    Each line is `<local ref> <local sha> <remote ref> <remote sha>`. The
    result carries those four fields plus `kind`: "deleted" when the local sha
    is all zeros, "new" when the remote sha is all zeros (a first push of that
    ref), otherwise "existing". Blank lines are ignored; any other line that
    does not have four fields raises ValueError, so the caller can fail closed.
    """
    refs: List[Dict[str, str]] = []
    for raw in text.splitlines():
        if not raw.strip():
            continue
        parts = raw.split()
        if len(parts) != 4:
            raise ValueError(f"unexpected pre-push line: {raw!r}")
        local_ref, local_sha, remote_ref, remote_sha = parts
        if _ZERO_SHA.match(local_sha):
            kind = "deleted"
        elif _ZERO_SHA.match(remote_sha):
            kind = "new"
        else:
            kind = "existing"
        refs.append({"local_ref": local_ref, "local_sha": local_sha,
                     "remote_ref": remote_ref, "remote_sha": remote_sha, "kind": kind})
    return refs


def _commit_exists(sha: str, cwd: Optional[str] = None) -> bool:
    """True when this clone has the commit."""
    try:
        result = subprocess.run(
            ["git", "cat-file", "-e", f"{sha}^{{commit}}"],
            capture_output=True, text=True, timeout=10, cwd=cwd,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False
    return result.returncode == 0


NOT_ON_A_REMOTE = "--not --remotes"


def _push_log_opts(ref: Dict[str, str], cwd: Optional[str]) -> str:
    """The `--log-opts` value for one pushed ref.

    An existing ref scans `remote..local`. A new ref scans every commit
    reachable from the local sha that is not already on a remote-tracking ref
    (`<sha> --not --remotes`; gitleaks splits --log-opts on spaces, verified
    on 8.30.1), so a branch cut from a pushed main does not rescan main. A
    repo with no remote-tracking refs yet still scans its whole history. When
    this clone lacks the remote sha (e.g. a force push over commits never
    fetched), the range would be invalid, and gitleaks 8.30.1 exits 0 with an
    empty report on an invalid range, so that case widens the same way rather
    than scanning nothing.
    """
    if ref["kind"] == "existing" and _commit_exists(ref["remote_sha"], cwd):
        return f"{ref['remote_sha']}..{ref['local_sha']}"
    return f"{ref['local_sha']} {NOT_ON_A_REMOTE}"


def _push_scan_runs(refs: List[Dict[str, str]], cwd: Optional[str]) -> List[Tuple[str, str]]:
    """(label, --log-opts) for each gitleaks run a push needs.

    Each existing range is its own run. Every ref that scans "not on a remote"
    shares one run, `<sha1> <sha2> --not --remotes`, so a push of several new
    branches walks their shared history once.
    """
    runs: List[Tuple[str, str]] = []
    widened: List[Dict[str, str]] = []
    for ref in refs:
        opts = _push_log_opts(ref, cwd)
        if opts.endswith(NOT_ON_A_REMOTE):
            widened.append(ref)
        else:
            runs.append((ref["local_ref"], opts))
    if widened:
        shas = " ".join(dict.fromkeys(r["local_sha"] for r in widened))
        label = ", ".join(r["local_ref"] for r in widened)
        runs.append((label, f"{shas} {NOT_ON_A_REMOTE}"))
    return runs


def _repo_auditor():
    """The repo_auditor module, or None if it cannot load."""
    try:
        import repo_auditor
        return repo_auditor
    except Exception:
        return None


def _fetch_github_posture(
    repo_path: Optional[Path], repo: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """GitHub's own answer (visibility plus posture), one `gh api` call.

    `repo` ("owner/name") asks about that repo; without it, `gh` asks about
    the clone's default repo. None when the posture module cannot load; a dict
    with visibility None when `gh` is missing, unauthenticated, or there is no
    GitHub remote.
    """
    auditor = _repo_auditor()
    if auditor is None:
        return None
    try:
        if repo:
            return auditor._fetch_posture(repo_path or Path.cwd(), repo=repo)
        return auditor._fetch_posture(repo_path or Path.cwd())
    except Exception:
        return None


# Hosts that are clearly not GitHub, for scp-style remotes whose host may be
# an ssh alias (e.g. `git@github-work:owner/repo.git`).
_OTHER_GIT_HOSTS = ("gitlab", "bitbucket", "codeberg", "sr.ht", "gitea",
                    "azure", "visualstudio", "sourceforge")
_OWNER_REPO = re.compile(r"^/*([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/*$")


def github_repo_from_url(url: Optional[str]) -> Optional[str]:
    """"owner/repo" when `url` reads as a GitHub remote, else None.

    Accepts https and ssh:// URLs whose host contains "github", and scp-style
    `user@host:owner/repo(.git)` where the host is github.com or an ssh alias
    that is not obviously another provider. Local paths and file:// URLs are
    not GitHub.
    """
    if not url or not url.strip():
        return None
    url = url.strip()
    if "://" in url:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        if "github" not in host:
            return None
        path = parsed.path
    else:
        match = re.match(r"^(?:[^@/:]+@)?([^/:]+):(?!/)(.+)$", url)
        if not match:
            return None
        host, path = match.group(1).lower(), match.group(2)
        if any(other in host for other in _OTHER_GIT_HOSTS):
            return None
    found = _OWNER_REPO.match(path)
    if not found:
        return None
    return f"{found.group(1)}/{found.group(2)}"


def _describe_github_posture(posture: Dict[str, Any]) -> str:
    auditor = _repo_auditor()
    if auditor is None:
        return ""
    try:
        return auditor._describe_posture(posture)
    except Exception:
        return ""


def _hygiene_warnings(repo_path: Optional[Path]) -> List[str]:
    """repo_auditor's gitignore-gap and dangerous-file checks, as warning lines."""
    lines: List[str] = []
    try:
        auditor = _repo_auditor()
        if auditor is None:
            # Re-raise the original import error so the warning names its type.
            import repo_auditor as auditor
        missing, _present = auditor.check_gitignore(repo_path)
        if missing:
            lines.append(f"WARNING: .gitignore is missing {len(missing)} required "
                         f"pattern(s): {', '.join(missing)}")
        dangerous = sorted(auditor.check_dangerous_committed_files(repo_path))
        if dangerous:
            shown = ", ".join(dangerous[:10])
            more = f" and {len(dangerous) - 10} more" if len(dangerous) > 10 else ""
            lines.append(f"WARNING: {len(dangerous)} file(s) in git history that should "
                         f"not be committed: {shown}{more}")
    except Exception as exc:  # noqa: BLE001 - hygiene is advisory; never abort the push
        lines.append(f"WARNING: hygiene checks could not run ({type(exc).__name__})")
    return lines


def visibility_mismatch(
    declared: Optional[str], github: Optional[str]
) -> Tuple[Optional[str], List[str]]:
    """Compare the declared visibility with GitHub's answer.

    Returns (level, lines) with level "block", "warn", or None. A declaration
    of PRIVATE or INTERNAL against a PUBLIC repo blocks, because the policy
    would treat the pushed content as private (PII warns, organization names
    are suppressed) while it is on the internet. A declared PUBLIC against a
    non-public repo only warns: the policy is stricter than it needs to be.
    No declaration, or no answer from GitHub, is not a finding.
    """
    if not declared or not github or declared == github:
        return None, []
    if declared in ("PRIVATE", "INTERNAL") and github == "PUBLIC":
        return "block", [
            f"BLOCKED: this repo is declared {declared} (git config {VISIBILITY_CONFIG_KEY}) "
            f"but GitHub reports PUBLIC.",
            "The scan applied private-repo rules to content that would be public.",
            "Fix one side, then push again:",
            "  - make the repo private: gh repo edit --visibility private "
            "--accept-visibility-change-consequences",
            f"  - or declare it public, so the audit runs as public: "
            f"git config {VISIBILITY_CONFIG_KEY} public",
        ]
    if declared == "PUBLIC":
        return "warn", [
            f"WARNING: this repo is declared PUBLIC but GitHub reports {github}. "
            "Public-repo rules were applied (stricter than needed). To match: "
            f"git config {VISIBILITY_CONFIG_KEY} {github.lower()}",
        ]
    return "warn", [
        f"WARNING: this repo is declared {declared} but GitHub reports {github}.",
    ]


def scan_pushed(
    stdin_text: str,
    repo_path: Optional[Path] = None,
    remote_url: Optional[str] = None,
) -> Tuple[int, str]:
    """
    Pre-push mode: scan the commits being pushed, read from the hook's stdin.

    Deleted refs are skipped. An existing remote ref scans `remote..local`. A
    new remote ref scans every commit not already on a remote and runs the
    first-push audit once per push: hygiene warnings, the visibility
    consistency check, and (for a public repo) GitHub's posture as a warning.

    `remote_url` is the URL git passes the hook. When it reads as a GitHub
    repo and GitHub answers for it, that answer is used rather than the
    clone's default repo, and a PUBLIC answer overrides a private or internal
    declaration for the scan rules. With no answer for it, the declaration
    then the default repo's answer decide, as before.

    Exit 1 only on a blocking finding, a visibility block, or a scan that did
    not complete. Returns (exit_code, report_text).
    """
    try:
        refs = parse_pre_push_lines(stdin_text)
    except ValueError as exc:
        return 1, f"Push blocked: could not read the refs git passed the hook ({exc})."

    to_scan = [r for r in refs if r["kind"] != "deleted"]
    if not to_scan:
        return 0, "Nothing to scan (no refs pushed, or only deletions)."

    err = _check_gitleaks(LOG_OPTS_MIN_GITLEAKS_VERSION,
                          "--log-opts on the 'git' subcommand")
    if err:
        return 1, err

    cwd = str(repo_path) if repo_path else None
    first_push = any(r["kind"] == "new" for r in to_scan)

    lines: List[str] = []
    blocked = False

    if first_push:
        declared = declared_visibility(repo_path)
        pushed_repo = github_repo_from_url(remote_url)
        posture = _fetch_github_posture(repo_path, repo=pushed_repo) if pushed_repo else None
        github = (posture or {}).get("visibility")
        if github == "PUBLIC":
            # The remote being pushed to is public: content lands on the
            # internet whatever the declaration says.
            visibility = github
        else:
            if not github:
                posture = _fetch_github_posture(repo_path)
                github = (posture or {}).get("visibility")
            # Declared wins, as in check_repo_visibility; GitHub's answer is
            # already in hand, so it is not asked twice.
            visibility = declared or github
    else:
        posture = None
        github = None
        visibility = check_repo_visibility(repo_path)
    is_public = visibility == "PUBLIC"

    config_path = write_merged_config()
    try:
        findings: List[Dict[str, Any]] = []
        seen = set()
        for label, log_opts in _push_scan_runs(to_scan, cwd):
            ref_findings, code, stderr = _gitleaks_report(
                ["git", "--log-opts", log_opts],
                "gitleaks-push-", config_path, cwd, is_public,
            )
            # Fail-closed on gitleaks abort (see _gitleaks_report).
            if ref_findings is None:
                return 1, (
                    f"gitleaks aborted before producing a report (exit {code}). "
                    f"Pre-push scan of {label} did not complete.\n"
                    f"stderr:\n{stderr or '(none)'}\n\n"
                    f"Push blocked. If this is a config issue, run "
                    f"/run-scan-secrets --list-formats to inspect rules."
                )
            for f in ref_findings:
                key = f.get("Fingerprint") or (f.get("Commit"), f.get("File"),
                                               f.get("StartLine"), f.get("RuleID"))
                if key in seen:
                    continue
                seen.add(key)
                findings.append(f)

        findings, policy_lines = apply_visibility_policy(findings, visibility)

        sync_note = consume_sync_note()
        if sync_note:
            lines.append(sync_note)
        if first_push:
            lines.append("First push of a ref: auditing every commit not already on a remote.")
            level, mismatch_lines = visibility_mismatch(declared, github)
            lines.extend(mismatch_lines)
            if declared and not github:
                reason = (posture or {}).get("reason") or "no answer"
                lines.append(f"WARNING: declared {declared}; GitHub could not confirm it "
                             f"({reason}), so the declaration was not verified.")
            blocked = blocked or level == "block"
            lines.extend(_hygiene_warnings(repo_path))
            if github == "PUBLIC" and posture is not None:
                described = _describe_github_posture(posture)
                if described:
                    lines.append("WARNING (not blocking): GitHub posture for this public repo:")
                    lines.append(described)
        if is_public:
            lines.append("Reminder: you are pushing to a PUBLIC repository")
        lines.extend(policy_lines)

        if findings:
            lines.append(_format_findings(findings))
        else:
            lines.append("No secrets detected in the pushed commits.")
        blocked = blocked or any(_is_blocking(f) for f in findings)
        if not blocked and findings:
            lines.append("No blocking findings; push allowed.")
        return (1 if blocked else 0), "\n".join(lines)
    finally:
        config_path.unlink(missing_ok=True)


def _load_workspace_loader():
    """The workspace layout loader from hooks/scripts, or None if it cannot load.

    The hooks directory is optional to the scanner (the per-project state
    update below soft-fails the same way), so a missing or broken loader must
    not stop a scan.
    """
    hooks_scripts = Path(__file__).parent.parent.parent.parent / "hooks" / "scripts"
    if str(hooks_scripts) not in sys.path:
        sys.path.insert(0, str(hooks_scripts))
    try:
        import workspace_types  # type: ignore
        return workspace_types
    except Exception:
        return None


def _find_workspace_repos(ws: Path) -> Tuple[List[Tuple[str, Path]], Optional[str]]:
    """Git repos under the workspace as (key, path), plus an optional note.

    With the loader: `<org>/<repo>`, plus `<org>/<client>/<repo>` under a
    directory marked `type: client`, keyed by the path relative to the
    workspace (the key Overwatch reads). A client directory that is itself a
    repo is included as the flat `<org>/<dir>`, so it is still scanned.

    Without the loader: the depth-2 walk, and a note saying client
    directories are not being descended.
    """
    loader = _load_workspace_loader()
    repos: List[Tuple[str, Path]] = []
    orgs = [d for d in sorted(ws.iterdir()) if d.is_dir() and not d.name.startswith(".")]

    if loader is None:
        for org_dir in orgs:
            for repo in sorted(org_dir.iterdir()):
                if repo.is_dir() and not repo.name.startswith(".") and (repo / ".git").exists():
                    repos.append((f"{org_dir.name}/{repo.name}", repo))
        note = ("Note: the workspace layout loader could not be imported, so client "
                "directories are not being descended; only <org>/<repo> is scanned.")
        return repos, note

    for org_dir in orgs:
        found = [(p.key, p.path) for p in loader.iter_projects(org_dir)
                 if (p.path / ".git").exists()]
        found.extend((f"{org_dir.name}/{c.name}", c) for c in loader.iter_containers(org_dir)
                     if (c / ".git").exists())
        repos.extend(sorted(found))
    return repos, None


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

    repos, layout_note = _find_workspace_repos(ws)

    if not repos:
        return 0, f"No git repos found in {ws}"

    # Lazy-import the per-project state updater. Soft-failure: if the
    # overwatch module can't be loaded, we still complete the scan.
    update_scoped_state = None
    try:
        from overwatch import update_scoped_state as _uss  # type: ignore
        update_scoped_state = _uss
    except (ImportError, Exception):
        pass

    lines = []
    if layout_note:
        lines.append(layout_note)
    lines.append(f"Scanning {len(repos)} repos in {ws}...\n")
    total_findings = 0
    now = int(time.time())

    for repo_name, repo in repos:
        exit_code, report = scan_repo(repo)
        if exit_code == 0:
            # A clean repo's report is not printed, so carry the public-only
            # suppression line and any warning count onto its one line. A
            # repo with warnings (personal data in a private repo) also gets
            # its report, so the warnings can be read.
            notes = [l for l in report.splitlines()
                     if "from public-only rules suppressed" in l]
            warned = re.search(r"\b(\d+) warning\(s\)", report)
            if warned:
                notes.append(f"{warned.group(1)} warning(s)")
            lines.append(f"  {repo_name}: clean"
                         + (f" ({'; '.join(notes)})" if notes else ""))
            if warned:
                lines.append(report)
        else:
            lines.append(f"  {repo_name}: FINDINGS DETECTED")
            lines.append(report)
            total_findings += 1

        # Record per-project scan timestamp so Overwatch can see this repo
        # was scanned. The key comes from the same loader session_start.py
        # uses, so the two agree for flat and nested projects alike.
        if update_scoped_state is not None:
            try:
                update_scoped_state("projects", repo_name, "last_secret_scan", now)
            except Exception:
                pass  # Per-project update is best-effort; don't fail the scan

    lines.append(f"\nScanned {len(repos)} repos. {total_findings} with findings.")

    # Account-wide posture pass. Posture is a property of the repo on GitHub,
    # not of the working copy, so a clone-only sweep can miss an unguarded
    # public repo entirely. Soft-failure: never let this break the scan.
    try:
        from github_protections import sweep_accounts  # type: ignore

        lines.extend(sweep_accounts(ws))
    except Exception:
        pass

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
