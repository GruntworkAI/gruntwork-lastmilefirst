"""Regression tests for the third-party-content boundary preamble and
for envelope coverage of plugin/marketplace source+path fields.

Origin: code-review blockers B-1 and B-2 on PR for feat/audit-plugin-phase-1.5.

B-1: `plugin.source`, `plugin.path`, `reports[].plugin.source`,
`reports[].plugin.path`, `marketplace.source`, `marketplace.path` must
all be enveloped before rendering. These are attacker-influenced
(registry-controlled or filesystem-controlled) and can carry ANSI,
bidi, zero-width, or envelope-break characters.

B-2: `render_marketplace` must emit the third-party-content boundary
preamble once at the top, before any enveloped value (including
`marketplace.source` in the header line). Per-plugin preambles are
redundant once the marketplace-level preamble is present.
"""

from __future__ import annotations

import io
from contextlib import redirect_stdout

import audit_plugin


OPEN = audit_plugin.ENVELOPE_OPEN
CLOSE = audit_plugin.ENVELOPE_CLOSE


def _render_single_to_string(report: dict) -> str:
    buf = io.StringIO()
    with redirect_stdout(buf):
        audit_plugin.render_single(report)
    return buf.getvalue()


def _render_marketplace_to_string(report: dict) -> str:
    buf = io.StringIO()
    with redirect_stdout(buf):
        audit_plugin.render_marketplace(report)
    return buf.getvalue()


