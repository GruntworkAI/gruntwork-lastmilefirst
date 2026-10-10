# 2026-10-09: PII rules in private repos and a pre-push first-push audit (0.37.0, PR #38)

Session note. The feature came out of pushing a client engagement's first code repo the same day: the pre-commit scan passed, but the only names rule was `public-only`, and the full-history check was a hand-run afterwards.

## What happened

- Todo and plan written and confirmed (two decisions: generic PII warns in private repos and blocks in public; a public repo's first push reports GitHub posture as a warning). Plan: `plans/2026-10-09-001-feat-pii-rules-and-pre-push-audit-plan.md`.
- Built through `ce-work` on `feat/pii-rules-and-pre-push-audit`: U1 and U2 as a parallel wave, then U3, U4, U5, each by an Opus worker with the session model reviewing and committing path-limited. Simplification pass applied eight behavior-preserving edits. Code review (eight reviewers, in-process adversarial because no other provider CLI is installed) confirmed five findings; all applied, two of them P1s:
  - the first-push visibility check asked GitHub about the clone's default repo, not the remote being pushed to; the dispatcher now forwards git's `$1 $2` and a public target overrides a private declaration;
  - a new branch rescanned its whole history, so an old finding on the remote's main blocked every new branch; new refs now scan `<sha> --not --remotes`, one gitleaks run for all of them.
- Scanner suite 72 to 215, hooks suite 336 to 358, all eight suites green, adapters fresh. Four end-to-end tests push for real through the generated hook to a tmp bare repo.
- PR #38 opened against main, not merged. Babysit skipped: no CI here.

## After the merge

1. `gh release create v0.37.0 --target main --latest` (Desktop installs resolve from the tag).
2. On this machine, after the plugin updates and `/reload-plugins`: `/run-scan-secrets --install-hooks` (writes the pre-push hook), `--update-formats` (pii rules), and split `lmf-private-names` into organizations plus a new `lmf-private-people` rule by hand.
3. Manual checks the plan listed and nobody ran: a first push against a real scratch GitHub repo, a visibility flip, the Claude Desktop surface.

## Lessons

- A `.pyc` under `__pycache__` can carry a constant-folded synthetic token from a test and trip `gitleaks dir` while the tracked tree is clean. Scan the commits, or exclude the cache, before reading a self-scan hit as a leak.
- Both P1s were "which repo is this really about" errors; the day's earlier AWS-default-profile finding in the engagement repo had the same shape. Identity and target should be asked for, never assumed from the working directory.
- `__pycache__` aside, the self-scan on the plugin repo found nothing because the end-to-end tests assemble their synthetic token at runtime; keep doing that.

## Follow-ups filed

- `todos/feature-overwatch-pre-push-hook-installed-check.md` (on the branch): alert when the pre-push hook is not installed.
- Two advisory review findings in the PR body: the unknown-remote-sha widening (kept, documented) and the private `repo_auditor` helpers.
