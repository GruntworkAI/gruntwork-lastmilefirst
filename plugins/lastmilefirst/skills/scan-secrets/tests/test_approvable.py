"""A repo marked approvable for a people rule (plan 2026-10-12-001, U1).

Covers the marker, per-finding eligibility, the unredacted second pass that
fetches the matched text (diff and archive), the grouped rendering, and
apply_approvals. gitleaks is replaced with a stand-in that writes REDACTED rows
on the first pass and the real text on the unredacted pass, the same way
test_visibility_policy.py stubs it. All names below are invented.
"""
from __future__ import annotations

import json
import subprocess
import zipfile
from pathlib import Path

import pytest

import scanner

PEOPLE_RULE = "lmf-private-people"

ORDINARY = {"RuleID": "generic-api-key", "File": "config.py", "StartLine": 9,
            "Severity": "HIGH", "Tags": ["org"]}
ORGANIZATION = {"RuleID": "lmf-private-names", "File": "README.md", "StartLine": 3,
                "Severity": "MEDIUM", "Tags": ["org", "public-only", "private-name"]}
PII = {"RuleID": "lmf-pii-personal-email", "File": "notes.md", "StartLine": 5,
       "Severity": "LOW", "Tags": ["pii"]}
PERSON = {"RuleID": PEOPLE_RULE, "File": "notes.md", "StartLine": 7,
          "Severity": "MEDIUM", "Tags": ["org", "private-name"]}
KINDS = {"ordinary": ORDINARY, "organization": ORGANIZATION, "pii": PII, "person": PERSON}
ALL_RULES = {f["RuleID"] for f in KINDS.values()}


# --- the marker ----------------------------------------------------------------

def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """A fresh repo with an empty global config, so the machine's own is not read."""
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tmp_path / "global.gitconfig"))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    path = tmp_path / "repo"
    path.mkdir()
    git(path, "init", "-q")
    return path


def test_no_marker_is_the_empty_set(repo):
    assert scanner.approvable_rules(repo) == set()


def test_one_marker(repo):
    git(repo, "config", "--add", "lastmilefirst.approvable", PEOPLE_RULE)
    assert scanner.approvable_rules(repo) == {PEOPLE_RULE}


def test_two_markers_are_read_lower_cased(repo):
    git(repo, "config", "--add", "lastmilefirst.approvable", "LMF-Private-People")
    git(repo, "config", "--add", "lastmilefirst.approvable", "lmf-family-names")
    assert scanner.approvable_rules(repo) == {PEOPLE_RULE, "lmf-family-names"}


def test_a_global_marker_does_not_count(repo, tmp_path):
    subprocess.run(["git", "config", "--global", "--add", "lastmilefirst.approvable", PEOPLE_RULE],
                   check=True, capture_output=True)
    assert "approvable = lmf-private-people" in (tmp_path / "global.gitconfig").read_text()
    assert scanner.approvable_rules(repo) == set()


def test_outside_a_repo_is_the_empty_set(tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tmp_path / "global.gitconfig"))
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    plain = tmp_path / "plain"
    plain.mkdir()
    assert scanner.approvable_rules(plain) == set()


MERGED_CONFIG = """
[extend]
useDefault = true

[[rules]]
id = 'lmf-private-people'
regex = '''(?i)\\b(examplesurname)\\b'''
tags = ['org', 'private-name']

[[rules]]
id = 'lmf-private-names'
regex = '''(?i)\\b(exampleco)\\b'''
tags = ['org', 'public-only', 'private-name']

[[rules]]
id = 'lmf-pii-personal-email'
regex = '''[a-z]+@example\\.com'''
tags = ['pii']

[[rules]]
id = 'lmf-example-token'
regex = '''tok_[a-z0-9]{16}'''
tags = ['org']
"""


