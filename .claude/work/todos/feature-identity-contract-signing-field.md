# Feature: a `signing` field on the identity contract

**Status:** OPEN
**Priority:** low (correctness of a rebuilt machine; no effect on a machine already set up)
**Created:** 2026-10-09
**Refs:** `.claude/work/plans/2026-10-09-002-feat-organize-device-plan.md` section 8.3

## The problem

An org can sign commits and tags (one does today, with an SSH key, through its git include file). The identity contract in `org.json` records account, name, email, remotes, and SSH alias, and says nothing about signing. So the device audit (organize-device) can report whether signing is on but cannot require it, and a machine rebuilt from the contracts would silently stop producing Verified commits for that org.

## Shape of a fix

Add an optional `signing` object to the `identity` block:

```json
"signing": { "format": "ssh", "key": "~/.ssh/id_ed25519_<org>_signing.pub" }
```

Absent means the org does not sign. `organize-orgs` validates it (format in a known set, key path `~`-relative), the audit in `audit_identity.py` reports a repo under a signing org whose effective `commit.gpgsign` is off, and organize-device's `--install --apply` writes `[user] signingkey`, `[gpg] format`, `[commit] gpgsign`, `[tag] gpgsign`, and the allowed-signers file reference into the org's include file. Key generation stays a `you` step.

## Touch together

SKILL.md for organize-orgs and organize-device, the `org.json` template, the identity-contract section of the org CLAUDE.md template, README, CHANGELOG.
