---
name: review-voice
description: Detect and fix the tells that make prose read as AI-generated, and rewrite toward an authentic human voice without flattening the author. Use when a draft sounds machine-written, when you want text to sound more human / less like AI / less like ChatGPT, or to humanize or de-slop a README, essay, memo, PRD, blog post, or AI-generated draft before publishing.
---

# Review Voice

Find the fingerprints that make writing read as machine-authored, then rewrite toward a
natural human voice — the author's own, not a generic "casual" one. This is the companion to
`review-signal`. Signal asks *does every line earn its keep?* Voice asks *does this read like a
person wrote it?* They are different questions, and they sometimes pull in opposite directions.

## When to Use

- a draft is clean and correct but reads unmistakably like AI wrote it
- you want prose to sound more human, less like ChatGPT, before you publish it
- an essay, post, memo, or README needs its machine tics removed without losing its point
- you tightened something with `review-signal` and now it reads *too* smooth — sanded flat

## When *Not* to Use

- **`/run-review-signal`** — the problem is filler, repetition, or weak prioritization, not that it sounds like AI
- **`/run-review-docs`** / **`/run-review-project`** / **`/run-review-claude`** — structure, staleness, or context placement
- The text is a **reference/spec doc** (SKILL.md, API table, config) — regularity is *correct* there; see Register-Match below

## The one idea worth holding

The durable signal is **homogenization** — suspiciously low variance. Across the research
(DetectGPT, Kobak, Sourati, Muñoz-Ortiz), the marker that survives as models improve isn't any
word or phrase; it's that machine prose has *less variance and less diversity* than human prose.
Uniform sentence lengths. Every paragraph the same shape. A small set of reliable words reused.
No friction. And here is the trap: **`review-signal`'s job is to remove variance** — it cuts
whatever doesn't pull weight, which includes the human texture that isn't strictly load-bearing.
So voice review is partly adversarial to signal review. Sometimes it protects, or restores, the
very roughness signal wanted gone.

## The Tells

Two tiers. Tier 1 is the crude stuff anyone can spot. Tier 2 is the payoff — fingerprints that
survive *because* the writer is good, so they're what catch already-tightened prose.

Each Tier 2 tell is tagged with how it's measured (this matters — see Method) and whether the
research backs it or it's an observed pattern.

### Tier 1 — crude tells

| Tell | What it looks like |
|------|--------------------|
| Lexical over-representation | *delve, showcase, underscore, leverage, robust, seamless, comprehensive, crucial, pivotal* used above a human rate |
| Formatting | bold-label bullets everywhere; emoji headers; the summary bow ("In conclusion", "Ultimately"); numbered lists for non-sequential things |
| Syntactic | participial pileups ("…, ensuring…", "…, allowing…"); "not only… but also"; correlative-conjunction addiction |

### Tier 2 — sophisticated fingerprints

| # | Fingerprint | Example | Measure | Evidence |
|---|-------------|---------|---------|----------|
| 1 | Not/but antithesis as the default move, repeated | "That's not misalignment. That's executing on a goal." | frequency | observed |
| 2 | Abstract-noun momentum openers | "That distinction matters beyond this incident." | frequency | observed |
| 3 | Recycled rhetorical-work vocabulary | precisely, exactly, relentlessly, materially, arguably, worth sitting with | frequency | literature-backed |
| 3b | Pet metaphors + performed candor | *load-bearing, spine, keystone, earns its keep*; "the honest take", "to be fair" | frequency | observed |
| 4 | Excessive structural regularity | nearly every paragraph is common-take → reframe → payoff line | **variance** | literature-backed |
| 5 | Absence of real noise | no tangents, no mid-thought long sentence, no non-load-bearing redundancy | **variance** | literature-backed |

Also flag: LLM tricolon addiction (distinct from an author who simply likes threes), uniform
paragraph length, and section/heading symmetry — all variance-measured.

The Tier 2 tells overlap on purpose: #1 is #4 at sentence scale, #2 feeds #4, and #5 is the
envelope around #4. One habit — antithetical reframing — can set off three rows. The Method
handles this so the score reflects one finding, not three.

## Method: how a tell becomes a verdict

Every reliable marker in the research is a **rate or a variance across the whole text**, never a
single occurrence. So the skill measures, it doesn't spot-flag.

