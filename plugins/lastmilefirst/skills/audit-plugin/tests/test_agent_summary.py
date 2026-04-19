"""Tests for --agent-summary output mode — the structured surface for Claude.

Agent-summary JSON shape (fields required):

    {
      "schema_version": "0.1",
      "wrapper_exit_code": 0,
      "verdict": "safe" | "review" | "block",
      "risk_tier": "none" | "low" | "medium" | "high" | "critical",
      "counts_by_severity": {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0},
      "top_findings": [{"file": "⟦...⟧", "rule_id": "...", "severity": "...", "message": "..."}, ...],
      "cve_counts_by_severity": {...},  // only when sca present
      "top_cves": [...],                // only when sca present
      "remediation_hints": ["install_osv_scanner", ...],
      "cache_path": "/path/to/cached.json" | null,
      "scan_status": "tier1_only" | "ok" | ...
    }
"""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout

import audit_plugin


OPEN = audit_plugin.ENVELOPE_OPEN
CLOSE = audit_plugin.ENVELOPE_CLOSE


def _build_summary(report: dict, wrapper_exit_code: int = 0, cache_path: str | None = None) -> dict:
    """Helper: invoke the agent-summary builder and return parsed JSON."""
    buf = io.StringIO()
    with redirect_stdout(buf):
        audit_plugin.emit_agent_summary(report, wrapper_exit_code=wrapper_exit_code, cache_path=cache_path)
    return json.loads(buf.getvalue())


class TestAgentSummaryShape:
    def test_required_keys_present(self, load_fixture):
        report = load_fixture("tier1_python")
        summary = _build_summary(report)
        for key in (
            "schema_version", "wrapper_exit_code",
            "verdict", "risk_tier", "counts_by_severity",
            "top_findings", "remediation_hints",
            "cache_path", "scan_status",
        ):
            assert key in summary, f"missing key {key}"

    def test_schema_version_passed_through(self, load_fixture):
        summary = _build_summary(load_fixture("tier1_python"))
        assert summary["schema_version"] == "0.1"


class TestVerdict:
    def test_clean_plugin_verdict_safe(self, load_fixture):
        summary = _build_summary(load_fixture("tier1_empty"))
        assert summary["verdict"] == "safe"
        assert summary["risk_tier"] == "none"

    def test_plugin_with_critical_findings_verdict_block(self):
        report = {
            "schema_version": "0.1",
            "plugin": {"name": "p", "path": ".", "source": "s"},
            "inventory": {"counts": {k: 0 for k in (
                "agents", "commands", "skills", "hooks", "mcp_servers",
                "personas", "templates", "unknown")},
                "totals": {"files": 0, "lines": 0}},
            "security": {
                "risk_level": "critical",
                "finding_count": 1,
                "findings": [{"rule_id": "rce", "severity": "critical",
                              "file": "hooks/evil.sh", "line": 1,
                              "message": "remote code execution"}],
            },
            "footprint": {"baseline_tokens_approx_cl100k": 0, "on_demand_max": 0,
                          "primary_driver": "none", "efficiency_rating": "excellent",
                          "per_component": {}},
            "architecture": {"pattern": "hybrid", "efficiency_notes": [], "recommendations": []},
            "dependencies": {"scan_status": "tier1_only", "manifests": [], "lockfiles": [],
                             "unscanned_manifests": [], "ecosystems": [], "package_count": 0,
                             "packages": [], "sca": None},
            "analysis_scope": ["static"],
            "untrusted_fields": list(audit_plugin.UNTRUSTED_FIELDS_V0_1),
            "meta": {"griffith_version": "0.1.0", "griffith_hardening_version": "1",
                     "analyzed_at": "2026-04-18T00:00:00Z", "source_type": "path"},
        }
        summary = _build_summary(report)
        assert summary["verdict"] == "block"
        assert summary["risk_tier"] == "critical"

    def test_plugin_with_medium_findings_verdict_review(self):
        report = {
            "schema_version": "0.1",
            "plugin": {"name": "p", "path": ".", "source": "s"},
            "inventory": {"counts": {k: 0 for k in (
                "agents", "commands", "skills", "hooks", "mcp_servers",
                "personas", "templates", "unknown")},
                "totals": {"files": 0, "lines": 0}},
            "security": {
                "risk_level": "medium",
                "finding_count": 1,
                "findings": [{"rule_id": "x", "severity": "medium",
                              "file": "y", "line": 1, "message": "m"}],
            },
            "footprint": {"baseline_tokens_approx_cl100k": 0, "on_demand_max": 0,
                          "primary_driver": "none", "efficiency_rating": "excellent",
                          "per_component": {}},
            "architecture": {"pattern": "hybrid", "efficiency_notes": [], "recommendations": []},
            "dependencies": {"scan_status": "tier1_only", "manifests": [], "lockfiles": [],
                             "unscanned_manifests": [], "ecosystems": [], "package_count": 0,
                             "packages": [], "sca": None},
            "analysis_scope": ["static"],
            "untrusted_fields": list(audit_plugin.UNTRUSTED_FIELDS_V0_1),
            "meta": {"griffith_version": "0.1.0", "griffith_hardening_version": "1",
                     "analyzed_at": "2026-04-18T00:00:00Z", "source_type": "path"},
        }
        summary = _build_summary(report)
        assert summary["verdict"] == "review"


