"""Tests for _apply_untrusted_envelope — the schema-driven walker.

The walker takes a Griffith JSON report and replaces every value at a
plugin-controlled dotted path with its enveloped form. It:

- Trusts the wrapper's `UNTRUSTED_FIELDS_V0_1` constant as authoritative.
- Treats the payload's `untrusted_fields[]` as a cross-check, not the
  source of truth. Divergence is logged; the walker applies the union.
- Handles dotted paths with up to two `[]` list markers.
- Handles missing keys silently (schema drift surfaces via
  check_unknown_top_level_keys, not via walker noise).
- Handles malformed `untrusted_fields` (null, int, dict) gracefully.

The critical B1 regression test verifies that when the payload lies
about its own untrusted list (e.g., `untrusted_fields: []`), the
wrapper's pinned list still catches known paths. This is the whole
reason the trust model is inverted.
"""

from __future__ import annotations

import audit_plugin


OPEN = audit_plugin.ENVELOPE_OPEN
CLOSE = audit_plugin.ENVELOPE_CLOSE


def _env(s: str) -> str:
    return audit_plugin._envelope(s)


class TestWalkerHappy:
    def test_scalar_leaf_path(self):
        report = {
            "plugin": {"name": "evil\nname", "source": "url"},
            "untrusted_fields": ["plugin.name"],
        }
        out = audit_plugin._apply_untrusted_envelope(
            report, wrapper_paths=("plugin.name",)
        )
        assert out["plugin"]["name"] == _env("evil\nname")
        # Source is not in the wrapper list OR payload list → not enveloped.
        assert out["plugin"]["source"] == "url"

    def test_original_report_is_not_mutated(self):
        report = {
            "plugin": {"name": "original"},
            "untrusted_fields": ["plugin.name"],
        }
        audit_plugin._apply_untrusted_envelope(
            report, wrapper_paths=("plugin.name",)
        )
        # Input unchanged — walker works on a deep copy.
        assert report["plugin"]["name"] == "original"

    def test_single_array_marker_path(self):
        report = {
            "security": {
                "findings": [
                    {"file": "hooks/a.sh", "rule_id": "x"},
                    {"file": "hooks/b.sh", "rule_id": "y"},
                ]
            },
            "untrusted_fields": [],
        }
        out = audit_plugin._apply_untrusted_envelope(
            report, wrapper_paths=("security.findings[].file",)
        )
        assert out["security"]["findings"][0]["file"] == _env("hooks/a.sh")
        assert out["security"]["findings"][1]["file"] == _env("hooks/b.sh")
        # rule_id (not in list) untouched.
        assert out["security"]["findings"][0]["rule_id"] == "x"

    def test_two_array_marker_path_list_of_strings(self):
        # `fixed_versions[]` is the canonical two-array case: a list
        # nested inside a list of dicts.
        report = {
            "dependencies": {
                "sca": {
                    "vulnerabilities": [
                        {"id": "CVE-1", "fixed_versions": ["1.0", "2.0"]},
                        {"id": "CVE-2", "fixed_versions": ["9.9"]},
                    ]
                }
            },
            "untrusted_fields": [],
        }
        out = audit_plugin._apply_untrusted_envelope(
            report,
            wrapper_paths=(
                "dependencies.sca.vulnerabilities[].fixed_versions[]",
            ),
        )
        assert out["dependencies"]["sca"]["vulnerabilities"][0]["fixed_versions"] == [
            _env("1.0"),
            _env("2.0"),
        ]
        assert out["dependencies"]["sca"]["vulnerabilities"][1]["fixed_versions"] == [
            _env("9.9"),
        ]


