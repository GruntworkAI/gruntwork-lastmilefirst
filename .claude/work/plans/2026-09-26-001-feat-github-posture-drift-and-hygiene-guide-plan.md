---
title: GitHub posture drift in Overwatch, and a hygiene guide for shared repositories
version: 1.0
date: 2026-09-26
status: proposed
type: feat
component: plugins/lastmilefirst/hooks/scripts/github_protections.py, skills/scan-secrets, docs/
target_version: 0.35.0
refs:
  - .claude/work/plans/2026-08-30-001-feat-github-secret-scanning-posture-check-plan.md (the check this extends)
  - ~/Code/gruntwork/gruntwork-stack-wisdom/stack-wisdom/github-account-and-repo-hygiene.md (the private checklist, v1.0)
---

# GitHub posture drift in Overwatch, and a hygiene guide for shared repositories (v1.0)

> **v1.0 (2026-09-26).** First version. Follows a day in which a squash merge of a fork pull request
> published a personal email address on a public default branch, and the checklist written
> afterwards turned out to split cleanly into things a tool can read and things only a person can
> set. This plan builds the first kind into the existing posture check and ships the second kind as
> a guide.

## Problem

### P1. The posture check reads two fields from a response that carries a dozen

`github_protections.fetch_posture()` makes one `gh api repos/{owner}/{repo}` call at session start
and reads `security_and_analysis.secret_scanning` and `.secret_scanning_push_protection`. The same
response also carries `visibility` (already used), `allow_squash_merge`, `allow_merge_commit`,
`allow_rebase_merge`, `allow_forking`, `delete_branch_on_merge`, `has_wiki`, `has_discussions`,
`has_projects`, `web_commit_signoff_required`, and `security_and_analysis.dependabot_security_updates`.
Each is a setting the hygiene checklist asks a person to verify by hand, and each is already in
memory on every session start, unread.

### P2. The drift that matters most to this plugin is not checked at all

Claude Desktop and the consumer app install a plugin from its release tag, not from `main`. A
`v*` tag that can be moved or deleted is a supply-chain hole for every Desktop user of the three
public marketplaces. Nothing in the plugin looks at tag rulesets. Nothing looks at branch rulesets,
Actions permissions, the default workflow token, webhooks without a secret, or writable deploy
keys either. Each needs its own API call, so none belongs at session start, and the plugin has an
`--audit` mode that is the right home and does not do it.

### P3. The human half has no shipped home

Email privacy, two-factor method, recovery codes, session review, app authorizations, and the
merge-method trap for fork pull requests are one-time actions on settings pages, and the two that
matter most (email privacy, two-factor) are not readable through the API. The checklist for them
exists once, in a private repo, with account names in it. The plugin's premise is people and
coding agents sharing repositories, which is exactly the situation that produced the incident,
and the plugin ships no guidance on it.

### P4. The posture module has no tests

`hooks/tests/` covers the compound counter and the plugin update check. `github_protections.py`
has none. Extending it without a fixture-based suite would repeat the pattern the 2026-08-30 plan
warned about.

## Decisions

**D1. Report, never change.** The plugin reads settings and says what it measured. It never
PATCHes a setting. The one existing exception stays as it is: `enable_command()` prints a command
the user can run. Nothing new prints a command.

**D2. Session start alerts do not grow.** The two alerts that exist (secret scanning off, push
protection off, on a public repo) remain the only session-start alerts from this module. The new
zero-cost fields are cached and shown in `--audit` and in `describe()`, not alerted on. Merge
method, forking, and wiki are policy choices, and alerting on a choice trains the user to ignore
the alert that is not a choice. One candidate is deferred rather than decided: a session-start
alert when a repo that ships a `marketplace.json` has no tag ruleset. See Open questions.

**D3. Per-call checks live in `--audit` only.** Rulesets, Actions permissions, workflow token
defaults, webhooks, deploy keys, and Dependabot alert status each cost a call. They run when the
user asks, never at session start.

