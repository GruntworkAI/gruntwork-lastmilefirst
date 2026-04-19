"""Tests for exit-code translation and subprocess handling.

The wrapper publishes its own stable exit-code enum:

| Wrapper | Meaning |
|---------|---------|
| 0 | Success |
| 1 | Generic failure (griffith exit 1, invalid source, clone failure) |
| 2 | (Reserved) |
| 3 | OSV_SCANNER_MISSING — griffith exit 2, --sca without osv-scanner |
| 4 | (Reserved — schema-drift could escalate) |
| 5 | TIMEOUT — subprocess wall-clock exceeded |
| 6 | MALFORMED_OUTPUT — griffith exit 0 but stdout not valid JSON |

Griffith's internal codes don't leak into the wrapper's contract.
"""

from __future__ import annotations

import json
import subprocess
from unittest.mock import MagicMock, patch

import pytest

import audit_plugin


class TestExitCodeTranslation:
    def test_griffith_exit_0_valid_json_wrapper_exit_0(self, tmp_path, monkeypatch):
        """Success: griffith returns 0 with valid JSON → wrapper returns 0."""
        fake_bin = tmp_path / "griffith"
        fake_bin.write_text("#!/bin/sh\necho fake\n")
        fake_bin.chmod(0o755)
        monkeypatch.setattr(audit_plugin, "find_griffith", lambda **k: fake_bin)

        valid_report = json.dumps({
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
            "untrusted_fields": [],
            "meta": {"griffith_version": "0.1.0", "griffith_hardening_version": "1",
                     "analyzed_at": "2026-04-18T00:00:00Z", "source_type": "path"},
        })
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=valid_report, stderr="")
            monkeypatch.setattr("sys.argv", ["audit_plugin.py", "./some-path", "--no-sca"])
            assert audit_plugin.main() == 0

    def test_griffith_exit_1_wrapper_exit_1(self, tmp_path, monkeypatch, capsys):
        """Generic failure: griffith exit 1 → wrapper exit 1 + GRIFFITH_ERR sentinel."""
        fake_bin = tmp_path / "griffith"
        fake_bin.write_text("#!/bin/sh\n")
        fake_bin.chmod(0o755)
        monkeypatch.setattr(audit_plugin, "find_griffith", lambda **k: fake_bin)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1, stdout="", stderr="Clone failed: refused protocol"
            )
            monkeypatch.setattr("sys.argv", ["audit_plugin.py", "./bad"])
            exit_code = audit_plugin.main()

        assert exit_code == 1
        err = capsys.readouterr().err
        assert "GRIFFITH_ERR" in err
        assert "GENERIC_FAILURE" in err

    def test_griffith_exit_2_wrapper_exit_3(self, tmp_path, monkeypatch, capsys):
        """Griffith exit 2 (osv-scanner missing on --sca) → wrapper exit 3."""
        fake_bin = tmp_path / "griffith"
        fake_bin.write_text("#!/bin/sh\n")
        fake_bin.chmod(0o755)
        monkeypatch.setattr(audit_plugin, "find_griffith", lambda **k: fake_bin)

        install_pitch = (
            "Recommended: install osv-scanner for dependency CVE analysis.\n"
            "..."
        )
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=2, stdout="", stderr=install_pitch)
            monkeypatch.setattr("sys.argv", ["audit_plugin.py", "./some", "--sca"])
            exit_code = audit_plugin.main()

        assert exit_code == 3
        err = capsys.readouterr().err
        assert "GRIFFITH_ERR" in err
        assert "OSV_SCANNER_MISSING" in err

    def test_malformed_json_wrapper_exit_6(self, tmp_path, monkeypatch, capsys):
        """Griffith exit 0 + invalid JSON → wrapper exit 6 MALFORMED_OUTPUT."""
        fake_bin = tmp_path / "griffith"
        fake_bin.write_text("#!/bin/sh\n")
        fake_bin.chmod(0o755)
        monkeypatch.setattr(audit_plugin, "find_griffith", lambda **k: fake_bin)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="not json {{{ incomplete", stderr=""
            )
            monkeypatch.setattr("sys.argv", ["audit_plugin.py", "./some", "--no-sca"])
            exit_code = audit_plugin.main()

        assert exit_code == 6
        err = capsys.readouterr().err
        assert "GRIFFITH_ERR" in err
        assert "MALFORMED_OUTPUT" in err

    def test_timeout_wrapper_exit_5(self, tmp_path, monkeypatch, capsys):
        """Subprocess timeout → wrapper exit 5 TIMEOUT."""
        fake_bin = tmp_path / "griffith"
        fake_bin.write_text("#!/bin/sh\n")
        fake_bin.chmod(0o755)
        monkeypatch.setattr(audit_plugin, "find_griffith", lambda **k: fake_bin)

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd=["griffith"], timeout=1)
            monkeypatch.setattr("sys.argv", ["audit_plugin.py", "./some", "--no-sca"])
            exit_code = audit_plugin.main()

        assert exit_code == 5
        err = capsys.readouterr().err
        assert "GRIFFITH_ERR" in err
        assert "TIMEOUT" in err

    def test_griffith_missing_wrapper_exit_1(self, monkeypatch, capsys):
        """griffith not discoverable → wrapper exit 1 + GRIFFITH_MISSING sentinel."""
        monkeypatch.setattr(audit_plugin, "find_griffith", lambda **k: None)
        monkeypatch.setattr("sys.argv", ["audit_plugin.py", "./some"])
        exit_code = audit_plugin.main()
        assert exit_code == 1
        err = capsys.readouterr().err
        assert "GRIFFITH_ERR" in err
        assert "GRIFFITH_MISSING" in err


class TestScaFlagForwarding:
    def test_sca_default_on(self, tmp_path, monkeypatch):
        """Default behavior: --sca forwarded to griffith (no explicit flag)."""
        fake_bin = tmp_path / "griffith"
        fake_bin.write_text("#!/bin/sh\n")
        fake_bin.chmod(0o755)
        monkeypatch.setattr(audit_plugin, "find_griffith", lambda **k: fake_bin)

        valid = json.dumps({
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
            "untrusted_fields": [],
            "meta": {"griffith_version": "0.1.0", "griffith_hardening_version": "1",
                     "analyzed_at": "2026-04-18T00:00:00Z", "source_type": "path"},
        })
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=valid, stderr="")
            monkeypatch.setattr("sys.argv", ["audit_plugin.py", "./some"])
            audit_plugin.main()
            # Explicit: assert subprocess.run's args include --sca.
            invoked_cmd = mock_run.call_args.args[0]
            assert "--sca" in invoked_cmd

    def test_no_sca_omits_flag(self, tmp_path, monkeypatch):
        """--no-sca → --sca NOT in griffith command."""
        fake_bin = tmp_path / "griffith"
        fake_bin.write_text("#!/bin/sh\n")
        fake_bin.chmod(0o755)
        monkeypatch.setattr(audit_plugin, "find_griffith", lambda **k: fake_bin)

        valid = json.dumps({
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
            "untrusted_fields": [],
            "meta": {"griffith_version": "0.1.0", "griffith_hardening_version": "1",
                     "analyzed_at": "2026-04-18T00:00:00Z", "source_type": "path"},
        })
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=valid, stderr="")
            monkeypatch.setattr("sys.argv", ["audit_plugin.py", "./some", "--no-sca"])
            audit_plugin.main()
            invoked_cmd = mock_run.call_args.args[0]
            assert "--sca" not in invoked_cmd