class TestWalkerUnion:
    def test_wrapper_and_payload_both_applied(self, capsys):
        """Union: wrapper-only path + payload-only path → both enveloped."""
        report = {
            "plugin": {"name": "pname"},
            "architecture": {
                "recommendations": ["rec1", "rec2"],
            },
            "untrusted_fields": ["architecture.recommendations[]"],
        }
        out = audit_plugin._apply_untrusted_envelope(
            report, wrapper_paths=("plugin.name",)
        )
        # Wrapper-only path enveloped.
        assert out["plugin"]["name"] == _env("pname")
        # Payload-only path ALSO enveloped (union semantics).
        assert out["architecture"]["recommendations"] == [_env("rec1"), _env("rec2")]

        # Divergence surfaced on stderr.
        err = capsys.readouterr().err
        assert "architecture.recommendations[]" in err
        assert "plugin.name" in err

    def test_divergence_warning_when_payload_has_extra_paths(self, capsys):
        report = {
            "plugin": {"name": "x"},
            "newfield": "unknown",
            "untrusted_fields": ["plugin.name", "newfield"],
        }
        audit_plugin._apply_untrusted_envelope(
            report, wrapper_paths=("plugin.name",)
        )
        err = capsys.readouterr().err
        # payload has "newfield" that wrapper doesn't — warning fires.
        assert "newfield" in err
        assert "not in wrapper" in err

    def test_divergence_warning_when_wrapper_has_extra_paths(self, capsys):
        # Wrapper expects a Tier 2 path but payload omits it (e.g., Griffith
        # rolled back).
        report = {
            "plugin": {"name": "x"},
            "untrusted_fields": ["plugin.name"],
        }
        audit_plugin._apply_untrusted_envelope(
            report,
            wrapper_paths=(
                "plugin.name",
                "dependencies.sca.vulnerabilities[].id",
            ),
        )
        err = capsys.readouterr().err
        assert "dependencies.sca.vulnerabilities[].id" in err
        assert "Griffith drift" in err

    def test_no_divergence_no_warning(self, capsys):
        report = {
            "plugin": {"name": "x"},
            "untrusted_fields": ["plugin.name"],
        }
        audit_plugin._apply_untrusted_envelope(
            report, wrapper_paths=("plugin.name",)
        )
        err = capsys.readouterr().err
        # No divergence warnings at all when sets match.
        assert "not in wrapper" not in err
        assert "Griffith drift" not in err


class TestWalkerB1Regression:
    """B1 — the payload lies about its own untrusted list; wrapper wins."""

    def test_empty_payload_list_wrapper_still_envelopes(self, capsys):
        """Critical: a malicious/buggy Griffith emits `untrusted_fields: []`.
        The wrapper's pinned list must still envelope known paths."""
        report = {
            "plugin": {"name": "hostile\npayload"},
            "untrusted_fields": [],  # lie
        }
        out = audit_plugin._apply_untrusted_envelope(
            report, wrapper_paths=("plugin.name",)
        )
        # Wrapper list authoritative — name IS enveloped.
        assert out["plugin"]["name"] == _env("hostile\npayload")

    def test_missing_payload_list_wrapper_still_envelopes(self):
        report = {"plugin": {"name": "x"}}  # no untrusted_fields at all
        out = audit_plugin._apply_untrusted_envelope(
            report, wrapper_paths=("plugin.name",)
        )
        assert out["plugin"]["name"] == _env("x")


class TestWalkerMalformedPayload:
    def test_null_untrusted_fields_handled(self):
        report = {"plugin": {"name": "x"}, "untrusted_fields": None}
        out = audit_plugin._apply_untrusted_envelope(
            report, wrapper_paths=("plugin.name",)
        )
        # Wrapper list still applied; `null` is treated like "absent".
        assert out["plugin"]["name"] == _env("x")

    def test_int_untrusted_fields_warns_and_falls_through(self, capsys):
        report = {"plugin": {"name": "x"}, "untrusted_fields": 42}
        audit_plugin._apply_untrusted_envelope(
            report, wrapper_paths=("plugin.name",)
        )
        err = capsys.readouterr().err
        assert "malformed" in err.lower()

    def test_dict_untrusted_fields_warns_and_falls_through(self, capsys):
        report = {"plugin": {"name": "x"}, "untrusted_fields": {"wrong": "type"}}
        audit_plugin._apply_untrusted_envelope(
            report, wrapper_paths=("plugin.name",)
        )
        err = capsys.readouterr().err
        assert "malformed" in err.lower()

    def test_list_of_nonstrings_warns(self, capsys):
        report = {
            "plugin": {"name": "x"},
            "untrusted_fields": ["plugin.name", 42, None],
        }
        audit_plugin._apply_untrusted_envelope(
            report, wrapper_paths=("plugin.name",)
        )
        err = capsys.readouterr().err
        assert "malformed" in err.lower()


class TestWalkerMissingKeys:
    def test_missing_nested_key_silent(self, capsys):
        """A wrapper-declared path that doesn't exist in the payload is
        silent — missing optional field is the common case."""
        report = {"plugin": {"name": "x"}, "untrusted_fields": []}
        audit_plugin._apply_untrusted_envelope(
            report,
            wrapper_paths=(
                "plugin.name",
                "dependencies.packages[].name",  # no dependencies in report
            ),
        )
        # No crash, no noise.

    def test_empty_list_at_array_marker(self):
        report = {
            "dependencies": {"packages": []},
            "untrusted_fields": [],
        }
        out = audit_plugin._apply_untrusted_envelope(
            report, wrapper_paths=("dependencies.packages[].name",)
        )
        assert out["dependencies"]["packages"] == []


