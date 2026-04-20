"""Tests for code-review majors on feat/audit-plugin-phase-1.5.

Covers:
- **osv_scanner_version envelope** — `dependencies.sca.osv_scanner_version`
  is produced by the osv-scanner binary's output; it's registry-controlled
  and must not render raw. Same class as the B-1 blocker fix for
  plugin.source/path.
- **GRIFFITH_ERR_CODES enforcement** — `_emit_griffith_err` validates
  the code against the declared frozenset. Typos at emit sites raise
  instead of silently shipping an unknown code.
- **run_griffith exit-code table extraction** — griffith→wrapper exit
  code mapping extracted to a module-level dict so the single source of
  truth lives next to the GRIFFITH_ERR_CODES enum.
- **Cache mtime surface** — agent-summary exposes `cache_mtime` (unix
  epoch seconds) so the consumer can decide staleness. Cache path alone
  doesn't tell them when the file was written.
- **render_single / _render_single_no_walk duplication** — shared
  plugin-body rendering extracted into `_render_plugin_body(enveloped)`
  helper; both call sites use it. The only differences (preamble
  placement, pre-walk step) stay in the outer functions.
"""

from __future__ import annotations

import io
import json
import os
import time
from contextlib import redirect_stdout
from pathlib import Path

import pytest

import audit_plugin


OPEN = audit_plugin.ENVELOPE_OPEN
CLOSE = audit_plugin.ENVELOPE_CLOSE


# ============================================================================
# osv_scanner_version envelope
# ============================================================================


class TestOsvScannerVersionEnveloped:
    def test_path_in_untrusted_list(self):
        assert (
            "dependencies.sca.osv_scanner_version"
            in audit_plugin.UNTRUSTED_FIELDS_V0_1
        )

    def test_nested_in_marketplace_paths(self):
        """reports[].dependencies.sca.osv_scanner_version must be
        enveloped in marketplace reports too (registry-controlled per-
        plugin CVE scan)."""
        assert (
            "reports[].dependencies.sca.osv_scanner_version"
            in audit_plugin.UNTRUSTED_FIELDS_V0_1
        )

    def test_rendered_version_is_enveloped(self, load_fixture):
        """Smoke test: a single-plugin report with a scanner version
        renders with the version wrapped in envelope markers."""
        report = _minimal_report_with_sca_version("1.9.2-evil\x1b[31m")
        buf = io.StringIO()
        with redirect_stdout(buf):
            audit_plugin.render_single(report)
        out = buf.getvalue()
        # ANSI stripped + wrapped. Raw escape byte must not appear.
        assert "\x1b" not in out
        # Envelope around the (sanitized) version — the raw version
        # string should only appear inside the envelope markers.
        assert f"{OPEN}1.9.2-evil{CLOSE}" in out or "1.9.2-evil" not in out.replace(
            f"{OPEN}1.9.2-evil{CLOSE}", ""
        )


def _minimal_report_with_sca_version(version: str) -> dict:
    return {
        "schema_version": "0.1",
        "plugin": {
            "name": "deps-demo",
            "source": "/tmp/demo",
            "path": "/tmp/demo",
        },
        "inventory": {
            "counts": {
                "agents": 0, "commands": 0, "skills": 0, "hooks": 0,
                "mcp_servers": 0, "personas": 0, "templates": 0, "unknown": 0,
            },
            "totals": {"files": 0, "lines": 0},
        },
        "security": {"risk_level": "none", "finding_count": 0, "findings": []},
        "footprint": {
            "baseline_tokens_approx_cl100k": 0,
            "on_demand_max": 0,
            "primary_driver": "agents",
            "efficiency_rating": "excellent",
            "per_component": {
                "agents": 0, "commands": 0, "skills": 0, "hooks": 0, "mcp_servers": 0,
            },
        },
        "architecture": {
            "pattern": "hybrid",
            "efficiency_notes": [],
            "recommendations": [],
        },
        "dependencies": {
            "scan_status": "sca_ok_clean",
            "manifests": [],
            "lockfiles": [],
            "unscanned_manifests": [],
            "ecosystems": [],
            "package_count": 0,
            "packages": [],
            "sca": {
                "scan_status": "sca_ok_clean",
                "osv_scanner_version": version,
                "vulnerabilities": [],
                "error": None,
            },
        },
        "analysis_scope": ["static"],
        "untrusted_fields": [],
        "meta": {
            "griffith_version": "0.1.0",
            "griffith_hardening_version": "1",
            "analyzed_at": "2026-04-20T00:00:00Z",
            "source_type": "path",
        },
    }


# ============================================================================
# GRIFFITH_ERR_CODES enforcement
# ============================================================================


class TestGriffithErrCodesEnforced:
    def test_known_code_succeeds(self, capsys):
        """Emitting a valid code works normally — no exception."""
        audit_plugin._emit_griffith_err(
            "TIMEOUT", "subprocess", "example remediation"
        )
        # Stderr got the sentinel.
        captured = capsys.readouterr()
        assert "GRIFFITH_ERR:" in captured.err
        assert '"code":"TIMEOUT"' in captured.err

    def test_unknown_code_raises(self):
        """Emitting an unknown code raises — a typo at a call site
        would otherwise ship a sentinel Claude can't dispatch on."""
        with pytest.raises((ValueError, AssertionError)):
            audit_plugin._emit_griffith_err(
                "TIMEOUTT", "subprocess", "typo"
            )

    def test_all_declared_codes_valid(self):
        """Every code in the enum must be emittable without raising."""
        for code in audit_plugin.GRIFFITH_ERR_CODES:
            # Should not raise.
            audit_plugin._emit_griffith_err(code, "test", "test")