def test_invalid_kinds_are_warned_once_each(tmp_path):
    config = tmp_path / "merged.toml"
    config.write_text(MERGED_CONFIG)
    marker = {PEOPLE_RULE, "lmf-private-names", "lmf-pii-personal-email",
              "lmf-example-token", "no-such-rule"}
    assert scanner.marker_warnings(marker, config) == [
        f"lastmilefirst.approvable names {rule}, which is not a people rule; ignored"
        for rule in ["lmf-example-token", "lmf-pii-personal-email",
                     "lmf-private-names", "no-such-rule"]
    ]


def test_a_people_rule_marker_is_not_warned(tmp_path):
    config = tmp_path / "merged.toml"
    config.write_text(MERGED_CONFIG)
    assert scanner.marker_warnings({PEOPLE_RULE}, config) == []
    assert scanner.marker_warnings(set(), config) == []


def test_an_unreadable_config_warns_about_nothing(tmp_path):
    config = tmp_path / "merged.toml"
    config.write_text("this is [not toml")
    assert scanner.marker_warnings({"anything"}, config) == []


# --- eligibility -----------------------------------------------------------------

@pytest.mark.parametrize("kind", sorted(KINDS))
def test_only_a_person_finding_is_approvable_even_when_every_rule_is_marked(kind):
    assert scanner.is_approvable(dict(KINDS[kind]), ALL_RULES) is (kind == "person")


def test_a_person_finding_from_an_unmarked_rule_is_not_approvable():
    other = dict(PERSON, RuleID="lmf-family-names")
    assert scanner.is_approvable(other, {PEOPLE_RULE}) is False


def test_rule_ids_compare_without_case():
    assert scanner.is_approvable(dict(PERSON, RuleID="LMF-Private-People"), {PEOPLE_RULE})


# --- the unredacted pass over the diff ---------------------------------------------

class StandIn:
    """gitleaks that writes `rows` on the first pass and `clear` when unredacted.

    The unredacted pass writes only the rows whose rule was enabled, as
    gitleaks does with --enable-rule. Each call is recorded.
    """

    def __init__(self):
        self.rows: list = []
        self.clear: list = []
        self.calls: list = []
        self.unredacted_writes = True

    def __call__(self, args, config_path=None, cwd=None, redact=True, enable_rules=None):
        report = Path(args[args.index("--report-path") + 1])
        self.calls.append({"args": list(args), "redact": redact,
                           "enable_rules": enable_rules, "report": report})
        if redact:
            report.write_text(json.dumps(
                [dict(r, Match="REDACTED", Secret="REDACTED") for r in self.rows]))
        elif self.unredacted_writes:
            report.write_text(json.dumps(
                [r for r in self.clear if r["RuleID"] in (enable_rules or [])]))
        return 1, "", ""


@pytest.fixture
def stand_in(monkeypatch):
    run = StandIn()
    monkeypatch.setattr(scanner, "_run_gitleaks", run)
    return run


def report(marker):
    findings, _code, _stderr = scanner._gitleaks_report(
        ["git", "--pre-commit", "--staged"], "gitleaks-staged-",
        Path("merged.toml"), None, False, approvable=marker)
    return findings


def test_enable_rule_ids_come_from_findings_not_marker_keys(stand_in):
    stand_in.rows = [dict(PERSON, Fingerprint="notes.md:lmf-private-people:7"), dict(ORDINARY)]
    stand_in.clear = [dict(PERSON, Fingerprint="notes.md:lmf-private-people:7",
                           Match="Examplesurname", Secret="Examplesurname")]

    report({PEOPLE_RULE, "lmf-family-names", "generic-api-key", "no-such-rule"})

    first, second = stand_in.calls
    assert first["redact"] is True and first["enable_rules"] is None
    assert second["redact"] is False
    assert second["enable_rules"] == [PEOPLE_RULE]


def test_the_first_pass_passes_no_new_arguments(stand_in, monkeypatch):
    """Older stand-ins that take (args, config_path, cwd) keep working."""
    seen = []

    def old_style(args, config_path=None, cwd=None):
        seen.append(args)
        Path(args[args.index("--report-path") + 1]).write_text("[]")
        return 0, "", ""

    monkeypatch.setattr(scanner, "_run_gitleaks", old_style)
    assert report({PEOPLE_RULE}) == []
    assert len(seen) == 1


