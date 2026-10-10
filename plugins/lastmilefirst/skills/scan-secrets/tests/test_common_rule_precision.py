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


# --- generic PII rules (tag `pii`) -----------------------------------------
#
# Added 2026-10-09. These rules warn in a private repo and block in a public
# one; the policy lives in the scanner, the shapes live here. Unlike the
# connection-string cases above, these run the real gitleaks binary with the
# shipped TOML as its only config, because the rules depend on things Python
# `re` does not model: the keyword prefilter and the rule's allowlist. Running
# the whole file also proves every rule in it compiles under RE2 (one bad
# regex panics gitleaks for the entire merged config).
#
# Every sample value is invented. Phone numbers use the 555-01xx fiction
# range; the card and IBAN are the published test values.

import json
import shutil
import subprocess

PII_RULES = [
    "lmf-pii-personal-email",
    "lmf-pii-phone",
    "lmf-pii-ssn",
    "lmf-pii-aws-account-id",
    "lmf-pii-bank-identifier",
]

# (case name, rule id, file content, should fire)
PII_CASES = [
    # personal email
    ("email_gmail", "lmf-pii-personal-email", "contact: jordan.sample42@gmail.com\n", True),  # gitleaks:allow
    ("email_proton", "lmf-pii-personal-email", "reply_to = 'river.example@proton.me'\n", True),  # gitleaks:allow
    ("email_corporate", "lmf-pii-personal-email", "contact: jordan.sample@example-corp.com\n", False),
    ("email_noreply", "lmf-pii-personal-email", "author = 123456+samplebot@users.noreply.github.com\n", False),
    # phone
    ("phone_labeled", "lmf-pii-phone", "phone: (415) 555-0142\n", True),  # gitleaks:allow
    ("phone_e164", "lmf-pii-phone", "emergency contact +44 20 7946 0958\n", True),  # gitleaks:allow
    ("phone_bare_order_id", "lmf-pii-phone", "order_id = 4155550142\n", False),
    ("phone_hotel_word", "lmf-pii-phone", "hotel booking ref 4155550142\n", False),
    # ssn
    ("ssn_labeled", "lmf-pii-ssn", "SSN: 123-45-6789\n", True),  # gitleaks:allow
    ("ssn_unlabeled", "lmf-pii-ssn", "part number 123-45-6789\n", False),
    ("ssn_classname", "lmf-pii-ssn", "classname 123-45-6789\n", False),
    # aws account id
    ("aws_arn", "lmf-pii-aws-account-id", "role = arn:aws:iam::123456789012:role/deployer\n", True),  # gitleaks:allow
    ("aws_labeled", "lmf-pii-aws-account-id", "aws_account_id = \"123456789012\"\n", True),  # gitleaks:allow
    ("aws_invoice", "lmf-pii-aws-account-id", "invoice_number = 482910374615\n", False),
    # bank identifier
    ("bank_iban", "lmf-pii-bank-identifier", "IBAN: GB82 WEST 1234 5698 7654 32\n", True),  # gitleaks:allow
    ("bank_card", "lmf-pii-bank-identifier", "card_number = 4111 1111 1111 1111\n", True),  # gitleaks:allow
    ("bank_card_unlabeled", "lmf-pii-bank-identifier", "tracking: 4111 1111 1111 1111\n", False),
    ("bank_cardholder", "lmf-pii-bank-identifier", "cardholder ref 4111111111111111\n", False),
]


@pytest.fixture(scope="module")
def pii_findings(tmp_path_factory):
    """Run gitleaks once over one file per case; map case name -> rule ids."""
    if shutil.which("gitleaks") is None:
        pytest.skip("gitleaks binary not installed")
    root = tmp_path_factory.mktemp("pii")
    corpus = root / "corpus"
    corpus.mkdir()
    for name, _rule, content, _fires in PII_CASES:
        (corpus / f"{name}.txt").write_text(content, encoding="utf-8")
    report = root / "report.json"
    proc = subprocess.run(
        [
            "gitleaks", "dir", str(corpus),
            "--config", str(DATA),
            "--report-format", "json",
            "--report-path", str(report),
            "--no-banner",
            "--exit-code", "0",
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, f"gitleaks failed to load the shipped config:\n{proc.stderr}"
    hits = {}
    for finding in json.loads(report.read_text(encoding="utf-8") or "[]"):
        hits.setdefault(Path(finding["File"]).stem, set()).add(finding["RuleID"])
    return hits


@pytest.mark.parametrize("rule_id", PII_RULES)
def test_pii_rules_are_tagged_low_and_keyword_gated(rules, rule_id):
    rule = rules[rule_id]
    assert {"pii", "lmf", "severity-low"} <= set(rule["tags"])
    assert rule.get("keywords"), f"{rule_id} has no keywords, so gitleaks cannot prefilter"


def test_every_pii_rule_has_a_positive_and_a_negative_case():
    for rule_id in PII_RULES:
        outcomes = {fires for _n, r, _c, fires in PII_CASES if r == rule_id}
        assert outcomes == {True, False}, rule_id


@pytest.mark.parametrize(
    "name,rule_id,content,fires", PII_CASES, ids=[c[0] for c in PII_CASES]
)
def test_pii_rule_precision(pii_findings, name, rule_id, content, fires):
    got = rule_id in pii_findings.get(name, set())
    assert got is fires, f"{rule_id} on {content!r}: expected fires={fires}, got {sorted(pii_findings.get(name, set()))}"


def test_noreply_allowlist_is_in_the_email_rule(rules):
    allow = rules["lmf-pii-personal-email"].get("allowlist") or {}
    assert any("users\\.noreply\\.github\\.com" in r for r in allow.get("regexes", []))
