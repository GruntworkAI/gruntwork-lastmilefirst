# review-voice tests

Hand-run tests for a prose skill. There is no harness yet; each test is a fresh agent that reads
`../SKILL.md`, the house rules named below, and the fixture, runs the critique pass, and returns
the report. The person running the test compares the report to the expectations here. Automating
this through `claude plugin eval` is a later unit.

All fixtures are reconstructed from misses observed in live use. They name roles, not people, and
no client or engagement. Keep it that way.

**House rules for every test:** sections 1 through 5 of `../voice-sheet-example.md` stand in for
the author's standing rules. Section 6 (rulings) is not loaded, so the session-vocabulary tell has
to be found by extraction, not by a rule. Test 3 adds its own engagement voice sheet.

## Test 1: the dirty fixtures produce every expected finding

Review `fixtures/dirty-arc-summary.md` and `fixtures/dirty-session-outline.md` together, as two
artifacts from one session. Expected findings, and the rule that must produce each:

| Finding | Where | Produced by |
|---|---|---|
| Comma-afterthought headings | arc summary: "The Idea, In Your Terms," "Their Vision, Stated as the Premise," "The Operating Model, Proposed"; outline: "The Problem, Restated," "The Cadence, Sketched" | house rule, construction sweep with headings pass |
| "installs what the idea needs," "the machinery of getting there" | arc summary | house rule, metaphor family |
| "load-bearing artifact" | outline | house rule, retired phrase, figurative |
| "binding constraint" | three times in the arc summary, twice in the outline | session vocabulary (#11), cross-document form |
| Evocative headings across the document | arc summary: "The Starting Point," "What Leadership Owns Across the Series," "Where This Leaves Us" | heading register (#12), variance |
| "Three sessions, sequenced; each produces the prerequisites for the next." | arc summary, line under the title | obligation check, tagline fragment |
| "Each assigned to a specific person." | arc summary, Operating Model | obligation check, unfulfilled specificity |
| Third-person references to the named readers ("Leadership makes the call," "What Leadership Owns," "Leadership decides") | both documents, addressed to the CEO and Head of Product | obligation check, audience address |

Expected verdict: **Rework** for the arc summary (heading register is a texture finding), **Hold**
or **Rework** for the outline. A report that reaches these findings by a different route (for
example, catching "binding constraint" only as a house rule) has not passed; the "produced by"
column is part of the expectation.

## Test 2: the clean fixture produces no findings

Review `fixtures/clean-session-plan.md`. Expected: **Ship**, with nothing in the first two tiers.
Specifically, each of these must pass and may be listed under "leave it":

- "the queue," defined in the introduction and used throughout: a defined term, not session vocabulary
- "Two decisions are yours and cannot be delegated. Where the code lives is the CEO's call... Where the queue lives is the Head of Product's call": specificity cashed in the same passage
- Headings "Introduction," "Session 1," "Session 2," "Session 3," "Decisions to Discuss": functional labels
- "As you put it in the kickoff, ship the boring version first": a callback to the readers' own words, a feature
- Direct address throughout ("You asked," "yours"): correct for the named readers
- A single not/but ("If it is shorter... If it is longer"): one instance, not a finding

## Test 3: a ruling revokes an exemption

Review `fixtures/ruling-accretion-round-four-draft.md` with
`fixtures/ruling-accretion-voice-sheet.md` loaded as the engagement voice sheet. Expected: "Here is
the honest list of what remains" is a first-tier finding by the engagement ruling, not exempted as
definitional or descriptive use. The report must name the layer (engagement) and must not argue
for keeping it.

## Test 4: verification catches what a rewrite missed

Treat `fixtures/verification-rewrite.md` as the rewrite of `fixtures/dirty-arc-summary.md` and run
the post-rewrite verification pass (the full method, not a search for previously flagged
instances). Expected: two leftovers. "The Budget, Revisited" is a comma-afterthought heading that
was not in the original, so a search for the original instances would miss it. "the binding
constraint" survives once in that section; alone it is under the density line, so the report must
say whether it flags it by the cross-session rule (the phrase was session vocabulary in the
previous round) or lets it pass, and why. A report that declares the rewrite clean has failed.
