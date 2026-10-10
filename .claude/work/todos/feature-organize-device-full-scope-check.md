# Feature: organize-device `--full` checks the gh token's scopes

**Status:** OPEN
**Priority:** low (the login check already catches the common failure; a missing scope fails later at push or workflow time with a clear GitHub error)
**Created:** 2026-10-09
**Refs:** `.claude/work/plans/2026-10-09-002-feat-organize-device-plan.md` section 3.4 (GitHub logins, full mode)

## The gap

The plan asked `--full` to confirm each account's token carries `repo` and `workflow` (and `admin:public_key` only when key upload is wanted). 0.38.0 shipped without it: `section_github` ignores `--full`, and the SKILL.md says so.

## Why it was left out

The only non-text source of scopes is the `X-OAuth-Scopes` header on an authenticated API response, which means handing the token to a subprocess (`GH_TOKEN=$(gh auth token --user X) gh api -i /user`). Parsing `gh auth status` text was ruled out as unstable. The token never has to be printed, but the env handoff deserved a deliberate design rather than a late addition.

## Shape of a fix

A `token_scopes(account) -> set[str] | None` probe in audit_device.py that runs `gh api -i /user` with `GH_TOKEN` set in the child's environment only, reads the header, and discards everything else. A `missing` finding per absent scope with remedy `gh auth refresh -s <scope>` as a `you` step. Tests stub `gh` and assert the token appears in no output. Update SKILL.md's GitHub logins paragraph.
