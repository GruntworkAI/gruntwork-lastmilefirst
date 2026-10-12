---
title: A repo marked approvable for a people-rule finding: show the match, then ask
version: 1.0
date: 2026-10-12
status: planned
type: feat
component: skills/scan-secrets/scripts/{scanner.py,scan_secrets.py,repo_auditor.py}, skills/scan-secrets/tests/, hooks/scripts/session_start.py, hooks/tests/, skills/scan-secrets/SKILL.md, CHANGELOG.md, README.md
target_version: 0.39.0
refs:
  - .claude/work/todos/feature-scan-secrets-approvable-repo.md (the spec this plan details; the "show the match, then ask" decision confirmed 2026-10-12)
  - .claude/work/plans/2026-10-09-001-feat-pii-rules-and-pre-push-audit-plan.md (the policy function and pre-push scan this extends)
  - .claude/work/todos/feature-scan-secrets-repo-local-config.md (rules that travel with a repo; a different mechanism, not touched)
  - skills/scan-secrets/tests/test_visibility_policy.py (the stand-in pattern the new tests extend)
---

# A repo marked approvable for a people-rule finding: show the match, then ask

Delta: first version, from the todo after the one open design decision was confirmed: the approval is always given against the matched text, with a tty prompt where there is one and an environment variable where there is not.

## 1. Problem

A repo whose subject is a person on the people list cannot commit. The first commit in a
campaign-website repo after the 0.37.0 names split was blocked on the candidate's surname
in every copy document and session note, and the only way through was `git commit
--no-verify`, which also skipped the identity check and every other rule, twice (once at
commit, once at push). Taking the name off the list weakens it in every other repo. A
per-repo exemption makes the finding disappear, and a second stray name from the same rule
would disappear with it.

The report also showed rule, file, and line for each of 42 findings and nothing about what
matched. The user had to trust a reading that it was the surname.

## 2. What changes for the user

- `git config --add lastmilefirst.approvable lmf-private-people` marks the repo approvable
  for that rule. Local git config, never a file in the repo. Only people and PII rules can
  be marked; naming any other rule prints a warning and does nothing.
- In such a repo, a commit whose only blocking findings come from approvable rules prints
  them grouped by matched term, in the clear, and asks. In a terminal the hook reads y/n.
  Under Claude Code, CI, or an editor's git client it blocks and prints the exact re-run
  with `LMF_APPROVE=1`. The identity check and every other rule run as before.
- A push of approved commits to a private remote is reported and allowed. A push to a
  remote GitHub reports as PUBLIC ignores the marker and blocks.
- Each approval is logged under `.git/lastmilefirst/`, `--audit` lists them, and session
  start prints one quiet line in an approvable repo.

## 3. Design

### 3.1 The marker

`approvable_rules(repo_path) -> set[str]` in `scanner.py` reads `git config --get-all
lastmilefirst.approvable`, lower-cased, beside `declared_visibility`. Invalid or missing
is the empty set. No new config module; the key sits next to the visibility key it
resembles.

Eligibility is decided per finding, not per key: a finding is **approvable** when its
`RuleID` is in the set and `_finding_kind` returns `person` or `pii`. A key naming an
ordinary secret rule or an organization rule never matches, and `scan_staged` prints
`lastmilefirst.approvable names <rule>, which is not a people or PII rule; ignored` once
per such key so the misconfiguration is visible rather than silent.

### 3.2 The matched text

`_run_gitleaks` always passes `--redact`, so every `Match` and `Secret` in the report reads
`REDACTED`. That stays. When at least one approvable finding exists, `_approvable_matches`
runs gitleaks a second time over the same target with `--enable-rule <id>` for each
approvable rule and no `--redact`. Only people and PII rules are enabled on that pass, so
an unredacted secret never leaves gitleaks. The second report is joined to the first on
`Fingerprint` (falling back to `File`, `StartLine`, `RuleID`), and each approvable finding
gains `Match`. The temp report is unlinked as today. Confirmed on this machine: gitleaks
8.30.1 has `--enable-rule strings` on the `git` subcommand; `_check_gitleaks` gains no new
floor because the flag predates `LOG_OPTS_MIN_GITLEAKS_VERSION`.

### 3.3 Rendering, grouped by term

`_format_approvable(findings) -> str` renders the approvable findings only:

```
lmf-private-people in 2 files (42 lines)
  <term>     42×   .claude/work/plans/copy-review/<copy-doc>.md (21)
                   .claude/work/plans/copy-review/<copy-doc>.docx (21)
```

