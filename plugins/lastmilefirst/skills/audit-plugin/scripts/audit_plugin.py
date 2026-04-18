#!/usr/bin/env python3
"""LMF audit-plugin wrapper — shells out to Griffith and renders results in session.

Griffith is the analyzer; this script is a thin adapter that:
1. Discovers the griffith binary (PATH → dev-mode venv → error)
2. Shells out to `griffith analyze <source> --json` with optional flags
3. Parses the JSON, validates schema_version
4. Renders a structured summary to stdout for display in the Claude session
5. Wraps untrusted content (plugin names, findings paths, notes) in escaped
   code fences so it cannot prompt-inject the surrounding Claude session

Usage:
    python audit_plugin.py <source>
    python audit_plugin.py <source> --strict
    python audit_plugin.py <source> --json      # emit raw Griffith JSON
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

DEV_GRIFFITH = Path.home() / "Code" / "gruntwork" / "gruntwork-griffith" / ".venv" / "bin" / "griffith"
SUPPORTED_SCHEMA_VERSIONS = {"0.1"}


def find_griffith() -> Path | None:
    """Return the griffith binary path: PATH first, then the dev-mode venv."""
    on_path = shutil.which("griffith")
    if on_path:
        return Path(on_path)
    if DEV_GRIFFITH.exists():
        return DEV_GRIFFITH
    return None


def run_griffith(griffith: Path, source: str, strict: bool) -> tuple[dict, int]:
    """Invoke `griffith analyze <source> --json`; return (parsed_json, exit_code)."""
    cmd = [str(griffith), "analyze", source, "--json"]
    if strict:
        cmd.append("--strict")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"griffith analyze failed (exit {result.returncode}):", file=sys.stderr)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        return {}, result.returncode
    try:
        return json.loads(result.stdout), 0
    except json.JSONDecodeError as e:
        print(f"griffith returned invalid JSON: {e}", file=sys.stderr)
        print(f"stdout (first 500 chars):\n{result.stdout[:500]}", file=sys.stderr)
        return {}, 1


def render_single(report: dict) -> None:
    """Render a single-plugin report as markdown for session display."""
    plugin = report["plugin"]
    print(f"# Plugin Audit: `{_esc(plugin['name'])}`\n")
    print(f"**Source:** `{_esc(plugin['source'])}`  ")
    print(f"**Griffith:** {report['meta']['griffith_version']} "
          f"(schema {report['schema_version']} — unstable)\n")

    _render_risk_banner(report["security"])
    print()

    _render_inventory(report["inventory"])
    print()

    _render_security_summary(report["security"])
    print()

    _render_footprint(report["footprint"])
    print()

    _render_architecture(report["architecture"])
    print()

    if report["security"]["findings"]:
        _render_findings_detail(report["security"]["findings"])
        print()

    _render_footer(report)


def render_marketplace(report: dict) -> None:
    """Render a marketplace report: summary table + one section per plugin."""
    market = report["marketplace"]
    summary = report["summary"]
    print(f"# Marketplace Audit: `{_esc(market['source'])}`\n")
    print(f"**{summary['plugin_count']} plugin(s) analyzed.**  \n")

    print("## Summary\n")
    print("| Dimension | Counts |")
    print("|-----------|--------|")
    risk_counts = summary["risk_level_counts"]
    pattern_counts = summary["patterns"]
    print(f"| Risk levels | {_dict_to_inline(risk_counts)} |")
    print(f"| Patterns | {_dict_to_inline(pattern_counts)} |")
    print()

    for i, plugin_report in enumerate(report["reports"], 1):
        print(f"---\n\n## Plugin {i} of {summary['plugin_count']}\n")
        render_single(plugin_report)


def _render_risk_banner(security: dict) -> None:
    risk = security["risk_level"]
    count = security["finding_count"]
    badge = {
        "critical": "🔴 **CRITICAL**",
        "high": "🟠 **HIGH**",
        "medium": "🟡 MEDIUM",
        "low": "🔵 LOW",
        "info": "⚪ INFO",
        "none": "🟢 CLEAN",
    }.get(risk, risk.upper())
    print(f"**Risk level:** {badge}  ({count} finding{'s' if count != 1 else ''})")


def _render_inventory(inv: dict) -> None:
    print("## Inventory\n")
    print("| Type | Count |")
    print("|------|------:|")
    counts = inv["counts"]
    for key in ("agents", "commands", "skills", "hooks", "mcp_servers", "personas", "templates", "unknown"):
        v = counts.get(key, 0)
        marker = "" if v > 0 else " *(none)*"
        print(f"| {key} | {v}{marker} |")
    print(f"| **total files** | **{inv['totals']['files']}** |")
    print(f"| **total lines** | **{inv['totals']['lines']:,}** |")


def _render_security_summary(security: dict) -> None:
    print("## Security\n")
    by_sev: dict[str, int] = {}
    for f in security["findings"]:
        by_sev[f["severity"]] = by_sev.get(f["severity"], 0) + 1
    if not by_sev:
        print("No findings. Scan scope: static analysis only (no LLM-based review).")
        return
    print("| Severity | Count |")
    print("|----------|------:|")
    for sev in ("critical", "high", "medium", "low", "info"):
        if sev in by_sev:
            print(f"| {sev} | {by_sev[sev]} |")


def _render_footprint(fp: dict) -> None:
    print("## Footprint\n")
    print(f"- **Efficiency:** `{fp['efficiency_rating']}`")
    print(f"- **Baseline:** {fp['baseline_tokens_approx_cl100k']:,} tokens "
          f"*(approx cl100k — not Claude's tokenizer)*")
    print(f"- **On-demand max:** {fp['on_demand_max']:,} tokens")
    print(f"- **Primary driver:** `{fp['primary_driver']}`")
    if fp["per_component"]:
        parts = [f"{k}={v:,}" for k, v in
                 sorted(fp["per_component"].items(), key=lambda kv: -kv[1]) if v > 0]
        if parts:
            print(f"- **Breakdown:** {' · '.join(parts)}")


def _render_architecture(arch: dict) -> None:
    print("## Architecture\n")
    print(f"**Pattern:** `{arch['pattern']}`\n")
    if arch["efficiency_notes"]:
        print("**Notes:**\n")
        for note in arch["efficiency_notes"]:
            # Notes are derived from the cost model (not untrusted) — safe as-is.
            print(f"- {note}")
        print()
    if arch["recommendations"]:
        print("**Recommendations:**\n")
        for rec in arch["recommendations"]:
            print(f"- {rec}")


def _render_findings_detail(findings: list[dict], cap_per_severity: int = 10) -> None:
    """Show findings grouped by severity, with per-group cap."""
    print("## Findings Detail\n")
    by_sev: dict[str, list[dict]] = {}
    for f in findings:
        by_sev.setdefault(f["severity"], []).append(f)
    for sev in ("critical", "high", "medium", "low", "info"):
        group = by_sev.get(sev)
        if not group:
            continue
        print(f"### {sev} ({len(group)})\n")
        for f in group[:cap_per_severity]:
            # file path and message are untrusted — escape inside code fence
            print(f"- `{_esc(f['file'])}:{f['line']}` — `{f['rule_id']}`")
            print(f"    - {_esc(f['message'])}")
        if len(group) > cap_per_severity:
            print(f"- *…and {len(group) - cap_per_severity} more (use `--json` for full list)*")
        print()


def _render_footer(report: dict) -> None:
    meta = report["meta"]
    print("---")
    print(f"*Analyzed {meta['analyzed_at']} · "
          f"scope: {', '.join(report['analysis_scope'])} · "
          f"hardening v{meta['griffith_hardening_version']}*")


def _esc(s: Any) -> str:
    """Escape a string so it can't break out of a code fence or interpret as Markdown."""
    if s is None:
        return ""
    s = str(s)
    # Backticks → escape; newlines → spaces; strip ANSI/bidi already stripped by griffith
    return s.replace("`", "'").replace("\n", " ").replace("\r", " ")


