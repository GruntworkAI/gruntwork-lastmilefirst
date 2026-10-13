# Feature: a repo marked approvable for a people-rule finding, instead of exempt

**Status:** BUILT 2026-10-12 on `feat/approvable-repo` (0.39.0; plan v1.4), awaiting merge and release; the campaign-side CLAUDE.md line and the manual verification run follow the release
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

### Showing what was found, then asking

The approval is always given against the matched text, never before it. Today's report
prints rule, file, and line only; for an approvable rule that is not enough, because the
match is the thing being approved. In an approvable repo, findings from approvable rules
are printed grouped by matched term, in the clear (ordinary secret rules keep their
redaction; a name or a phone number is shown whole):

```
lmf-private-people in 2 files (42 lines)
  <term>     42×   .claude/work/plans/copy-review/<copy-doc>.md (21)
                   .claude/work/plans/copy-review/<copy-doc>.docx (21)
Approve these for this commit? This repo is marked approvable for lmf-private-people.
```

A second term is its own row, so a stray name from the same rule is seen before anything
is approved. gitleaks' JSON output carries the match, so no second scan is needed.

### Approving a commit

How the ask is answered depends on where the hook runs:

- **Terminal.** The hook reads a y/n from `/dev/tty` with the list on screen. `n` blocks.
- **Non-interactive** (Claude Code's Bash tool, CI, an editor's git client). No prompt is
  possible, so the hook blocks, prints the list, and prints the exact re-run:
  `LMF_APPROVE=1 git commit ...`. The variable is the answer to the list just printed.

With the approval given, the hook prints `approved: <rule>, terms: <term>[, <term>] (<n>
findings)` and exits 0. Any finding from a non-approvable rule blocks regardless of the
answer or the variable. The identity check always runs. Without an approval the block
message also carries the `--no-verify` warning that it skips identity too.

### Record

Append one line per approval to `.git/lastmilefirst/approvals.log` (rule, the approved
terms, finding count, commit date, the staged paths, and whether the answer came from the
tty or the variable). Local only. `--audit` reads it and reports approvals in
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
- Confirm the hook sees `LMF_APPROVE` under Claude Code's Bash tool (git inherits the
  environment, so it should), and that the permission layer treats it as an ordinary
  variable rather than a safety bypass the way it treats `--no-verify`.
- Confirm `/dev/tty` is readable from a git hook in Terminal and in Cursor's git client;
  fall back to the non-interactive path whenever it is not.

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
