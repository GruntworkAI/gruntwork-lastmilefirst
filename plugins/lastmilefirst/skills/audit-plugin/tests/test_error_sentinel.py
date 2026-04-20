"""Tests for the GRIFFITH_ERR machine-parseable sentinel.

Contract: on every non-zero wrapper exit, stderr contains exactly one
`GRIFFITH_ERR: {json}` sentinel line. The JSON carries code, category,
and remediation fields. Claude parses the sentinel without scraping
English prose.
"""

from __future__ import annotations

import json

import audit_plugin


class TestSentinelFormat:
    def test_single_sentinel_line(self, capsys):
        audit_plugin._emit_griffith_err("GENERIC_FAILURE", "subprocess", "check stderr")
        err = capsys.readouterr().err
        lines = err.strip().split("\n")
        sentinel_lines = [l for l in lines if l.startswith("GRIFFITH_ERR:")]
        assert len(sentinel_lines) == 1

    def test_sentinel_json_parseable(self, capsys):
        audit_plugin._emit_griffith_err(
            "OSV_SCANNER_MISSING", "dependency", "install osv-scanner"
        )
        err = capsys.readouterr().err
        sentinel = next(l for l in err.split("\n") if l.startswith("GRIFFITH_ERR:"))
        payload = json.loads(sentinel[len("GRIFFITH_ERR: "):])
        assert payload == {
            "code": "OSV_SCANNER_MISSING",
            "category": "dependency",
            "remediation": "install osv-scanner",
        }

    def test_sentinel_is_compact_not_pretty(self, capsys):
        audit_plugin._emit_griffith_err("TIMEOUT", "subprocess", "retry")
        err = capsys.readouterr().err
        sentinel = next(l for l in err.split("\n") if l.startswith("GRIFFITH_ERR:"))
        # Compact JSON: no spaces between separators.
        assert ", " not in sentinel
        assert ": " not in sentinel[len("GRIFFITH_ERR:"):]

    def test_multiple_sentinels_do_not_interleave(self, capsys):
        audit_plugin._emit_griffith_err("SCHEMA_DRIFT", "contract", "update wrapper")
        audit_plugin._emit_griffith_err("GENERIC_FAILURE", "subprocess", "see stderr")
        err = capsys.readouterr().err
        sentinels = [l for l in err.split("\n") if l.startswith("GRIFFITH_ERR:")]
        assert len(sentinels) == 2
        # Each parses independently.
        for line in sentinels:
            payload = json.loads(line[len("GRIFFITH_ERR: "):])
            assert "code" in payload
            assert "category" in payload
            assert "remediation" in payload


class TestErrorCodeEnum:
    def test_known_codes_documented(self):
        # The wrapper ships a pinned set of codes. Cross-reference.
        for code in (
            "GRIFFITH_MISSING",
            "OSV_SCANNER_MISSING",
            "GENERIC_FAILURE",
            "SCHEMA_DRIFT",
            "TIMEOUT",
            "MALFORMED_OUTPUT",
            "INVALID_SOURCE",
        ):
            assert code in audit_plugin.GRIFFITH_ERR_CODES
