"""Tests for the network plugin-update check (U1-U5).

Everything is offline: the only network primitive, `overwatch._http_get_json`,
is stubbed, and state is redirected to a tmp dir. Fixtures mirror the real-world
marketplace shapes we validated against live installs.
"""

from __future__ import annotations

import json

import pytest

import overwatch
import session_start


# --------------------------------------------------------------------------
# Helpers / fixtures
# --------------------------------------------------------------------------

def _http_stub(routes):
    """Build a stub for _http_get_json: first route substring found in the URL
    wins; unmatched URLs return None (a 404/offline)."""
    def stub(url, timeout):
        for key, val in routes.items():
            if key in url:
                return val
        return None
    return stub


@pytest.fixture
def tmp_state(tmp_path, monkeypatch):
    """Redirect Overwatch state to an isolated tmp dir."""
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    monkeypatch.setattr(overwatch, "get_state_dir", lambda: state_dir)
    return state_dir


@pytest.fixture
def plugins_dir(tmp_path, monkeypatch):
    """A tmp ~/.claude/plugins with installed + known_marketplaces, wired into
    session_start.get_plugins_dir."""
    d = tmp_path / "plugins"
    d.mkdir()
    (d / "installed_plugins.json").write_text(json.dumps({
        "plugins": {
            "lastmilefirst@gruntwork-marketplace": [{"version": "0.16.0"}],
        }
    }))
    (d / "known_marketplaces.json").write_text(json.dumps({
        "gruntwork-marketplace": {
            "source": {"source": "github", "repo": "GruntworkAI/gruntwork-marketplace"},
        }
    }))
    monkeypatch.setattr(session_start, "get_plugins_dir", lambda: d)
    return d


# --------------------------------------------------------------------------
# U1: resolver + source-path validation
# --------------------------------------------------------------------------

class TestResolver:
    def test_github_repo_valid(self):
        known = {"m": {"source": {"source": "github", "repo": "Owner/repo.name-1"}}}
        assert overwatch.resolve_github_repo("m", known) == "Owner/repo.name-1"

    @pytest.mark.parametrize("repo", ["../x", "a/b/c", "-lead/x", "a b/c", "ext::sh", "a@b/c"])
    def test_github_repo_malformed_rejected(self, repo):
        known = {"m": {"source": {"source": "github", "repo": repo}}}
        assert overwatch.resolve_github_repo("m", known) is None

    def test_non_github_source_rejected(self):
        known = {"m": {"source": {"source": "gitlab", "repo": "a/b"}}}
        assert overwatch.resolve_github_repo("m", known) is None

    def test_missing_marketplace(self):
        assert overwatch.resolve_github_repo("absent", {}) is None

    def test_source_path_in_repo(self):
        assert overwatch._validate_source_path("./plugins/x") == "plugins/x"
        assert overwatch._validate_source_path("plugins/x") == "plugins/x"

    def test_source_path_root(self):
        assert overwatch._validate_source_path("./") == ""
        assert overwatch._validate_source_path(".") == ""

    def test_source_path_dict_skipped(self):
        assert overwatch._validate_source_path({"source": "git-subdir"}) is None

    @pytest.mark.parametrize("bad", ["../etc", "%2e%2e/x", "/abs/path", "a/../b"])
    def test_source_path_traversal_rejected(self, bad):
        assert overwatch._validate_source_path(bad) is None


# --------------------------------------------------------------------------
# U2: fetcher
# --------------------------------------------------------------------------

