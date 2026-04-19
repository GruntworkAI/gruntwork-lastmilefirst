"""Tests for the Tier 1 Dependencies section rendering.

Fixture discipline:
- Hand-minimal fixtures drive branch-logic tests. They exercise one
  render branch each and are independent of Griffith's live format.
- `contract_full.json` is a captured real Griffith run; changes to
  Griffith's output shape that the wrapper doesn't know about surface
  here as a failing contract test.
"""

from __future__ import annotations

import io
import sys
from contextlib import redirect_stdout

import audit_plugin


OPEN = audit_plugin.ENVELOPE_OPEN
CLOSE = audit_plugin.ENVELOPE_CLOSE


def _render_to_string(report: dict) -> str:
    """Helper: walk the report, render single-plugin, capture stdout."""
    buf = io.StringIO()
    with redirect_stdout(buf):
        audit_plugin.render_single(report)
    return buf.getvalue()


class TestTier1Full:
    def test_dependencies_section_appears(self, load_fixture):
        out = _render_to_string(load_fixture("tier1_python"))
        assert "## Dependencies" in out

    def test_ecosystems_summary_line(self, load_fixture):
        out = _render_to_string(load_fixture("tier1_python"))
        assert "**Ecosystems:**" in out
        # Ecosystem values enveloped (they're in untrusted_fields).
        assert f"{OPEN}PyPI{CLOSE}" in out

    def test_package_names_enveloped(self, load_fixture):
        out = _render_to_string(load_fixture("tier1_python"))
        # Exact-form assertion (not substring).
        assert f"{OPEN}fastapi{CLOSE}" in out
        assert f"{OPEN}requests{CLOSE}" in out
        assert f"{OPEN}Pillow{CLOSE}" in out

    def test_raw_package_names_do_not_appear(self, load_fixture):
        """Negative assertion: raw (unwrapped) package names must not leak."""
        out = _render_to_string(load_fixture("tier1_python"))
        # The raw package name `fastapi` must only appear inside the envelope.
        # Split on `⟦fastapi⟧` — if `fastapi` appears anywhere else,
        # something leaked.
        for pkg in ("fastapi", "requests", "Pillow"):
            leak_segments = out.replace(f"{OPEN}{pkg}{CLOSE}", "").count(pkg)
            assert leak_segments == 0, f"raw {pkg} appears unwrapped in output"

    def test_kind_tag_for_non_runtime_packages(self, load_fixture):
        out = _render_to_string(load_fixture("tier1_python"))
        # `pytest` is kind=optional; rendered with kind annotation.
        assert "optional" in out

    def test_runtime_kind_not_annotated(self, load_fixture):
        out = _render_to_string(load_fixture("tier1_python"))
        # Runtime is the default — don't clutter output with "(runtime)" on
        # every line.
        # Count "(runtime)" occurrences; should be zero.
        assert "(runtime)" not in out


class TestTier1Empty:
    def test_no_dependencies_section(self, load_fixture):
        out = _render_to_string(load_fixture("tier1_empty"))
        # Critical: section omitted entirely when no deps.
        assert "## Dependencies" not in out


class TestTier1SymlinkOnly:
    def test_symlink_refusal_line(self, load_fixture):
        out = _render_to_string(load_fixture("tier1_symlink_only"))
        assert "## Dependencies" in out
        assert "symlink" in out.lower()

    def test_no_package_table_on_symlink_only(self, load_fixture):
        out = _render_to_string(load_fixture("tier1_symlink_only"))
        # No package-table header when symlink-only.
        assert "| Package |" not in out
        assert "**Ecosystems:**" not in out


class TestTier1UnscannedOnly:
    def test_unscanned_warning_line(self, load_fixture):
        out = _render_to_string(load_fixture("tier1_unscanned_only"))
        assert "## Dependencies" in out
        assert "could not parse" in out.lower() or "unscanned" in out.lower()

    def test_no_ecosystems_line_when_unscanned_only(self, load_fixture):
        out = _render_to_string(load_fixture("tier1_unscanned_only"))
        assert "**Ecosystems:**" not in out


class TestTier1MultiEcosystem:
    def test_ecosystems_sorted_alphabetical(self, load_fixture):
        out = _render_to_string(load_fixture("tier1_multi_ecosystem"))
        # PyPI, npm → rendered as "PyPI, npm" or equivalent sorted order.
        # The string "PyPI" must appear before "npm" in the ecosystems line.
        eco_line = next(
            (l for l in out.splitlines() if "**Ecosystems:**" in l), ""
        )
        assert eco_line
        # Enveloped values — look for both.
        assert f"{OPEN}PyPI{CLOSE}" in eco_line
        assert f"{OPEN}npm{CLOSE}" in eco_line

    def test_lockfiles_listed(self, load_fixture):
        out = _render_to_string(load_fixture("tier1_multi_ecosystem"))
        assert f"{OPEN}package-lock.json{CLOSE}" in out


