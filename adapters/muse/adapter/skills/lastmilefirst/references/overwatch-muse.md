# Overwatch, mapped to Muse

Overwatch in the plugin is hooks + a state file: SessionStart checks, PostToolUse
change tracking, a Stop-hook commit nudge. Muse has different machinery for the
same job: scheduled jobs (`cron`) for the periodic checks, and the agent's own
working state for the session-scoped ones. This file is the mapping. It is
hand-written because the design is new; the check *definitions* live in the
canonical `skills/overwatch/SKILL.md`.

## Check → mechanism

| Overwatch check | Muse equivalent |
|---|---|
| Uncommitted changes | Weekly hygiene job: `git status --porcelain` across `~/workspace/repos/*` |
| Stale todos | Same job: review the `todo.write` working list and goal briefings |
| Secret scan freshness | Same job: `bin/scan-secrets` on each repo; alert on findings |
| Project review freshness (7d) | Same job: compare against memory/dated notes of last review |
| Plugin/skill updates | `python3 adapters/muse/build.py --check`, which fails if the generated skill package drifted from canonical sources |
| Expert roster sync | Roster is generated (`references/personas.md`); the check is `--check` above |
| Repo visibility (public) | Same job: flag repos with unexpected visibility |
| Missing working notes | Same job: flag repos without notes/README |

## Session-scoped behavior (no cron needed)

- **Change tracking during work:** the agent already sees every edit it makes;
  no log file required.
- **Commit nudge at stop:** when a coding task ends with uncommitted changes,
  ask whether to commit; don't push without confirmation.
- **State:** memory files and dated notes replace `overwatch-state.json`.

## The weekly hygiene job (proposed)

One scheduled run, Monday morning: scan repos, report findings, stay silent
when clean. Per-check thresholds mirror the plugin (7d review, 14d todos).
Nothing is committed or pushed by the job. It reports, the user decides.
