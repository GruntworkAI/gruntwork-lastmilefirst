---
title: review-org, and a review-claude that knows all three tiers
version: 1.1
date: 2026-09-21
status: in-progress
type: feat
component: plugins/lastmilefirst/skills/{review-claude,review-org,review-project,organize-claude,overwatch}
target_version: 0.34.0
refs: []
---

# review-org, and a review-claude that knows all three tiers (v1.1)

> **v1.1 (2026-09-24).** Build started on `feat/review-org`. Retargeted from 0.34.0 to 0.34.0,
> because 0.33.0 shipped in between (review-voice round three). The three open questions are
> resolved on their own recommendations: no health score in `review-org`, no session-start alert
> yet, Approved Tools stays required with a pointer to the workspace list. Build order follows
> Sequencing, with U1 and U4 in parallel since they touch disjoint files.
>
> **v1.0 (2026-09-21).** First version. Nothing to compare against yet. Written after a session
> that ran `review-claude` across the workspace, fixed the Gruntwork org file by hand, and found
> that neither problem fixed that day was visible to the tool.

## Problem

### P1. Tier is inferred from directory depth, and the inference breaks on symlinks

`determine_level()` in `review_claude.py` classifies a file by position: parent is the workspace
root (user), grandparent is the workspace root (org), anything else (project). Single-file mode
calls `.expanduser().resolve()` on the `--file` path first. A CLAUDE.md that is a symlink resolves
to wherever its source lives, so the position test runs against the wrong path.

Observed 2026-09-21: `--file ~/Code/gruntwork/CLAUDE.md` resolved into
`gruntwork-stack-wisdom/claude/claude-md-files/org-gw-claude-file/`, was classified as a project,
and was told to declare an archetype. The full-workspace run does not hit this, because it walks
directories from the top and never resolves anything. Keeping tier files in a versioned repo and
symlinking them into place is a reasonable setup, and the README recommends separate git repos for
org-level material, so this is not an exotic case.

### P2. The top tier has three names, and no tier has a stated purpose

The README calls the top tier "workspace-level." The `review-claude` and `organize-claude` skills
and the template call it "user-level." Overwatch's state file calls it `global`. The README's
"Tiered CLAUDE.md" section explains inheritance and says nothing about what each file is for or
what does not belong in it. Without a test for where content goes, it lands wherever it was first
written.

### P3. The review checks each file alone, and the failures happen between tiers

Both defects fixed by hand on 2026-09-21 passed the review:

- The Gruntwork org file approved VS Code, Zed, Copilot, and Vercel. The workspace file marks Zed
  and Vercel as not in use. Both files had every expected heading.
- The org file's Projects table listed 11 projects. The org directory held 27.

The templates make the first kind likely. The workspace template asks for a Project Directory
Mapping, and the org template asks for a Projects table and an Approved Tools section, so two tiers
are asked to describe overlapping things and the tool does not compare them.

### P4. An org can be set up and never reviewed

The skill family has `organize-orgs`, `organize-project`, and `review-project`. There is no
`review-org`. `review-project` composes `review-docs` and `review-work` and explicitly excludes
CLAUDE.md. So the project tier has a health review that skips the file every session loads, and the
org tier has no health review at all.

## Decisions already made (2026-09-21, with the author)

1. `review-org` is an org **health** review, the analogue of `review-project`. The org CLAUDE.md is
   one input, not the whole subject.
2. `review-claude` is adjusted to handle all three tiers properly, and stays the standalone tool for
   checking CLAUDE.md files across the hierarchy.
3. The health reviews are **symmetric**. `review-project` and `review-org` each call `review-claude`
   for their own tier and record both timestamps.
4. Vocabulary is **workspace / org / project**, the README's existing wording.

## Scope

In scope: the tier-detection fix; one vocabulary and a purpose statement per tier; a cross-tier
pass in `review-claude`; a new `review-org` skill and `/run-review-org` command; `review-project`
calling `review-claude`; Overwatch state for the new review; the 0.34.0 release, which also carries
the manifest descriptions held in `todos/2026-09-21-manifest-descriptions-match-readme.md`.

Out of scope:

- A workspace-tier health review. Overwatch's workspace summary already covers cross-project
  health at session start. Revisit if `review-org` proves useful.
- A declared tier line (e.g. `## Tier: Org`). Position already defines the tier. A declaration
  would be a second source of truth that can disagree with where the file sits.
- Reading section bodies for quality. `review-claude` stays a structure check, and prose quality
  stays with `review-signal` and `review-voice`.
- Renaming template files or Overwatch state keys (see U2).

## Design

Five units. U1 is standalone and can ship alone. U4 depends on U3. The rest are independent.

### U1. Fix tier detection

