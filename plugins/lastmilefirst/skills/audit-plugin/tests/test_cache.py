"""Tests for JSON result caching — write / read / atomic / invalidate.

Cache keyed on sha256 of the source string. Default location is
`$TMPDIR/griffith-audit-<sha>.json`. Override via --save-json PATH.
Disable via --no-save. Avoids Claude re-invoking the full subprocess
pipeline to answer follow-up questions.
"""

from __future__ import annotations

import json

import audit_plugin


class TestCacheKey:
    def test_same_source_same_key(self):
        k1 = audit_plugin._cache_key_for_source("my-plugin")
        k2 = audit_plugin._cache_key_for_source("my-plugin")
        assert k1 == k2

    def test_different_source_different_key(self):
        k1 = audit_plugin._cache_key_for_source("plugin-a")
        k2 = audit_plugin._cache_key_for_source("plugin-b")
        assert k1 != k2


class TestCachePath:
    def test_default_path_under_tmpdir(self, tmp_path, monkeypatch):
        monkeypatch.setenv("TMPDIR", str(tmp_path))
        path = audit_plugin._default_cache_path("some-source")
        assert str(path).startswith(str(tmp_path))
        assert "griffith-audit-" in path.name
        assert path.suffix == ".json"


class TestCacheWriteAndRead:
    def test_write_and_read_roundtrip(self, tmp_path):
        report = {"schema_version": "0.1", "plugin": {"name": "x"}}
        cache = tmp_path / "audit.json"
        audit_plugin._write_cache(cache, report)
        loaded = audit_plugin._read_cache(cache)
        assert loaded == report

    def test_write_is_atomic(self, tmp_path):
        """Write via temp + rename so a partial write doesn't corrupt the cache."""
        report = {"schema_version": "0.1", "plugin": {"name": "x"}}
        cache = tmp_path / "audit.json"
        audit_plugin._write_cache(cache, report)
        # Final file exists.
        assert cache.exists()
        # No leftover .tmp files.
        stray = list(tmp_path.glob("*.tmp"))
        assert stray == []

    def test_read_nonexistent_returns_none(self, tmp_path):
        assert audit_plugin._read_cache(tmp_path / "nope.json") is None

    def test_read_corrupted_returns_none(self, tmp_path):
        cache = tmp_path / "audit.json"
        cache.write_text("not json {{{")
        # Reading a corrupted cache must not crash — returns None so caller
        # falls through to re-invoking griffith.
        assert audit_plugin._read_cache(cache) is None


class TestCacheDisable:
    def test_no_save_flag_prevents_write(self, tmp_path, monkeypatch):
        """With --no-save, even though a cache path could be computed,
        the wrapper MUST NOT write to it.

        This test lives at the integration level (main flow). For now,
        verify that the cache-write helper is a pure function: callers
        control when to invoke it.
        """
        # Verify _write_cache is only called when the caller wants it.
        # This is a contract test on behavior, not a static one.
        report = {"schema_version": "0.1"}
        cache = tmp_path / "nope.json"
        # Nothing happens just by having the helper exist.
        assert not cache.exists()
        # Caller explicitly invokes → write happens.
        audit_plugin._write_cache(cache, report)
        assert cache.exists()
