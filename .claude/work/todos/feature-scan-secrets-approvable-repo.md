# Feature: a repo marked approvable for a people-rule finding, instead of exempt

**Status:** open
**Priority:** high
**Created:** 2026-10-11

## What happened

The first commit in a campaign-website repo after the 0.37.0 names split was blocked by
`lmf-private-people`: the candidate's surname is on the people list, and the repo's whole
subject is the candidate. Every copy document, every session note, and the content YAML
match. The scanner has no per-repo switch of any kind, so the round went in with
`git commit --no-verify`, which also skipped the identity check and every other rule.
The same thing will happen on every round in that repo, and in any repo whose subject is
a person on the list (a family member's project, a client founder's own repo).

Taking the name off the list is the wrong fix: the list exists to keep that name out of
every other repo. A per-repo exemption is also wrong: an exemption makes the finding
disappear, and a stray second name from the same rule would disappear with it.

## The feature

A repo can be marked **approvable** for a named rule. In an approvable repo the finding
still prints on every commit, and the commit goes through only with an explicit approval
for that commit. Nothing is silent, nothing else is skipped.

### Marking the repo

Local git config, never committed (the term list stays out of repos, same as today):

```
git config --add lastmilefirst.approvable lmf-private-people
```

Repeatable for more than one rule. Only rules tagged `private-name` (and, later, `pii`)
may be marked approvable; an ordinary secret rule named here is ignored with a warning,
so a real credential can never be approved through.

### Approving a commit

```
LMF_APPROVE=1 git commit -m "..."
```

The hook, in an approvable repo with findings only from approvable rules:

1. prints the findings as it does today, plus one line naming the rule and the matched
   terms, so a *second* name in the same rule is seen before it is approved;
2. with `LMF_APPROVE` set, prints `approved: <rule> (<n> findings) in <repo>` and exits 0;
3. without it, blocks and prints the exact command to re-run with approval, and the
   `--no-verify` warning that it also skips identity.

Any finding from a non-approvable rule blocks regardless of `LMF_APPROVE`. The identity
check always runs.

### Record

Append one line per approval to `.git/lastmilefirst/approvals.log` (rule, finding count,
commit date, the staged paths). Local only. `--audit` reads it and reports approvals in
the repo so a review can see how often the switch was used.

### Pre-push

The pre-push hook (0.37.0) scans the pushed range and would block the same commits. It
honors the same marker: approvable-rule findings in an approvable repo are reported and
allowed on push without a second `LMF_APPROVE`, because the approval was given at commit
time and is in the log. A repo GitHub reports as **public** ignores the marker: a person's
name reaching a public remote is the case the rule exists for, and the `public-only`
logic already has the GitHub answer.

### Overwatch

Session start in an approvable repo prints one quiet line (`this repo is approvable for
lmf-private-people`) so the marker is never forgotten.

## Open questions

- Per-rule or per-term? Per-rule is simpler and keeps the term out of git config; the
  matched-terms line in the output is what makes a second name visible. Start per-rule.
- Should `LMF_APPROVE` take a rule name rather than `1`, so the approval is scoped when
  two approvable rules fire at once? Probably yes once there is a second approvable rule.
- Claude Code commits run the hook non-interactively, so a prompt is not an option; the
  env var is the approval. Confirm the hook sees the variable under the Bash tool.

## Files affected

- `skills/scan-secrets/scripts/scan_secrets.py` (pre-commit and pre-push paths)
- wherever `lastmilefirst.visibility` is read (same config read, new key)
- `skills/scan-secrets/scripts/repo_auditor.py` (approvals in `--audit`)
- `skills/scan-secrets/SKILL.md` (new section beside "Splitting an existing names list")
- `skills/overwatch/` (the one-line notice)
- tests beside `test_visibility_policy.py`

## Related

`feature-scan-secrets-repo-local-config.md` is about rules that travel with a repo; this
is about a local decision that must not travel. Different mechanisms on purpose.
