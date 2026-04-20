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


class TestMarketplaceAggregation:
    """Regression tests from real-world smoke on trailofbits/skills-curated.

    Marketplace reports don't have top-level `security` or `dependencies`;
    the data lives under `reports[]`. A naive implementation reads top-level
    and emits safe/none for every marketplace, which is wrong when any
    nested plugin has findings.
    """

    def _build_marketplace(
        self,
        plugin_severities: list[str],
        vuln_severities: list[str] | None = None,
    ) -> dict:
        reports = []
        for i, sev in enumerate(plugin_severities):
            r: dict = {
                "schema_version": "0.1",
                "plugin": {"name": f"plugin-{i}", "path": ".", "source": "s"},
                "inventory": {"counts": {k: 0 for k in (
                    "agents", "commands", "skills", "hooks", "mcp_servers",
                    "personas", "templates", "unknown")},
                    "totals": {"files": 0, "lines": 0}},
                "security": {
                    "risk_level": sev,
                    "finding_count": 1 if sev != "none" else 0,
                    "findings": (
                        [{"rule_id": f"r{i}", "severity": sev,
                          "file": f"f{i}", "line": 1, "message": f"m{i}"}]
                        if sev != "none" else []
                    ),
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
            reports.append(r)
        return {
            "schema_version": "0.1",
            "marketplace": {"source": "s", "path": "/tmp/x"},
            "reports": reports,
            "summary": {"plugin_count": len(reports), "risk_level_counts": {},
                        "patterns": {}},
            "meta": {"griffith_version": "0.1.0", "griffith_hardening_version": "1",
                     "analyzed_at": "2026-04-18T00:00:00Z", "source_type": "path"},
        }

    def test_marketplace_all_clean_verdict_safe(self):
        mp = self._build_marketplace(["none", "none", "none"])
        summary = _build_summary(mp)
        assert summary["verdict"] == "safe"
        assert summary["risk_tier"] == "none"

    def test_marketplace_with_info_finding_not_none(self):
        """The bug this test catches: marketplace with info findings
        previously returned risk_tier=none because emit_agent_summary
        read top-level report['security'] which doesn't exist for
        marketplace shape."""
        mp = self._build_marketplace(["none", "info", "none"])
        summary = _build_summary(mp)
        assert summary["risk_tier"] == "info"
        assert summary["counts_by_severity"]["info"] == 1

    def test_marketplace_worst_tier_wins(self):
        mp = self._build_marketplace(["low", "critical", "medium"])
        summary = _build_summary(mp)
        assert summary["risk_tier"] == "critical"
        assert summary["verdict"] == "block"

    def test_marketplace_plugin_count_in_summary(self):
        mp = self._build_marketplace(["none", "none"])
        summary = _build_summary(mp)
        assert summary["plugin_count"] == 2

    def test_marketplace_top_findings_aggregated_worst_first(self):
        mp = self._build_marketplace(["low", "critical", "high", "medium"])
        summary = _build_summary(mp)
        # Sorted worst-first; we expect critical then high then medium
        # (low falls out because we only take top 3).
        severities = [f["severity"] for f in summary["top_findings"]]
        assert severities == ["critical", "high", "medium"]


class TestVerdictFromCVEs:
    """Regression from real-world smoke on compound-engineering 2.67.0 —
    2 critical Pillow CVEs initially surfaced as verdict="review" because
    _derive_verdict only considered security-finding severity.
    """

    def _build_with_cve_severity(self, cve_severity: str) -> dict:
        return {
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
                "scan_status": "ok",
                "manifests": [{"path": "req.txt", "is_symlink": False, "size_skipped": False}],
                "lockfiles": [], "unscanned_manifests": [],
                "ecosystems": ["PyPI"], "package_count": 1,
                "packages": [{"ecosystem": "PyPI", "name": "pkg", "constraint": "1.0",
                              "kind": "runtime", "manifest": "req.txt"}],
                "sca": {
                    "osv_scanner_version": "2.3.5",
                    "vulnerability_count": 1,
                    "vulnerabilities": [{
                        "id": "CVE-1",
                        "severity": cve_severity,
                        "severity_raw": "9.3",
                        "summary": "bad",
                        "affected_package": "pkg",
                        "fixed_versions": ["2.0"],
                    }],
                    "note": None, "error": None,
                },
            },
            "analysis_scope": ["static"],
            "untrusted_fields": list(audit_plugin.UNTRUSTED_FIELDS_V0_1),
            "meta": {"griffith_version": "0.1.0", "griffith_hardening_version": "1",
                     "analyzed_at": "2026-04-18T00:00:00Z", "source_type": "path"},
        }

    def test_critical_cve_forces_block(self):
        """The Pillow-in-compound-engineering case. Security layer clean,
        CVE layer critical — verdict must be `block`."""
        summary = _build_summary(self._build_with_cve_severity("critical"))
        assert summary["verdict"] == "block"

    def test_high_cve_forces_block(self):
        summary = _build_summary(self._build_with_cve_severity("high"))
        assert summary["verdict"] == "block"

    def test_medium_cve_forces_review(self):
        summary = _build_summary(self._build_with_cve_severity("medium"))
        assert summary["verdict"] == "review"


class TestCachePath:
    def test_cache_path_in_summary_when_provided(self, load_fixture, tmp_path):
        cache = str(tmp_path / "audit.json")
        summary = _build_summary(load_fixture("tier1_python"), cache_path=cache)
        assert summary["cache_path"] == cache

    def test_cache_path_null_when_not_provided(self, load_fixture):
        summary = _build_summary(load_fixture("tier1_python"))
        assert summary["cache_path"] is None
