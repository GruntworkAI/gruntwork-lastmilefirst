# 2026-10-12: a repo marked approvable for a people-rule finding (0.39.0, `feat/approvable-repo`)

Session note. The feature came out of a repo whose subject is a person on the people list:
after the 0.37.0 names split, every commit there blocked on the subject's surname and the
only way through was `--no-verify`, which also skips the identity check. The spec rejected
both an exemption and removing the name; the plan (v1.0 to v1.3) went through a five-persona
document review before the build.

## What was built

Four units on Opus, one per commit, then a read-only code review and one fix commit:

| Commit | Unit | What |
|---|---|---|
| dc11be7 | U1 | marker reader, unredacted enable-rule pass joined inside both scanners, grouped renderer, approval applier; 35 tests |
| 6c84526 | U2 | the ask in the staged scan: tty prompt, `LMF_APPROVE` carrying the shown terms, Claude Code wording; 24 tests |
| 84abc66 | U3 | the same ask on push, remote visibility checked on every push, decision steps shared in one helper; 12 tests |
| 762292a | U4 | SKILL.md section "Marking a repo approvable", CHANGELOG 0.39.0 |
| a572810 | U4 | version bump, adapters regenerated |
| c590b1a | review | blank term never approved, comma term approvable from the printed re-run, hint gated by visibility, push guard on `blocked`, first-seen casing displayed |

Suites at the end: scan-secrets 292, hooks 382. Both adapter checks fresh.

## Decisions made during the build

- The join between the redacted and unredacted passes carries the column. gitleaks'
  fingerprint is `file:rule:line`, so two matches on one line would otherwise collide.
- Terms group on a lower-cased, whitespace-collapsed key but display the casing first seen.
  The plan said lower-cased; the point of the block is to show what was found.
- The mark-it hint is suppressed where marking would do nothing (unmarked public repo, push
  to a public remote). The plan's step 4 had no visibility gate.
- On the tty route the block goes to the terminal once and only the trailing lines go to
  stderr, so the doc review's "printed twice" FYI did not materialize.
- Left as a follow-up: a later push to a remote GitHub now reports public does not re-run the
  visibility policy (`todos/bug-scan-pushed-policy-not-rerun-on-public-remote.md`). The exit
  code is right; the report is wrong.

## Still to do

Push the branch, open the PR, merge, `gh release create v0.39.0 --target main --latest`,
then the plan's section 5 verification in a scratch repo and the first real commit in the
originating repo with the marker set. The one-sentence rule for Claude goes into that repo's
CLAUDE.md as its first consumer.

## Also this session

The two org rules in the local formats file were found during the plan review to carry an
identical regex (the 0.37.0 split moved keywords, not terms). Fixed by hand in the local
file, verified with a `gitleaks dir` scan; never committed anywhere. A project review was
recorded for this repo (health 52/100; CHANGELOG missing 19 tagged releases, plan and todo
statuses lagging shipping, archive backlog) with the housekeeping queued for `main`.

## Verification (2026-10-13, after the release)

Plugin updated and reloaded at 0.39.0; the global hooks resolve to the marketplace copy.
In a scratch private repo with two throwaway terms added to the local people rule for the
run (removed after): step 1 unmarked blocked with the hint; step 3 marked under Claude Code
blocked with the get-confirmation line, approved with the terms in the variable (approved
line carried the agent marker), bare `1` blocked; step 4 two terms gave two rows and a
variable naming one blocked; step 5 an AWS-format key beside the term blocked with no ask.
Step 2 (the terminal prompt) needs a real tty and was not run from this session. Two bad
inputs on the first try at step 5: AWS's documented example key is allowlisted by gitleaks,
and an unchanged line is not in the staged diff. Found and logged: the generic trailer
prints under the approvable block.
