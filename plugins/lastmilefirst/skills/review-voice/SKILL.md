---
name: review-voice
description: Detect and fix the tells that make prose read as AI-generated, and rewrite toward an authentic human voice without flattening the author. Use when a draft sounds machine-written, when you want text to sound more human / less like AI / less like ChatGPT, or to humanize or de-slop a README, essay, memo, PRD, blog post, or AI-generated draft before publishing.
---

# Review Voice

Find the fingerprints that make writing read as machine-authored, then rewrite toward a
natural human voice (the author's own, not a generic "casual" one). This is the companion to
`review-signal`. Signal asks whether every line pays its way. Voice asks whether this reads
like a person wrote it. They are different questions, and they sometimes pull in opposite
directions.

## When to Use

- a draft is clean and correct but reads unmistakably like AI wrote it
- you want prose to sound more human, less like ChatGPT, before you publish it
- an essay, post, memo, or README needs its machine tics removed without losing its point
- you tightened something with `review-signal` and now it reads too smooth, sanded flat

## When Not to Use

- **`/run-review-signal`** when the problem is filler, repetition, or weak prioritization,
  not that it sounds like AI
- **`/run-review-docs`**, **`/run-review-project`**, or **`/run-review-claude`** for
  structure, staleness, or context placement
- The text is a **reference or spec doc** (SKILL.md, API table, config). Regularity is
  correct there; see Register-Match below

## The one idea worth holding

The durable signal is **homogenization**: suspiciously low variance. Across the research
(DetectGPT, Kobak, Sourati, Muñoz-Ortiz), the marker that survives as models improve is not
any word or phrase. It is that machine prose has less variance and less diversity than human
prose. Uniform sentence lengths. Every paragraph the same shape. A small set of reliable words
reused. No friction. And here is the trap: `review-signal`'s job is to remove variance. It cuts
whatever does not pull weight, and that includes the human texture that is not strictly
necessary. So voice review is partly adversarial to signal review. Sometimes it protects, or
restores, the very roughness signal wanted gone.

## Three kinds of rule

This skill applies three kinds of rule, and they are measured differently.

**Fingerprints** are patterns. They are measured as a rate or a variance across the whole text,
and a single occurrence is never a finding. The taxonomy below is general and ships with the
skill.

**House rules** are the author's own hard rules, supplied by the author, and a single instance
is a finding. They exist because some tells do their damage on the first hit. The skill ships an
example file only; the real list comes from the author. See House Rules below.

**Obligation checks** are general, ship with the skill, and a single instance is a finding,
because the text made a promise or named a reader and then did not follow through. There are
three, listed after the Tier 2 table. They are checked per instance, never by density, and never
de-duplicated against fingerprints.

## The Tells

Two tiers. Tier 1 is the crude stuff anyone can spot. Tier 2 is the payoff: fingerprints that
survive because the writer is good, so they are what catch already-tightened prose.

Each Tier 2 tell is tagged with how it is measured (this matters; see Method) and whether the
research backs it or it is an observed pattern. Rows tagged "author-calibrated" were extracted
by diffing one author's hand edits against machine drafts, so they are observed with a
specimen behind them rather than a general study.

### Tier 1: crude tells

| Tell | What it looks like |
|------|--------------------|
| Lexical over-representation | *delve, showcase, underscore, leverage, robust, seamless, comprehensive, crucial, pivotal* used above a human rate |
| Formatting | bold-label bullets everywhere; emoji headers; the summary bow ("In conclusion", "Ultimately"); numbered lists for non-sequential things |
| Syntactic | participial pileups ("…, ensuring…", "…, allowing…"); "not only… but also"; correlative-conjunction addiction |

### Tier 2: sophisticated fingerprints

| # | Fingerprint | Example | Measure | Evidence |
|---|-------------|---------|---------|----------|
| 1 | Not/but antithesis as the default move, repeated | "That's not misalignment. That's executing on a goal." | frequency | observed |
| 1b | In-clause balanced antithesis as the default contrast shape | "the way the network and not the cardholder knows the balance" (vs. "the network knows the balance (i.e. not the cardholder)") | frequency | observed (author-calibrated) |
| 2 | Abstract-noun momentum openers | "That distinction matters beyond this incident." | frequency | observed |
| 3 | Recycled rhetorical-work vocabulary | precisely, exactly, relentlessly, materially, arguably, worth sitting with | frequency | literature-backed |
| 3b | Pet metaphors and performed candor | *keystone, earns its keep, load-bearing, spine*; "the honest take", "to be fair" | frequency | observed |
| 4 | Excessive structural regularity | nearly every paragraph is common-take, then reframe, then payoff line | **variance** | literature-backed |
| 5 | Absence of real noise | no tangents, no mid-thought long sentence, no redundancy that is not strictly working | **variance** | literature-backed |
| 6 | Universal-quantifier inflation | "every card program", "always", "nobody has ever" above a defensible rate | frequency | observed (author-calibrated) |
| 7 | Canon-speak definite articles | "the first threshold" for a system that does not exist yet (vs. "a first threshold") | frequency | observed (author-calibrated) |
| 8 | Wit-personification of components | a component that "holds no opinions" (vs. "is just there to enforce the limits") | frequency | observed (author-calibrated) |
| 9 | Emphasis tags after the semantic landing | "declined right there" (vs. "declined.") | frequency | observed (author-calibrated) |
| 10 | Negative-universal setups as a framing move | "Nobody sets out to build a bureaucracy," "no one ever asks" opening a paragraph (vs. "the cardholder doesn't get asked," or naming the absence directly) | frequency | observed (author-calibrated) |
| 11 | Session vocabulary: the draft's own recycled phrase | "binding constraint" in two documents and the drafting conversation; a phrase no list holds because the session chose it fresh | frequency, cross-document | observed |
| 12 | Heading register: evocative where a working document wants a label | "The starting point," "What leadership owns across the series" (vs. "Introduction," "Decisions to discuss") | **variance** | observed |

Also flag, all variance-measured: LLM tricolon addiction (distinct from an author who simply
likes threes), uniform paragraph length, section and heading symmetry, consecutive paragraphs
with identical skeletons, and consecutive sections built on colon-led feature lists.

The Tier 2 tells overlap on purpose. #1 is #4 at sentence scale, #1b is #1 read at the clause,
#2 feeds #4, #9 is the payoff line of #4 seen on its own, #10 is #6 used as an opener, and #5 is the envelope around #4. One
habit (antithetical reframing) can set off three rows. The Method handles this so the score
reflects one finding, not three.

### Obligation checks

Checked per instance, at the place the obligation arises. One uncashed instance is a finding.

- **Tagline fragments.** Look at the line directly under the title and under each section
  head for a verbless kicker in apposition cadence ("Three sessions, sequenced; each produces
  the prerequisites for the next."). The location makes this cheap: check those positions, not
  the whole text. Fix is deletion or a working sentence; the content usually exists elsewhere.
- **Unfulfilled specificity.** A phrase that promises precision ("a specific person," "a
  concrete plan," "a named owner," "a clear standard") obliges the same passage to name the
  person, plan, owner, or standard. Uncashed, it is worse than vagueness, because it asserts a
  precision the author never supplied. Cashed, it passes and is not a finding.
- **Audience address.** When the document names or clearly implies its readers (a plan for two
  named principals, a memo "for the team," a letter), each third-person reference to those
  readers ("leadership decides," "the team should") is a finding. The fix is direct address
  ("your call") or a note that the mix is deliberate. Exempt broad or unnamed readerships,
  where third person is correct.

## Method: how a tell becomes a verdict

Every reliable marker in the research is a rate or a variance across the whole text, never a
single occurrence. So the skill measures fingerprints. It does not spot-flag them.

- **Extract the session vocabulary first (#11).** Before scoring, list the two-to-four-word
  content phrases that recur, with a tally. Do it by reading: skip phrases that are only
  stopwords, and skip the document's own defined terms of art (a term the draft defines and
  then uses consistently is vocabulary; "fork 4" forty times in a decision-tree spec is
  correct). Where a shell exists, a short n-gram count over the text is a fine accelerator, and
  the method is the same without one. When reviewing more than one artifact from the same
  session, any content phrase appearing in two or more of them is a candidate on sight;
  same-session repetition across documents is the strongest form of this signal.
- **Presence-tells (#1, #1b, #2, #3, #3b, #6 through #11, Tier 1 lexical):** count per ~1,000
  words. Flag when density crosses from device to fingerprint. Once is a rhetorical choice; six
  times in one piece is a tell. For 3b, learn the author's genuine reach-words first, then flag
  over-recurrence.
- **Texture-tells (#4, #5, #12, paragraph length, symmetry, identical skeletons):** measure
  variance. Low variance of sentence length and paragraph shape is the tell. You cannot count
  an absence, so you measure the flatness. Sentence-length variance is the hand-checkable
  proxy for the burstiness idea. For #12, classify each heading as a functional label or an
  evocative description; one evocative heading is a choice and a title may be evocative, but a
  document whose section headings mostly editorialize is a fingerprint. Working documents
  only (memos, summaries, briefs, specs); essays and marketing pieces are exempt by genre.
- **Obligation checks:** walk the three positions and phrase classes above. Per instance.
- **De-dup:** when entangled tells trace to one habit (#1, #1b, #2 as instances, #4 as their
  aggregate shape, #5 as the envelope), they count once, weighted. Do not let one habit triple
  the finding count.
- **House rules are checked separately** and never de-duped against fingerprints. One hit is
  one finding. See House Rules for the pattern sweep and the headings pass.
- **Verify by re-running, not by re-grepping.** After any rewrite, run the full pass again:
  extraction, house-rule patterns, obligation checks, fingerprints. Verifying only the instances
  you found confirms a subset of the rule and produces a false clean.

### Findings and verdict

Every finding carries the same fields, whichever lens or rule produced it: **lens** (signal,
voice, house), **tier**, **where** (quote or location), **what** (the tell, rule, or leak,
named), **evidence** (density per ~1,000 words, the variance observation, or "single instance"
with the rule), and **fix** (the concrete move, or "protected").

Three tiers. *Fix before it ships:* house-rule hits in figurative use, uncashed obligation
checks. *Fix if you are editing:* fingerprints past the density line, session vocabulary,
heading-register skew. *Leave it:* protected voice, literal uses, the author's own reach-words,
register-appropriate regularity. Recorded so a rewrite does not sand them, never counted.

The verdict is derived, one word with a plain gloss, shared with `review-signal` and Ripley:

- **Ship.** Nothing in the first tier, and the second tier is short and local. The gloss names
  the natural verb for the artifact: publish as is, send as is, merge as is.
- **Hold.** First-tier findings exist and every one is a local edit (a phrase swap, a heading
  rename, cashing a promise, converting to direct address). Fix them, then ship. No rewrite.
- **Rework.** The shape is the problem. Any texture finding (#4, #5, #12 across the document)
  forces rework, because no line edit reaches it.

The verdict line carries the tier counts so a round compares to the last one without a
denominator: `Hold: three local fixes, then ship. 3 / 5 / 4, down from 6 / 9 / 2.`

## House Rules

An author's hard rules, where one instance is a finding. Usually a retired phrase banned in
figurative use with a literal exception ("load-bearing" as a metaphor, fine for a wall).
Sometimes a construction ("X has a name"; a comma-afterthought heading like "The masthead,
confirmed."). Sometimes a single-instance version of a fingerprint, such as a sincerity badge on
a verdict ("honestly," "the honest take") where the author has said one is enough.

**Three layers, closest wins, and a layer can only add.**

1. **Standing rules (the author).** The author's user-level `CLAUDE.md`, in a `## Voice`
   section or any section that lists retired phrases or hard rules. On a surface with no
   CLAUDE.md (Desktop, Cowork), the same rules live in the app's stored preferences and writing
   settings. An agent persona's rules live in that agent's own repository.
2. **Engagement rules (the voice sheet).** Rules and rulings for one body of work, at
   `.claude/work/voice-sheet.md` in the project, or passed by path (`voice-sheet <path>`) when
   the deliverables live elsewhere. This is the layer that accretes. To start one, copy
   `voice-sheet-example.md` from this skill's directory and keep only what is the author's.
3. **Session rules (this conversation).** Rules the author states while working, and rulings
   made this round that are not yet written down.

A lower layer never loosens a rule above it. A ruling only adds a ban or revokes an exemption.
If none of the three layers yields anything, ask. Never apply the example file as if it were
the author's list.

**Check as patterns, not strings.** From each construction rule derive the general shape and
sweep for the shape, not for the instances already seen. Headings get their own pass: they are
short, visible, and where the comma-afterthought hides.

**A retired metaphor retires its family.** When the author has retired "load-bearing," the other
mechanical and structural metaphors doing the same work are suspect ("installs a discipline,"
"the machinery of," "wired into"). The fix, per the author's own rule, is naming the claim the
metaphor stood in for, never a fresher metaphor.

**Rulings accrete.** When the author cuts something the reviewer had exempted (a "definitional
use," a "genuine reach-word"), the exemption is revoked for that word or pattern for the rest of
the engagement, and later rounds flag remaining and new instances. The author outranks the
reviewer's taxonomy; a defense the author has already overruled is a repeated mistake, not a
considered judgment. At the end of a round, list the rulings inferred from the author's edits,
one line each; on the author's confirmation, append them to the voice sheet. Never write a
ruling the author has not seen. Where there is no file, restate the confirmed list so the author
can paste it into preferences.

**Reporting.** House-rule hits get their own short table: rule, quote, literal or figurative.
Literal uses are noted and not counted. Say which layer each rule came from.

## Guards (do not skip these)

These keep the skill from flagging authentic human writing. They are not optional polish.
Without them the skill reproduces the known false-positive failures of AI detectors.

- **Plainness is not a tell.** GPT detectors flag 61%+ of non-native-English essays as AI (Liang
  et al., *Patterns* 2023) because plain vocabulary and short sentences resemble LLM output.
  Never flag simplicity, small vocabulary, or ESL-style directness.
- **Em dashes are folklore.** No study establishes em dash presence as a discriminator, and
  plenty of humans lean on them. Only ever consider frequency density, never a single dash. An
  author may have a house rule about dashes; that is theirs to set, not the skill's to assume.
- **One instance is nothing, for fingerprints.** Density and low variance are the signals. A
  lone "delve" or a single not/but is noise. House rules and obligation checks are the named
  exceptions: the first because the author supplied them, the second because the text made a
  promise.
- **Provenance is not quality.** Over-represented words mark how text was likely made (RLHF and
  annotator preference), not that it is bad. Flag the pattern; do not moralize the word.
- **This is not detector evasion.** We do not tune output to beat GPTZero or any classifier.
  Those scores are evadable and decay under paraphrase. The goal is prose that reads human
  because it is better.
- **Register-match to artifact type.** A reference doc (SKILL.md, API table, config, runbook)
  should be regular and terse. Exempt spec and reference text from the uniformity tells (#4,
  #5). Uniformity is a tell in an essay and correct in a spec. Essays and marketing pieces are
  exempt from #12; evocative headings are their genre.
- **Author's-voice exemption.** Learn the author's real voice before cutting it. Worked
  example: an author who reaches for threes in every essay is not exhibiting tricolon
  addiction; that is their cadence, and the skill should measure it against their own baseline,
  not a generic one. Do not flag an author's genuine, working habits as fingerprints. Session
  vocabulary (#11) is the session's habit, not the author's; the author never chose it.
- **Homely abbreviations and parenthetical variation are voice.** "i.e.," "e.g.," "aka," and a
  trailing "(or asked)" mid-prose are how some authors write. Do not clean them.

## Modes

- **critique** (default): diagnose and score, no rewrite. Stop and wait for authorization.
  A voice rewrite changes the author's words, so confirm the diagnosis before touching the prose.
- **rewrite**: produce the humanized version, after the user authorizes, then verify by
  re-running the full pass.
- **LFG**: one shot, critique and rewrite in a single pass, no gate, when the user wants speed.

## How to Run

1. **Name the job and the voice.** What is the text for, and whose voice should it be in? Match
   the author, not a generic human. Note who the named readers are, if any.
2. **Load the house rules**, all three layers: standing rules from the user-level CLAUDE.md or
   stored preferences, the engagement voice sheet if one exists or is passed, then the
   conversation. Say which layers you found. If none, ask.
3. **Check the register.** If it is a reference or spec doc, apply Tier 1, the lexical tells,
   the house rules, and the obligation checks only. Skip the uniformity tells. Regularity is
   correct there.
4. **Extract, then measure. Do not spot-flag.** Run the session-vocabulary extraction, the
   presence counts, and the variance checks. Sweep the house rules as patterns, headings
   separately. Walk the obligation checks. Build the findings table.
5. **De-dup and tier.** Collapse entangled tells to the underlying habit. Tier every finding.
   House-rule and obligation hits stay separate from fingerprints. Derive the verdict.
6. **Separate voice from tell.** Before proposing a cut, ask: is this the author's genuine
   habit or a machine reflex? Protect the former.
7. **(On authorize or LFG) Rewrite toward variance.** Break the parallelism. Vary sentence
   length: short, then one that runs a little long because the thought did. Leave one aside
   that does not strictly need to be there. Swap the recycled words for the author's own range.
   Prefer a plain functional subject over a coined compression ("the monitoring and oversight,"
   not "the actuals"). Where a section repeats a colon-led feature list, dissolve it into
   prose. Size claims to reality ("most," not "every"). Where a paragraph opens on "nobody does X,"
   recast with the specific actor who does not, say what happens instead, or name the absence.
   Move a woven contrast into a trailing
   parenthetical. Give a component a job, not a personality. End where the information ends.
   Keep what is real. For a compressed line or a reader-context failure, write the passage the
   way you would answer "what does this mean?" aloud, in the reader's vocabulary, rather than
   decompressing the original phrasing in place; the spoken explanation is the target register.
8. **(After a rewrite) Verify by re-running the full pass**, then list any rulings to confirm.

## Output Format (critique pass)

```markdown
## Job
What the text is for, whose voice it should be in, and who the named readers are.

## Verdict
Ship / Hold / Rework: plain gloss. tier counts (fix before it ships / fix if editing / leave it), vs. last round if any.

## Findings
| Lens | Tier | Where | What | Evidence | Fix |
|------|------|-------|------|----------|-----|

## House Rules
| Rule | Layer | Quote | Literal or figurative |
|------|-------|-------|-----------------------|
(omit the section when no house rules were found in any layer)

## Fingerprints
The tells that crossed from device to fingerprint, with quoted examples.

## What to Preserve
Genuine voice and working friction that must NOT be smoothed.

## Humanized Version   (only on authorization or LFG)
[the rewrite]

## Notes   (with the rewrite)
What changed, what was left rough on purpose, what was protected as real voice, and the
result of the verification pass.

## Rulings to Confirm   (when the author's edits revoked an exemption)
One line each; appended to the voice sheet on confirmation.
```

## Style Rules for Your Response

- Lead with the verdict, not a lecture. The verdict says whether this is a patch or a rewrite.
- Quote the exact tell; name its category.
- Never flag a single instance of a fingerprint. Argue from density or variance. A house rule or
  an obligation check is the exception, and say which rule it is.
- If the draft already reads human, say so and stop. Do not manufacture findings.
- Distinguish the author's voice from a machine reflex out loud; when unsure, protect the voice.
- Do not sand the prose into a generic "casual" register. Human is not the same as chatty.
- Never re-defend a use the author has already cut.

## Integration with Other lastmilefirst Components

- **`/run-review-signal`** for usefulness per line. Run it when the problem is filler, not
  AI tone. Same verdict words, same tiers, so the two can be read side by side.
- **`Task: consult-ripley`** for a full editorial pass. Ripley runs both lenses and reconciles
  the conflict (signal says cut, voice says that friction is doing work; she adjudicates).
- **`/run-add-wisdom`** to capture durable voice patterns once they stabilize.

## Notes

- Gated by default: critique first, rewrite on authorization (LFG for one shot).
- Do not run this as a blind cleanup right after `review-signal`. Signal removes the variance
  that voice wants to keep. Reconcile deliberately, or let Ripley's dual mode do it.
- Best on prose meant for a reader (essays, posts, memos, READMEs), not on reference or spec
  docs.
- Reader-context failures (the draft leans on the drafting conversation's private vocabulary)
  are a clarity defect, not a voice tell. That belongs to `review-signal`.
