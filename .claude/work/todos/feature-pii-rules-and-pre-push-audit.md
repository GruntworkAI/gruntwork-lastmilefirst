# Feature: PII rules that apply in private repos too, and a pre-push audit on first push

**Status:** open
**Priority:** high
**Created:** 2026-10-09

## What happened

A new private client repo was created and pushed 2026-10-09. The pre-commit hook ran on every commit and
passed. A manual check afterwards (gitleaks over the full history, plus a grep for staff names, personal
emails, and account numbers) was also clean, but it was manual. Two gaps surfaced:

1. **The only names rule is `public-only`.** `lmf-private-names` carries the `public-only` tag, so in a
   private repo every match is suppressed ("19 finding(s) from public-only rules suppressed"). That is right
   for a client's company and product names, which belong in a private engagement repo. It is wrong for
   people: a founder's name, a contractor's name, a personal email, a phone number, an AWS account id should
   be caught in a private repo as well, because the private repo is where that material is most likely to
   be typed, and "private" is one setting change from not.
2. **Nothing runs at the moment content first leaves the machine.** Repo creation has no git hook, but the
   first push to a new remote ref does, and that is the moment that matters. The plugin has a pre-commit
   hook only; the pre-push scan has been a standing idea (memory `project_lmf_prepush_scan`) without a spec.

## Proposed change

### A. Two kinds of private-name rule

Split the org-tier names rule into two rules in `~/.claude/lastmilefirst/secret-formats/org_secret_formats.toml`
(the names list stays only in that local file, never in a repo; see the standing rule):

| Rule | Tag | Fires in |
|---|---|---|
| `lmf-private-orgs` (client companies, products, engagement codenames) | `public-only` | public repos only (today's behavior) |
| `lmf-private-people` (client staff, contractors, counterparts; their emails and handles) | none (always) | every repo |

`--add-format` gets a prompt for which kind a new term is. The SKILL.md section on public-only rules
documents the split.

### B. Generic PII patterns in the common tier

New rules in `data/common_secret_formats.toml`, each with a `pii` tag and `severity = "low"` so they
report without drowning the secret findings:

- personal-mailbox email addresses (gmail, outlook/hotmail/live, icloud/me, yahoo, proton); corporate
  domains are left to the org tier, and `users.noreply.github.com` is allowlisted
- phone numbers in the common US and E.164 shapes, keyed on `tel`, `phone`, `mobile`, `cell`, or a
  leading `+`, to avoid matching every ten-digit number
- US SSN shape, keyed on `ssn` / `social`
- AWS account ids: twelve digits keyed on `account`, `arn:aws`, `aws_account`, or `:iam::`
- IBAN and the common card-number shapes only when keyed on `iban` / `card`

Blocking rule: a `pii` finding blocks a commit in a PUBLIC repo and warns in a PRIVATE one, unless it
also matches an `lmf-private-people` term, which blocks everywhere. Visibility unknown is treated as public,
as today.

### C. A pre-push hook with a first-push audit

`scan_secrets.py --pre-push` reads the ref updates git passes on stdin. For each update:

- **New remote ref** (remote sha is all zeros, or the remote has no commits): run the full audit on what is
  about to leave: `gitleaks git` over the whole pushed range with the merged config, the PII rules above,
  `repo_auditor` (gitignore gaps, dangerous files), and a visibility check that compares the local
  `lastmilefirst.visibility` declaration with what `gh repo view` reports. A mismatch blocks the push with
  the remedy printed; a PUBLIC repo with any `lmf-private-*` finding blocks.
- **Existing remote ref:** scan only the pushed range (`remote_sha..local_sha`), so routine pushes stay fast.

Installed by the same `--install-hooks` dispatcher into `~/.claude/lastmilefirst/git-hooks/pre-push`
(`core.hooksPath` is already global). `--uninstall-hooks` removes both. The hook dispatcher pattern from
`pre-commit` is reused: plugin-root glob, `CHECKS_RUN` counter, warn-not-block when the plugin is missing.

### D. Overwatch: visibility drift

Session start reports ACTION REQUIRED when the current repo's declared visibility disagrees with GitHub's,
reusing `check_repo_visibility` and `declared_visibility` from `scanner.py`.

## Open decisions

1. Should generic `pii` findings block in private repos too, or only warn? Proposed: warn, because the
   false-positive rate on phone and account shapes is real, and the people-list already blocks.
2. Should the first-push audit also run `--audit --github` posture checks (push protection, secret scanning)
   for a public repo? Proposed: yes, as a warning block, not a block on the push.

## Files

`skills/scan-secrets/scripts/scan_secrets.py` (new `--pre-push` mode), `scanner.py` (pii tag handling,
range scan), `hook_installer.py` (second hook file), `data/common_secret_formats.toml` (pii rules),
`SKILL.md` (document the split, the hook, the blocking rule), `hooks/scripts/session_start.py` (visibility
drift), `tests/` for each.

## Notes

Discovered 2026-10-09 while pushing a client engagement's first code repo. Related: `feature-scan-secrets-repo-local-config.md`
(a third config tier would let a repo carry its own pii allowlist), `bug-scan-secrets-low-severity-rule-noise.md`
(the noise discipline the `pii` rules must respect). Memory: `project_lmf_prepush_scan`.
