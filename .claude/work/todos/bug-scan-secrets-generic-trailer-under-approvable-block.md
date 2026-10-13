# Bug: the generic "potential secrets" trailer prints under the approvable block

**Status:** OPEN
**Priority:** low (wording only)
**Created:** 2026-10-13

## What happens

When a marked repo's only blocking findings come from the marked people rule, the hook
prints the grouped block and the re-run line (0.39.0), and then the pre-commit wrapper
appends today's trailer: "Secret scan found potential secrets in staged changes. Review
the findings above and either: 1. Remove the secrets and re-stage ...". A name is not a
secret and the three options do not apply; the re-run line above is the instruction.

Seen in the 0.39.0 verification run in a scratch repo.

## Fix

Have the hook wrapper (or `scan_secrets.py`'s pre-commit mode) skip the trailer when the
report ended in an approvable ask or refusal, or replace it with one line pointing at the
re-run instruction. Same for the pre-push wrapper.

## Files

- `hooks/` pre-commit and pre-push wrappers under `~/.claude/lastmilefirst/git-hooks/` (installed by `hook_installer.py`)
- `skills/scan-secrets/scripts/scan_secrets.py`
