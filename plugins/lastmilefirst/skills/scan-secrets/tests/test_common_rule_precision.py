"""Precision guards for the low-severity common rules.

These rules generate most of the false positives in a workspace sweep, and
the fix for that is narrowing where they apply. The risk of narrowing is
over-narrowing, so every suppression case here is paired with a case that
must STILL fire. A change that silences the noise and the signal together
fails this suite.

Patterns are read from the shipped TOML rather than restated, so editing a
rule without revisiting its behavior breaks these tests. gitleaks uses Go
RE2; these patterns are in the common subset, so Python `re` is a faithful
stand-in and needs no gitleaks binary.
"""
import re
import sys
from pathlib import Path

import pytest

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - the repo targets 3.11+
    tomllib = pytest.importorskip("tomli")

DATA = Path(__file__).resolve().parents[1] / "data" / "common_secret_formats.toml"

CONNECTION_RULES = [
    "lmf-postgres-connection-string",
    "lmf-mysql-connection-string",
    "lmf-mongodb-connection-string",
    "lmf-redis-connection-string",
]


@pytest.fixture(scope="module")
def rules():
    with DATA.open("rb") as fh:
        return {r["id"]: r for r in tomllib.load(fh)["rules"]}


def _fires(rule, text):
    """True when the rule matches and no allowlist regex excuses the match."""
    match = re.search(rule["regex"], text)
    if not match:
        return False
    for pattern in (rule.get("allowlist") or {}).get("regexes", []):
        if re.search(pattern, match.group(0)):
            return False
    return True


# --- connection strings ----------------------------------------------------

@pytest.mark.parametrize("rule_id", CONNECTION_RULES)
def test_connection_rules_carry_an_allowlist(rules, rule_id):
    """The gap that caused the noise: these four shipped without one."""
    allowlist = rules[rule_id].get("allowlist")
    assert allowlist, f"{rule_id} has no allowlist"
    assert allowlist.get("paths"), f"{rule_id} allowlist has no paths"
    assert allowlist.get("regexes"), f"{rule_id} allowlist has no regexes"


@pytest.mark.parametrize(
    "text",
    [
        "postgres://postgres:postgres@localhost/gemname_test",  # gitleaks:allow
        "postgresql://user:password@127.0.0.1:5432/app",  # gitleaks:allow
        "postgres://root:secret@db/appdb",  # gitleaks:allow
        "postgres://test:changeme@host.docker.internal/x",  # gitleaks:allow
    ],
)
def test_local_dummy_databases_are_suppressed(rules, text):
    assert not _fires(rules["lmf-postgres-connection-string"], text)


@pytest.mark.parametrize(
    "text",
    [
        "postgres://admin:Xk9dHq2mZpQw7Lv@prod-db.example.com/app",  # gitleaks:allow
        "postgres://svc_user:aB3dEf9hJk@10.4.2.9:5432/warehouse",  # gitleaks:allow
        # dummy-looking password, but a real remote host: still a leak
        "postgres://postgres:password@prod.internal.example.com/app",  # gitleaks:allow
    ],
)
def test_real_connection_strings_still_fire(rules, text):
    assert _fires(rules["lmf-postgres-connection-string"], text)


def test_allowlist_shape_is_shared_across_schemes(rules):
    """One regexes block covers all four schemes; keep them in step."""
    blocks = {tuple(rules[r]["allowlist"]["regexes"]) for r in CONNECTION_RULES}
    assert len(blocks) == 1, "connection-string allowlists have drifted apart"


# --- hardcoded password ----------------------------------------------------

def test_prompt_string_no_longer_matches(rules):
    """The regression that motivated the fix.

    The old value run `[^"']{8,}` was not confined to the string that opened
    it, so it consumed from this prompt's closing quote to the next quote on
    the line and reported an interactive prompt as a credential.
    """
    line = 'sudo -p "Enter your Mac login password: " systemsetup -getremotelogin | grep -q "On"'
    assert not _fires(rules["lmf-hardcoded-password"], line)


@pytest.mark.parametrize(
    "line",
    [
        'password = "hunter2hunter2"',
        "passwd: 'sup3rS3cretValue'",
        'PWD="correcthorsebattery"',
    ],
)
def test_genuine_hardcoded_passwords_still_fire(rules, line):
    assert _fires(rules["lmf-hardcoded-password"], line)


def test_value_run_excludes_whitespace(rules):
    """The substantive change. Documented so it is not 'simplified' back."""
    assert r"""[^"'\s]{8,}""" in rules["lmf-hardcoded-password"]["regex"]


def test_short_values_still_ignored(rules):
    assert not _fires(rules["lmf-hardcoded-password"], 'password = "short"')
