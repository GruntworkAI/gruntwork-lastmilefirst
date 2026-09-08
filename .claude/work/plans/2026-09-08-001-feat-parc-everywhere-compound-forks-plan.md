# Plan: PARC everywhere, Compound as forks, rhyming lessons, and the human rung

**Status:** APPROVED 2026-09-08, building (U1 started)
**Created:** 2026-09-08
**Type:** feature (parc, strict-parc, add-wisdom, add-knowledge, overwatch) + docs propagation (stack-wisdom, CLAUDE.md, app settings)
**Version:** v1.3 (2026-09-08). Open question 3 settled: no separate escape hatch for the Compound close. Two clarifications do that work: the close has a one-line cost ceiling when nothing was found, and it runs once per cycle (a unit of work that produced an artifact or a decision), not once per message. All three questions are now settled and the plan is approved.

v1.2 (2026-09-08). Open question 2 settled the other way: spaced repetition moves from session start to the Compound close, as recall rather than re-reading. The startup archive line is dropped. Compound closes on three questions in a fixed order, applied lessons get a date on the entry, and the stop hook nudges once per session when a cycle closed without a Compound step.

v1.1 (2026-09-08). Open question 1 settled: the Overwatch warning counts sessions that ran a closing skill, not sessions with edits. Adds U8, the weekly transcript review, after confirming Claude Code sessions are local JSONL transcripts (77 in the last seven days, about 90 MB) and that claude.ai and Desktop sessions are not.

v1.0 (2026-09-08). First draft from the discussion of 2026-09-08.

## Problem

Two process vocabularies describe the same thing at different scales. PARC (Plan, Allocate,
Review, Compound) is the plugin's workflow for a unit of work. DPV (Discovery, Production,
Verification) is the per-exchange rule set in `~/Code/CLAUDE.md` and the Claude app settings.
Discovery is the first move of Plan. Production is Allocate with the job handed to yourself.
Verification is Review entered directly. DPV is PARC minus the C, and the C is the part that
compounds. Two names for one method is a duplication, and the duplicated copy is the one
missing the step that matters most.

PARC's Compound phase has the right triggers and two holes. It never asks whether the work
produced a skill or a project, which are the two destinations that compound hardest. And every
destination it offers is the AI's memory. Nothing in it compounds the human. Every's "To Read,
Or Not to Read the Code" (2026) names the failure: the system keeps getting more capable while
the person's ability to judge it decays, unless something forces the learning. Its four
practices (revisit merged code, ask for the mechanics, recover design rationale, quiz yourself)
are all things a Compound step could do and does not.

Third, wisdom is written once and never resurfaced. A lesson that recurs is a procedure that never
got written down, and nothing today notices the recurrence.

## Decisions taken (Fish, 2026-09-08)

1. **DPV is retired. PARC is the one name**, in the skill, in CLAUDE.md, and in the app
   settings. The settings carry a copy of the rules, the same pattern as Voice.
2. **Compound destinations are forks, not rungs.** The routing question is what kind of thing
   was learned. Magnitude decides only whether to capture at all. Operative versus project
   depends on the shape of the problem, never on escalation.
3. **Rhyming lessons.** At Compound time, look for a prior lesson this one rhymes with. A rhyme
   is the promotion signal. Spaced repetition applies to the human too: old lessons get
   resurfaced.
4. **ce-explain is leveraged, not required.** The human rung is a contract with a native
   lightweight fallback. ce-explain is preferred where installed, for high cycles and weekly
   recaps.

## Assumptions

Defaults the units follow unless overridden.

- Compound stays inside the PARC skill and its checklist. No new router command. Revisit if the
  checklist proves too easy to skip.
- Overwatch nagging on zero compound actions is welcome. Threshold below is a starting guess.
- No archived lesson at session start. Recall happens at close (see The Compound close).
- The CLAUDE.md section is titled `## PARC` and replaces `## The DPV Flow` in place.
- Plugin version bumps to 0.31.0 (minor: new behavior, nothing removed).
- The weekly review is a skill run by hand first. Scheduling it is a later step, once the cards
  format has survived a few weeks.

## Design