**D4. Findings are measurements.** The 0.21.0 rule: "0 rulesets target tags matching `v*`" is a
measurement; "release tags are unprotected" is a conclusion the user draws. Where a measurement
has a consequence the user may not know, one clause states it ("Desktop installs resolve from
this tag").

**D5. The guide ships generalized, in a new `docs/` folder at the plugin level.** The plugin has no
`docs/` today. The workspace convention is that `docs/` is for users and deployers, which is who
reads a hygiene guide. The private stack-wisdom checklist keeps the account names and gains a
pointer to the shipped guide as its source of record for the generic content.

**D6. No new skill.** "Is GitHub's safety net switched on" already lives in scan-secrets. "What
should a person set once" is a document. The fork-PR merge-method check is a workflow rule and
fires at a GitHub merge, where no local hook runs.

## Design

### Zero-cost fields (session start, cached)

`parse_posture()` grows to return, from the same payload: `visibility`, `merge_methods` (the set of
allowed methods), `allow_forking`, `delete_branch_on_merge`, `features` (wiki, discussions,
projects: on or off), `dependabot_security_updates`. Absent fields stay `UNKNOWN`, for the same
reason the existing ones do (no admin on the repo means no `security_and_analysis`). The cache
entry under `github_protections` in project state carries the new fields, so `--audit` can show
them without a second call when the cache is fresh.

### Per-call checks (`--audit`)

| Check | Endpoint | Measurement printed |
|---|---|---|
| Default-branch ruleset | `repos/{r}/rulesets` filtered to branch targets | count of rulesets targeting the default branch; whether any requires a pull request, blocks force pushes, restricts deletions |
| Tag ruleset | same, tag targets | count of rulesets whose pattern matches `v*` (or any tag); whether deletions are restricted and force pushes blocked; "this repo ships a marketplace.json" noted when true |
| Dependabot alerts | `repos/{r}/vulnerability-alerts` | on (204) or off (404) |
| Actions policy | `repos/{r}/actions/permissions` | enabled; allowed actions class |
| Workflow token | `repos/{r}/actions/permissions/workflow` | default permissions; can approve pull requests |
| Webhooks | `repos/{r}/hooks` | count; count with no secret; count with `insecure_ssl` on |
| Deploy keys | `repos/{r}/keys` | count; count writable |

Each endpoint can 403 or 404 for a caller without admin. That reads as `UNKNOWN` and prints one
line saying so, never as a finding. A user-account repo on a free plan cannot have rulesets on a
private repo; the tag and branch checks say "not available on this plan" when the API says so,
rather than "0 rulesets".

`--audit --github` (the account sweep) gains the zero-cost fields per public repo, since it already
makes one call per repo. It does not run the per-call checks, which would multiply the calls by
seven; a flag `--deep` does, and the SKILL.md says what it costs.

### The guide

`docs/github-hygiene-for-shared-repos.md`, generalized from the private checklist: account
settings a person sets once, repository settings, the fork-pull-request merge-method trap, the
audit commands, and a cadence. The plugin's setup illustrates the pattern without naming
accounts. Linked from the plugin README and from the scan-secrets SKILL.md posture section, with
one sentence in each saying which parts the plugin checks for you and which parts it cannot.

## Units

### U1. Tests first for the module as it stands

`hooks/tests/test_github_protections.py`, fixture payloads only, no live calls: `parse_posture()`
on a full payload, on a payload with no `security_and_analysis`, on a malformed one; `is_exposed()`
and `posture_alert()` on public and private repos; `describe()` output shape. This locks the
current behavior before U2 changes it.

*Accept:* the hooks suite passes with the new file; every existing public function has at least
one test.

### U2. Zero-cost fields

Extend `parse_posture()` and `describe()`; extend the cache entry; no change to `posture_alert()`.
Update the scan-secrets SKILL.md posture table.

*Accept:* tests for each new field including the absent case; session start output is unchanged
on a repo with both protections on; `--audit` shows the new block.

### U3. Per-call checks in `--audit`

New functions in `github_protections.py`, one per endpoint, each returning a small dict with
`UNKNOWN` on any non-2xx. An `audit_posture(repo)` that runs them and a `describe_audit()` that
prints measurements per D4. Wire into `scan_secrets.py --audit` and `--audit --github --deep`.

*Accept:* fixture tests per endpoint including 403 and 404; a test that a repo containing
`.claude-plugin/marketplace.json` gets the Desktop consequence clause when no tag ruleset
matches; a live read-only run against this repo pasted into the PR.

### U4. The guide

`docs/github-hygiene-for-shared-repos.md` plus the two links. Generalize from the private
checklist; no account names, no incident narrative (the public-repo content rule). The private
checklist gains a one-line pointer and drops the sections the guide now owns, keeping only the
account-specific notes.

*Accept:* the guide passes the public-repo content rule by inspection; both links resolve;
`review-voice` critique pass on the guide returns Ship or Hold with local fixes only.

### U5. Release 0.35.0

Version bump across the three files, PR, merge, `gh release create v0.35.0 --target main --latest`.
Run the new audit against all three public marketplaces before tagging and record the tag-ruleset
measurement for each in the PR, because the tag protection finding applies to this plugin's own
distribution first.

## Verification

- Hooks suite passes; count reported.
- Session start on this repo: output identical to before U2, apart from nothing.
- `scan_secrets.py --audit` on this repo: the new blocks print, every line a measurement.
- `--audit --github --deep` on one account completes, and the SKILL.md states the call count.
- The three marketplaces' tag-ruleset measurements are in the PR.

## Risks

- **Rules engine.** The 2026-08-30 plan's warning applies twice over here. Seven per-call checks is
  the ceiling for this plan. If a check needs a judgment ("is this webhook suspicious"), it does
  not go in; the plugin prints the count and the user judges.
- **Rate limits and latency.** `--deep` across an account with many repos is eight calls per repo.
  The SKILL.md says so and the script prints a running count.
- **Plan-gated features.** Rulesets on private user repos need a paid plan; the API reports this
  as a 403 with a message. Map that to "not available on this plan" so it is not read as a gap.
- **Reading settings you do not own.** Every endpoint returns less for non-admins. `UNKNOWN` stays
  silent, as it does today.

## Open questions

1. **A session-start alert for an unprotected release tag on a marketplace repo.** It is the one
   new alert with a supply-chain consequence and a fixed audience (Desktop users). Against it: it
   costs one extra call per session start on those repos, and D2 says alerts do not grow.
   Recommendation: ship without it, run `--audit` on the three marketplaces at release time (U5),
   and revisit after a month of audits.
2. **Whether the guide or the checklist is canonical for the generic content.** Recommendation: the
   shipped guide is canonical; the private checklist keeps only what names accounts.

## Deferred

- A `--fix` that applies settings. D1 says never; revisit only if a user asks for it twice.
- Organization-level settings. Both accounts here are user accounts; write the org section when
  there is an org to test against.
- Email privacy and two-factor status. Not readable through the API; they stay in the guide.
