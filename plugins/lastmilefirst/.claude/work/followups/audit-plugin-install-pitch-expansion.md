# Followup: expand `/run-audit-plugin` install pitch documentation

**Status: deferred. Documentation work, not bug fix.**

**Surfaced during:** code review of `feat/audit-plugin-phase-1.5` on
2026-04-20 (merged commit `769b3db`).

## Context

The audit-plugin wrapper has three distinct failure modes requiring
user action:

1. **Griffith binary missing** → `GRIFFITH_MISSING` sentinel →
   install pitch on stderr
2. **osv-scanner missing** (--sca path) → `OSV_SCANNER_MISSING`
   sentinel → griffith's install pitch passed through
3. **Dev-mode unreachable** → `GRIFFITH_MISSING` with special gating
   (`LMF_ALLOW_DEV_GRIFFITH=1`)

Today's SKILL.md documents the happy path plus basic error handling
but doesn't enumerate:

- Exact install commands per platform (brew/apt/manual download)
- Where Griffith looks for its own config (rules/, limits.yaml)
- How `LMF_ALLOW_DEV_GRIFFITH=1` interacts with
  `GRIFFITH_BIN=/custom/path`
- Troubleshooting for containment-check rejections (e.g., Griffith
  installed to `/Applications/tools/griffith` rather than allow-
  listed prefixes)
- Upgrade path when Griffith's schema_version changes

## Why deferred

Documentation is low-risk but boilerplate-heavy. Worth doing in one
focused pass with attention to:

- Platform-specific commands tested on macOS + Linux
- Screenshots / example session output (if markdown rendering
  supports them in this skill context)
- SKILL.md vs README.md vs `commands/run-audit-plugin.md` — which
  audience lives where

Defer until the wrapper has real external consumers (today Michael
is the only user; the install pitch is self-documenting for him).

## Trigger conditions to revisit

- First external user report: "I tried to install but got lost"
- CE or other marketplace plugins start depending on audit-plugin
- `/run-audit-plugin` gets mentioned in a blog post / tutorial and
  we want the install story to be polished

## Scope when we revisit

- SKILL.md: full install walkthrough section
- README.md: quick-start snippet with one-line install commands
- `commands/run-audit-plugin.md`: short — just the usage summary

## Related

- PR: feat/audit-plugin-phase-1.5 (merged `769b3db`)
- SKILL.md at: `plugins/lastmilefirst/skills/audit-plugin/SKILL.md`
