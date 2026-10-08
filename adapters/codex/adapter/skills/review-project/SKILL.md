---
name: review-project
description: Read-only LastMileFirst project review covering docs, work artifacts, project context, archetype expectations, and cross-cutting inconsistencies. Use for a selected project's health review, not a whole-org audit.
---

# Review one project

Read [the operating boundaries](../lastmilefirst/SKILL.md) and
[audit usage](../lastmilefirst/references/audit.md). Run the bounded helper with the approved
project path. If org context is needed, first establish its approved root using
[the hierarchy contract](../lastmilefirst/references/hierarchy.md); do not guess ancestors.
A project-only result must say organization coverage is partial.

Missing docs/, context, or work directories are findings. They do not block useful inspection,
justify scaffolding, or require running the obsolete /organize command.

Read the relevant bounded project files and these shared criteria:
- [Docs review](../lastmilefirst/references/review-docs.md): duplication, stale claims, broken references, gaps, and misplaced material
- [Work review](../lastmilefirst/references/review-work.md): todos, plans, sessions, and debt
- [Project consistency](../lastmilefirst/references/review-project.md): disconnects across code, docs, and work
- [Expected structure](../lastmilefirst/references/project-layout.md): preserve existing storage paths

Apply the declared Deployable, Usable, Referenceable, or Experimental archetype. Missing or
unknown archetypes are findings, not a reason to impose Deployable requirements. Evaluate
whether docs are essential for the actual archetype; there is no requirement to create every
sample document. Archive-age thresholds in source rubrics differ; report candidates and ask
for the chosen policy before proposing any move. No archival is performed.

Return a concise evidence-based report: scope and coverage; actionable findings with file
references; docs/work/context results; cross-cutting issues; suggested next steps; checks not
run. Distinguish scripted heading/inventory checks from your semantic reading. Do not produce
a numerical health score. GitHub issue synchronization is unverified in this offline pilot;
identify candidates without assuming duplicates were checked or creating issues.
