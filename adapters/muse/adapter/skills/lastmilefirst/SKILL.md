---
name: lastmilefirst
description: PARC workflow (Plan, Allocate, Review, Compound) for AI-assisted work, plus review checklists for docs and voice. Use for any substantive build, implementation, or review task; skip on "quick question" or "no PARC".
---

# LastMileFirst

**P**lan → **A**llocate → **R**eview → **C**ompound. A disciplined workflow for
AI-assisted work that scales with task complexity, from one exchange to a
multi-agent build. Ported from the GruntworkAI LastMileFirst Claude Code
plugin; the full workflow lives in `references/parc-full.md`.

## Purpose

Stop the four failure modes of unstructured agent work: tunnel vision
(fixating on one approach), wasted cycles (work thrown away), quality gaps
(bugs ship), repeated mistakes (same problems recur).

## Workflow

**1. Plan: think before doing.** Discovery first when the request is
exploratory; widen before narrowing. State assumptions and flag the shaky
ones. Run the YAGNI check (simplest thing that solves the real problem?) and
the YAGWYDI check (one-time infrastructure cost with ongoing benefit?).
YAGNI for features, YAGWYDI for scaffolding, tests, and wisdom capture.
Check `muse.memory_search` for prior art. For HIGH complexity, brief a
subagent with the scout-coordinator persona to decompose the work. The
proposal precedes the artifact; three sentences can be enough.

**2. Allocate: delegate to subagents.** Break work into chunks, brief one
`subagent.spawn` per chunk with role, context, task, constraints, and success
criteria. Parallelize independent chunks; sequence dependent ones. Match
experts to domains (a subagent briefed with the relevant persona file from
the plugin's `personas/` directory).

**3. Review: the quality gate.** Tests, then a reviewer subagent for the
code type, then validation against the Plan's success criteria. A review that
returns "strong, with a few small notes" has usually not been done. Name
the weakest link plainly. For docs use `references/review-docs.md`; for
prose that must sound human use `references/review-voice.md`. For secrets,
run `bin/scan-secrets` against the repo before anything is committed. The
wrapper passes only paths and flags to the local scanner — findings stay in
your workspace and nothing is transmitted anywhere by this tool.

**Expert consultation.** To get a specialist's take, `subagent.spawn` a
subagent briefed with the persona file from `references/personas.md`
(e.g. Adam for AWS, Paloma for Python, Quinn for QA strategy). Give it role,
context, task, constraints, and success criteria; it reports back.

**4. Compound: close every cycle.** Once per unit of work that produced an
artifact or decision, ask in order: (1) did we apply an old lesson?
(`muse.memory_search`, confirm matches); (2) does anything rhyme with an
existing lesson? (don't write a second copy; promote or fix the original);
(3) is there anything new? Route it: facts → `MEMORY.md`, generalizable
lessons → memory, repo-bound gotchas → the project's notes, repeatable
procedures → a skill. "Nothing" is an acceptable answer, said out loud. When
all three are empty, one line: *Compound: nothing applied, no rhymes,
nothing new.*

## Output Contract

- Substantive tasks open with a short plan before any artifact exists.
- Reviews lead with the weakest finding, no hedged praise.
- Every cycle ends with a Compound close (one line when empty).

## Operating Rules

1. Scale ceremony to complexity: TRIVIAL (just do it) → LOW (brief plan, tests,
   one-line close) → MODERATE (full plan, agents, review, chat close) → HIGH
   (documented plan, scout orchestration, comprehensive review, full close).
2. Escape hatches: "quick question", "no PARC", or equivalent skips the
   ceremony and answers directly.
3. Never let the mechanism outrank the judgment: if a step adds no leverage
   at this complexity, skip it and say so.
4. This skill's `references/` are generated from the canonical plugin sources
   by `adapters/muse/build.py`. Read them, don't edit them here.