def _dict_to_inline(d: dict) -> str:
    if not d:
        return "(none)"
    return " · ".join(f"`{k}`: {v}" for k, v in d.items())


def _print_install_instructions() -> None:
    print("ERROR: `griffith` not found.", file=sys.stderr)
    print("", file=sys.stderr)
    print("Install options:", file=sys.stderr)
    print("  1. Dev install:", file=sys.stderr)
    print("     git clone https://github.com/GruntworkAI/gruntwork-griffith", file=sys.stderr)
    print("     cd gruntwork-griffith && poetry install", file=sys.stderr)
    print("", file=sys.stderr)
    print("  2. Or add the poetry venv's griffith to PATH:", file=sys.stderr)
    print(f"     export PATH={DEV_GRIFFITH.parent}:$PATH", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit a Claude Code plugin via Griffith.",
    )
    parser.add_argument("source", help="Plugin source: URL, owner/repo, or local path")
    parser.add_argument(
        "--strict", action="store_true", help="Enable broader security rules"
    )
    parser.add_argument(
        "--json",
        dest="as_json",
        action="store_true",
        help="Emit raw Griffith JSON instead of rendered markdown",
    )
    args = parser.parse_args()

    griffith = find_griffith()
    if griffith is None:
        _print_install_instructions()
        return 1

    report, exit_code = run_griffith(griffith, args.source, args.strict)
    if exit_code != 0:
        return exit_code

    # Verify schema compatibility
    schema_version = report.get("schema_version", "")
    if schema_version not in SUPPORTED_SCHEMA_VERSIONS:
        print(
            f"WARNING: griffith returned schema_version={schema_version!r} "
            f"but this wrapper supports {sorted(SUPPORTED_SCHEMA_VERSIONS)}. "
            "Output may be incomplete.",
            file=sys.stderr,
        )

    if args.as_json:
        json.dump(report, sys.stdout, indent=2)
        print()
        return 0

    if "marketplace" in report:
        render_marketplace(report)
    else:
        render_single(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
