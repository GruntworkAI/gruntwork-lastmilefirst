---
name: review-docs
description: Review an explicitly selected documentation set for duplication, stale claims, gaps, broken references, and misplaced content. Read-only by default; works with supplied text or files without requiring a standard project layout.
---

# Review documentation

Read [the operating boundaries](../lastmilefirst/SKILL.md) and
[the shared documentation criteria](../lastmilefirst/references/review-docs.md).
Review the user's selected documentation directory, files, sections, or pasted material.
If scope is ambiguous, ask the smallest question that identifies it. Do not expand a
document review into a whole-project or organization audit.

No repository or docs/ directory is required. Missing conventional directories are coverage
findings, not reasons to require setup, scaffold files, or run an organization command.
Use the established project archetype and document purpose when judging essential coverage;
the rubric's example filenames are candidates, not a mandatory checklist for every project.
For placement advice in an approved project, consult
[the shared layout reference](../lastmilefirst/references/project-layout.md) and preserve
existing storage paths. Do not migrate .claude data into a guessed Codex layout.

Inventory and read the selected material. Assess actual overlap, claims, instructions, and
local references against evidence available in the approved scope. Repeated subjects may
serve different readers; old modification times alone do not prove stale content. Identify
unread files, unavailable implementation evidence, and reference checks not run. Do not
execute commands copied from the documents to establish whether they work.

Return a concise coverage summary and prioritized findings with source locations, evidence,
reader impact, and specific proposals. Include missing essential documentation, consolidation
or placement candidates, and potential issues where supported. Remote issue duplicates and
external links are unverified unless those checks are separately authorized and actually
performed. Do not assume a GitHub tool, network access, or issue synchronization exists.

This review writes nothing: no edits, cache, review records, suggested-action files, moves,
archives, scaffolding, or issues. Present proposals in chat; implementation requires separate
authorization for the target and action. Use [review-signal](../review-signal/SKILL.md) for a
requested prose-tightening pass and [review-work](../review-work/SKILL.md) for selected work
artifacts, without silently expanding the review.
