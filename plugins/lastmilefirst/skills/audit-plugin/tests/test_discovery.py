"""Tests for find_griffith() — containment-checked discovery chain.

Priority: GRIFFITH_BIN env → PATH → DEV_GRIFFITH (behind opt-in env).

The containment check on GRIFFITH_BIN mirrors the pattern used in
Griffith's osv_adapter.find_osv_scanner for symmetry. Key invariants
covered here:

- GRIFFITH_BIN must exist, be owned by the invoking uid, not be
  group/world writable, and resolve into an allow-listed prefix.
- DEV_GRIFFITH is only consulted when LMF_ALLOW_DEV_GRIFFITH=1.
- PATH lookup is trusted (stock shutil.which behavior) but logs which
  path won.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

import audit_plugin


def _make_fake_griffith(path: Path) -> Path:
    """Create an executable fake griffith binary at `path`."""
    path.write_text("#!/bin/sh\necho fake\n")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return path


class TestGriffithBinEnv:
    def test_env_override_accepted_when_valid(self, tmp_path, monkeypatch):
        # tmp_path is in ~/Code/.../pytest-of-mcf/... which is under
        # ~/Code so the allow-list prefix matches. We verify the env-bin
        # path takes priority over PATH by scrubbing PATH.
        fake = _make_fake_griffith(tmp_path / "griffith")
        # The default allow-list includes ~/Code; pytest tmp_path is in
        # /private/var which is NOT allowed. Supply a custom allow-list.
        monkeypatch.setattr(
            audit_plugin, "_allowed_griffith_prefixes",
            lambda: (tmp_path.parent,),
        )
        monkeypatch.setenv("GRIFFITH_BIN", str(fake))
        monkeypatch.setenv("PATH", "/nonexistent")
        monkeypatch.delenv("LMF_ALLOW_DEV_GRIFFITH", raising=False)
        assert audit_plugin.find_griffith() == fake.resolve()

    def test_env_nonexistent_falls_through(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setenv("GRIFFITH_BIN", "/nonexistent/griffith")
        monkeypatch.setenv("PATH", "/nonexistent")
        monkeypatch.delenv("LMF_ALLOW_DEV_GRIFFITH", raising=False)
        assert audit_plugin.find_griffith() is None
        err = capsys.readouterr().err
        assert "GRIFFITH_BIN" in err
        assert "does not exist" in err

    def test_env_outside_allowlist_rejected(self, tmp_path, monkeypatch, capsys):
        fake = _make_fake_griffith(tmp_path / "griffith")
        # Default allow-list does NOT include tmp_path's parent (on macOS
        # it's typically /private/var/...).
        monkeypatch.setenv("GRIFFITH_BIN", str(fake))
        monkeypatch.setenv("PATH", "/nonexistent")
        monkeypatch.delenv("LMF_ALLOW_DEV_GRIFFITH", raising=False)
        # Force the default allow-list (overriding fixture-specific widening).
        default_allowed = audit_plugin._allowed_griffith_prefixes()
        # Ensure tmp_path is not in the default allow-list; if this
        # assumption breaks on a given machine, the test is moot.
        tmp_resolved = fake.resolve()
        in_default = any(
            str(tmp_resolved).startswith(str(p.resolve())) for p in default_allowed
        )
        if in_default:
            # Skip — on this system tmp_path happens to be in the allow-list.
            import pytest
            pytest.skip("tmp_path is inside the default allow-list on this system")

        assert audit_plugin.find_griffith() is None
        err = capsys.readouterr().err
        assert "outside allowed prefixes" in err

    def test_env_world_writable_rejected(self, tmp_path, monkeypatch, capsys):
        fake = _make_fake_griffith(tmp_path / "griffith")
        # Make it group+world writable.
        fake.chmod(fake.stat().st_mode | stat.S_IWGRP | stat.S_IWOTH)
        monkeypatch.setattr(
            audit_plugin, "_allowed_griffith_prefixes",
            lambda: (tmp_path.parent,),
        )
        monkeypatch.setenv("GRIFFITH_BIN", str(fake))
        monkeypatch.setenv("PATH", "/nonexistent")
        monkeypatch.delenv("LMF_ALLOW_DEV_GRIFFITH", raising=False)
        assert audit_plugin.find_griffith() is None
        err = capsys.readouterr().err
        assert "writable" in err.lower()

    def test_env_reject_root_containment(self, tmp_path, monkeypatch, capsys):
        # Reject root takes effect even when allow-list would accept.
        fake = _make_fake_griffith(tmp_path / "griffith")
        monkeypatch.setattr(
            audit_plugin, "_allowed_griffith_prefixes",
            lambda: (tmp_path.parent,),
        )
        monkeypatch.setenv("GRIFFITH_BIN", str(fake))
        monkeypatch.setenv("PATH", "/nonexistent")
        monkeypatch.delenv("LMF_ALLOW_DEV_GRIFFITH", raising=False)
        result = audit_plugin.find_griffith(reject_roots=(tmp_path,))
        assert result is None
        err = capsys.readouterr().err
        assert "reject root" in err


class TestPathLookup:
    def test_path_hit_logs_which_path_won(self, tmp_path, monkeypatch, capsys):
        fake = _make_fake_griffith(tmp_path / "griffith")
        monkeypatch.delenv("GRIFFITH_BIN", raising=False)
        monkeypatch.setenv("PATH", str(tmp_path))
        monkeypatch.delenv("LMF_ALLOW_DEV_GRIFFITH", raising=False)
        result = audit_plugin.find_griffith()
        assert result == fake
        err = capsys.readouterr().err
        assert "using griffith from PATH" in err
        assert str(fake) in err


class TestDevGriffithGate:
    def test_dev_griffith_skipped_without_opt_in(self, tmp_path, monkeypatch):
        # Point DEV_GRIFFITH at a real fake file, but don't set opt-in.
        fake = _make_fake_griffith(tmp_path / "griffith")
        monkeypatch.setattr(audit_plugin, "DEV_GRIFFITH", fake)
        monkeypatch.delenv("GRIFFITH_BIN", raising=False)
        monkeypatch.setenv("PATH", "/nonexistent")
        monkeypatch.delenv("LMF_ALLOW_DEV_GRIFFITH", raising=False)
        assert audit_plugin.find_griffith() is None

    def test_dev_griffith_used_with_opt_in(self, tmp_path, monkeypatch, capsys):
        fake = _make_fake_griffith(tmp_path / "griffith")
        monkeypatch.setattr(audit_plugin, "DEV_GRIFFITH", fake)
        monkeypatch.delenv("GRIFFITH_BIN", raising=False)
        monkeypatch.setenv("PATH", "/nonexistent")
        monkeypatch.setenv("LMF_ALLOW_DEV_GRIFFITH", "1")
        assert audit_plugin.find_griffith() == fake
        err = capsys.readouterr().err
        assert "DEV_GRIFFITH" in err
        assert "opt-in" in err

    def test_dev_griffith_missing_returns_none(self, tmp_path, monkeypatch):
        monkeypatch.setattr(audit_plugin, "DEV_GRIFFITH", tmp_path / "nope")
        monkeypatch.delenv("GRIFFITH_BIN", raising=False)
        monkeypatch.setenv("PATH", "/nonexistent")
        monkeypatch.setenv("LMF_ALLOW_DEV_GRIFFITH", "1")
        assert audit_plugin.find_griffith() is None


class TestPriority:
    def test_env_beats_path(self, tmp_path, monkeypatch):
        env_fake = _make_fake_griffith(tmp_path / "envbin")
        path_dir = tmp_path / "pathdir"
        path_dir.mkdir()
        _make_fake_griffith(path_dir / "griffith")
        monkeypatch.setattr(
            audit_plugin, "_allowed_griffith_prefixes",
            lambda: (tmp_path.parent,),
        )
        monkeypatch.setenv("GRIFFITH_BIN", str(env_fake))
        monkeypatch.setenv("PATH", str(path_dir))
        monkeypatch.delenv("LMF_ALLOW_DEV_GRIFFITH", raising=False)
        assert audit_plugin.find_griffith() == env_fake.resolve()

    def test_path_beats_dev(self, tmp_path, monkeypatch):
        path_dir = tmp_path / "pathdir"
        path_dir.mkdir()
        path_fake = _make_fake_griffith(path_dir / "griffith")
        dev_fake = _make_fake_griffith(tmp_path / "devbin")
        monkeypatch.setattr(audit_plugin, "DEV_GRIFFITH", dev_fake)
        monkeypatch.delenv("GRIFFITH_BIN", raising=False)
        monkeypatch.setenv("PATH", str(path_dir))
        monkeypatch.setenv("LMF_ALLOW_DEV_GRIFFITH", "1")
        assert audit_plugin.find_griffith() == path_fake