Terms are the `Match` text lower-cased and whitespace-collapsed; a different casing of the
same name is one row. Files under a term are listed with their line counts, longest first,
capped at five with `... and N more files`. A second term is its own row. Non-approvable
findings keep today's table, printed above this block, because they are what still blocks.

### 3.4 The ask

`_approval(prompt_lines) -> tuple[bool, str]` returns `(approved, source)`:

1. `LMF_APPROVE` set to anything other than empty or `0`: `(True, "env")`. Checked first,
   so a scripted run never touches the tty.
2. Otherwise, try `open("/dev/tty", "r+")`. If it opens, write the rendered block and
   `Approve these for this commit? [y/N] `, read one line, and return `(True, "tty")` on
   `y` or `yes`, else `(False, "tty")`. Any `OSError` means no terminal.
3. No terminal: `(False, "none")`.

The hook never asks before the block is printed, and the block is printed in full even when
`LMF_APPROVE` short-circuits the question, so the approval is always visible beside what it
approved.

### 3.5 Where it sits in `scan_staged`

After `apply_visibility_policy`, a new pass `apply_approvals(findings, approvable,
approved) -> (findings, approvable_subset)` sets `Blocking=False` and `Approved=True` on
each approvable finding when `approved` is true. The sequence in `scan_staged`:

1. Policy as today. Partition kept findings into `approvable` and `other`.
2. If `other` has a blocking finding: block with today's report, append the approvable
   block with a line `the <rule> findings above could be approved once the blocking
   findings are fixed`, and skip the ask. A real secret is never approved past.