def test_no_second_pass_without_an_approvable_finding(stand_in):
    stand_in.rows = [dict(ORDINARY), dict(PERSON, RuleID="lmf-family-names")]
    report({PEOPLE_RULE})
    assert len(stand_in.calls) == 1


def test_no_second_pass_without_a_marker(stand_in):
    stand_in.rows = [dict(PERSON)]
    findings = scanner._gitleaks_report(["git"], "p-", Path("m.toml"), None, False)[0]
    assert len(stand_in.calls) == 1
    assert findings[0]["Match"] == "REDACTED"


def test_the_unredacted_report_is_written_in_a_temp_dir_that_is_removed(stand_in):
    stand_in.rows = [dict(PERSON)]
    stand_in.clear = [dict(PERSON, Match="Examplesurname", Secret="Examplesurname")]
    report({PEOPLE_RULE})
    unredacted = stand_in.calls[1]["report"]
    assert unredacted.parent.name.startswith("lmf-approvable-")
    assert not unredacted.parent.exists()


def test_diff_findings_join_on_fingerprint_and_column(stand_in):
    """Two matches on one line share a fingerprint; the column keeps them apart,
    and the unredacted rows may come back in any order."""
    fp = "notes.md:lmf-private-people:7"
    stand_in.rows = [dict(PERSON, Fingerprint=fp, StartColumn=3),
                     dict(PERSON, Fingerprint=fp, StartColumn=40),
                     dict(ORDINARY, Fingerprint="config.py:generic-api-key:9")]
    stand_in.clear = [dict(PERSON, Fingerprint=fp, StartColumn=40,
                           Match="name: Otherperson", Secret="Otherperson"),
                      dict(PERSON, Fingerprint=fp, StartColumn=3,
                           Match="name: Examplesurname", Secret="Examplesurname")]

    findings = report({PEOPLE_RULE})

    by_column = {f.get("StartColumn"): f for f in findings if f["RuleID"] == PEOPLE_RULE}
    assert by_column[3]["Secret"] == "Examplesurname"
    assert by_column[40]["Secret"] == "Otherperson"
    assert all(f["_unredacted"] for f in by_column.values())
    ordinary = next(f for f in findings if f["RuleID"] == "generic-api-key")
    assert ordinary["Match"] == "REDACTED" and "_unredacted" not in ordinary
    assert scanner.unmatched_rules(findings, {PEOPLE_RULE}) == []


def test_diff_findings_without_a_fingerprint_join_on_file_line_rule(stand_in):
    stand_in.rows = [dict(PERSON), dict(PERSON, StartLine=8)]
    stand_in.clear = [dict(PERSON, StartLine=8, Secret="Otherperson"),
                      dict(PERSON, Secret="Examplesurname")]
    findings = report({PEOPLE_RULE})
    assert {f["StartLine"]: f["Secret"] for f in findings} == {
        7: "Examplesurname", 8: "Otherperson"}


def test_no_unredacted_report_leaves_the_findings_unmatched(stand_in):
    stand_in.rows = [dict(PERSON)]
    stand_in.unredacted_writes = False
    findings = report({PEOPLE_RULE})
    assert findings[0]["Match"] == "REDACTED"
    assert "no report from the unredacted pass" in findings[0]["_match_error"]
    assert scanner.unmatched_rules(findings, {PEOPLE_RULE}) == [PEOPLE_RULE]


def test_a_finding_with_no_row_in_the_unredacted_report_is_unmatched(stand_in):
    stand_in.rows = [dict(PERSON), dict(PERSON, StartLine=8)]
    stand_in.clear = [dict(PERSON, Secret="Examplesurname")]
    findings = report({PEOPLE_RULE})
    assert scanner.unmatched_rules(findings, {PEOPLE_RULE}) == [PEOPLE_RULE]
    missing = next(f for f in findings if f["StartLine"] == 8)
    assert missing["_match_error"] == "no matching row in the unredacted pass"


