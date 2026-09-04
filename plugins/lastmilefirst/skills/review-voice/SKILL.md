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

## Two kinds of rule

This skill applies two kinds of rule, and they are measured differently.

**Fingerprints** are patterns. They are measured as a rate or a variance across the whole text,
and a single occurrence is never a finding. The taxonomy below is general and ships with the
skill.

**House rules** are the author's own hard rules, supplied by the author, and a single instance
is a finding. They are the one exception to the density method, and they exist because some
tells do their damage on the first hit. The skill ships with an example list only; the real
list comes from the author. See House Rules below.

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

Also flag, all variance-measured: LLM tricolon addiction (distinct from an author who simply
likes threes), uniform paragraph length, section and heading symmetry, consecutive paragraphs
with identical skeletons, and consecutive sections built on colon-led feature lists.

The Tier 2 tells overlap on purpose. #1 is #4 at sentence scale, #1b is #1 read at the clause,
#2 feeds #4, #9 is the payoff line of #4 seen on its own, and #5 is the envelope around #4. One
habit (antithetical reframing) can set off three rows. The Method handles this so the score
reflects one finding, not three.

## Method: how a tell becomes a verdict

Every reliable marker in the research is a rate or a variance across the whole text, never a
single occurrence. So the skill measures fingerprints. It does not spot-flag them.

