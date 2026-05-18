#!/usr/bin/env python3
"""
Two-tier secret format library system.

Tier 1 — common_secret_formats.toml: Ships with plugin, covers universal gaps
         in gitleaks defaults. Updated via --update-formats.
Tier 2 — org_secret_formats.toml: User-managed, org-specific patterns.
         Never overwritten by plugin updates.

Storage: ~/.claude/lastmilefirst/secret-formats/
Merge order: common -> org. Rules with same id — last writer wins.
"""
from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

# Python 3.11+ has tomllib in stdlib; older versions need tomli
try:
    import tomllib
except ModuleNotFoundError:
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ModuleNotFoundError:
        tomllib = None  # type: ignore[assignment]

# Plugin data directory (ships with plugin)
PLUGIN_DATA_DIR = Path(__file__).parent.parent / "data"

# User format storage (survives plugin updates)
FORMAT_DIR = Path.home() / ".claude" / "lastmilefirst" / "secret-formats"

COMMON_FILENAME = "common_secret_formats.toml"
ORG_FILENAME = "org_secret_formats.toml"

# Global allowlist injected into every merged config. Paths matched here are
# excluded from rule scans regardless of which rules a user has loaded.
# Two purposes:
#   1. Vendor / build / cache directories that contain other people's code
#      (node_modules, .venv, vendor, etc.) — findings there are noise the
#      consumer cannot remediate
#   2. The plugin's own data/*.toml files — without this, scanning the
#      gruntwork-marketplace repo flags the rule regex patterns themselves
#
# Patterns are gitleaks-style regex matched against the full file path.
# Anchored with `(^|/)` so e.g. `dist/` doesn't also match `redistribute/`.
GLOBAL_ALLOWLIST_PATHS = [
    r"(^|/)node_modules/",
    r"(^|/)\.venv/",
    r"(^|/)venv/",
    r"(^|/)vendor/",
    r"(^|/)dist/",
    r"(^|/)build/",
    r"(^|/)\.next/",
    r"(^|/)\.terraform/",
    r"(^|/)target/",
    # Plugin's own format files — prevent self-match on regex pattern bodies
    r"plugins/lastmilefirst/skills/scan-secrets/data/.*\.toml$",
]

ORG_TEMPLATE = """\
# Organization-specific secret formats for Gitleaks
# Add your org's custom secret patterns here.
# This file is never overwritten by plugin updates.
#
# Format follows gitleaks TOML rule syntax:
#
# [[rules]]
# id = "my-org-internal-token"
# description = "Internal service token format"
# regex = '''myorg_[a-z0-9]{32}'''
# tags = ["org", "internal"]
# keywords = ["myorg_"]
#
# See: https://github.com/gitleaks/gitleaks#configuration

title = "Organization Secret Formats"

# Add your rules below:
"""


def _read_toml(path: Path) -> Dict[str, Any]:
    """Read a TOML file and return parsed dict."""
    if tomllib is None:
        # Fallback: return empty if no TOML parser available
        print(
            "Warning: No TOML parser available. Install tomli: pip install tomli",
            file=sys.stderr,
        )
        return {}
    with open(path, "rb") as f:
        return tomllib.load(f)


def ensure_format_dir() -> Path:
    """Create format directory and seed files on first run."""
    FORMAT_DIR.mkdir(parents=True, exist_ok=True)

    common_dest = FORMAT_DIR / COMMON_FILENAME
    if not common_dest.exists():
        # Copy common formats from plugin data
        common_src = PLUGIN_DATA_DIR / COMMON_FILENAME
        if common_src.exists():
            shutil.copy2(common_src, common_dest)

    org_dest = FORMAT_DIR / ORG_FILENAME
    if not org_dest.exists():
        org_dest.write_text(ORG_TEMPLATE, encoding="utf-8")

    return FORMAT_DIR


def update_common_formats() -> str:
    """Refresh common formats from plugin data without touching org file."""
    ensure_format_dir()
    common_src = PLUGIN_DATA_DIR / COMMON_FILENAME
    common_dest = FORMAT_DIR / COMMON_FILENAME

    if not common_src.exists():
        return "Error: Plugin common formats not found"

    shutil.copy2(common_src, common_dest)
    return f"Updated common formats at {common_dest}"


def load_rules() -> List[Dict[str, Any]]:
    """Load and merge rules from both tiers. Org rules override common by id."""
    fmt_dir = ensure_format_dir()

    rules_by_id: Dict[str, Dict[str, Any]] = {}

    # Tier 1: common (plugin-shipped)
    common_path = fmt_dir / COMMON_FILENAME
    if common_path.exists():
        data = _read_toml(common_path)
        for rule in data.get("rules", []):
            rule_id = rule.get("id", "")
            if rule_id:
                rule["_source"] = "common"
                rules_by_id[rule_id] = rule

    # Tier 2: org (user-managed) — last writer wins
    org_path = fmt_dir / ORG_FILENAME
    if org_path.exists():
        data = _read_toml(org_path)
        for rule in data.get("rules", []):
            rule_id = rule.get("id", "")
            if rule_id:
                rule["_source"] = "org"
                rules_by_id[rule_id] = rule

    return list(rules_by_id.values())