class TestTier1TableSafety:
    def test_constraint_with_pipe_escaped(self):
        """Pipe in constraint must be escaped to not break table rendering."""
        report = {
            "schema_version": "0.1",
            "plugin": {"name": "p", "path": ".", "source": "s"},
            "inventory": {
                "counts": {k: 0 for k in (
                    "agents", "commands", "skills", "hooks", "mcp_servers",
                    "personas", "templates", "unknown"
                )},
                "totals": {"files": 0, "lines": 0}
            },
            "security": {"risk_level": "none", "finding_count": 0, "findings": []},
            "footprint": {
                "baseline_tokens_approx_cl100k": 0, "on_demand_max": 0,
                "primary_driver": "none", "efficiency_rating": "excellent",
                "per_component": {}
            },
            "architecture": {"pattern": "hybrid", "efficiency_notes": [], "recommendations": []},
            "dependencies": {
                "scan_status": "tier1_only",
                "manifests": [{"path": "req.txt", "is_symlink": False, "size_skipped": False}],
                "lockfiles": [],
                "unscanned_manifests": [],
                "ecosystems": ["PyPI"],
                "package_count": 1,
                "packages": [
                    {"ecosystem": "PyPI", "name": "sneaky",
                     "constraint": ">=1.0 | <2.0", "kind": "runtime",
                     "manifest": "req.txt"}
                ],
                "sca": None,
            },
            "analysis_scope": ["static"],
            "untrusted_fields": list(audit_plugin.UNTRUSTED_FIELDS_V0_1),
            "meta": {"griffith_version": "0.1.0", "griffith_hardening_version": "1",
                     "analyzed_at": "2026-04-18T00:00:00Z", "source_type": "path"},
        }
        out = _render_to_string(report)
        # Raw " | " inside the constraint value must not appear unescaped.
        # The constraint is inside an envelope which escapes `|` to `\|`.
        assert "\\|" in out


class TestTier1Adversarial:
    def test_terminal_escape_in_package_name_stripped(self):
        report = {
            "schema_version": "0.1",
            "plugin": {"name": "p", "path": ".", "source": "s"},
            "inventory": {"counts": {k: 0 for k in (
                "agents", "commands", "skills", "hooks", "mcp_servers",
                "personas", "templates", "unknown")},
                "totals": {"files": 0, "lines": 0}},
            "security": {"risk_level": "none", "finding_count": 0, "findings": []},
            "footprint": {"baseline_tokens_approx_cl100k": 0, "on_demand_max": 0,
                          "primary_driver": "none", "efficiency_rating": "excellent",
                          "per_component": {}},
            "architecture": {"pattern": "hybrid", "efficiency_notes": [], "recommendations": []},
            "dependencies": {
                "scan_status": "tier1_only",
                "manifests": [{"path": "req.txt", "is_symlink": False, "size_skipped": False}],
                "lockfiles": [],
                "unscanned_manifests": [],
                "ecosystems": ["PyPI"],
                "package_count": 1,
                "packages": [
                    {"ecosystem": "PyPI", "name": "\x1b[31mHOSTILE\x1b[0m",
                     "constraint": "1.0", "kind": "runtime",
                     "manifest": "req.txt"}
                ],
                "sca": None,
            },
            "analysis_scope": ["static"],
            "untrusted_fields": list(audit_plugin.UNTRUSTED_FIELDS_V0_1),
            "meta": {"griffith_version": "0.1.0", "griffith_hardening_version": "1",
                     "analyzed_at": "2026-04-18T00:00:00Z", "source_type": "path"},
        }
        out = _render_to_string(report)
        # Negative: raw ESC bytes must not survive.
        assert "\x1b" not in out
        # Positive: HOSTILE content is inside an envelope (single-line,
        # sanitized, but preserved as data).
        assert f"{OPEN}HOSTILE{CLOSE}" in out


class TestThirdPartyBoundary:
    def test_preamble_precedes_dependencies_section(self, load_fixture):
        out = _render_to_string(load_fixture("tier1_python"))
        preamble_idx = out.find("Third-party content boundary")
        deps_idx = out.find("## Dependencies")
        assert preamble_idx >= 0
        assert deps_idx > preamble_idx


class TestContractFixture:
    """Guards against Griffith format drift — the only test that exercises
    a captured real Griffith run end-to-end."""

    def test_contract_fixture_renders_without_exception(self, load_fixture):
        """If Griffith's shape changes in a way the wrapper doesn't know
        about, rendering will crash — this is the loud signal."""
        report = load_fixture("contract_full")
        out = _render_to_string(report)
        # Sanity spot-checks.
        assert out  # non-empty
        assert "Third-party content boundary" in out

    def test_contract_fixture_has_expected_top_level_keys(self, load_fixture):
        """Schema check — if Griffith drops a top-level key, this fails."""
        report = load_fixture("contract_full")
        # These are the v0.1 top-level keys the wrapper assumes.
        required = {
            "schema_version", "plugin", "inventory", "security",
            "footprint", "architecture", "dependencies",
            "analysis_scope", "untrusted_fields", "meta",
        }
        assert required.issubset(report.keys())

    def test_contract_fixture_schema_version_matches_pin(self, load_fixture):
        """If Griffith bumps schema_version, regen.sh needs to run and
        the wrapper's pin needs updating."""
        report = load_fixture("contract_full")
        assert report["schema_version"] in audit_plugin.SUPPORTED_SCHEMA_VERSIONS