### The four rules DPV carried, restated as PARC

None of these is in the PARC skill today. They go in as a short section near the top, before the
phases, titled "Entry points and posture."

1. **Entry points.** A request enters at Plan. A draft, plan, or analysis handed over for
   review enters at Review directly, with no Plan or Allocate. Review of a handed artifact
   means finding what is weakest and naming it plainly. "Strong, with a few small notes" is
   usually a review that was not done.
2. **Discovery is the first move of Plan.** When the request is exploratory, Plan means
   interviewing and widening the frame before proposing. Arriving fast is the failure. In
   every case the proposal precedes the artifact: three sentences can be enough, skipping it
   cannot.
3. **The five elements are Plan's completeness test.** Role, context, task, constraints,
   success. Receiving a request, do not audit it; answer on the best reading and name the one
   missing element that changed the answer. Authoring a prompt for another model, use all five
   as a checklist. Success is the element most often missing and the one to ask for.
4. **Escape hatches.** "Quick question," "no PARC," or the equivalent drops the ceremony. The
   trivial tier in Adaptive Guidance already does this implicitly; this makes it explicit.

And the beat DPV lacked: **every cycle closes on Compound**, where a cycle is a unit of work
that produced an artifact or a decision, whether that is code, a document, or an analysis. Once
per cycle, not once per message. When nothing was applied, nothing rhymes, and nothing is new,
the close is one line ("Compound: nothing applied, no rhymes, nothing new"), not a checklist.
The ceremony scales with what was found. There is no separate hatch for the close: "no PARC"
and the trivial tier already cover the cases where it is wrong, and a one-word skip would get
used exactly when the close would have caught something.

### Compound as forks

Replace the Compound Triggers table and the Compound Checklist with a routing question and a
fork table. "What kind of thing did we learn?"

| Learned | Home | Tool |
|---|---|---|
| A fact about how something works or is configured | stack-knowledge | `/run-add-knowledge` |
| A lesson, pattern, or gotcha that generalizes | stack-wisdom | `/run-add-wisdom` |
| A gotcha bound to one repo | that project's CLAUDE.md gotchas section | edit |
| A repeatable procedure | a skill | new or extended SKILL.md |
| Something Claude must know every session | context (CLAUDE.md at the right level) | Shannon decides the level |
| Judgment in a domain, across many problems | an operative | `/run-create-operative` |
| A line of work with its own roadmap | a project | `/run-organize-project` |
| A repo learning in the ce-compound shape | `docs/solutions/` | `ce-compound` (where installed) |

Two forks need a test because they are judgment calls rather than type matches.

**Skill or context.** Context if Claude needs to know it every session (a rule, a constraint, a
fact about the environment). Skill if Claude needs to do it on demand (a procedure with steps,
inputs, and an output). A thing that is both gets a one-line pointer in context and the
procedure in a skill.

**Operative or project.** An operative encodes judgment: how to think about a domain, applied
across many problems. A project encodes work: a roadmap, a repo, deliverables. The work may
later produce the operative; the operative never substitutes for the work.

Magnitude gates capture, not destination. Trivial: skip. Everything else: ask the routing
question, and "nothing" is an acceptable answer that has to be said out loud.

### Rhyming lessons

Before any Compound write, run the rhyme check. Search wisdom and knowledge for a prior entry on
the same problem, mechanism, or trap. Three outcomes:

- **No rhyme.** Write the entry. First occurrence.
- **One rhyme.** Do not write a second entry. This is the promotion signal: a lesson that
  recurred is a procedure or a rule that never got written down. Route to the skill-or-context fork.
  Update the original entry with a `rhymes_with:` line pointing at the new occurrence, and a
  `promoted_to:` line once the skill or rule exists.
- **Rhyme with an entry already promoted.** The promotion did not hold. That is the finding.
  Fix the skill or the rule rather than adding a third copy.

This is the same escalation the debugging circuit breaker already uses (same error seen twice
escalates), applied to learning instead of debugging.

### The Compound close

Spaced repetition is recall, not re-reading. A lesson shown at startup is passive; a lesson
retrieved at close, against the work just done, is what sticks. So Compound opens with three
questions, in this order, before the fork table:

1. **Did we apply an old lesson?** Search wisdom and knowledge with the session as the query
   (project, files touched, prompts, skills used) and surface the matches. Fish confirms which
   were used. Each confirmation writes `last_applied:` with the date on the entry. That date is
   the spaced-repetition ledger: applied last week needs nothing, never applied in six months is
   forgotten or dead, and the weekly review (U8) decides which.
2. **Does anything rhyme?** The same search, scored against what was learned rather than what
   was done. A hit is the promotion signal above.
3. **Is there anything new to compound?** The fork table, with "nothing" said out loud.

The order is deliberate. Asking what is new first produces a lesson that already exists. Asking
what was applied first primes the search, and the rhyme question catches the duplicate before it
is written.

### The human rung

A contract with two implementations. The contract is the article's four practices reduced to
what fits at the end of a cycle:

1. Walk the mechanics of what was built: where it starts, what happens next, where the data
   goes.
2. Recover why one safeguard or design choice exists.
3. Predict before seeing: a short quiz taken before the explanation, so the gap between the
   guess and the mechanism is visible.

**Preferred implementation:** ce-explain in diff mode with "Quiz me," which already does all
three with a prediction protocol and a durable artifact. Recap mode covers the weekly review
("what happened this week?"). Use it for HIGH cycles and for the weekly recap.

**Native fallback:** three questions in chat, no artifact, no run directory. Claude asks the
prediction question first, then walks the mechanics, then names one design rationale. Use it
when ce-explain is not installed, and by default for MODERATE cycles, where ce-explain's
ceremony (run directory, destination menu, publishing gate) is more than the moment warrants.

Detection: ce-explain is present when it appears in the session's available skills. Do not
probe the filesystem for it.

Two prompts from the article go in the checklist as questions, not mechanisms: "what is the
measurable learning goal for this cycle?" and "is this a task I have been routing around for
years, and should I do it by hand once?"

### Enforcement

- **PARC checklist and Adaptive Guidance.** Compound rows per tier: LOW runs the rhyme check
  only; MODERATE runs forks, rhyme check, and the native human rung; HIGH runs forks, rhyme
  check, and ce-explain where present.
- **strict-parc final gate** requires the fork question answered (including "nothing"), the
  rhyme check run, and the human rung answered, before completion.
- **Overwatch compound counter.** Count invocations of add-wisdom, add-knowledge,
  create-operative, ce-compound, and ce-explain in the existing invocations log, and print
  "N compound actions this week" beside the skill count. WARNING when the week has 5 or more
  sessions that ran a closing skill (a review skill, a PR skill, or strict-parc, from the same
  log) and zero compound actions. Closing skills count cycles; edit sessions would count
  keystrokes. A floor of zero is unarguable where a ratio would fire on the first week of a
  new project. Decided 2026-09-08; tune the 5 after a month.

## Units

### U1. PARC skill

`skills/parc/SKILL.md`. Add "Entry points and posture." Rewrite Compound per the design: fork
table, the two tests, rhyme check, human rung with both implementations, the two article
prompts. Update Adaptive Guidance rows and the PARC State Tracking example. Keep everything else.
Acceptance: the four DPV rules are present and cite nothing named DPV; a reader can route any
learning through the fork table without a judgment call except the two named tests.

### U2. strict-parc

`skills/strict-parc/SKILL.md`. Final gate gains three required items. Tracker template gains a
Compound section with fork, rhyme, and human fields. Acceptance: the gate cannot be passed with
the Compound section empty.

### U3. add-wisdom and add-knowledge

Both SKILL.md files gain a "Rhyme check first" step that runs the matching search skill before
writing, with the three outcomes. This is the guard for direct invocation; the Compound close
runs the same search earlier. Wisdom and knowledge entries gain optional `rhymes_with:`,
`promoted_to:`, and `last_applied:` frontmatter, and search-wisdom learns to filter and sort on
`last_applied`. Acceptance: a planted duplicate is caught and the skill proposes promotion instead
of a second entry.

### U4. Overwatch

