---
name: review-signal
description: Review text or files for slop, weak prioritization, repetition, and low-signal writing. Use for README.md, docs/, CLAUDE.md, PRDs, ADRs, prompts, memos, and AI-generated drafts.
---

# Review Signal

Analyze a text artifact for editorial quality issues: filler, repetition, abstraction, weak prioritization, unsupported claims, bloated openings/endings, and other forms of low-signal writing.

## When to Use

Use this skill when:
- a draft feels generic, padded, or AI-sloppy
- a `README.md`, `CLAUDE.md`, or `docs/` file is technically fine but hard to scan
- a PRD, ADR, memo, or status update buries the real point
- an AI-generated answer sounds polished but not useful enough
- you want a rewrite that preserves voice while cutting filler

## When *Not* to Use

Use other skills when the main problem is elsewhere:
- **`/run-review-docs`**: Docs folder structure, staleness, missing docs, misplaced content
- **`/run-review-project`**: Cross-cutting project hygiene across docs and work artifacts
- **`/run-review-claude`**: CLAUDE.md hierarchy, context placement, and token-efficiency decisions
- **`/run-consult-expert shannon`**: Skills vs CLAUDE.md, plugin structure, context architecture
- **`/run-consult-expert reese`**: Source validation, product/vendor research, factual comparisons
- **`/run-consult-expert quinn`**: Test strategy and validation quality

Use `review-signal` when the bottleneck is writing quality, clarity, prioritization, or signal density.

## Core Standard

Every sentence should earn its place by adding at least one of these:

- **Relevant**: directly serves the task, reader, or argument
- **Evidenced**: grounded in fact, reasoning, example, or clearly marked judgment
- **New**: adds information, movement, distinction, or priority
- **Traction**: helps the reader understand, decide, or act

Call this the **RENT** test.

If a sentence fails two or more RENT dimensions, cut it, compress it, clarify it, or flag it for verification.

## Slop Patterns to Hunt For

Look especially for:

1. **Throat-clearing**
   - "It is important to note"
   - "In today's rapidly evolving landscape"
   - "There are many factors to consider"

2. **Prompt-mirroring**
   - Restating the question instead of answering it

3. **Generic abstraction**
   - strategy, alignment, optimization, innovation, leverage, transformation, framework, efficiency
   - especially when there is no mechanism, actor, example, or consequence

4. **False balance**
   - "it depends" without naming what it depends on
   - "there are pros and cons" without ranking the important ones

5. **Repetition disguised as completeness**
   - intro, body, and ending repeating the same point

6. **Pseudo-specificity**
   - "studies show," "experts agree," or "best practices suggest" without grounding

7. **List bloat**
   - too many options, no prioritization

8. **Bloated openings or endings**
   - framing paragraphs that do not materially help the reader

## Editing Priorities

Always optimize in this order:

1. **Truthfulness** — preserve what is actually supported
2. **Task fit** — answer the real question and respect the requested scope
3. **Signal density** — remove filler and repetition
4. **Specificity** — replace abstractions with concrete claims, distinctions, examples, or mechanisms
5. **Prioritization** — force ranking where the draft is flat
6. **Voice preservation** — retain the author's character unless asked to change it

## Input Modes

This skill can work on:
- a pasted draft
- one specific file path
- a short list of files
- a named section inside a file
- a response Claude just generated in the current session

Optional inputs:
- **audience**: who the text is for
- **job**: explain, recommend, summarize, compare, persuade, etc.
- **mode**: critique-only, rewrite-only, or critique+rewrite
- **aggressiveness**: light, standard, ruthless
- **voice constraint**: preserve current voice, simplify, harden, soften, executive, etc.

## How to Run

### Step 1: Freeze the Job
State in one line what the text is supposed to do.

Examples:
- explain a concept clearly
- recommend a course of action
- summarize evidence
- onboard a new engineer
- tighten an AI-generated answer for executive use

If the job is fuzzy, say so. Unclear purpose is often the root problem.

### Step 2: Inspect the Artifact
Read the target text and identify:
- what the document is trying to do
- who the reader seems to be
- where the real point first appears
- whether the opening and ending are earning their keep

### Step 3: Diagnose the Biggest Leaks
Focus on the highest-value issues:
- repetition
- abstraction
- weak prioritization
- unsupported authority language
- bloated framing
- low actionability
- mismatch between scope and depth

Do not nitpick every sentence unless the user asks for line-by-line markup.

### Step 4: Score the Draft
Score each category as:
- **0** = clean
- **1** = somewhat present
- **2** = obvious problem

Categories:
- generic wording
- repetition
- weak specificity
- weak prioritization
- unsupported or blurry claims
- unnecessary caveats
- bloated opening/ending
- low actionability

Then give an **overall signal/slop score** out of 16.

### Step 5: Revise Decisively
Apply these moves:
- **Cut** generic, ceremonial, or repetitive language
- **Compress** any point that takes too long to say
- **Clarify** fact vs inference vs recommendation
- **Concrete-ify** abstractions with mechanism, example, actor, or consequence
- **Re-rank** flat lists into what matters most, next, and optional

### Step 6: Preserve the Author's Intent
Do not inject new arguments or new facts unless the user explicitly asks for augmentation.
Keep the original meaning intact unless the text is internally contradictory.

## Default Output Format

Use this structure unless the user requests a different one.

```markdown
## Job
One line on what the text is trying to accomplish.

## Verdict
A concise diagnosis of the draft.

## Signal / Slop Score
X/16 — short interpretation

## Biggest Leaks
- ...
- ...

## Revised Version
[Tightened rewrite]

## Notes
- what you cut
- what you compressed
- what you clarified
- what you re-ranked
- what needs verification
```

## Operating Modes

### Critique-Only
Use when the user wants feedback but not a rewrite.
Return:
- Job
- Verdict
- Signal / Slop Score
- Biggest Leaks
- Notes

### Rewrite-Only
Use when the user wants the improved version fast.
Keep diagnosis brief and lead with the rewrite.

### Critique + Rewrite
Default mode when the user wants both diagnosis and improvement.

## Style Rules for Your Response

- Lead with the diagnosis, not a lecture
- Prefer direct language over editorial jargon
- Quote exact weak phrases when useful
- Do not congratulate mediocre text
- If the draft is already clean, say so and make only light edits
- If the draft has factual problems, flag them separately from slop
- Be concise, but do not hide the main judgment

## Follow-Up Actions to Offer

After the review, offer appropriate next steps:
- rewrite the text in a different voice
- shorten it further for executive use
- expand it for documentation completeness
- convert it into bullets, memo, README, or PRD format
- apply the same review pass to related files
- turn repeated advice into a reusable pattern for `CLAUDE.md` or another skill

## Integration with Other lastmilefirst Components

- **`/run-review-docs`**: Use when the problem is document set health, duplication, or missing docs
- **`/run-review-project`**: Use when the problem spans docs and work artifacts
- **`/run-review-claude`**: Use when the problem is context hierarchy or placement
- **`Task: consult-ripley ...`**: Use Ripley as a public expert agent for focused editorial consultation
- **`/run-consult-expert ripley ...`**: Interactive routed consultation
- **`/run-search-wisdom`** / **`/run-add-wisdom`**: Capture or retrieve durable writing patterns once they stabilize

## Notes

- Non-destructive by default: critique first unless the user explicitly asks for rewrite-only
- Best for targeted artifacts, not entire repos at once
- Especially useful after AI drafting and before final delivery
- The goal is not just brevity; it is earned language