# --- the unredacted pass inside an archive -------------------------------------------

def test_archive_findings_join_on_file_line_rule(stand_in, monkeypatch, tmp_path):
    """The expanded directory is removed before scan_archives returns, so the
    second pass runs inside it; the join ignores the per-run fingerprint."""
    doc = tmp_path / "copy.docx"
    with zipfile.ZipFile(doc, "w") as zf:
        zf.writestr("word/document.xml", "<w:t>Examplesurname</w:t>")
    monkeypatch.setattr(scanner, "_candidate_files", lambda _cwd, _staged: ["copy.docx"])

    def rows_in(scan_dir, fingerprint, **extra):
        return [dict(PERSON, File=str(scan_dir / "word/document.xml"), StartLine=1,
                     Fingerprint=fingerprint, **extra)]

    def run(args, config_path=None, cwd=None, redact=True, enable_rules=None):
        scan_dir = Path(args[args.index("dir") + 1])
        assert scan_dir.is_dir()
        stand_in.calls.append({"redact": redact, "enable_rules": enable_rules})
        if redact:
            rows = rows_in(scan_dir, f"{scan_dir}/word/document.xml:x:1",
                           Match="REDACTED", Secret="REDACTED")
        else:
            rows = rows_in(scan_dir, "a-different-per-run-path:x:1",
                           Match="Examplesurname", Secret="Examplesurname")
        Path(args[args.index("--report-path") + 1]).write_text(json.dumps(rows))
        return 1, "", ""

    monkeypatch.setattr(scanner, "_run_gitleaks", run)

    findings = scanner.scan_archives(tmp_path, Path("merged.toml"), False,
                                     staged_only=True, approvable={PEOPLE_RULE})

    assert [f["File"] for f in findings] == ["copy.docx -> word/document.xml"]
    assert findings[0]["Secret"] == "Examplesurname"
    assert findings[0]["_unredacted"] is True
    assert [c["redact"] for c in stand_in.calls] == [True, False]
    assert stand_in.calls[1]["enable_rules"] == [PEOPLE_RULE]


def test_archive_without_a_marker_runs_one_pass(stand_in, monkeypatch, tmp_path):
    doc = tmp_path / "copy.docx"
    with zipfile.ZipFile(doc, "w") as zf:
        zf.writestr("word/document.xml", "<w:t>text</w:t>")
    monkeypatch.setattr(scanner, "_candidate_files", lambda _cwd, _staged: ["copy.docx"])
    stand_in.rows = [dict(PERSON)]
    findings = scanner.scan_archives(tmp_path, Path("merged.toml"), False, staged_only=True)
    assert len(stand_in.calls) == 1
    assert findings[0]["Match"] == "REDACTED"


# --- grouping by term -------------------------------------------------------------

def person(file, line, secret, match=None):
    return dict(PERSON, File=file, StartLine=line, Secret=secret,
                Match=match if match is not None else secret)


def test_casings_of_one_name_are_one_row():
    rows = ([person("copy.md", n, "Examplesurname") for n in range(1, 4)]
            + [person("copy.docx -> word/document.xml", n, "EXAMPLESURNAME") for n in range(1, 3)]
            + [person("notes.md", 1, "examplesurname")])
    text = scanner._format_approvable(rows)
    lines = text.splitlines()
    assert lines[0] == f"{PEOPLE_RULE} in 3 files (6 lines)"
    assert len([line for line in lines if "examplesurname" in line]) == 1
    assert "6×" in lines[1]
    # Files under the term, most lines first.
    assert [line.split()[-2] for line in lines[1:]] == [
        "copy.md", "word/document.xml", "notes.md"]
    assert lines[1].endswith("copy.md (3)")
    assert lines[2].endswith("copy.docx -> word/document.xml (2)")