# ============================================================================
# run_griffith exit-code table extraction
# ============================================================================


class TestExitCodeTable:
    def test_table_constant_exists(self):
        """Exit-code mapping lives in a module-level dict so the table
        is a single source of truth, not scattered across if/elif."""
        assert hasattr(audit_plugin, "_GRIFFITH_EXIT_CODE_MAP") or hasattr(
            audit_plugin, "GRIFFITH_EXIT_CODE_MAP"
        )

    def test_table_covers_known_griffith_codes(self):
        """Explicit entries for 0 (success), 1 (generic), 2 (osv-scanner
        missing)."""
        table = getattr(
            audit_plugin,
            "_GRIFFITH_EXIT_CODE_MAP",
            getattr(audit_plugin, "GRIFFITH_EXIT_CODE_MAP", None),
        )
        assert 0 in table
        assert 1 in table
        assert 2 in table


# ============================================================================
# Cache mtime surface (agent-summary)
# ============================================================================


class TestCacheMtimeInAgentSummary:
    def test_agent_summary_includes_cache_mtime_when_cache_exists(
        self, tmp_path: Path, capsys
    ):
        """agent-summary output exposes `cache_mtime` (unix epoch) when a
        cache file exists, so the consumer can gate staleness."""
        cache_file = tmp_path / "cached.json"
        cache_file.write_text('{"test": 1}\n')
        # Make mtime predictable.
        known_ts = 1713600000
        os.utime(cache_file, (known_ts, known_ts))

        report = _minimal_report_with_sca_version("1.0.0")
        audit_plugin.emit_agent_summary(
            report, wrapper_exit_code=0, cache_path=str(cache_file)
        )
        captured = capsys.readouterr()
        summary = json.loads(captured.out)
        assert "cache_mtime" in summary
        assert summary["cache_mtime"] == known_ts

    def test_agent_summary_cache_mtime_null_when_no_cache(self, capsys):
        """No cache_path → cache_mtime is null (not missing), so the
        schema stays stable for consumers."""
        report = _minimal_report_with_sca_version("1.0.0")
        audit_plugin.emit_agent_summary(
            report, wrapper_exit_code=0, cache_path=None
        )
        captured = capsys.readouterr()
        summary = json.loads(captured.out)
        assert "cache_mtime" in summary
        assert summary["cache_mtime"] is None

    def test_agent_summary_cache_mtime_null_when_cache_missing(
        self, tmp_path: Path, capsys
    ):
        """cache_path points to a non-existent file → cache_mtime null.
        Defensive: writer may have failed and the orchestrator already
        handles that, but emit_agent_summary must not crash."""
        report = _minimal_report_with_sca_version("1.0.0")
        missing = tmp_path / "never_written.json"
        audit_plugin.emit_agent_summary(
            report,
            wrapper_exit_code=0,
            cache_path=str(missing),
        )
        captured = capsys.readouterr()
        summary = json.loads(captured.out)
        assert summary["cache_mtime"] is None


# ============================================================================
# render_single / _render_single_no_walk duplication
# ============================================================================


class TestRenderPluginBodyShared:
    def test_single_and_marketplace_render_identical_body(self, capsys):
        """A plugin rendered standalone and the same plugin rendered as
        part of a marketplace report must produce the same body content
        (inventory, security, footprint, architecture, dependencies,
        findings, footer). Only the marketplace wrapper adds its own
        header + summary + separator line."""
        report = _minimal_report_with_sca_version("1.0.0")

        # Standalone render.
        buf_single = io.StringIO()
        with redirect_stdout(buf_single):
            audit_plugin.render_single(report)
        standalone = buf_single.getvalue()

        # Marketplace render containing the same report.
        marketplace_report = {
            "schema_version": "0.1",
            "marketplace": {"source": "example", "path": "/tmp/ex"},
            "summary": {
                "plugin_count": 1,
                "risk_level_counts": {
                    "critical": 0, "high": 0, "medium": 0,
                    "low": 0, "info": 0, "none": 1,
                },
                "patterns": {},
            },
            "reports": [report],
            "analysis_scope": ["static"],
            "untrusted_fields": [],
            "meta": {
                "griffith_version": "0.1.0",
                "griffith_hardening_version": "1",
                "analyzed_at": "2026-04-20T00:00:00Z",
                "source_type": "marketplace",
            },
        }
        buf_market = io.StringIO()
        with redirect_stdout(buf_market):
            audit_plugin.render_marketplace(marketplace_report)
        marketplace = buf_market.getvalue()

        # Section headers that both paths must render (dependencies
        # omit when manifests/lockfiles/packages/unscanned are all
        # empty; this report has them empty, so Dependencies is NOT
        # asserted — the point is shape parity, not a checklist).
        for section in [
            "## Inventory",
            "## Security",
            "## Footprint",
            "## Architecture",
        ]:
            assert section in standalone, f"standalone missing {section}"
            assert section in marketplace, f"marketplace missing {section}"

        # Direct shape parity: the body content shared between both
        # renders (everything after plugin header through footer) must
        # match byte-for-byte. This is the real regression guard.
        def _extract_body(text: str) -> str:
            # Drop preamble (standalone has it; marketplace doesn't
            # emit per-plugin). Start at "## Inventory".
            start = text.index("## Inventory")
            return text[start:]

        assert _extract_body(standalone) == _extract_body(marketplace)

    def test_shared_helper_exists(self):
        """A shared rendering helper exists so render_single and
        _render_single_no_walk don't drift."""
        assert hasattr(audit_plugin, "_render_plugin_body")