class TestFetcher:
    def test_inline_version(self, monkeypatch):
        monkeypatch.setattr(overwatch, "_http_get_json", _http_stub({
            "marketplace.json": {"plugins": [{"name": "p", "version": "1.2.3"}]},
        }))
        assert overwatch.fetch_upstream_version("o/r", "p", overwatch.time.monotonic() + 5) == "1.2.3"

    def test_plugin_json_fallback(self, monkeypatch):
        monkeypatch.setattr(overwatch, "_http_get_json", _http_stub({
            "marketplace.json": {"plugins": [{"name": "p", "source": "./sub"}]},
            "sub/.claude-plugin/plugin.json": {"version": "3.19.0"},
        }))
        assert overwatch.fetch_upstream_version("o/r", "p", overwatch.time.monotonic() + 5) == "3.19.0"

    def test_name_not_listed_skips(self, monkeypatch):
        monkeypatch.setattr(overwatch, "_http_get_json", _http_stub({
            "marketplace.json": {"plugins": [{"name": "other", "version": "1.0.0"}]},
        }))
        assert overwatch.fetch_upstream_version("o/r", "p", overwatch.time.monotonic() + 5) is None

    def test_dict_source_skips(self, monkeypatch):
        monkeypatch.setattr(overwatch, "_http_get_json", _http_stub({
            "marketplace.json": {"plugins": [{"name": "p", "source": {"source": "git-subdir"}}]},
        }))
        assert overwatch.fetch_upstream_version("o/r", "p", overwatch.time.monotonic() + 5) is None

    def test_manifest_404_returns_none(self, monkeypatch):
        monkeypatch.setattr(overwatch, "_http_get_json", _http_stub({}))  # everything 404s
        assert overwatch.fetch_upstream_version("o/r", "p", overwatch.time.monotonic() + 5) is None

    def test_deadline_exceeded_returns_none(self, monkeypatch):
        called = []
        monkeypatch.setattr(overwatch, "_http_get_json",
                            lambda url, timeout: called.append(url))
        # deadline already passed -> no fetch attempted
        assert overwatch.fetch_upstream_version("o/r", "p", overwatch.time.monotonic() - 1) is None
        assert called == []

    def test_http_get_json_rejects_non_raw_host(self):
        # host pin enforced before any network use
        assert overwatch._http_get_json("https://evil.com/x", 1) is None
        assert overwatch._http_get_json("https://raw.githubusercontent.com.attacker.com/x", 1) is None

    def test_redirect_handler_refuses_foreign_host(self):
        handler = overwatch._PinnedRedirectHandler()
        req = overwatch.urllib.request.Request(
            "https://raw.githubusercontent.com/a/b/main/x")
        result = handler.redirect_request(req, None, 302, "Found", {}, "https://evil.com/x")
        assert result is None


# --------------------------------------------------------------------------
# U3: version selection
# --------------------------------------------------------------------------

class TestVersionSelect:
    @pytest.mark.parametrize("installed,upstream,expected", [
        ("0.16.0", "0.16.1", True),
        ("0.16.1", "0.16.1", False),
        ("0.17.0", "0.16.1", False),
        ("0.9.0", "0.16.1", True),          # lexical trap
        ("0.17.0", "0.17.1-rc1", False),    # pre-release guard
    ])
    def test_is_newer(self, installed, upstream, expected):
        assert overwatch.is_newer(installed, upstream) is expected

    def test_is_pre_release(self):
        assert overwatch.is_pre_release("0.17.1-rc1") is True
        assert overwatch.is_pre_release("0.16.1") is False
        assert overwatch.is_pre_release("") is True


# --------------------------------------------------------------------------
# U4: throttle + cache state
# --------------------------------------------------------------------------

class TestState:
    def test_check_due(self):
        assert overwatch.is_plugin_check_due({"global": {"last_plugin_check": 0}}, 1_000_000) is True
        assert overwatch.is_plugin_check_due({"global": {"last_plugin_check": 999_000}}, 1_000_000) is False
        assert overwatch.is_plugin_check_due({"global": {"last_plugin_check": 1000}}, 1_000_000) is True

    def test_record_check_started_advances_timestamp(self, tmp_state):
        overwatch.record_check_started(555)
        assert overwatch.load_state()["global"]["last_plugin_check"] == 555

    def test_cache_round_trip_and_prune(self, tmp_state):
        overwatch.write_plugin_update_results({"p@m": "1.0.1", "q@m": "2.0.0"}, 100)
        cache = overwatch.get_plugin_update_cache(overwatch.load_state())
        assert cache["p@m"]["available"] == "1.0.1"
        assert cache["p@m"]["checked_at"] == 100
        # writing wholesale prunes q@m
        overwatch.write_plugin_update_results({"p@m": "1.0.1"}, 200)
        cache = overwatch.get_plugin_update_cache(overwatch.load_state())
        assert "q@m" not in cache

    def test_ensure_v2_forward_fills_cache_field(self):
        state = overwatch._ensure_v2({"version": 2, "global": {"last_plugin_check": 5}})
        assert state["global"]["plugin_update_cache"] == {}

    def test_malformed_cache_treated_empty(self):
        assert overwatch.get_plugin_update_cache({"global": {"plugin_update_cache": "oops"}}) == {}


# --------------------------------------------------------------------------
# U5: check_plugin_updates end-to-end
# --------------------------------------------------------------------------