class TestCountsAndFindings:
    def test_counts_by_severity_reflects_findings(self):
        report = {
            "schema_version": "0.1",
            "plugin": {"name": "p", "path": ".", "source": "s"},
            "inventory": {"counts": {k: 0 for k in (
                "agents", "commands", "skills", "hooks", "mcp_servers",
                "personas", "templates", "unknown")},
                "totals": {"files": 0, "lines": 0}},
            "security": {
                "risk_level": "high",
                "finding_count": 3,
                "findings": [
                    {"rule_id": "a", "severity": "high", "file": "f1", "line": 1, "message": "m"},
                    {"rule_id": "b", "severity": "medium", "file": "f2", "line": 1, "message": "m"},
                    {"rule_id": "c", "severity": "medium", "file": "f3", "line": 1, "message": "m"},
                ],
            },
            "footprint": {"baseline_tokens_approx_cl100k": 0, "on_demand_max": 0,
                          "primary_driver": "none", "efficiency_rating": "excellent",
                          "per_component": {}},
            "architecture": {"pattern": "hybrid", "efficiency_notes": [], "recommendations": []},
            "dependencies": {"scan_status": "tier1_only", "manifests": [], "lockfiles": [],
                             "unscanned_manifests": [], "ecosystems": [], "package_count": 0,
                             "packages": [], "sca": None},
            "analysis_scope": ["static"],
            "untrusted_fields": list(audit_plugin.UNTRUSTED_FIELDS_V0_1),
            "meta": {"griffith_version": "0.1.0", "griffith_hardening_version": "1",
                     "analyzed_at": "2026-04-18T00:00:00Z", "source_type": "path"},
        }
        summary = _build_summary(report)
        assert summary["counts_by_severity"]["high"] == 1
        assert summary["counts_by_severity"]["medium"] == 2

    def test_top_findings_capped_at_3(self):
        findings = [
            {"rule_id": f"r{i}", "severity": "high", "file": f"f{i}",
             "line": i, "message": f"m{i}"}
            for i in range(10)
        ]
        report = {
            "schema_version": "0.1",
            "plugin": {"name": "p", "path": ".", "source": "s"},
            "inventory": {"counts": {k: 0 for k in (
                "agents", "commands", "skills", "hooks", "mcp_servers",
                "personas", "templates", "unknown")},
                "totals": {"files": 0, "lines": 0}},
            "security": {"risk_level": "high", "finding_count": 10, "findings": findings},
            "footprint": {"baseline_tokens_approx_cl100k": 0, "on_demand_max": 0,
                          "primary_driver": "none", "efficiency_rating": "excellent",
                          "per_component": {}},
            "architecture": {"pattern": "hybrid", "efficiency_notes": [], "recommendations": []},
            "dependencies": {"scan_status": "tier1_only", "manifests": [], "lockfiles": [],
                             "unscanned_manifests": [], "ecosystems": [], "package_count": 0,
                             "packages": [], "sca": None},
            "analysis_scope": ["static"],
            "untrusted_fields": list(audit_plugin.UNTRUSTED_FIELDS_V0_1),
            "meta": {"griffith_version": "0.1.0", "griffith_hardening_version": "1",
                     "analyzed_at": "2026-04-18T00:00:00Z", "source_type": "path"},
        }
        summary = _build_summary(report)
        assert len(summary["top_findings"]) == 3


class TestSCAInSummary:
    def test_cve_counts_present_when_sca(self, load_fixture):
        summary = _build_summary(load_fixture("tier2_ok_vulns"))
        assert "cve_counts_by_severity" in summary
        assert summary["cve_counts_by_severity"]["medium"] == 4

    def test_top_cves_capped_at_3(self, load_fixture):
        summary = _build_summary(load_fixture("tier2_ok_vulns"))
        assert len(summary["top_cves"]) == 3

    def test_remediation_hint_install_osv_scanner_on_missing(self):
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
            "dependencies": {"scan_status": "tier1_only", "manifests": [], "lockfiles": [],
                             "unscanned_manifests": [], "ecosystems": [], "package_count": 0,
                             "packages": [], "sca": None},
            "analysis_scope": ["static"],
            "untrusted_fields": list(audit_plugin.UNTRUSTED_FIELDS_V0_1),
            "meta": {"griffith_version": "0.1.0", "griffith_hardening_version": "1",
                     "analyzed_at": "2026-04-18T00:00:00Z", "source_type": "path"},
        }
        # wrapper_exit_code=3 signals OSV_SCANNER_MISSING → remediation hint.
        summary = _build_summary(report, wrapper_exit_code=3)
        assert "install_osv_scanner" in summary["remediation_hints"]


class TestCachePath:
    def test_cache_path_in_summary_when_provided(self, load_fixture, tmp_path):
        cache = str(tmp_path / "audit.json")
        summary = _build_summary(load_fixture("tier1_python"), cache_path=cache)
        assert summary["cache_path"] == cache

    def test_cache_path_null_when_not_provided(self, load_fixture):
        summary = _build_summary(load_fixture("tier1_python"))
        assert summary["cache_path"] is None