def test_a_second_term_is_its_own_row():
    rows = [person("copy.md", 1, "Examplesurname"), person("copy.md", 2, "Examplesurname"),
            person("notes.md", 9, "Otherperson")]
    lines = scanner._format_approvable(rows).splitlines()
    assert lines[0] == f"{PEOPLE_RULE} in 2 files (3 lines)"
    assert lines[1].split()[:2] == ["examplesurname", "2×"]
    assert lines[2].split()[:2] == ["otherperson", "1×"]


def test_the_term_is_the_capture_group_not_the_label_text():
    rows = [person("copy.md", 1, "Examplesurname", match="author: Examplesurname")]
    text = scanner._format_approvable(rows)
    assert "examplesurname" in text
    assert "author" not in text


def test_the_term_falls_back_to_match_and_collapses_whitespace():
    rows = [person("copy.md", 1, "", match="Example   Surname"),
            person("copy.md", 2, "", match="example surname")]
    lines = scanner._format_approvable(rows).splitlines()
    assert lines[1].split()[:3] == ["example", "surname", "2×"]


def test_files_under_a_term_are_capped_at_five():
    rows = [person(f"doc-{i}.md", line, "Examplesurname")
            for i in range(7) for line in range(1, 8 - i)]
    lines = scanner._format_approvable(rows).splitlines()
    assert lines[0] == f"{PEOPLE_RULE} in 7 files (28 lines)"
    listed = [line for line in lines[1:] if ".md (" in line]
    assert len(listed) == 5
    assert listed[0].endswith("doc-0.md (7)")
    assert listed[-1].endswith("doc-4.md (3)")
    assert lines[-1].strip() == "... and 2 more files"


def test_a_single_file_and_line_read_singular():
    lines = scanner._format_approvable([person("copy.md", 1, "Examplesurname")]).splitlines()
    assert lines[0] == f"{PEOPLE_RULE} in 1 file (1 line)"


# --- apply_approvals ----------------------------------------------------------------

def policy(rows):
    kept, _ = scanner.apply_visibility_policy(rows, "PRIVATE")
    return kept


def test_approved_findings_stop_blocking_and_others_are_untouched():
    rows = policy([dict(PERSON), dict(ORDINARY), dict(PERSON, RuleID="lmf-family-names")])
    out, subset = scanner.apply_approvals(rows, {PEOPLE_RULE}, approved=True)
    assert [f["RuleID"] for f in subset] == [PEOPLE_RULE]
    assert subset[0]["Blocking"] is False and subset[0]["Approved"] is True
    others = [f for f in out if f["RuleID"] != PEOPLE_RULE]
    assert all(f["Blocking"] is True and "Approved" not in f for f in others)
    assert len(out) == 3


def test_unapproved_findings_still_block_and_are_returned_for_rendering():
    rows = policy([dict(PERSON), dict(ORDINARY)])
    out, subset = scanner.apply_approvals(rows, {PEOPLE_RULE}, approved=False)
    assert out == rows
    assert [f["RuleID"] for f in subset] == [PEOPLE_RULE]
    assert subset[0]["Blocking"] is True and "Approved" not in subset[0]


def test_apply_approvals_does_not_mutate_its_input():
    rows = policy([dict(PERSON)])
    scanner.apply_approvals(rows, {PEOPLE_RULE}, approved=True)
    assert rows[0]["Blocking"] is True and "Approved" not in rows[0]


def test_a_marker_on_a_non_people_rule_approves_nothing():
    rows = policy([dict(ORDINARY), dict(PII)])
    out, subset = scanner.apply_approvals(rows, {"generic-api-key", "lmf-pii-personal-email"},
                                          approved=True)
    assert subset == []
    assert out == rows


# --- the ask in scan_staged (U2) ------------------------------------------------------
#
# scan_staged with gitleaks, the merged config, the marker, and visibility
# replaced. /dev/tty is replaced too, so no test reads the real terminal.