3. Else if `approvable` is non-empty: fetch matches (3.2), render (3.3), ask (3.4). On
   approval print `approved: <rule>, terms: <t>[, <t>] (<n> findings) [tty|env]`, log
   (3.6), exit 0. On refusal or no terminal print the block, the re-run line
   `LMF_APPROVE=1 git commit ...` (reconstructed from nothing: the hook does not know the
   user's arguments, so it prints `LMF_APPROVE=1 git commit <your arguments>`), and the
   warning `--no-verify would also skip the identity check`, exit 1.
4. Else: today's path.

`scan_repo` and `scan_workspace` do not ask; they report. A full scan is for reading, and
an approvable finding there prints with `approvable` in the severity column so the reader
knows which switch is involved.

### 3.6 The log

`.git/lastmilefirst/approvals.log`, one JSON line per approval, found via `git rev-parse
--git-dir` so worktrees resolve correctly:

```
{"at": "2026-10-12T14:30:00Z", "mode": "commit", "rule": "lmf-private-people",
 "terms": ["<term>"], "findings": 42, "source": "env", "files": ["..."]}
```

`audit_repo` adds a section `Approvable rules: <list>` with the count of logged approvals
and the last three lines rendered as `date  rule  terms  N findings`. No marker and no log
prints nothing.

### 3.7 Pre-push

`scan_pushed` reads the same marker. After the policy, approvable findings in an approvable
repo are set non-blocking and reported under a header `approved at commit time (this repo
is approvable for <rule>)`, with the grouped block from 3.3 so the push shows the terms
too. There is no second ask on push and the log is not consulted to gate it: a commit from
another machine carries no log line, and the terms are on screen either way. The log is
read only to print `N approval(s) logged in this repo` as context.

The exception is the remote: when the remote being pushed to reads as PUBLIC (the
`github == "PUBLIC"` branch already in `scan_pushed`, which overrides the declaration), the
marker is ignored and the findings block as today with one added line: `this repo is marked
approvable for <rule>, but the remote is public; the marker applies to private remotes
only`.

### 3.8 Overwatch

`session_start.py` gains `approvable_notice(cwd) -> Optional[str]` returning `this repo is
approvable for <rule>[, <rule>]` as an info line (the `results` list that carries "N skill
invocations this week"), not an alert. It reads git config only, no `gh`, so it costs
nothing at session start.

## 4. Units

| Unit | Builds | Done when |
|---|---|---|
| U1 | `approvable_rules`, eligibility, `_approvable_matches` (second gitleaks pass with `--enable-rule`, joined on fingerprint), `_format_approvable`, `apply_approvals` | new `test_approvable.py` covers: marker parsing (none, one, two, invalid kind warned), eligibility per finding kind, the join on fingerprint with a stand-in gitleaks, grouping by term with mixed case and the five-file cap; `test_visibility_policy.py` passes unchanged |
| U2 | `_approval` and the `scan_staged` sequence in 3.5, the log writer in 3.6 | `test_approvable.py` adds: env var set (approved, source env, block printed, log line written), tty stand-in answering y and n, no tty (blocked, re-run line and `--no-verify` warning present), a real secret alongside an approvable finding (blocked, no ask, no log), exit codes per branch |
| U3 | `scan_pushed` in 3.7, `audit_repo` section in 3.6 | `test_scan_pushed.py` adds: approvable findings on a private remote (allowed, header and grouped block present, no ask), the same on a public remote (blocked with the one added line); `test_repo_auditor` or the existing audit test adds the approvals section with and without a log |
| U4 | `approvable_notice` in `session_start.py` | `hooks/tests/test_approvable_notice.py` covers marker present, absent, outside a repo |
| U5 | SKILL.md section "Marking a repo approvable" beside "Splitting an existing names list", with the grouped-block example and the two ways to answer; CHANGELOG `Unreleased` -> `0.39.0`; README version table; the version bump across `plugin.json` and both `marketplace.json` fields; `adapters/codex/build.py --check` | docs reviewed with `/run-review-voice`; adapter check passes; `gh release create v0.39.0 --target main --latest` after merge |

U1 first. U2 and U3 depend on U1 and are independent of each other. U4 depends on nothing
but follows U3 so the config read is written once and imported. U5 last.

## 5. Verification

- `../../.venv/bin/pytest -q skills/scan-secrets/tests/` and `hooks/tests/` green from the
  repo's documented venv, each suite on its own.
- Manual, in a scratch private repo with a throwaway people term added to the local people
  rule for the duration, then removed:
  1. Commit a file carrying the term with no marker: blocked, as today, no ask.
  2. Add the marker. Commit from Terminal: the grouped block prints, the prompt reads `n`,
     the commit is blocked; again with `y`, the commit lands and the log has one line.
  3. Commit from Claude Code's Bash tool: blocked with the re-run line; re-run with
     `LMF_APPROVE=1`: lands, log has two lines, and the permission layer did not treat the
     variable as a bypass (this is the open question the build settles first; if it does
     treat it as one, the fallback is a commit-message trailer read by a `commit-msg`
     hook, and this plan gets a v1.1 before U2).
  4. Add a second throwaway term to the same file: two rows in the block.
  5. Stage a fake AWS key beside the term: blocked, no ask, the approvable block appears
     below the secret with the "could be approved once" line.
  6. Push to a private scratch remote: allowed, header and terms shown. Flip the remote to
     public, push a further commit: blocked with the public-remote line. Delete the
     scratch repo and remote afterwards.
  7. Open a session in the scratch repo: the one info line appears.
- The campaign repo, with `lastmilefirst.approvable lmf-private-people` set, commits its
  next content round with `LMF_APPROVE=1` and no `--no-verify`, and pushes clean.

## 6. Risks

- **The second gitleaks pass sees unredacted matches.** Mitigated by enabling only the
  approvable rules on that pass, so a secret rule's match is never in the unredacted
  report; the temp file is unlinked as today. If a PII rule's regex can overlap a secret
  (none of the five do today), the overlap shows as PII text, which is what the user asked
  to see.
- **`/dev/tty` from a hook.** Terminal and iTerm expose it; Cursor's git client and Claude
  Code's Bash tool do not, which is the designed fallback. A tty that opens but blocks on
  read (a detached session) is bounded by the hook's own patience; no timeout is added in
  this version, and the manual step 2 confirms the prompt returns.
- **Permission classifier.** If `LMF_APPROVE=1` on the command line is treated as a safety
  bypass under Claude Code, the variable route is no better than `--no-verify` in that
  surface. Verification step 3 settles it before U2 is finished; the trailer fallback is
  named in the plan so the pivot is a version note, not a rethink.
- **Scope creep into exemptions.** The marker must never suppress a finding. Every branch
  that lets a commit through prints the grouped block first; U2's tests assert the block's
  presence in the output on the approved path, not only the exit code.

## 7. Out of scope

Per-term markers (the grouped block makes a second term visible without them), a rule-name
argument to `LMF_APPROVE` (one approvable rule exists today; add when a second does),
approvals that gate the push (a log line is per machine), and any change to the pre-commit
dispatcher's identity check.

## Change log

- 1.0 (2026-10-12): first version, after the "show the match, then ask" decision was confirmed.