class TestWalkerMarketplaceShape:
    """Marketplace report shape: plugin data lives under `reports[]`.

    Regression test from real-world smoke on trailofbits/skills-curated —
    the initial UNTRUSTED_FIELDS_V0_1 only listed single-plugin paths,
    so marketplace-nested fields rendered raw.
    """

    def test_reports_plugin_name_enveloped(self):
        report = {
            "schema_version": "0.1",
            "marketplace": {"source": "s", "path": "/tmp/x"},
            "reports": [
                {"plugin": {"name": "first-plugin", "path": ".", "source": "s"}},
                {"plugin": {"name": "second-plugin", "path": ".", "source": "s"}},
            ],
            "summary": {"plugin_count": 2, "risk_level_counts": {}, "patterns": {}},
            "meta": {},
            "untrusted_fields": [],
        }
        out = audit_plugin._apply_untrusted_envelope(report)
        # BOTH plugin names must be enveloped by the wrapper's pinned list.
        assert out["reports"][0]["plugin"]["name"] == _env("first-plugin")
        assert out["reports"][1]["plugin"]["name"] == _env("second-plugin")

    def test_reports_nested_cve_fields_enveloped(self):
        report = {
            "schema_version": "0.1",
            "marketplace": {"source": "s", "path": "/tmp/x"},
            "reports": [
                {
                    "plugin": {"name": "p", "path": ".", "source": "s"},
                    "dependencies": {
                        "sca": {
                            "vulnerabilities": [
                                {"id": "CVE-NESTED",
                                 "summary": "nested vuln",
                                 "affected_package": "pkg",
                                 "fixed_versions": ["1.0"]}
                            ]
                        }
                    },
                }
            ],
            "summary": {"plugin_count": 1, "risk_level_counts": {}, "patterns": {}},
            "meta": {},
            "untrusted_fields": [],
        }
        out = audit_plugin._apply_untrusted_envelope(report)
        sca = out["reports"][0]["dependencies"]["sca"]
        assert sca["vulnerabilities"][0]["id"] == _env("CVE-NESTED")
        assert sca["vulnerabilities"][0]["summary"] == _env("nested vuln")
        assert sca["vulnerabilities"][0]["affected_package"] == _env("pkg")
        assert sca["vulnerabilities"][0]["fixed_versions"][0] == _env("1.0")


class TestWalkerFullPinnedList:
    def test_full_v0_1_list_runs_without_error(self):
        """Sanity: the full wrapper list walks a realistic report without crashing."""
        report = {
            "schema_version": "0.1",
            "plugin": {"name": "p", "source": "s", "path": "."},
            "inventory": {"counts": {}, "totals": {"files": 0, "lines": 0}},
            "security": {
                "risk_level": "none",
                "finding_count": 1,
                "findings": [
                    {"rule_id": "r", "severity": "low", "file": "f", "line": 1, "message": "m"}
                ],
            },
            "footprint": {
                "baseline_tokens_approx_cl100k": 0, "on_demand_max": 0,
                "primary_driver": "none", "efficiency_rating": "excellent",
                "per_component": {},
            },
            "architecture": {
                "pattern": "hybrid",
                "efficiency_notes": ["note"],
                "recommendations": ["rec"],
            },
            "dependencies": {
                "scan_status": "tier1_only",
                "manifests": [{"path": "requirements.txt", "is_symlink": False, "size_skipped": False}],
                "lockfiles": [],
                "unscanned_manifests": ["bad.toml"],
                "ecosystems": ["PyPI"],
                "package_count": 1,
                "packages": [
                    {"ecosystem": "PyPI", "name": "req", "constraint": ">=1", "kind": "runtime", "manifest": "requirements.txt"}
                ],
                "sca": {
                    "osv_scanner_version": "2.3.5",
                    "vulnerability_count": 1,
                    "vulnerabilities": [
                        {
                            "id": "CVE-1", "severity": "high",
                            "severity_raw": "7.5", "summary": "bad",
                            "affected_package": "req",
                            "fixed_versions": ["1.1"],
                        }
                    ],
                    "note": None,
                    "error": None,
                },
            },
            "analysis_scope": ["static"],
            "untrusted_fields": list(audit_plugin.UNTRUSTED_FIELDS_V0_1),
            "meta": {"griffith_version": "0.1.0", "griffith_hardening_version": "1",
                     "analyzed_at": "2026-04-18T00:00:00Z", "source_type": "path"},
        }
        out = audit_plugin._apply_untrusted_envelope(report)
        # Spot check: key enveloped values.
        assert out["plugin"]["name"].startswith(OPEN)
        assert out["security"]["findings"][0]["file"].startswith(OPEN)
        assert out["architecture"]["recommendations"][0].startswith(OPEN)
        assert out["dependencies"]["packages"][0]["name"].startswith(OPEN)
        assert out["dependencies"]["sca"]["vulnerabilities"][0]["id"].startswith(OPEN)
        assert out["dependencies"]["sca"]["vulnerabilities"][0]["fixed_versions"][0].startswith(OPEN)
