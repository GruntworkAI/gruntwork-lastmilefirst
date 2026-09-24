---
title: review-voice round three, living house rules, and one verdict across signal and voice
version: 1.3
date: 2026-09-22
status: proposed
type: feat
component: plugins/lastmilefirst/skills/{review-voice,review-signal}, agents/consult-ripley.md
target_version: 0.33.0
refs:
  - ~/Code/drafts/review_voice_improvement_brief_v0.3.md (the work order this plan reconciles)
  - .claude/work/plans/2026-07-26-001-feat-review-voice-humanize-skill-plan.md (the original design)
  - ~/Code/gruntwork/gruntwork-stack-wisdom/voice/fish-voice-guide-v1.7.md (house-rule provenance)
  - ~/Code/gruntwork/gruntwork-stack-wisdom/voice/agent-voice-guide-v1.5.md (the "whose voice" open question)
---

# review-voice round three, living house rules, and one verdict across signal and voice (v1.4)

> **v1.4 (2026-09-24).** Built on `feat/review-voice-round-three`. All four hand-run tests
> passed on fresh agents reading only the skill; two things they surfaced were folded in (role
> names splitting address between named readers pass; instances of one rule share a findings
> row). Net growth of `review-voice/SKILL.md` is +101 lines against a budget of about 50; the
> growth is method (three obligation checks, the layered house rules, the verdict derivation),
> not padding, and is reported rather than compressed. Release 0.33.0 pending merge and tag.
>
> **v1.3 (2026-09-23).** Verdict verb reaffirmed as ship, with the gloss carrying the natural
> verb for the artifact (publish, send, merge). A standing sanitization rule for public-repo
> content is added to U8, because the plan had stated it twice at unit level and nowhere as a
> rule. Appendix A provenance no longer names our own project where the reader does not need it.
>
> **v1.2 (2026-09-23).** The three open questions are decided: verdict words are ship / hold /
> rework; the engagement file is a *voice sheet*, not a style sheet (it is about voice, and
> "style sheet" already means something else), at `.claude/work/voice-sheet.md`; and the reviewer
> proposes a ruling, the author confirms, then it writes. Renames applied throughout. Open
> Questions section replaced by the record of those decisions.
>
> **v1.1 (2026-09-22).** Adds U2b: a shipped example house-rules file that doubles as the
> template for an engagement voice sheet, with the candidate rule set in Appendix A for review.
> The in-skill "example list, for shape only" becomes a pointer to that file, which recovers
> lines. Line budget updated. Nothing else changed.
>
> **v1.0 (2026-09-22).** First version. Reconciles the v0.3 improvement brief (written from
> three rounds of live use on a consulting engagement) against the skill as it stands at 0.31.0,
> and adds a second problem the brief did not cover: the scoring that `review-signal`,
> `review-voice`, and Ripley's dual review report is confusing, and the three do not agree with
> each other. Target 0.33.0, because 0.32.0 is claimed by the review-org plan of 2026-09-21.

## Problem

### P1. Three rounds of live use found ten things the skill passed

A session ran `review-voice` on consulting deliverables across three author-review rounds. Each
round the skill caught real problems and the author then found tells it had let through. The
brief lists them; grouped by what the skill lacked:

- **No way to see the session's own vocabulary.** "Binding constraint" recurred across two
  documents and the drafting conversation. It is on no list, and no fixed list could hold it,
  because the phrase is chosen fresh each session.
- **House rules checked as strings, not patterns.** The author has banned the comma-afterthought
  construction ("The masthead, confirmed."). The skill knew two instances and grepped for those.
  Four headings with the same shape passed. The same failure let "installs" through: it is the
  retired "load-bearing" move wearing a different metaphor.
- **No structural checks on the places tells hide.** Evocative section headings where a working
  document wants plain labels. A verbless tagline under the title. A phrase that promises
  precision ("a specific person") the text never supplies.
- **No audience check.** A document written for two named readers talked about them in the third
  person throughout.
