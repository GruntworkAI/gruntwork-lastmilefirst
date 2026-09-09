"""Tests for the compound counter, the named invocation log, and the stop nudge (0.31.0).

Offline. State is redirected to a tmp dir via monkeypatch.
"""

from __future__ import annotations

import time

import pytest

import overwatch
import session_start
import stop_hook


NOW = int(time.time())


@pytest.fixture
def state_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(overwatch, "get_state_dir", lambda: tmp_path)
    monkeypatch.setattr(overwatch, "get_invocations_file", lambda: tmp_path / "invocations.log")
    monkeypatch.setattr(session_start, "get_invocations_file", lambda: tmp_path / "invocations.log")
    monkeypatch.setattr(session_start, "get_lock_file", lambda: tmp_path / "lock")
    monkeypatch.setattr(session_start, "get_state_dir", lambda: tmp_path)
    monkeypatch.setattr(stop_hook, "get_state_dir", lambda: tmp_path)
    monkeypatch.setattr(session_start.random, "randint", lambda a, b: 5)
    return tmp_path


def _write(path, lines):
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# --- parsing and normalization ------------------------------------------------

def test_normalize_strips_plugin_prefix_and_run():
    assert overwatch.normalize_skill_name("lastmilefirst:run-review-voice") == "review-voice"
    assert overwatch.normalize_skill_name("compound-engineering:ce-explain") == "ce-explain"
    assert overwatch.normalize_skill_name("add-wisdom") == "add-wisdom"
    assert overwatch.normalize_skill_name("") == "unknown"


def test_name_from_payload_skill_and_agent():
    assert overwatch.invocation_name_from_payload(
        {"tool_input": {"skill": "lastmilefirst:run-add-wisdom"}}) == "add-wisdom"
    assert overwatch.invocation_name_from_payload(
        {"tool_input": {"subagent_type": "lastmilefirst:consult-ripley"}}) == "consult-ripley"
    assert overwatch.invocation_name_from_payload({}) == "unknown"
    assert overwatch.invocation_name_from_payload({"tool_input": "not a dict"}) == "unknown"


def test_parse_accepts_legacy_and_v2_lines():
    legacy = overwatch.parse_invocation_line(f"{NOW}|skill")
    assert legacy == {"ts": NOW, "kind": "skill", "name": "", "session": ""}
    v2 = overwatch.parse_invocation_line(f"{NOW}|skill|lastmilefirst:run-code-review|s1")
    assert v2["name"] == "code-review" and v2["session"] == "s1"
    assert overwatch.parse_invocation_line("garbage") is None
    assert overwatch.parse_invocation_line("notanint|skill") is None


def test_closing_and_compound_classification():
    assert overwatch.is_closing_skill("review-voice")
    assert overwatch.is_closing_skill("strict-parc")
    assert overwatch.is_closing_skill("ce-commit-push-pr")
    assert not overwatch.is_closing_skill("search-wisdom")
    assert overwatch.is_compound_skill("ce-explain")
    assert overwatch.is_compound_skill("lastmilefirst:run-add-knowledge")
    assert not overwatch.is_compound_skill("review-voice")


# --- summary ------------------------------------------------------------------

def test_compound_summary_counts_sessions_not_keystrokes():
    recs = [overwatch.parse_invocation_line(l) for l in [
        f"{NOW}|skill|review-voice|s1",
        f"{NOW}|skill|review-voice|s1",      # same session, still one closing session
        f"{NOW}|skill|code-review|s2",
        f"{NOW}|skill|add-wisdom|s2",
        f"{NOW}|skill|search-wisdom|s3",
        f"{NOW}|skill",                       # legacy, no name: ignored
    ]]
    s = overwatch.compound_summary(recs)
    assert s == {"compound": 1, "closing_sessions": 2, "sessions": 3}


# --- session start ------------------------------------------------------------

def test_usage_stats_names_top_skills_and_counts_compound(state_dir):
    _write(state_dir / "invocations.log", [
        f"{NOW}|skill|lastmilefirst:run-review-voice|s1",
        f"{NOW}|skill|lastmilefirst:run-review-voice|s2",
        f"{NOW}|skill|ce-explain|s2",
        f"{NOW - 40 * 86400}|skill|old-skill|s0",   # pruned (older than a month)
    ])
    out = session_start.check_usage_stats()
    assert out[0] == "3 skill invocations this week"
    assert "review-voice (2)" in out[1]
    assert "1 compound actions this week (2 sessions closed a cycle)" in out[2]
    assert not any(line.startswith("WARNING") for line in out)
    assert "old-skill" not in (state_dir / "invocations.log").read_text()


def test_usage_stats_warns_at_threshold(state_dir):
    n = overwatch.COMPOUND_WARNING_MIN_CYCLES
    _write(state_dir / "invocations.log",
           [f"{NOW}|skill|code-review|s{i}" for i in range(n)])
    out = session_start.check_usage_stats()
    warn = [l for l in out if l.startswith("WARNING")]
    assert len(warn) == 1 and f"{n} sessions closed a cycle" in warn[0]


def test_usage_stats_no_warning_below_threshold_or_when_compounded(state_dir):
    n = overwatch.COMPOUND_WARNING_MIN_CYCLES
    _write(state_dir / "invocations.log",
           [f"{NOW}|skill|code-review|s{i}" for i in range(n - 1)])
    assert not any(l.startswith("WARNING") for l in session_start.check_usage_stats())
    _write(state_dir / "invocations.log",
           [f"{NOW}|skill|code-review|s{i}" for i in range(n)] + [f"{NOW}|skill|add-wisdom|s0"])
    assert not any(l.startswith("WARNING") for l in session_start.check_usage_stats())


# --- stop hook ----------------------------------------------------------------

def test_stop_nudge_fires_once_per_session(state_dir, capsys):
    _write(state_dir / "invocations.log", [f"{NOW}|skill|review-voice|sess-a"])
    assert stop_hook.check_compound_nudge("sess-a") is True
    assert overwatch.COMPOUND_NUDGE in capsys.readouterr().out
    assert stop_hook.check_compound_nudge("sess-a") is False   # flag set
    assert capsys.readouterr().out == ""


def test_stop_nudge_silent_without_closing_or_with_compound(state_dir, capsys):
    _write(state_dir / "invocations.log", [f"{NOW}|skill|search-wisdom|sess-b"])
    assert stop_hook.check_compound_nudge("sess-b") is False
    _write(state_dir / "invocations.log",
           [f"{NOW}|skill|review-voice|sess-c", f"{NOW}|skill|add-wisdom|sess-c"])
    assert stop_hook.check_compound_nudge("sess-c") is False
    assert stop_hook.check_compound_nudge("") is False
    assert capsys.readouterr().out == ""


def test_session_start_prunes_old_nudge_flags(state_dir):
    import os
    _write(state_dir / "invocations.log", [f"{NOW}|skill|search-wisdom|s1"])
    old = state_dir / "compound-nudged-old"; old.touch()
    os.utime(old, (NOW - 8 * 86400, NOW - 8 * 86400))
    fresh = state_dir / "compound-nudged-fresh"; fresh.touch()
    session_start.check_usage_stats()
    assert not old.exists() and fresh.exists()
