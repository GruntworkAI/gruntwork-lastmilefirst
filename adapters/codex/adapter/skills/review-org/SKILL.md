---
name: review-org
description: Review one explicitly selected organization's local health, identity contract, support repos, project inventory, client tier, todos, and context. Read-only by default; disclose partial coverage when only a repository is available.
---

# Review an organization

Read [the operating boundaries](../lastmilefirst/SKILL.md),
[the hierarchy contract](../lastmilefirst/references/hierarchy.md), and
[audit usage](../lastmilefirst/references/audit.md). Establish the approved organization root;
ask the smallest scope question if it is ambiguous. A selected project alone cannot establish
the whole organization's health. Continue a bounded project review and report the coverage
gap if broader access is unavailable. Do not substitute a guessed ~/Code layout.

Run the audit helper with --org and an explicitly selected --project. Add --workspace only
when that root's context and organization identity claims are approved for reading. An org
root may contain direct projects or one marker-declared client tier. Empty clients still
need layout checks. Respect org.json support-repo opt-outs and existing .claude storage.
No marker or org.json means an organization setup finding, not permission to create it.

Assess the org context, local identity contract, declared operatives/wisdom/knowledge resources,
project inventory, and per-project context/archetype/work evidence. Report local Git checks
and their limits, especially inherited Git identity and ownership claims outside the approved
workspace. Do not equate a network-free check with GitHub account verification, server-side
security, or a secret scan. Skip inaccessible projects with a named coverage gap.

Use [the canonical report grouping](../lastmilefirst/references/review-org.md): Fix now,
Schedule, Informational, Suggested next steps. Keep empty sections so clean and unrun checks
are distinguishable. Use counts and evidence rather than a score. Old review history is only
historical evidence; no automated Overwatch hooks or fresh review records are provided.
Detailed content reviews of every project are not implied by a structural roll-up; list which
projects actually received [a project review](../review-project/SKILL.md).
