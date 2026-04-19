"""Tests for schema-version handshake and unknown-top-level-key drift detection.

Schema-version mismatch is a soft-fail: stderr warning + GRIFFITH_ERR
sentinel with code SCHEMA_DRIFT; render proceeds best-effort so Claude
still gets whatever can be extracted.

Unknown top-level keys are a secondary drift signal. They catch
"additive without version bump" (which Griffith's contract permits but
the wrapper can't render).
"""

from __future__ import annotations

import json

import audit_plugin


class TestSchemaVersion:
    def test_pinned_version_silent(self, capsys):
        report = {"schema_version": "0.1"}
        assert audit_plugin.check_schema_version(report) == "0.1"
        err = capsys.readouterr().err
        assert "warning" not in err.lower()
        assert "GRIFFITH_ERR" not in err

    def test_unknown_version_warns_and_emits_sentinel(self, capsys):
        report = {"schema_version": "0.2"}
        audit_plugin.check_schema_version(report)
        err = capsys.readouterr().err
        assert "0.2" in err
        assert "GRIFFITH_ERR" in err
        assert "SCHEMA_DRIFT" in err

    def test_missing_version_warns(self, capsys):
        report = {}  # no schema_version at all
        audit_plugin.check_schema_version(report)
        err = capsys.readouterr().err
        assert "GRIFFITH_ERR" in err

    def test_sentinel_is_valid_json(self, capsys):
        audit_plugin.check_schema_version({"schema_version": "99.99"})
        err = capsys.readouterr().err
        # Extract the sentinel line
        sentinel_line = next(
            (l for l in err.splitlines() if l.startswith("GRIFFITH_ERR:")), None
        )
        assert sentinel_line is not None
        payload = json.loads(sentinel_line[len("GRIFFITH_ERR: "):])
        assert payload["code"] == "SCHEMA_DRIFT"
        assert payload["category"] == "contract"
        assert "remediation" in payload


class TestUnknownTopLevelKeys:
    def test_known_keys_silent(self, capsys):
        report = {
            "schema_version": "0.1",
            "plugin": {}, "inventory": {}, "security": {}, "footprint": {},
            "architecture": {}, "dependencies": {}, "analysis_scope": [],
            "untrusted_fields": [], "meta": {},
        }
        audit_plugin.check_unknown_top_level_keys(report)
        err = capsys.readouterr().err
        assert "unknown" not in err.lower()

    def test_unknown_key_emits_debug_breadcrumb(self, capsys):
        report = {
            "schema_version": "0.1",
            "plugin": {}, "inventory": {}, "security": {}, "footprint": {},
            "architecture": {}, "dependencies": {}, "analysis_scope": [],
            "untrusted_fields": [], "meta": {},
            "novel_field": {"added": "without bump"},
        }
        audit_plugin.check_unknown_top_level_keys(report)
        err = capsys.readouterr().err
        assert "novel_field" in err
        assert "unknown" in err.lower()

    def test_marketplace_has_its_own_key_set(self, capsys):
        report = {
            "schema_version": "0.1",
            "marketplace": {}, "reports": [], "summary": {}, "meta": {},
        }
        audit_plugin.check_unknown_top_level_keys(report)
        err = capsys.readouterr().err
        # `reports` is expected for marketplace shape; no warning.
        assert "unknown" not in err.lower()

    def test_marketplace_with_unknown_key_warns(self, capsys):
        report = {
            "schema_version": "0.1",
            "marketplace": {}, "reports": [], "summary": {}, "meta": {},
            "extra": 1,
        }
        audit_plugin.check_unknown_top_level_keys(report)
        err = capsys.readouterr().err
        assert "extra" in err