`hooks/scripts/session_start.py`, `stop_hook.py`, and `overwatch.py`. Compound counter with the
WARNING rule at session start. In the stop hook, once per session: when the invocations log
shows a closing skill this session and no compound skill, print the three Compound-close
questions as a one-line nudge. A state flag keeps it to one nudge per session, since the stop
hook fires at every turn end. Acceptance: a fresh session prints the counter; a week of closing
skills with no compound actions produces the WARNING; a session that runs a review skill and
then stops gets the nudge exactly once.

### U5. Rename propagation

In stack-wisdom: `~/Code/CLAUDE.md` `## The DPV Flow` becomes `## PARC`, carrying the four rules
and the Compound close, and pointing at the skill for the phases. App settings bump to v2.6 with
the same replacement (a paste). `agent-voice-guide` bumps to v1.5: the DPV section becomes a
PARC section and the "where this is live" note is rewritten, since the rules are now in
CLAUDE.md. `voice/README.md` updates. Raw files and the applied-proposal record keep the old
name as history. Acceptance: `grep -rn DPV` across CLAUDE.md, the settings, and the two guides
returns only the delta notes and raw files.

### U6. Plugin docs and release

Plugin README PARC section and get-started mention the entry points and the human rung. Version
trio to 0.31.0, CHANGELOG entry, release tag after merge. Acceptance: per the repo CLAUDE.md
release checklist.

### U8. Weekly transcript review

Claude Code writes every session to `~/.claude/projects/<working-dir-slug>/<session>.jsonl`,
with timestamp, `cwd`, `gitBranch`, `sessionId`, and the full message stream. That is the
material for a weekly look at what was learned and repeated, which is where rhymes live and
which neither git nor the invocations log can show.

Two limits. Volume: a week is about 90 MB, mostly tool output and file snapshots, so nothing
reads transcripts directly. Scope: only Claude Code writes local transcripts. claude.ai and
Desktop sessions are not reachable, so the Cowork editing sessions stay invisible and the human
carries those lessons across (the Ardeo memo is the worked example).

Two parts.

**Extraction script** in the plugin (`skills/review-week/scripts/`), local only. For each
transcript touched in the window: keep user prompts and assistant prose, drop tool results,
snapshots, and task notifications. Reduce each session to a card: first prompt, project, branch,
skills invoked, commits made, and any lesson stated in prose. Write the cards to one local file
under `~/.claude/tmp/`. Never write cards into a repo; transcripts include client work.

**`review-week` skill** that reads the cards and returns: the week in one paragraph, rhymes
across sessions (the same problem, trap, or lesson appearing in more than one card), stuck
points (sessions with the circuit-breaker shape), and a proposed compound action for each rhyme
routed through the fork table. Run by hand on Mondays; a scheduled routine can call it later.

The extraction also serves Overwatch's counter, so U4 and U8 share the parsing code.

Acceptance: on last week's transcripts, the cards file is under 200 KB, the skill names at least
one rhyme that is real on inspection, and no card contains a tool result.

### U7. Verification

Run one MODERATE cycle end to end on a real task and confirm Compound asks the fork question,
runs the rhyme check, and runs the native human rung. Plant a duplicate wisdom entry and confirm
U3 catches it. Start a session and confirm the Overwatch lines. Run ce-explain in diff mode on
the U1 diff itself, with Quiz me, as the first real use of the human rung.

## Sequence

1. U1 first, on a branch. Everything else depends on the fork table and the rung contract.
2. U2, U3, U4 in parallel once U1's wording settles.
3. U5 in stack-wisdom, direct to main, once U1 is merged so CLAUDE.md points at a skill that
   exists in that shape.
4. U6, merge, release, reload.
5. U7.

## Out of scope

- A `/run-compound` router command. Revisit if the checklist is skipped in practice.
- Changes to ce-compound or ce-explain. They are third-party and used as-is.
- Friday's practices file. It carries its own copy of the five elements by design.
- Re-running the review-voice live critique. Separate open item.

## Open questions

1. Settled 2026-09-08. See Enforcement.
2. Settled 2026-09-08. Moved to the Compound close; see The Compound close.
3. Settled 2026-09-08: no separate hatch. One-line ceiling, once per cycle.