- **The reviewer re-litigated the author.** It exempted "the honest list" as definitional use
  twice after the author had cut the word family. An author's edit is a ruling, and the skill has
  no place to keep one.
- **Verification confirmed a subset.** After the rewrite, the reviewer grepped for the flagged
  instances instead of re-running the method, and declared a false clean.

Round three also produced a positive result worth keeping: the final pass on a clean document
behaved correctly on every count (defined terms exempt, cashed specificity passed, client-meeting
callbacks read as features). A clean fixture is as important as the dirty ones.

### P2. The brief's item 2 rebuilds a section that already exists, and three new checks break the scoring model

The brief proposes a "style sheet" input. The skill has had a House Rules section since 0.30.0
with a source order, a phrase-versus-construction distinction, and single-instance scoring. What
is new in the brief is four extensions to that section, not a second mechanism. Two names for one
thing would be a second source of truth, so the name stays "house rules."

Three of the brief's new checks (unfulfilled specificity, tagline fragments, audience address) are
neither fingerprints (density, one instance is never a finding) nor house rules (author-supplied,
one instance is a finding). They ship with the skill and a single instance counts. Dropped into
the Tier 2 table as written, they contradict the "one instance is nothing" guard on the same page.
The skill needs a third kind of rule. The brief's keep-the-structure constraint did not foresee
this, and the brief asked to be told rather than have it chosen silently. This plan is that.

### P3. The scoring is confusing, and Ripley reports two of them

Today:

| Where | Headline | Direction | Denominator |
|---|---|---|---|
| `review-signal` | "Signal / Slop Score X/16" | higher is worse | 8 categories × 0..2 |
| `review-voice` | "AI-Tell Score X/N (de-duped)" | higher is worse | N is never defined |
| `consult-ripley` dual mode | "a combined verdict, both scores" | | two numbers, no combination rule |

The name "Signal / Slop Score" reads as a signal score, where high would be good, and the rubric
means the opposite. The voice denominator changes with de-duplication, so the same draft can
score 4/9 or 3/7 depending on how the reviewer collapsed the table. House rules sit beside the
score as a bare count. Ripley is told never to return two stapled reports and then told to return
both scores. And none of the numbers tell the writer the one thing they need: whether this is a
patch or a rewrite.

The review family already has a verdict vocabulary that works. `review-deliverable` returns
urgency-tiered findings and a ship / hold / rework verdict. The prose lenses should use the same
one, so a user learns it once.

### P4. The work order has stale facts

The brief names the repo as gruntwork-marketplace, the skill path without the `plugins/lastmilefirst/`
prefix, a wrapper skill that is actually the command file `commands/run-review-voice.md`, a
changelog that does not exist, and a shell the skill never claims. Recorded here so the build does
not inherit them.

## How house rules work, and where they live

This section is the explanation the skill should be able to point at. It describes the design
after this plan; the differences from 0.31.0 are marked.

**What a house rule is.** An author's hard rule, where one instance is a finding. Usually a
retired phrase banned in figurative use with a literal exception ("load-bearing" as a metaphor,
fine for a wall). Sometimes a construction ("X has a name," the comma-afterthought heading).
Sometimes a single-instance version of a fingerprint (a sincerity badge on a verdict). House
rules exist because some tells do their damage on the first hit, and the author has said so.
They are the one exception to the skill's density method.

**Three layers, closest wins, and a layer can only add.** *(New: the layering. 0.31.0 has the
source order but no engagement layer and no accretion.)*

1. **Standing rules (the author).** Canonical home is the author's user-level `CLAUDE.md`, in
   its `## Voice` section. For Fish that is `~/Code/CLAUDE.md`: the four retired phrases, the
   sincerity-badge rule, the negative-universal rule, and the eight moves. In Claude Code this
   file is already in context, so reading it costs nothing. On Desktop and in Cowork the same
   rules live in the app's stored preferences and writing settings, mirrored from the same
   canon. The reasoning and the dated evidence behind each rule live in stack-wisdom at
   `voice/fish-voice-guide-v1.7.md`, and the skill does not read that file; it is for arguing
   with a rule, not applying one. An agent persona's rules live in that agent's own repository.