class FakeTty:
    """A terminal that records what is written and answers one line."""

    def __init__(self, answer):
        self.answer = answer
        self.written = ""
        self.opened = 0

    def __call__(self):
        self.opened += 1
        return self

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def write(self, text):
        self.written += text

    def flush(self):
        pass

    def readline(self):
        return self.answer


def no_tty():
    raise OSError(6, "Device not configured")


def must_not_open_tty():
    raise AssertionError("the tty was opened")


class Staged:
    """Knobs for one scan_staged run."""

    def __init__(self, monkeypatch, stand_in, tmp_path):
        self.monkeypatch = monkeypatch
        self.stand_in = stand_in
        self.tmp_path = tmp_path
        self.archive_rows: list = []
        self.marker = {PEOPLE_RULE}
        self.visibility = "PRIVATE"
        self.tty = no_tty

    def person(self, line, secret, file="copy.md", column=1):
        fp = f"{file}:{PEOPLE_RULE}:{line}"
        row = dict(PERSON, File=file, StartLine=line, StartColumn=column, Fingerprint=fp)
        self.stand_in.rows.append(row)
        self.stand_in.clear.append(dict(row, Match=f"by {secret}", Secret=secret))

    def run(self):
        config = self.tmp_path / "merged.toml"
        mp = self.monkeypatch
        mp.setattr(scanner, "_check_gitleaks", lambda: None)
        mp.setattr(scanner, "write_merged_config",
                   lambda *a, **k: (config.write_text(MERGED_CONFIG), config)[1])
        mp.setattr(scanner, "consume_sync_note", lambda: None)
        mp.setattr(scanner, "scan_archives", lambda *a, **k: [dict(r) for r in self.archive_rows])
        mp.setattr(scanner, "approvable_rules", lambda _repo=None: set(self.marker))
        mp.setattr(scanner, "check_repo_visibility", lambda _repo=None: self.visibility)
        mp.setattr(scanner, "_open_tty", self.tty)
        return scanner.scan_staged(self.tmp_path)


@pytest.fixture
def staged(stand_in, monkeypatch, tmp_path):
    monkeypatch.delenv("CLAUDECODE", raising=False)
    monkeypatch.delenv("LMF_APPROVE", raising=False)
    return Staged(monkeypatch, stand_in, tmp_path)


RERUN = "to approve these terms, re-run: LMF_APPROVE='{}' git commit <your arguments>"
AGENT_RERUN = ("show the user the terms above and get their confirmation, then re-run: "
               "LMF_APPROVE='{}' git commit <your arguments>")
NO_VERIFY = "--no-verify would also skip the identity check"
HEADER = f"{PEOPLE_RULE} in 1 file (3 lines)"


def two_terms(staged):
    staged.person(1, "Examplesurname")
    staged.person(2, "Examplesurname")
    staged.person(3, "Otherperson")


def test_env_naming_every_shown_term_approves_and_prints_the_block(staged, monkeypatch):
    two_terms(staged)
    staged.tty = must_not_open_tty
    monkeypatch.setenv("LMF_APPROVE", "Examplesurname, OTHERPERSON")
    code, out = staged.run()
    assert code == 0
    assert HEADER in out
    assert "examplesurname" in out and "otherperson" in out
    assert (f"approved: {PEOPLE_RULE}, terms: examplesurname, otherperson "
            f"(3 findings) [env]") in out.splitlines()
    assert "agent:" not in out
    # The block comes before the approval it records.
    assert out.index(HEADER) < out.index("approved:")


def test_env_missing_one_shown_term_blocks_and_reprints_the_block(staged, monkeypatch):
    two_terms(staged)
    staged.tty = must_not_open_tty
    monkeypatch.setenv("LMF_APPROVE", "examplesurname")
    code, out = staged.run()
    assert code == 1
    assert HEADER in out and "otherperson" in out
    assert "LMF_APPROVE does not name every term shown above; nothing was approved" in out
    assert RERUN.format("examplesurname,otherperson") in out
    assert NO_VERIFY in out
    assert "approved:" not in out