- **Presence-tells (#1, #2, #3, #3b, Tier 1 lexical):** count per ~1,000 words. Flag when density
  crosses from *device* to *fingerprint*. Once is a rhetorical choice; six times in one piece is a
  tell. For 3b, learn the author's genuine reach-words first, then flag over-recurrence.
- **Texture-tells (#4, #5, paragraph length, symmetry):** measure variance. Low variance of
  sentence length and paragraph shape is the tell. You can't count an absence — you measure the
  flatness. Sentence-length variance is the hand-checkable proxy for the burstiness idea.
- **De-dup the score:** when entangled tells trace to one habit (#1/#2 as instances, #4 as their
  aggregate shape, #5 as the envelope), they count once, weighted. Don't let one habit triple the
  number.

## Guards (do not skip these)

These keep the skill from flagging authentic human writing. They are not optional polish; without
them the skill reproduces the known false-positive failures of AI detectors.

- **Plainness is not a tell.** GPT detectors flag 61%+ of non-native-English essays as AI (Liang
  et al., *Patterns* 2023) because plain vocabulary and short sentences resemble LLM output. Never
  flag simplicity, small vocabulary, or ESL-style directness.
- **Em-dashes are folklore.** No study establishes em-dash *presence* as a discriminator, and
  plenty of humans lean on them. Only ever consider frequency density, never a single dash.
- **One instance is nothing.** Density and low variance are the signals. A lone "delve" or a
  single not/but is noise.
- **Provenance is not quality.** Over-represented words mark how text was likely made (RLHF /
  annotator preference), not that it's bad. Flag the pattern; don't moralize the word.
- **This is not detector evasion.** We do not tune output to beat GPTZero or any classifier. Those
  scores are evadable and decay under paraphrase. The goal is prose that reads human because it *is*
  better, full stop.
- **Register-match to artifact type.** A reference doc — SKILL.md, API table, config, runbook —
  *should* be regular and terse. Exempt spec/reference text from the uniformity tells (#4, #5).
  Uniformity is a tell in an essay and correct in a spec.
- **Author's-voice exemption.** Learn the author's real voice before cutting it. Worked example:
  Ripley's own idiolect — *load-bearing, earn its keep, collect the rent, spine* — is her voice,
  not a tell. Do not flag an author's genuine, load-bearing habits as fingerprints.

## Modes

- **critique** (default) — diagnose and score, no rewrite. Stop and wait for authorization.
  A voice rewrite changes the author's words, so confirm the diagnosis before touching the prose.
- **rewrite** — produce the humanized version, after the user authorizes.
- **LFG** — one-shot: critique + rewrite in a single pass, no gate, when the user wants speed.

## How to Run

1. **Name the job and the voice.** What is the text for, and whose voice should it be in? Match
   the author, not a generic human.
2. **Check the register first.** If it's a reference/spec doc, apply Tier 1 and the lexical tells
   only — skip the uniformity tells. Regularity is correct there.
3. **Measure, don't spot-flag.** Run the presence counts and the variance checks. Build the table.
4. **De-dup and score.** Collapse entangled tells to the underlying habit. Score the real findings.
5. **Separate voice from tell.** Before proposing a cut, ask: is this the author's genuine habit or
   a machine reflex? Protect the former.
6. **(On authorize / LFG) Rewrite toward variance.** Break the parallelism. Vary sentence length —
   short, then one that runs a little long because the thought did. Leave one aside that doesn't
   strictly earn its place. Swap the recycled words for the author's own range. Keep what's real.

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
X/N (de-duped) — short interpretation.

## Fingerprints
The tells that crossed device → fingerprint, with quoted examples.

## What to Preserve
Genuine voice and load-bearing friction that must NOT be smoothed.

## Humanized Version   ← only on authorization or LFG
[the rewrite]

## Notes   ← with the rewrite
What changed, what was left rough on purpose, what was protected as real voice.
```

## Style Rules for Your Response

- Lead with the verdict, not a lecture.
- Quote the exact tell; name its category.
- Never flag a single instance — always argue from density or variance.
- If the draft already reads human, say so and stop. Don't manufacture findings.
- Distinguish the author's voice from a machine reflex out loud; when unsure, protect the voice.
- Don't sand the prose into generic "casual" register. Human ≠ chatty.

## Integration with Other lastmilefirst Components

- **`/run-review-signal`** — usefulness per line. Run it when the problem is filler, not AI-tone.
- **`Task: consult-ripley`** — for a full editorial pass, Ripley runs *both* lenses and reconciles
  the conflict (signal says cut, voice says that friction is load-bearing — she adjudicates).
- **`/run-add-wisdom`** — capture durable voice patterns once they stabilize.

## Notes

- Gated by default: critique first, rewrite on authorization (LFG for one-shot).
- Do **not** run this as a blind cleanup right after `review-signal` — signal removes the variance
  that voice wants to keep. Reconcile deliberately, or let Ripley's dual mode do it.
- Best on prose meant for a reader (essays, posts, memos, READMEs), not on reference/spec docs.
```