class TestCheckPluginUpdates:
    def test_refresh_then_surface(self, plugins_dir, tmp_state, monkeypatch):
        monkeypatch.setattr(overwatch, "_http_get_json", _http_stub({
            "marketplace.json": {"plugins": [{"name": "lastmilefirst", "version": "0.16.1"}]},
        }))
        # call 1: empty cache, triggers refresh
        assert session_start.check_plugin_updates() == []
        # call 2: surfaces from populated cache
        out = session_start.check_plugin_updates()
        assert out == ["   lastmilefirst@gruntwork-marketplace: 0.16.0 -> 0.16.1"]

    def test_self_clears_when_installed_matches(self, plugins_dir, tmp_state, monkeypatch):
        # cache says 0.16.0 available but installed is 0.16.0 -> no alert
        monkeypatch.setattr(overwatch, "_http_get_json", _http_stub({
            "marketplace.json": {"plugins": [{"name": "lastmilefirst", "version": "0.16.0"}]},
        }))
        session_start.check_plugin_updates()  # refresh: nothing newer
        assert session_start.check_plugin_updates() == []

    def test_uninstalled_cache_entry_pruned(self, plugins_dir, tmp_state, monkeypatch):
        monkeypatch.setattr(overwatch, "_http_get_json", _http_stub({}))
        # seed cache with a plugin that is NOT installed
        overwatch.write_plugin_update_results({"ghost@m": "9.9.9"}, 1)
        assert session_start.check_plugin_updates() == []

    def test_not_due_skips_network(self, plugins_dir, tmp_state, monkeypatch):
        import time as _t
        overwatch.record_check_started(int(_t.time()))  # just checked -> not due
        called = []
        monkeypatch.setattr(overwatch, "_http_get_json",
                            lambda url, timeout: called.append(url))
        session_start.check_plugin_updates()
        assert called == []

    def test_local_manifest_diff_still_fires(self, plugins_dir, tmp_state, monkeypatch):
        # local cached manifest ahead of installed -> alert without network
        mp = plugins_dir / "marketplaces" / "gruntwork-marketplace" / "plugins" / "lastmilefirst" / ".claude-plugin"
        mp.mkdir(parents=True)
        (mp / "plugin.json").write_text(json.dumps({"version": "0.16.1"}))
        import time as _t
        overwatch.record_check_started(int(_t.time()))  # not due -> no network path
        out = session_start.check_plugin_updates()
        assert out == ["   lastmilefirst@gruntwork-marketplace: 0.16.0 -> 0.16.1"]

    def test_malformed_installed_never_crashes(self, plugins_dir, tmp_state, monkeypatch):
        # non-dict install record + numeric version must not crash the hook
        (plugins_dir / "installed_plugins.json").write_text(json.dumps({
            "plugins": {
                "bad@m": ["1.0.0"],             # install record is a str, not a dict
                "num@m": [{"version": 0.16}],   # version is a number, not a str
            }
        }))
        monkeypatch.setattr(overwatch, "_http_get_json", _http_stub({}))
        assert session_start.check_plugin_updates() == []

    def test_local_diff_ignores_prerelease(self, plugins_dir, tmp_state, monkeypatch):
        # a locally-cached pre-release manifest must not raise a false alert
        mp = (plugins_dir / "marketplaces" / "gruntwork-marketplace" / "plugins" /
              "lastmilefirst" / ".claude-plugin")
        mp.mkdir(parents=True)
        (mp / "plugin.json").write_text(json.dumps({"version": "0.17.1-rc1"}))
        import time as _t
        overwatch.record_check_started(int(_t.time()))  # not due -> local path only
        assert session_start.check_plugin_updates() == []


class _FakeResp:
    def __init__(self, body, status=200):
        self._body, self.status = body, status

    def read(self, n):
        return self._body[:n]

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class TestHttpPrimitive:
    def test_valid_json(self, monkeypatch):
        monkeypatch.setattr(overwatch._OPENER, "open",
                            lambda req, timeout: _FakeResp(b'{"version":"1.0.0"}'))
        assert overwatch._http_get_json(
            "https://raw.githubusercontent.com/a/b/main/x", 1) == {"version": "1.0.0"}

    def test_bounded_read_rejected(self, monkeypatch):
        big = b'{"x":1}' + b" " * (overwatch._MAX_FETCH_BYTES + 10)
        monkeypatch.setattr(overwatch._OPENER, "open", lambda req, timeout: _FakeResp(big))
        assert overwatch._http_get_json(
            "https://raw.githubusercontent.com/a/b/main/x", 1) is None

    def test_non_200_rejected(self, monkeypatch):
        monkeypatch.setattr(overwatch._OPENER, "open",
                            lambda req, timeout: _FakeResp(b"{}", status=500))
        assert overwatch._http_get_json(
            "https://raw.githubusercontent.com/a/b/main/x", 1) is None