@pytest.mark.parametrize("value", ["1", "0", "yes"])
def test_a_bare_value_approves_nothing(staged, monkeypatch, value):
    staged.person(1, "Examplesurname")
    staged.tty = must_not_open_tty
    monkeypatch.setenv("LMF_APPROVE", value)
    code, out = staged.run()
    assert code == 1
    assert "approved:" not in out
    assert RERUN.format("examplesurname") in out


def test_tty_answering_y_approves(staged):
    two_terms(staged)
    staged.tty = FakeTty("y\n")
    code, out = staged.run()
    assert code == 0
    # The block and the question went to the terminal, block first.
    assert HEADER in staged.tty.written
    assert staged.tty.written.endswith("Approve these for this commit? [y/N] ")
    # The returned text carries what follows it, not the block a second time.
    assert out == (f"approved: {PEOPLE_RULE}, terms: examplesurname, otherperson "
                   f"(3 findings) [tty]")


@pytest.mark.parametrize("answer", ["n\n", "\n", ""])
def test_tty_answering_anything_else_blocks(staged, answer):
    two_terms(staged)
    staged.tty = FakeTty(answer)
    code, out = staged.run()
    assert code == 1
    assert HEADER in staged.tty.written
    assert RERUN.format("examplesurname,otherperson") in out
    assert NO_VERIFY in out
    assert "approved:" not in out


def test_no_tty_blocks_with_the_rerun_line_and_the_warning(staged):
    two_terms(staged)
    code, out = staged.run()
    assert code == 1
    assert HEADER in out
    lines = out.splitlines()
    assert RERUN.format("examplesurname,otherperson") in lines
    assert NO_VERIFY in lines
    assert out.index(HEADER) < out.index("re-run:")


def test_under_claude_code_the_rerun_line_asks_for_the_users_confirmation(staged, monkeypatch):
    staged.person(1, "Examplesurname")
    monkeypatch.setenv("CLAUDECODE", "1")
    code, out = staged.run()
    assert code == 1
    assert AGENT_RERUN.format("examplesurname") in out.splitlines()
    assert NO_VERIFY in out


def test_under_claude_code_the_approved_line_carries_the_agent_marker(staged, monkeypatch):
    staged.person(1, "Examplesurname")
    monkeypatch.setenv("CLAUDECODE", "1")
    monkeypatch.setenv("LMF_APPROVE", "examplesurname")
    code, out = staged.run()
    assert code == 0
    assert (f"approved: {PEOPLE_RULE}, terms: examplesurname (1 finding) "
            f"[env] agent: claude-code") in out.splitlines()


def test_a_real_secret_beside_an_approvable_finding_blocks_without_asking(staged, monkeypatch):
    staged.person(1, "Examplesurname")
    staged.stand_in.rows.append(dict(ORDINARY, Fingerprint="config.py:generic-api-key:9"))
    staged.tty = must_not_open_tty
    monkeypatch.setenv("LMF_APPROVE", "examplesurname")
    code, out = staged.run()
    assert code == 1
    assert "generic-api-key" in out
    assert f"{PEOPLE_RULE} in 1 file (1 line)" in out
    assert (f"the {PEOPLE_RULE} findings above could be approved once "
            f"the blocking findings are fixed") in out
    # The secret's table comes first; the approvable block below it.
    assert out.index("generic-api-key") < out.index(f"{PEOPLE_RULE} in 1 file")
    assert "approved:" not in out and "re-run:" not in out


def test_no_unredacted_report_blocks_without_asking(staged, monkeypatch):
    staged.person(1, "Examplesurname")
    staged.stand_in.unredacted_writes = False
    staged.tty = must_not_open_tty
    monkeypatch.setenv("LMF_APPROVE", "examplesurname")
    code, out = staged.run()
    assert code == 1
    assert (f"could not fetch the matched text for {PEOPLE_RULE}; "
            f"nothing was approved") in out
    assert "examplesurname" not in out
    assert "approved:" not in out and "re-run:" not in out