- In single-file mode, make the path absolute **without** resolving symlinks
  (`Path(os.path.abspath(path.expanduser()))`), and classify that.
- In `determine_level()`, test for an org before counting depth: a CLAUDE.md whose directory
  contains `.claude/org.json` is org tier. Keep the depth test as the fallback, since the plugin
  supports orgs by convention with no `org.json`.
- Add `--tier {workspace,org,project}` to override detection, for the case where someone points the
  tool at the source file on the far side of a symlink.
- Print the detected tier and how it was decided (`org: found .claude/org.json`), so a wrong
  classification is visible rather than silent.

Tests (in `skills/review-claude/tests/`): a symlinked org file under `tmp_path` classifies as org;
an org with `org.json` classifies as org at any depth; an org without `org.json` still classifies
by depth; `--tier` wins over detection.

### U2. One vocabulary, and a purpose per tier

Rename the CLAUDE.md top tier to "workspace" in user-facing text: the `review-claude` and
`organize-claude` SKILL.md files, their script output, and the template's comments. Leave alone:

- "User-level" where it means `~/.claude/` (e.g. user-level operatives in `create-operative`,
  `consult-operative`, and the README's operative storage section). That is a different thing and
  the word is right there.
- The template filename `user-claude.md.template` and Overwatch's `global` scope key. Both are
  internal. Renaming them buys nothing a reader sees and costs a state migration.
- `--tier user` is accepted as an alias for `workspace`.

Add a purpose statement per tier to the README's "Tiered CLAUDE.md" section, and as a comment block
at the top of each template. Draft wording, to be edited by the author:

| Tier | The file is for | Belongs here | Does not belong here |
|------|-----------------|--------------|----------------------|
| Workspace | How you work, and where things are | Preferences, voice, tools you use, the map of orgs and projects | Anything true of only one org or one project |
| Org | What every project in this org shares | Identity, security and data handling, naming, the org's tech stack, the project list | Personal preferences; one project's commands or gotchas |
| Project | What someone needs to change or run this repo | Commands, environment, deployment, gotchas, the archetype | Standards that apply to sibling projects too |

One rule covers the overlaps: **a lower tier may narrow or extend a higher one, and must not
restate or contradict it.** A client org that forbids a tool the workspace allows is narrowing, and
that is fine. An org tools table that repeats the workspace list is restating, and should point up
instead.

### U3. A cross-tier pass in review-claude

Two scripted checks and one instruction to Claude.

- **Inventory against disk (scripted).** For an org file, compare the names in the `## Projects`
  table with the project directories `find_projects()` already returns. For the workspace file,
  compare `## Project Directory Mapping` paths with the directories present. Report both directions:
  on disk and not listed, and listed and not on disk. A listed project that is not cloned is
  normal at the workspace tier (the author's own workspace file says so), so "listed, not on disk" is
  informational there and a finding at the org tier.
- **Overlapping sections (scripted).** Using a small fixed map of topics that more than one
  template asks for (tools, project inventory), print which tiers carry each topic for the file
  under review and the files above it. This does not judge the content. It tells Claude where to
  look.
- **Contradictions (Claude).** Add a step to SKILL.md: for each overlap the script prints, read both
  sections and report anything the lower tier says that the higher tier contradicts, quoting both
  lines. State plainly in the report that this step is a reading, not a scripted check.

Report wording follows the existing rule from 0.21.0: say what was measured. "11 of 27 project
directories are listed" is a measurement. "The Projects table is stale" is not.

Tests: a fixture org with three project dirs and a two-row table reports one unlisted directory; a
row with no directory reports as a finding at org tier and as informational at workspace tier; a
table using `[name](path)` links and one using bare names both parse.

### U4. review-org (new skill)

Shape follows `review-project`: a SKILL.md that composes existing pieces, with Claude as the
conversational layer. No health score (see Open questions).

Prerequisite: the org has `.claude/org.json` or the conventional repos. If not, send the user to
`/run-organize-orgs`, the way `review-project` sends them to `/run-organize-project`.

What it runs, all of which exists today except the last two:

| Check | Source |
|-------|--------|
| Identity contract: `org.json` and the CLAUDE.md prose agree, and repos comply | `organize-orgs/scripts/audit_identity.py` (full mode, not `--cheap`) |
| Operatives and stack-wisdom repos exist, are git repos, and have no uncommitted work | `organize-orgs` audit logic, plus `git status` |
| Open and stale todos across the org | `todos-summary/scripts/todos_summary.py` scoped to the org |
| The org CLAUDE.md: sections, inventory against disk, overlaps with the workspace file | `review_claude.py --file <org>/CLAUDE.md` (U1 and U3) |
| Project roll-up: which projects have no CLAUDE.md, no archetype, or no review on record | Overwatch state file, read-only. New small script `review_org.py` |
| Projects whose review, organize, or secret scan is past its Overwatch threshold | Same script, same thresholds Overwatch uses, imported rather than copied |

The report groups findings by what the user would do about them (fix now, schedule, informational)
rather than by which sub-tool produced them.

New files: `skills/review-org/SKILL.md`, `skills/review-org/scripts/review_org.py`,
`skills/review-org/tests/`, `commands/run-review-org.md`. Adding a skill touches the same set of
listing files that adding a persona does, so update together: the README commands table,
`get-started`, the Plugin Layout tree, and `plugin-inventory` if it enumerates by hand.

### U5. Symmetry and Overwatch

- `review-project` SKILL.md gains a step: run `review_claude.py --file ./CLAUDE.md` and include the
  result. Its description and the "For CLAUDE.md review, use review-claude" note change to say that
  `review-claude` is still the tool for checking the whole hierarchy at once.
- State recorded: `review-project` records `review` and `review_claude` at project scope.
  `review-org` records a new `review_org` action and `review_claude`, both at org scope. Add
  `review_org` to `DEFAULT_SCOPES` in `update_state.py` with a default of `orgs`.
- `update_state.py review_claude --scope org` currently fails outside an org directory with "not in
  a recognized org" (seen 2026-09-21 when run from the workspace root). `review-org` always passes
  `--key <org>` so it does not depend on the working directory.
- A session-start alert for an overdue org review is an open question, not part of this unit.

### U6. Release 0.34.0

Version bump across `plugin.json`, both `version` fields in `marketplace.json`, and the root README
table. CHANGELOG entry. The three manifest descriptions from the held todo go out in this release,
and the todo is closed. After merge: `gh release create v0.34.0 --target main --latest`.

## Verification

- The three existing suites still pass, run separately (they cannot share one pytest invocation).
- New unit tests listed under U1, U3, and U4 pass.
- Live workspace, before and after:
  - `--file ~/Code/gruntwork/CLAUDE.md` reports **org** tier and the org sections. Before: project
    tier and an archetype prompt.
  - The inventory check run against the Gruntwork org file as of commit `88fa9fb` in stack-wisdom
    (the version before the 2026-09-21 fix) reports 16 unlisted directories. Against the current
    file it reports none.
  - `/run-review-org` in `~/Code/outsideshot/` reports the five sections its CLAUDE.md lacks and a
    clean identity contract.
- No regression in the full-workspace run: same 34 files, same section findings as the 2026-09-21
  run, apart from the new tier labels and the added inventory lines.

## Risks

- **Over-building.** The 2026-07-29 review-claude plan reached v1.2 before a deliberate descope
  removed most of it. The same risk is here in U3: a topic-overlap map can grow into a rules
  engine. The map stays a short fixed list, and judgment stays with Claude. If U3 needs more than
  two scripted checks to be useful, stop and re-plan.
- **Table parsing.** Project tables are hand-written markdown. The inventory check should match on
  the directory name appearing anywhere in a row, and should say "could not read the table" rather
  than report every directory as unlisted.
- **Noise at the workspace tier.** A workspace map legitimately lists projects that are not cloned.
  Reporting those as findings would train the user to ignore the check.
- **`review-project` gets longer.** One more sub-review per run. Acceptable, since the file it adds
  is the one every session loads.

## Open questions

1. **Health score.** `review-project` prints a score out of 100. A number built from heading checks
   and timestamps claims more precision than it has. Recommendation: `review-org` reports grouped
   findings and no score, and the `review-project` score is reconsidered separately.
2. **Overwatch alert for org review.** Should session start warn when an org has gone N days
   without `review-org`, and what is N? Recommendation: ship without the alert, use the skill for a
   few weeks, then decide. 30 days is a starting guess, not a measured one.
3. **The org template's Approved Tools section.** Keep it as a required section (orgs do narrow the
   tool list, especially client orgs), or make it optional with a pointer to the workspace list as
   the default content? Recommendation: keep it required, and change the template body to the
   pointer plus a "narrowed or extended here" table.

## Deferred

- A workspace-tier health review.
- A `--fix` mode for the inventory check that appends missing rows. Descriptions cannot be
  generated honestly, so a fix mode would write rows with `(specify)` and needs its own thought.
- The three-suites-in-one-command problem (issue #12), which a fourth test directory makes slightly
  worse.

## Sequencing

1. U1 alone, as a fix. Small, tested, and it unblocks trustworthy single-file runs.
2. U2 (docs and wording). Needs the author's edit on the purpose table before it lands.
3. U3, then U4, then U5.
4. U6 once the rest is merged.

Code goes through a branch and a PR. U2's README wording can go direct to main if it lands before
the code.