- **Presence-tells (#1, #1b, #2, #3, #3b, #6 through #9, Tier 1 lexical):** count per ~1,000
  words. Flag when density crosses from device to fingerprint. Once is a rhetorical choice; six
  times in one piece is a tell. For 3b, learn the author's genuine reach-words first, then flag
  over-recurrence.
- **Texture-tells (#4, #5, paragraph length, symmetry, identical skeletons):** measure variance.
  Low variance of sentence length and paragraph shape is the tell. You cannot count an absence,
  so you measure the flatness. Sentence-length variance is the hand-checkable proxy for the
  burstiness idea.
- **De-dup the score:** when entangled tells trace to one habit (#1, #1b, #2 as instances, #4
  as their aggregate shape, #5 as the envelope), they count once, weighted. Do not let one habit
  triple the number.
- **House rules are scored separately** and never de-duped against fingerprints. One hit is one
  finding.

## House Rules

An author's hard rules, where one instance is a finding. These are not fingerprints, and the
"one instance is nothing" guard does not apply to them, because the author has said the damage
happens on the first hit.

**Where they come from, in order:**

1. The author's user-level `CLAUDE.md`, when there is one. Look for a `## Voice` section (or
   any section that lists retired or banned phrases) and take the rules stated there.
2. Rules the author has stated in the conversation.
3. Otherwise, ask. Do not guess an author's house rules and do not apply the example list below
   as if it were theirs.

**What a house rule looks like.** Usually a retired phrase or construction, banned in
figurative use, with a literal-use exception: "load-bearing" is banned as a metaphor and fine
for a wall. Sometimes a construction rather than a phrase ("X has a name" as a framing device).
Sometimes a single-instance version of a fingerprint, such as a sincerity badge on a verdict
("honestly," "the honest take") where the author has said one is enough.

**Example list, for shape only.** Retired in figurative use: "load-bearing," "the spine,"
"earns its keep." Retired as a construction: "X has a name." A real author's list will differ,
and the example is not a default.

**Reporting.** House-rule hits get their own short table: rule, quote, literal or figurative.
Literal uses are noted and not counted.

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
  lone "delve" or a single not/but is noise. House rules are the named exception, and only when
  the author supplied them.
- **Provenance is not quality.** Over-represented words mark how text was likely made (RLHF and
  annotator preference), not that it is bad. Flag the pattern; do not moralize the word.
- **This is not detector evasion.** We do not tune output to beat GPTZero or any classifier.
  Those scores are evadable and decay under paraphrase. The goal is prose that reads human
  because it is better.
- **Register-match to artifact type.** A reference doc (SKILL.md, API table, config, runbook)
  should be regular and terse. Exempt spec and reference text from the uniformity tells (#4,
  #5). Uniformity is a tell in an essay and correct in a spec.
- **Author's-voice exemption.** Learn the author's real voice before cutting it. Worked
  example: an author who reaches for threes in every essay is not exhibiting tricolon
  addiction; that is their cadence, and the skill should measure it against their own baseline,
  not a generic one. Do not flag an author's genuine, working habits as fingerprints.
- **Homely abbreviations and parenthetical variation are voice.** "i.e.," "e.g.," "aka," and a
  trailing "(or asked)" mid-prose are how some authors write. Do not clean them.

## Modes

- **critique** (default): diagnose and score, no rewrite. Stop and wait for authorization.
  A voice rewrite changes the author's words, so confirm the diagnosis before touching the prose.
- **rewrite**: produce the humanized version, after the user authorizes.
- **LFG**: one shot, critique and rewrite in a single pass, no gate, when the user wants speed.

## How to Run

1. **Name the job and the voice.** What is the text for, and whose voice should it be in? Match
   the author, not a generic human.
2. **Load the house rules.** User-level CLAUDE.md first, then the conversation, then ask.
3. **Check the register.** If it is a reference or spec doc, apply Tier 1, the lexical tells,
   and the house rules only. Skip the uniformity tells. Regularity is correct there.
4. **Measure, do not spot-flag.** Run the presence counts and the variance checks. Build the
   table. Run the house rules as a separate pass.
5. **De-dup and score.** Collapse entangled tells to the underlying habit. Score the real
   findings. House-rule hits stay separate.
6. **Separate voice from tell.** Before proposing a cut, ask: is this the author's genuine
   habit or a machine reflex? Protect the former.
7. **(On authorize or LFG) Rewrite toward variance.** Break the parallelism. Vary sentence
   length: short, then one that runs a little long because the thought did. Leave one aside
   that does not strictly need to be there. Swap the recycled words for the author's own range.
   Prefer a plain functional subject over a coined compression ("the monitoring and oversight,"
   not "the actuals"). Where a section repeats a colon-led feature list, dissolve it into
   prose. Size claims to reality ("most," not "every"). Move a woven contrast into a trailing
   parenthetical. Give a component a job, not a personality. End where the information ends.
   Keep what is real.

## Output Format (critique pass)

```markdown
## Job
What the text is for, and whose voice it should be in.

## Verdict
One line: how machine-authored this reads, and why.

## AI-Tell Table
| Tell | Measure | Count / variance | Device or fingerprint |
|------|---------|------------------|-----------------------|

## AI-Tell Score
X/N (de-duped), with a short interpretation.

## House Rules
| Rule | Quote | Literal or figurative |
|------|-------|-----------------------|
(omit the section when no house rules were supplied)

## Fingerprints
The tells that crossed from device to fingerprint, with quoted examples.

## What to Preserve
Genuine voice and working friction that must NOT be smoothed.

## Humanized Version   (only on authorization or LFG)
[the rewrite]

## Notes   (with the rewrite)
What changed, what was left rough on purpose, what was protected as real voice.
```

## Style Rules for Your Response

- Lead with the verdict, not a lecture.
- Quote the exact tell; name its category.
- Never flag a single instance of a fingerprint. Argue from density or variance. A house rule
  is the exception, and say which rule it is.
- If the draft already reads human, say so and stop. Do not manufacture findings.
- Distinguish the author's voice from a machine reflex out loud; when unsure, protect the voice.
- Do not sand the prose into a generic "casual" register. Human is not the same as chatty.

## Integration with Other lastmilefirst Components

- **`/run-review-signal`** for usefulness per line. Run it when the problem is filler, not
  AI tone.
- **`Task: consult-ripley`** for a full editorial pass. Ripley runs both lenses and reconciles
  the conflict (signal says cut, voice says that friction is doing work; she adjudicates).
- **`/run-add-wisdom`** to capture durable voice patterns once they stabilize.

## Notes

- Gated by default: critique first, rewrite on authorization (LFG for one shot).
- Do not run this as a blind cleanup right after `review-signal`. Signal removes the variance
  that voice wants to keep. Reconcile deliberately, or let Ripley's dual mode do it.
- Best on prose meant for a reader (essays, posts, memos, READMEs), not on reference or spec
  docs.
