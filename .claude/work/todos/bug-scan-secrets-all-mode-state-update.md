# Bug: `scan-secrets --all` doesn't update per-project `last_secret_scan` state

**Status:** RESOLVED in v0.14.2 (2026-05-17)
**Priority:** medium
**Created:** 2026-05-17
**Resolved:** 2026-05-17

## Resolution

`scanner.scan_workspace()` now imports `update_scoped_state` from `overwatch` and calls it for each scanned repo using key `f"{repo.parent.name}/{repo.name}"` — matching the key shape `session_start.py` reads from state. Update runs regardless of findings (a clean scan still resets the freshness clock). Best-effort: if the import or update fails, the scan still completes.

Smoke-tested 2026-05-17: after a `--all` run, `session_start.py --full` "Never scanned" list went from 18 entries to 1 — and that 1 is `splash`, which isn't a git repo and didn't get scanned (correct behavior).

**Related sub-issue (`--full` double-print) was a misdiagnosis.** Verified by separating streams: stdout has 93 lines, stderr has 90 lines, the only diff is the stdout-only DIRECTIVE block. The script intentionally writes alerts to both streams (stdout for Claude context, stderr for the user's terminal); the "double print" I observed was from running with `2>&1` which merges the streams. Closing the double-print sub-issue as not-a-bug.

---

## Original report (preserved below for context)

## Summary

Running `python3 scan_secrets.py --all` scans every repo in `~/Code/` but only writes a single global `last_secret_scan` timestamp (or no per-project timestamp at all). Overwatch's per-project freshness check reads `state['projects'][project_key]['last_secret_scan']`, so projects that were just scanned still show up as "Never scanned for secrets".

Concrete reproduction (2026-05-17 session):
- Ran `--all`, scanned 23 repos
- Immediately ran `python3 session_start.py --full`
- Workspace report: "Never scanned for secrets (18)" — including projects that were just scanned (e.g., `gruntwork-remail`, `gruntwork-marketplace`, `gruntwork-ai-team`)
- Only the 4 projects with previously-recorded state appeared in "overdue >7d" (`gruntwork-operatives`, `gruntwork-stack-wisdom`, `lastmilefirst.ai-operatives`, `lastmilefirst.ai-stack-wisdom`) — those had timestamps from earlier individual `/run-scan-secrets` runs

## Root Cause (to verify)

`plugins/lastmilefirst/skills/scan-secrets/scripts/scan_secrets.py` (the `--all` mode) likely calls the scan loop without invoking the state-update path that the single-repo mode uses. The single-repo mode probably calls something like `update_state.py last_secret_scan <project_key>` after a successful scan; the `--all` mode either skips the update entirely or updates only one global key.

## Symptom

- Overwatch workspace summary reports false "Never scanned" counts after `--all` runs
- Users see "22/23 need secret scan" indefinitely no matter how often they run `--all`
- Combines with the activity-blind freshness bug (see `bug-overwatch-activity-blind-freshness.md`) to compound the noise — fix one without the other and the report is still wrong

## Fix

For each repo scanned in `--all` mode, call the same state-update path as the single-repo mode using `f"{org_name}/{project_dir.name}"` as the project key (the same key Overwatch reads). This must run regardless of whether findings were found (a clean scan also resets the freshness clock).

The state schema is per-project as of v0.13.0 (see `MEMORY.md` and `plugins/lastmilefirst/.claude/work/plans/` notes on v0.13.0). The `--all` mode needs to use that schema, not the legacy global-key path.

## Files Affected

- `plugins/lastmilefirst/skills/scan-secrets/scripts/scan_secrets.py` (the `--all` loop)
- `plugins/lastmilefirst/hooks/scripts/update_state.py` (verify the existing API accepts per-project keys)

## Verification

After fix:
1. Run `--all` on a fresh state file
2. Immediately run `session_start.py --full`
3. "Never scanned for secrets" should be empty (or only contain repos that errored during scan)
4. Re-run `--all` 8 days later: every project should now appear in "overdue >7d" if not re-scanned (this also validates the activity-blind fix once that lands)

## Related minor bug (file together)

`session_start.py --full` prints its entire output twice — observed 2026-05-17 in the same invocation. The Overwatch banner + workspace report block appear back-to-back, byte-identical. Likely the `--full` codepath calls `_render` (or equivalent) twice, or the script's `__main__` doesn't gate on the `--full` flag and falls through to the default render after the full render completes. Trivial to fix; trace from `if __name__ == "__main__":` in `session_start.py`.

## Notes

Discovered 2026-05-17 during `/run-overwatch check` after the workspace scan from earlier in the same session. Together with the three other todos from this session (`bug-overwatch-activity-blind-freshness`, `bug-scan-secrets-node-modules-noise`, `bug-scan-secrets-self-match-on-format-file`), this completes the "scan + Overwatch output is unreliable" picture.

Recommend treating all four as a single mini-epic: their combined effect is that a user can't trust the workspace summary at all today. Fix them together and the summary becomes the source of truth it was designed to be.
