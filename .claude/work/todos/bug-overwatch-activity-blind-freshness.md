# Bug: Overwatch freshness checks ignore project activity

**Status:** RESOLVED in v0.14.2 (2026-05-17)
**Priority:** medium
**Created:** 2026-05-17
**Resolved:** 2026-05-17

## Resolution

Added `_get_last_commit_ts(repo_path)` to `session_start.py` and gated all three per-project freshness checks (review, secret scan, organize) on it:

- "Never X" alerts: now fire only when the repo has at least one commit (`has_commits = last_commit > 0`). Empty / placeholder dirs like `splash/` (no git) are silent.
- "Stale X" alerts: now fire only when `last_commit > last_action_ts` (something changed since the last action). Dormant repos with no activity since their last scan/review/organize no longer perpetually alert.

Trade-off: one `git log -1 --format=%ct` call per project on every session start (~3ms × 23 projects ≈ 70ms). Acceptable for now; can cache `last_commit_ts` in state later if it becomes a hot path.

**Smoke-tested 2026-05-17:** workspace summary went from `22/23 need review | 22/23 need secret scan` to `21/23 need review` (secret-scan line disappeared because activity gate suppressed all post-`--all` repos). `splash` (no commits) dropped out of "never" lists.

---

## Original report (preserved below for context)

## Summary

Overwatch's per-project freshness checks (`last_review`, `last_secret_scan`, `last_organize`) are pure time deltas — they fire on every project at every threshold crossing regardless of whether the project has been touched. A repo untouched for a year still produces "needs secret scan" every 7 days, indistinguishable from an actively-changing project that genuinely needs re-scanning.

Concrete impact at 2026-05-17 session start: `22/23 need review` and `22/23 need secret scan` workspace-summary lines — the numbers are mostly noise, and the signal-to-noise ratio causes the user to ignore the summary entirely.

## Root Cause

`plugins/lastmilefirst/hooks/scripts/session_start.py:451-470`:

```python
# Check review freshness
last_review = project_state.get("last_review", 0)
if last_review == 0:
    never_reviewed.append(project_label)
elif (now - last_review) // 86400 >= 7:
    stale_reviewed.append(project_label)

# Check secret scan freshness
last_scan = project_state.get("last_secret_scan", 0)
if last_scan == 0:
    never_scanned.append(project_label)
elif (now - last_scan) // 86400 >= 7:
    stale_scanned.append(project_label)

# Check organize freshness
last_organize = project_state.get("last_organize", 0)
if last_organize == 0:
    never_organized.append(project_label)
elif (now - last_organize) // 86400 >= 14:
    stale_organized.append(project_label)
```

No condition compares against project activity. The state file tracks `last_*` timestamps but never asks "has anything changed since then?"

## Symptom

Workspace summary at session start over-reports stale projects. Operationally, this trains the user to dismiss the summary, defeating Overwatch's purpose.

## Fix Options

1. **Gate on last-commit recency (recommended):**
   - For each project, capture `git -C <project> log -1 --format=%ct` (latest commit unix ts) cheaply
   - A project is "stale" only if `last_commit > last_scan` (i.e., something changed after the last scan)
   - "Never scanned" still flags any repo with ≥1 commit; truly empty / placeholder dirs stop firing
   - Cache per-project commit ts in the state file so we don't shell out on every session start; refresh on `update_state.py` calls

2. **Gate on tracked-file mtime:**
   - Walk project tracked files (`git ls-files`) and find max mtime
   - More expensive than option 1; redundant with commit time in normal workflow

3. **Add an explicit dormancy flag per project:**
   - Allow projects to opt out of freshness alerts via a `dormant: true` marker
   - Doesn't solve the discovery problem (user still has to mark each)

## Files Affected

- `plugins/lastmilefirst/hooks/scripts/session_start.py` (the freshness check block)
- `plugins/lastmilefirst/hooks/scripts/overwatch.py` (state schema if caching last-commit ts)
- `plugins/lastmilefirst/hooks/scripts/update_state.py` (if commit-ts cache lives in state)

## Verification

After fix:
- Repo with no commits since last scan: should NOT appear in `stale_scanned`
- Repo with commits since last scan: should appear in `stale_scanned`
- Repo never scanned but with any commit history: should appear in `never_scanned`
- Truly empty repo (no commits): should be silent

Smoke test by inspecting a session-start summary on the current workspace — expect the 22/23 numbers to drop significantly (Michael's projects are a mix of active and long-dormant).

## Notes

Discovered 2026-05-17 during a workspace-wide scan-secrets run that flagged dormant projects (e.g., synthasaurus, paused) alongside active ones. The bug doesn't affect correctness (alerts are still based on real timestamps), only signal quality.

Related design issue: the per-project alert pattern should probably also surface *which* projects are stale (currently only counts are shown in the summary; the `--full` mode is opt-in). Worth considering whether the default summary should always print "stale: A, B, C" rather than "3/23 need X".