def _minimal_single_report(
    source: str = "https://example.com/attacker/plugin",
    path: str = "/tmp/clone/attacker-path",
) -> dict:
    return {
        "schema_version": "0.1",
        "plugin": {
            "name": "victim",
            "source": source,
            "path": path,
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
        "analysis_scope": ["static"],
        "untrusted_fields": [],
        "meta": {
            "griffith_version": "0.1.0",
            "griffith_hardening_version": "1",
            "analyzed_at": "2026-04-20T00:00:00Z",
            "source_type": "path",
        },
    }


def _minimal_marketplace_report(
    marketplace_source: str = "https://example.com/attacker/marketplace",
    marketplace_path: str = "/tmp/clone/attacker-marketplace",
    reports: list[dict] | None = None,
) -> dict:
    if reports is None:
        reports = [_minimal_single_report()]
    return {
        "schema_version": "0.1",
        "marketplace": {
            "source": marketplace_source,
            "path": marketplace_path,
        },
        "summary": {
            "plugin_count": len(reports),
            "risk_level_counts": {
                "critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0, "none": len(reports),
            },
            "patterns": {},
        },
        "reports": reports,
        "analysis_scope": ["static"],
        "untrusted_fields": [],
        "meta": {
            "griffith_version": "0.1.0",
            "griffith_hardening_version": "1",
            "analyzed_at": "2026-04-20T00:00:00Z",
            "source_type": "marketplace",
        },
    }


class TestB1SinglePluginSourcePathEnveloped:
    """B-1: plugin.source and plugin.path must be enveloped in the
    single-plugin render path. Raw values from attacker-controlled
    registry URLs or filesystem paths cannot reach Claude's session."""

    def test_plugin_source_is_enveloped(self):
        report = _minimal_single_report(source="https://attacker.example/evil")
        out = _render_single_to_string(report)
        assert f"{OPEN}https://attacker.example/evil{CLOSE}" in out

    def test_plugin_path_is_enveloped_in_untrusted_fields_list(self):
        assert "plugin.path" in audit_plugin.UNTRUSTED_FIELDS_V0_1

    def test_plugin_source_is_in_untrusted_fields_list(self):
        assert "plugin.source" in audit_plugin.UNTRUSTED_FIELDS_V0_1

    def test_raw_attacker_source_does_not_appear_unwrapped(self):
        # The attacker-controlled source must never appear in the output
        # without envelope markers directly surrounding it.
        source = "https://attacker.example/evil"
        report = _minimal_single_report(source=source)
        out = _render_single_to_string(report)
        # The raw string appears wrapped; verify it never appears in
        # a context where markers are absent on either side.
        # Tight check: the only occurrence of the source is inside an envelope.
        raw_occurrences = out.count(source)
        wrapped_occurrences = out.count(f"{OPEN}{source}{CLOSE}")
        assert raw_occurrences == wrapped_occurrences, (
            "Every occurrence of plugin.source must be envelope-wrapped"
        )


class TestB1MarketplaceSourcePathEnveloped:
    """B-1: marketplace.source and marketplace.path must be enveloped
    in the marketplace render path, and nested reports[].plugin.source
    and reports[].plugin.path must also be enveloped."""

    def test_marketplace_source_in_untrusted_list(self):
        assert "marketplace.source" in audit_plugin.UNTRUSTED_FIELDS_V0_1

    def test_marketplace_path_in_untrusted_list(self):
        assert "marketplace.path" in audit_plugin.UNTRUSTED_FIELDS_V0_1

    def test_reports_plugin_source_in_untrusted_list(self):
        assert "reports[].plugin.source" in audit_plugin.UNTRUSTED_FIELDS_V0_1

    def test_reports_plugin_path_in_untrusted_list(self):
        assert "reports[].plugin.path" in audit_plugin.UNTRUSTED_FIELDS_V0_1

    def test_marketplace_source_envelope_in_rendered_header(self):
        src = "https://attacker.example/market"
        report = _minimal_marketplace_report(marketplace_source=src)
        out = _render_marketplace_to_string(report)
        assert f"{OPEN}{src}{CLOSE}" in out

    def test_reports_plugin_source_envelope_in_marketplace_render(self):
        src = "https://attacker.example/inner-plugin"
        inner = _minimal_single_report(source=src)
        report = _minimal_marketplace_report(reports=[inner])
        out = _render_marketplace_to_string(report)
        assert f"{OPEN}{src}{CLOSE}" in out

    def test_raw_marketplace_source_only_appears_wrapped(self):
        src = "https://attacker.example/market"
        report = _minimal_marketplace_report(marketplace_source=src)
        out = _render_marketplace_to_string(report)
        raw = out.count(src)
        wrapped = out.count(f"{OPEN}{src}{CLOSE}")
        assert raw == wrapped, (
            "Every occurrence of marketplace.source must be envelope-wrapped"
        )


class TestB1AnsiStrippedFromPluginSource:
    """B-1 defense-in-depth: ANSI and bidi chars in attacker-controlled
    source/path must be stripped at envelope time."""

    def test_ansi_in_plugin_source_stripped(self):
        # Red color escape wrapping malicious text.
        malicious = "\x1b[31mevil\x1b[0m"
        report = _minimal_single_report(source=malicious)
        out = _render_single_to_string(report)
        # Raw escape byte must not appear.
        assert "\x1b" not in out
        # Nor the literal color code fragments.
        assert "[31m" not in out
        assert "[0m" not in out

    def test_bidi_in_marketplace_source_stripped(self):
        # RIGHT-TO-LEFT OVERRIDE — classic bidi attack.
        malicious = "evil\u202etxt.safe"
        report = _minimal_marketplace_report(marketplace_source=malicious)
        out = _render_marketplace_to_string(report)
        assert "\u202e" not in out


class TestB2PreamblePlacement:
    """B-2: render_marketplace emits the third-party-content boundary
    preamble once, at the top, before any enveloped value."""

    def test_marketplace_preamble_present(self):
        report = _minimal_marketplace_report()
        out = _render_marketplace_to_string(report)
        # Match on a distinctive phrase from the preamble.
        assert "Third-party content boundary" in out

    def test_preamble_precedes_marketplace_source_header(self):
        src = "example-market-source"
        report = _minimal_marketplace_report(marketplace_source=src)
        out = _render_marketplace_to_string(report)
        preamble_idx = out.index("Third-party content boundary")
        header_idx = out.index(f"{OPEN}{src}{CLOSE}")
        assert preamble_idx < header_idx, (
            "Preamble must render before any enveloped marketplace header value"
        )

    def test_preamble_emitted_once_in_marketplace_render(self):
        # Two plugins in the report — the preamble should still only
        # appear once (per-plugin duplication was removed alongside B-2).
        report = _minimal_marketplace_report(
            reports=[_minimal_single_report(), _minimal_single_report()]
        )
        out = _render_marketplace_to_string(report)
        assert out.count("Third-party content boundary") == 1

    def test_render_single_still_emits_preamble(self):
        # Ensure the B-2 edit didn't regress the single-plugin path.
        out = _render_single_to_string(_minimal_single_report())
        assert "Third-party content boundary" in out