@pytest.mark.parametrize("visibility", ["PUBLIC", None])
def test_a_public_or_unconfirmed_repo_ignores_the_marker(staged, monkeypatch, visibility):
    staged.person(1, "Examplesurname")
    staged.visibility = visibility
    staged.tty = must_not_open_tty
    monkeypatch.setenv("LMF_APPROVE", "examplesurname")
    code, out = staged.run()
    assert code == 1
    assert (f"this repo is marked approvable for {PEOPLE_RULE}, but it is public "
            f"or unconfirmed; the marker applies to private repos only") in out
    # Today's table, and no unredacted pass.
    assert "Found 1 blocking finding(s)" in out
    assert [c["redact"] for c in staged.stand_in.calls] == [True]
    assert "examplesurname" not in out
    assert "approved:" not in out and "re-run:" not in out
    # The repo is marked, so the hint to mark it is not shown.
    assert "mark it approvable" not in out


def test_an_unmarked_repo_with_a_people_finding_says_how_to_mark_it(staged):
    staged.person(1, "Examplesurname")
    staged.marker = set()
    code, out = staged.run()
    assert code == 1
    assert "Found 1 blocking finding(s)" in out
    assert (f"if this repo's subject is on the list, mark it approvable: "
            f"git config --add lastmilefirst.approvable {PEOPLE_RULE} "
            f"(the match is then shown and asked about on each commit)") in out
    assert [c["redact"] for c in staged.stand_in.calls] == [True]


def test_an_unmarked_repo_with_only_a_secret_gets_no_hint(staged):
    staged.stand_in.rows.append(dict(ORDINARY))
    staged.marker = set()
    code, out = staged.run()
    assert code == 1
    assert "mark it approvable" not in out


def test_a_marker_naming_a_secret_rule_is_warned_and_ignored(staged):
    staged.stand_in.rows.append(dict(ORDINARY))
    staged.marker = {PEOPLE_RULE, "lmf-example-token"}
    code, out = staged.run()
    assert code == 1
    assert ("lastmilefirst.approvable names lmf-example-token, which is not a people rule; "
            "ignored") in out.splitlines()


def test_an_archive_finding_is_shown_and_approved_with_the_diff(staged, monkeypatch):
    staged.person(1, "Examplesurname")
    staged.archive_rows = [dict(PERSON, File="copy.docx -> word/document.xml", StartLine=1,
                                Match="Examplesurname", Secret="Examplesurname",
                                _unredacted=True)]
    monkeypatch.setenv("LMF_APPROVE", "examplesurname")
    code, out = staged.run()
    assert code == 0
    assert f"{PEOPLE_RULE} in 2 files (2 lines)" in out
    assert "copy.docx -> word/document.xml (1)" in out
    assert "(2 findings) [env]" in out


def test_personal_data_warnings_show_above_the_block_and_do_not_block(staged, monkeypatch):
    staged.person(1, "Examplesurname")
    staged.stand_in.rows.append(dict(PII))
    monkeypatch.setenv("LMF_APPROVE", "examplesurname")
    code, out = staged.run()
    assert code == 0
    assert "WARNING" in out and "lmf-pii-personal-email" in out
    assert out.index("lmf-pii-personal-email") < out.index(f"{PEOPLE_RULE} in 1 file")


@pytest.mark.parametrize("visibility", ["PRIVATE", "PUBLIC"])
def test_a_marked_repo_with_nothing_staged_passes(staged, visibility):
    staged.visibility = visibility
    staged.tty = must_not_open_tty
    code, out = staged.run()
    assert code == 0
    assert "No secrets detected in staged changes." in out


def test_a_term_with_a_quote_is_escaped_for_the_shell(monkeypatch):
    monkeypatch.delenv("CLAUDECODE", raising=False)
    assert scanner._rerun_line(["o'example"]) == RERUN.format("o'\\''example")