2. **Engagement rules (the project or deliverable set).** A voice sheet for one body of work:
   rules the author has added for this engagement, and rulings made during it. Lives in the
   project at `.claude/work/voice-sheet.md` when the work is a repo, or beside the deliverables
   when it is not. Passed to the skill by path when it is not at the conventional location.
   This is the layer that accretes.
3. **Session rules (this conversation).** Rules the author states while working, and rulings
   made this round that are not yet written down. Highest precedence and shortest-lived.

A rule from a lower layer never loosens one above it. A ruling only adds a ban or revokes an
exemption. If the standing rules retire "load-bearing" and an engagement voice sheet is silent,
"load-bearing" is still retired.

**What the skill does with them.**

- *Loads before scoring*, in layer order, and says which layers it found. If it found none, it
  asks. It never applies its own example list as if it were the author's.
- *Checks as patterns, not strings.* *(New.)* From each construction rule it derives the general
  shape and sweeps for the shape. Headings get their own pass, because that is where the
  comma-afterthought hides and because headings are short and visible.
- *Treats a retired metaphor as a family.* *(New.)* Retiring "load-bearing" makes the other
  mechanical and structural metaphors doing the same work suspect ("installs a discipline," "the
  machinery of," "wired into"). The fix, per the author's own rule, is naming the claim the
  metaphor stood in for, never a fresher metaphor.
- *Records rulings.* *(New.)* When the author cuts something the reviewer exempted, the
  exemption is revoked for that word or pattern for the rest of the engagement. At the end of
  the round the reviewer proposes the ruling in one line, the author confirms, and the reviewer
  writes it into the engagement voice sheet. Where there is no file (Desktop, Cowork), it
  restates the accreted list at the end of each round so the author can paste it into
  preferences. Later rounds flag remaining and new
  instances. A defense the author has already overruled is a repeated mistake, not a judgment.
- *Reports them in their own table*, separate from fingerprints, never de-duplicated against
  them. Literal uses are noted and not counted.

**What the skill does not do.** It does not read the stack-wisdom voice guides, it does not
maintain the standing rules, and it does not promote a session ruling to a standing rule. Promotion
is the author's move, made by editing `CLAUDE.md` and adding the dated quote to the guide's
flagged-phrases table, so a rule keeps its provenance.

## Decisions

**D1. Three kinds of rule.** Fingerprints (density or variance, general, one instance is never a
finding). House rules (author-supplied, one instance is a finding). Obligation checks (general,
ship with the skill, one instance is a finding, because the text made a promise or named a reader
and then did not follow through). The "Two kinds of rule" section becomes three. The guard "One
instance is nothing, for fingerprints" keeps its qualifier and gains a pointer to the other two.

**D2. Extend House Rules; no "style sheet" input.** Item 2 of the brief lands as four extensions
to the existing section (patterns, families, sources, rulings) plus the engagement layer. The
optional path argument is called `voice-sheet`, and a file at the conventional location is picked
up without it.

**D3. The method must run without a shell.** The session-vocabulary extraction is written as
something a reviewer does by reading: list the two-to-four-word content phrases that recur, tally
them, drop the document's defined terms. A script is offered as an accelerator where Bash exists,
and the skill says so in one line. This follows from the open environment-declarations todo,
which names the prose lenses as the subset meant to run on surfaces with no filesystem.

**D4. One verdict vocabulary across signal, voice, and Ripley.** Numeric headline scores go.
Both lenses report findings in three tiers and a one-word verdict derived from them, using the
ship / hold / rework words that `review-deliverable` already uses. Details under Design. This is
the one place this plan touches `review-signal`, against the brief's constraint, because a
scoring change that touched one lens would leave Ripley reconciling two schemes. The adversarial
relationship between the lenses is untouched; only how they report.

**D5. Fixtures are reconstructed and sanitized.** The engagement documents cannot go in a public
repo. The fixtures are rebuilt from the misses in the brief with no client, person, or engagement
name in them, under the skill's own `tests/` directory, matching how `review-claude` and
`scan-secrets` keep theirs. The tests are hand-run this round. Automating them is a later unit
once `claude plugin eval` has been tried on a prose skill.

**D6. The routing note is accepted and filed, not built.** Reader-context failure (the draft leans
on the drafting conversation's private vocabulary) is a clarity defect, not a voice tell. It goes
to `review-signal` as a todo. The rewrite-side companion (explain it the way you would say it
aloud) belongs in `review-voice` and is built here.

**D7. Two outside-repo edits ride along.** The sentence in `~/Code/CLAUDE.md` claiming the eight
moves are "numbered the same way in the voice guide and the review-voice skill" is false: the
skill's tell numbers do not match the move numbers, and move 2 maps to two rows. The mapping that
is true already lives in the Fish voice guide. The sentence gets corrected, not the tables. The
Desktop-trigger question from July stays open and is not in scope.

## Design: findings and verdict

Every finding, from either lens, carries the same fields:

| Field | Values |
|---|---|
| lens | signal, voice, house |
| tier | **fix before it ships**, **fix if you are editing**, **leave it** |
| where | quote or location (heading, line under title, paragraph n) |
| what | the tell, rule, or leak, named |
| evidence | the measurement: density per ~1,000 words, the variance observation, the RENT dimensions failed, or "single instance, house rule" |
| fix | the concrete move, or "protected" |

**Tier assignment.**

- *Fix before it ships:* house-rule hits in figurative use, uncashed obligations (specificity,
  audience address, tagline fragment), a signal category the reviewer would have marked
  "obvious problem."
- *Fix if you are editing:* fingerprints past the density line, session vocabulary, heading-register
  skew, a signal category "somewhat present" with a concrete cut attached.
- *Leave it:* protected voice, literal uses, the author's own reach-words, register-appropriate
  regularity. Recorded so the rewrite does not sand them, never counted.

The signal rubric's 0 / 1 / 2 per category stays as the reviewer's private step for choosing a
tier. The "X/16" headline goes. The voice density and variance measurements stay in the evidence
column. The "X/N" headline goes.

**Verdict, derived, per lens and combined.**

- **Ship.** Nothing in the first tier, and the second tier is short and local.
- **Hold.** First-tier findings exist and every one is a local edit: a phrase swap, a heading
  rename, cashing a promise, converting to direct address. Fix them, then ship. No rewrite.
- **Rework.** The shape is the problem. Any texture finding (uniform paragraph shape, absence of
  noise, heading register skewed across the document) or any signal finding at the
  prioritization level (weak prioritization, scope and depth mismatch) forces rework, because no
  line edit reaches it.

The verdict line carries a plain gloss and the tier counts, so a round can be compared to the
last one without a denominator: `Hold: three local fixes, then ship. 3 / 5 / 4, down from 6 / 9 / 2.`

**Ripley's dual mode.** One findings list with the lens column filled, one verdict (the worse of
the two lenses), and each finding where the lenses disagreed marked as a conflict with a one-line
adjudication. The agent file's step 4 changes from "both scores" to this. The persona file does
not mention scores and is untouched.

## Units

Sequence matters for U1 and U2, which change the frame the later units write into.

### U1. Three kinds of rule

`review-voice/SKILL.md`. Rename "Two kinds of rule" and add obligation checks as the third kind
with its measure (per instance, redemption- or position-checked) and its scoring (own table,
never de-duplicated). Update the guard sentence. Add "Obligation Checks" to the Output Format
beside House Rules.

*Accept:* the skill states three kinds, each with how it is measured and how it is scored, and no
guard contradicts any of them.

### U2. House rules: layered, patterned, accreting

`review-voice/SKILL.md`, House Rules section and step 2 of How to Run. Add the three layers and
precedence, the `house-rules` path argument and conventional location, the pattern sweep with an
explicit headings pass, metaphor families, ruling accretion with propose-confirm-write and the no-file
fallback, and stored preferences as a source on surfaces with no CLAUDE.md. Keep the "example
list only" guard.

*Accept:* the section answers, in order, what a house rule is, where each layer lives, which wins,
what the reviewer does with a ruling, and what it never does. Success test 3 passes.

### U2b. A shipped example house-rules file, which is also the voice-sheet template

`review-voice/voice-sheet-example.md`, new. One file that does two jobs: it is the worked
example of what a robust house-rules set looks like, with every kind of rule the skill can check
represented at least twice, and it is the template a user copies to start an engagement style
sheet at the conventional location. Sections by kind of rule (retired phrases, retired
constructions, single-instance fingerprints, metaphor families, register rules, rulings), each
entry carrying the rule, its scope or literal exception, the fix move, and when and where it was
flagged. The header states plainly that this is one author's canon shipped for shape, that the
user copies and replaces it, and that the skill never applies it as the author's own.

`SKILL.md` keeps a two-line pointer in House Rules in place of the current four-item example
list, and step 2 of How to Run says when the file is used: as the template when an engagement
sheet is created, and as a starter only when the user asks for one. Never as a default.

Provenance is kept as a date and a context, not a quote. The quotes belong to the voice guide in
stack-wisdom, which is the private home for the reasoning.

*Accept:* the file exists with every rule in Appendix A; each section has at least two entries or
says why it has one; the skill's inline example list is gone and the pointer is in its place; a
user with no CLAUDE.md can copy the file, delete what is not theirs, and be running house rules
in one step.

### U3. Session-vocabulary tell

`review-voice/SKILL.md`. Tier 2 row 11, frequency, observed. Extraction step in Method written
for a reader first, script as accelerator in one line. Cross-document rule: a content phrase in
two or more artifacts from one session is a candidate on sight. Defined terms of art exempt.
Author's reach-words exempt by the existing guard.

*Accept:* success test 1 flags "binding constraint" by the cross-document rule; test 2 passes the
clean fixture's defined terms.

### U4. Structural tells and the audience check

`review-voice/SKILL.md`. Heading register as Tier 2 row 12, variance, working documents only,
essays and marketing exempt by the register guard. Tagline fragments, unfulfilled specificity, and
audience address as the three obligation checks, each with where to look and what redeems it.
Audience address exempts broad or unnamed readerships and notes a deliberate mix.

*Accept:* success test 1 flags the evocative headings, the under-title tagline, the uncashed
"specific person," and the third-person references to the named readers; test 2 passes the cashed
specificity phrase and the functional headings.

### U5. Verification and the explanation register

`review-voice/SKILL.md`, Method and the rewrite mode. After a rewrite, verification re-runs the
full pass: extraction, house-rule patterns, obligation checks, fingerprints. State the failure
mode in one sentence. Add one sentence of rewrite method: for a compressed or reader-context
failure, write the passage the way you would answer "what does this mean?" aloud, in the reader's
vocabulary, rather than decompressing the original in place.

*Accept:* success test 4 catches the planted leftover.

### U6. One verdict across the lenses

`review-voice/SKILL.md` (Method scoring, Output Format, Style Rules), `review-signal/SKILL.md`
(Step 4, Default Output Format, Critique mode), `agents/consult-ripley.md` (Dual-Review step 4).
Replace the two numeric headlines with the tiered findings table and the derived verdict from
Design. Keep signal's 0 / 1 / 2 as the private tiering step. Keep voice's density and variance as
evidence. Ripley returns one list, one verdict, conflicts marked.

*Accept:* the three files describe the same tiers, the same three verdict words, and the same
derivation. A reader can say from the verdict line alone whether to patch or rewrite. Neither
skill prints a fraction.

### U7. Fixtures and hand-run tests

`review-voice/tests/fixtures/`: a dirty arc summary and a dirty session outline (reconstructed,
carrying all eight misses between them, cross-document "binding constraint" included), a clean
session plan (defined terms repeated, cashed specificity, functional headings, one callback to a
meeting phrase), a ruling-accretion case (voice sheet noting the author cut "honest" as a list
descriptor, plus a draft with a planted new instance), and a verification case (a rewrite with one
planted leftover). A `tests/README.md` lists the four tests, the expected findings per fixture,
and the expected verdict. No client, person, or engagement name anywhere in the directory.

*Accept:* all four tests run by hand against the updated skill and match expectations. The
results are reported in the PR, test by test, with any miss stated as a miss.

### U8. Ride-alongs

Todo `.claude/work/todos/feature-review-signal-reader-context-test.md` carrying the routing note
verbatim. Correct the numbering sentence in `~/Code/CLAUDE.md` (outside this repo; commit there
separately). Update the memory entry for `review-voice` with the new shape.

A standing sanitization rule, because D5 and U7 each state it and nothing above them does.
**Landed 2026-09-24**, ahead of the build: in this repo's `CLAUDE.md` as "Public-Repo Content
Rule" (`e9e7fb6`, main) and in `~/Code/CLAUDE.md` Voice section, both verbatim:

> Nothing committed to a public repo names a client, an engagement, or a private person. Skill
> text, example files, fixtures, tests, commit messages, PRs, and release notes reconstruct their
> examples. Provenance is a date and a generic context ("a README review," "an engagement's first
> round"), never a name or a quote. Our own project names are allowed where the reader needs them
> and dropped where they do not.

*Accept:* the todo exists; the false sentence is gone; the rule is in both files; memory reflects
0.33.0 and the rule.

### U9. Release 0.33.0

Bump `plugins/lastmilefirst/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`.
README: touch the `review-voice`, `review-signal`, and Ripley lines only if their descriptions
changed. PR against `main` with the four test results in the body. After merge:
`gh release create v0.33.0 --target main --latest`, because Desktop and consumer installs resolve
from the release, not the branch.

## Line budget

The brief allowed about 65 net lines in `review-voice/SKILL.md`. Folding item 2 into the existing
House Rules section, replacing the scoring headline rather than adding to it, and moving the
example list out to its own file should bring the net under 50. The example file itself is not in
the budget: it loads only when a sheet is created or a starter is asked for. `review-signal/SKILL.md` should change size by close to zero. The plan is a budget,
not a target; if a unit needs more, say so in the PR rather than compressing the method into
something a reviewer cannot follow.

## Out of scope

- Reader-context test in `review-signal` (D6; filed as a todo).
- The "whose voice" profile loading proposed in the agent voice guide. Same file, different
  problem, and it has its own open question about coupling a public plugin to a private repo.
- Automating the fixtures through `claude plugin eval`.
- The Desktop auto-trigger test from July.

## Decisions taken 2026-09-23 (formerly Open questions)

1. **Verdict words: ship / hold / rework.** Reused from `review-deliverable` so the review family
   has one vocabulary. Reconsidered 2026-09-23 against "publish" and kept: publish fits an essay
   and not a memo, a PR body, or a commit message, and ship already means "can go out as is" in
   this workspace. The verdict word is the category; the gloss names the natural verb for the
   artifact ("Ship: publish as is," "Ship: send as is"), so the writer reads the right word on
   the line that matters.
2. **The engagement file is a voice sheet** at `.claude/work/voice-sheet.md`, passed by
   `voice-sheet <path>` when it lives elsewhere. Not "style sheet": the file is about voice, and
   style sheet already has a meaning in publishing and in CSS that a user may be carrying.
3. **Write-back is propose, confirm, write.** At the end of a round the reviewer lists the
   rulings it inferred from the author's edits, one line each; the author confirms or strikes;
   the reviewer appends the confirmed lines to the voice sheet. The reviewer never writes a
   ruling the author has not seen. Where there is no file, the confirmed list is restated for
   the author to paste.

## Appendix A. Candidate example house-rules set (for U2b)

Drawn from the author's standing canon (`~/Code/CLAUDE.md` Voice section, the voice guide's
flagged-phrases table) and from the engagement rulings in the v0.3 brief. Every kind of rule the
skill can check is represented. Dates are when the rule was set; contexts say where. Quotes are
deliberately left in the voice guide.

### A1. Retired phrases (banned in figurative use; literal use passes and is noted)

| Phrase | Literal exception | Fix | Since | Context |
|---|---|---|---|---|
| load-bearing | a wall, a beam | name the actual dependency ("changing one changes the product") | 2026-08-15 | README review; had appeared twice in one session |
| the spine, architectural spine | anatomy, a book binding | state the sequence the metaphor stood for | 2026-08-31 | CLAUDE.md review |
| earns its keep, earns its place | rent actually paid | say what the thing does that justifies it | 2026-09 | a project style-sheet canonicalization memo; promoted from fingerprint 3b |

### A2. Retired constructions (the shape is banned, not the words)

| Construction | Shape to sweep for | Fix | Since | Context |
|---|---|---|---|---|
| "X has a name" in any form, including "names a seat" | a clause that announces a coinage instead of making the claim | make the claim; drop the announcement | 2026-09 | a project style-sheet canonicalization memo |
| Comma-afterthought ("The masthead, confirmed." "Three terms, plainly." "The idea, in your terms") | noun phrase, comma, trailing modifier; headings especially | a working sentence or a plain functional label | 2026-09-21 | engagement round one; four headings in one document |

### A3. Single-instance fingerprints (a density tell the author has made absolute)

| Rule | Scope | Fix | Since | Context |
|---|---|---|---|---|
| No sincerity badges on an assessment: honestly, genuinely, truly, really, candidly, frankly, to be frank, in all seriousness, for real; no labels of the kind ("Honest verdict:", "genuinely good", "the real answer is") | assessments, verdicts, critiques only; the factual-qualifier use ("genuinely enumerable") passes | delete; if the point is strong, say why | 2026-09-01 | fingerprint 3b at full sharpness |
| No negative-universal setups as a framing move ("nobody does X," "no one ever asks") | zero by default; at most one literal idiomatic instance per document | recast with the specific actor who does not, say what happens instead, or name the absence | 2026-09 | essay-series edit arc; seven sites in one draft |

### A4. Metaphor families (suspect once a member is retired)

| Family | Members seen | Fix | Since | Context |
|---|---|---|---|---|
| Mechanical and structural | installs (a discipline), the machinery of, wired into, scaffolding, plumbing, bolt on, undergird | name the claim the metaphor stood in for; never a fresher metaphor | 2026-09-21 | "installs" passed review while "load-bearing" was retired; same move |

### A5. Register rules (preferences with a threshold; one instance is a finding)

| Rule | Threshold | Fix | Since | Context |
|---|---|---|---|---|
| Em dashes ranked: parenthetical for an aside, two sentences for a pivot or contrast, a dash only when neither works | a dash bridging a contrast is a finding; a dash for an aside is a note | parenthetical, or split the sentence | 2026-09-04 | relaxed from a ban to "very sparingly" |
| American spelling and punctuation; ISO dates; 24-hour times | any instance | mechanical | standing | CLAUDE.md Voice |
| Open with the answer; no preamble, no restating the question | first paragraph of any document or reply | lead with the conclusion | standing | CLAUDE.md Voice |

### A6. Rulings (the engagement layer; the format the reviewer appends to after the author confirms)

| Date | Ruling | Effect | Context |
|---|---|---|---|
| 2026-09-22 | "honest" as a list descriptor ("the honest list") | exemption as definitional use revoked; every instance flagged for the rest of the engagement | author cut all instances in round three after the reviewer defended two |
| 2026-09-21 | "binding constraint" | session vocabulary; any recurrence in this engagement is a finding | recurred across two documents and the drafting conversation |

### What is deliberately not here

*keystone* stays a fingerprint 3b pet metaphor, measured by density, because the author has not
retired it. The tagline fragment under a title is a general obligation check now, not a house
rule. Neither should be promoted by the example file; promotion is the author's move.