def list_formats() -> str:
    """List all active rules with source indicator."""
    rules = load_rules()
    if not rules:
        return "No secret format rules loaded."

    lines = [f"{'ID':<40} {'Source':<8} Description"]
    lines.append("-" * 80)

    for rule in sorted(rules, key=lambda r: r.get("id", "")):
        rid = rule.get("id", "unknown")
        source = rule.get("_source", "?")
        desc = rule.get("description", "")
        lines.append(f"{rid:<40} {source:<8} {desc}")

    lines.append(f"\nTotal: {len(rules)} rules")
    lines.append(f"Common file: {FORMAT_DIR / COMMON_FILENAME}")
    lines.append(f"Org file:    {FORMAT_DIR / ORG_FILENAME}")
    return "\n".join(lines)


def write_merged_config(extra_rules: Optional[List[Dict[str, Any]]] = None) -> Path:
    """
    Write a merged gitleaks config to a temp file for use with --config.
    Returns path to the temp config file.
    """
    rules = load_rules()
    if extra_rules:
        for rule in extra_rules:
            rules.append(rule)

    # Build TOML content manually (no toml writer dependency).
    #
    # TOML quoting choice: literal strings ('''...''') everywhere strings are
    # serialized. Basic strings (""") interpret backslash escapes — that's
    # wrong for regex (\d/\s/\+ either hard-error or silently mangle).
    #
    # Ordering invariant: scalar/list keys are emitted before any sub-tables
    # (e.g. [rules.allowlist]). TOML requires keys to belong unambiguously to
    # the most recently opened table — any scalar after a sub-table header
    # would silently bind to the wrong table.
    def fmt_string(value: str) -> str:
        return f"'''{value}'''"

    def fmt_list(values: List[Any]) -> str:
        parts = []
        for v in values:
            if isinstance(v, str):
                parts.append(fmt_string(v))
            elif isinstance(v, bool):
                parts.append("true" if v else "false")
            elif isinstance(v, (int, float)):
                parts.append(str(v))
            # Unknown element types skipped — defensive, not currently exercised.
        return "[" + ", ".join(parts) + "]"

    lines = ['title = "lastmilefirst merged secret formats"', ""]

    # Global allowlist (vendor dirs + plugin's own data files). Top-level
    # [allowlist] applies to every rule. Must come before [[rules]] arrays so
    # subsequent scalar keys don't bind to the wrong table.
    lines.append("[allowlist]")
    lines.append(
        f"description = {fmt_string('lastmilefirst global allowlist (vendor dirs + plugin data files)')}"
    )
    lines.append(f"paths = {fmt_list(GLOBAL_ALLOWLIST_PATHS)}")
    lines.append("")

    for rule in rules:
        lines.append("[[rules]]")
        sub_tables: List[tuple] = []  # (key, dict_value) emitted after scalars

        for key, value in rule.items():
            if key.startswith("_"):
                continue  # Skip internal metadata
            if isinstance(value, str):
                lines.append(f"{key} = {fmt_string(value)}")
            elif isinstance(value, bool):
                lines.append(f"{key} = {'true' if value else 'false'}")
            elif isinstance(value, (int, float)):
                lines.append(f"{key} = {value}")
            elif isinstance(value, list):
                lines.append(f"{key} = {fmt_list(value)}")
            elif isinstance(value, dict):
                sub_tables.append((key, value))
            # Unknown types skipped — defensive, not currently exercised.

        # Sub-tables must follow all scalars/lists for the parent rule, or TOML
        # parses subsequent scalars as belonging to the sub-table.
        for sub_key, sub_dict in sub_tables:
            lines.append(f"[rules.{sub_key}]")
            for inner_key, inner_value in sub_dict.items():
                if isinstance(inner_value, str):
                    lines.append(f"{inner_key} = {fmt_string(inner_value)}")
                elif isinstance(inner_value, bool):
                    lines.append(f"{inner_key} = {'true' if inner_value else 'false'}")
                elif isinstance(inner_value, (int, float)):
                    lines.append(f"{inner_key} = {inner_value}")
                elif isinstance(inner_value, list):
                    lines.append(f"{inner_key} = {fmt_list(inner_value)}")
                # Nested-nested dicts not currently exercised; skipped.

        lines.append("")

    # Write to temp file
    tmp = tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".toml",
        prefix="gitleaks-lmf-",
        delete=False,
        encoding="utf-8",
    )
    tmp.write("\n".join(lines))
    tmp.close()
    return Path(tmp.name)


def get_org_formats_path() -> Path:
    """Return path to org formats file (for --add-format interactive editing)."""
    ensure_format_dir()
    return FORMAT_DIR / ORG_FILENAME
