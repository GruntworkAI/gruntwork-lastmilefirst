# Bug: a later push to a remote GitHub now reports public keeps the private-repo policy

**Status:** OPEN
**Priority:** low (exit code is already correct; the report is wrong)
**Created:** 2026-10-12

## What happens

`scan_pushed` runs `apply_visibility_policy` with the declared visibility first and
checks the remote's visibility afterwards (0.39.0, the approvable-repo feature). When a
later push finds the remote public but the repo is declared private, the people findings
block and the marker is ignored, which is right. But the policy has already run as
private, so the same report says organization findings were "suppressed in a private
repo" and personal-data findings are warnings, not blocks, directly above the line that
says the remote is public. On a first push the existing branch prints a visibility
mismatch block line; later pushes never do (pre-existing).

Found in the 0.39.0 code review. Plan `2026-10-12-001-feat-approvable-repo-plan.md`
section 3.7 asked for "block as today with one added line", so the build followed the
plan; the gap is the plan's.

## Fix

Move the remote fetch above the policy (it only needs `is_approvable`, which reads
`RuleID` and tags), set `visibility = "PUBLIC"` when the remote says so, then run the
policy and `visibility_mismatch` once for every push, not only a ref's first push.
Severity bumps applied at parse time with the old `is_public` would stay unbumped
unless re-applied; acceptable. Add a test: declared private, later push, remote public,
one organization finding and one pii finding beside a people finding; all three block
and the mismatch line prints.

## Files

- `skills/scan-secrets/scripts/scanner.py` (`scan_pushed`)
- `skills/scan-secrets/tests/test_scan_pushed.py`
