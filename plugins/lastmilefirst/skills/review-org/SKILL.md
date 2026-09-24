---
name: review-org
description: Org health review - identity contract, org repos, todos, the org CLAUDE.md, and a roll-up of every project in the org. The org-tier counterpart of review-project.
---

# Review Org

A health review for one org, the way `/run-review-project` is for one project. It runs checks that already exist elsewhere in the plugin, adds a read-only roll-up of the org's projects from Overwatch state, and gives back one report grouped by what the user would do about each finding.

The org CLAUDE.md is one input here, not the whole subject. To check CLAUDE.md files across the whole hierarchy at once, use `/run-review-claude`.

## Prerequisites

The org directory has `.claude/org.json`, or the conventional `<org>-operatives/` and `<org>-stack-wisdom/` repos. If it has neither, respond:
> "This directory is not set up as an org yet. Run `/run-organize-orgs` first."

The org is the directory given as an argument, or the org containing the working directory. Confirm which one before running anything if it is ambiguous (e.g. run from the workspace root).

## What It Runs

`${SKILL_ROOT}` is this skill's directory, and sibling skills sit next to it.

| Check | Source |
|-------|--------|
| Identity contract: `org.json` and the CLAUDE.md prose agree, and the org's repos comply | `python3 ${SKILL_ROOT}/../organize-orgs/scripts/audit_identity.py --json` (full mode, not `--cheap`) |
| Operatives and stack-wisdom repos exist, are git repos, and have no uncommitted work | `org.json` plus `git -C <repo> status --porcelain` |
| Open and old todos across the org | `python3 ${SKILL_ROOT}/../todos-summary/scripts/todos_summary.py --org <org> --format json` |
| The org CLAUDE.md sections | `python3 ${SKILL_ROOT}/../review-claude/scripts/review_claude.py --file <org>/CLAUDE.md` |
| Project roll-up: CLAUDE.md, archetype, and actions on record per project | `python3 ${SKILL_ROOT}/scripts/review_org.py --org <org>` |
| Projects whose review, organize, secret scan, or CLAUDE.md review is past its Overwatch threshold | Same script |

A few notes on reading those results.

The identity audit covers the whole workspace. Keep the findings whose `org` field is this org, and drop the rest. The full audit probes GitHub to check the declared account exists; add `--no-liveness` if the user is offline.

For the org repos, read `org.json` first. An org can opt out of either repo with `"enabled": false`, and a repo the org opted out of is not a finding. The repo names default to `<org>-operatives` and `<org>-stack-wisdom` unless `org.json` names them.

The org CLAUDE.md check reports the file's sections against the org template. Comparing the file's Projects table with the directories on disk, and its tools section with the workspace file, belongs to `review-claude` and is not in it yet. Report only what the script prints.

`review_org.py` is read-only. It reads the Overwatch state file and never writes it. It counts every non-hidden directory in the org as a project directory and applies the Overwatch thresholds the same way session start does: an action past its threshold counts only when the repo has commits since it last ran. A project with no commits at all is listed separately. Pass `--json` to get the per-project data.

## The Report

Group findings by what the user would do, not by which check found them. There is no health score. A number built from heading checks and timestamps would claim more precision than it has.

Say what was measured. "11 of 27 project directories have a CLAUDE.md" is a measurement. "Project docs are stale" is not.

```markdown
# Org Review: <org>

## Fix now
Identity contract errors, an org repo with uncommitted work, an org CLAUDE.md missing required sections.

## Schedule
Projects past an Overwatch threshold, projects with no CLAUDE.md or no archetype, open todos that have sat for weeks.

## Informational
Projects with no review on record, identity notes, the org's own record (when it was last reviewed or organized), anything the user has already decided to leave.

## Suggested next steps
The two or three commands that would clear the most of the above, e.g. `/run-review-project` in a named project, `/run-organize-orgs`, `/run-scan-secrets --all`.
```

Where a section is empty, say so in one line rather than dropping it, so the user can tell a clean result from a check that did not run. If a check failed to run, say which and why.

## Update Overwatch

After the report, record both reviews at org scope. Always pass `--key <org>` (the org directory's name), so the record does not depend on the working directory:

```bash
python3 ~/.claude/plugins/marketplaces/gruntwork-lastmilefirst/plugins/lastmilefirst/hooks/scripts/update_state.py review_org --scope org --key <org>
python3 ~/.claude/plugins/marketplaces/gruntwork-lastmilefirst/plugins/lastmilefirst/hooks/scripts/update_state.py review_claude --scope org --key <org>
```

## Integration

- **`/run-organize-orgs`**: sets up what this review finds missing
- **`/run-review-project`**: the same review, one project at a time
- **`/run-review-claude`**: CLAUDE.md files across all three tiers
- **`/run-todos-summary`**: the full todo list behind the todo counts here
- **`/run-overwatch`**: the session-start view of the same state
