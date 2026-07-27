# Plan: `review-voice` + Ripley editorial synthesis

**Date:** 2026-07-26
**Status:** Ripley-reviewed, research-augmented — awaiting go/no-go
**Target version:** 0.18.0 (new skill + command; behavior change to review-signal)

## Thesis

Editorial quality is **one judgment made through two lenses that pull against each other.**

- **Signal** (`review-signal`): usefulness per line — RENT, prioritization, cut what doesn't pull weight.
- **Voice** (`review-voice`, new): authenticity — detect the tells that make prose read machine-authored, without flattening the author.

The lenses conflict. Signal says "cut this tangent"; voice says "that tangent is the friction that marks a human wrote this." Neither wins by default. So the product is not two skills — it is **a reconciler (Ripley) that owns the tradeoff, with two clean single-objective lenses underneath it.** Two skills because the lenses are independently reusable and each is easier to keep sharp with one objective; a reconciler because someone has to adjudicate when they disagree.

## The friction paradox (why the lenses conflict, stated precisely)

RENT's Relevance test kills text that doesn't serve the task. Some of that text is filler — good riddance. Some of it is *human texture*: an aside, a mid-thought long sentence, a minor non-load-bearing redundancy. The research calls the result **homogenization** — LLM polishing "selectively amplifies dominant characteristics while suppressing others," and lexical diversity measurably drops (Sourati et al. 2025; Muñoz-Ortiz et al. 2024).

So: **running signal→voice in sequence without judgment over-smooths texture.** Not a catastrophe, an expected side effect. Consequence the skills must state plainly: run standalone, they give conflicting advice and nothing reconciles it. That is what dual-mode is for. (Ripley's earlier "maximally AI-sounding prose" flourish cut — the mechanism is enough.)

## review-voice: the tell taxonomy

Two tiers. Tier 1 is the crude stuff. **Tier 2 is the value** — fingerprints that survive *because* the writer is skilled, so they catch tightened prose (Fish's and Claude's included).

### Tier 1 — crude tells (catch lazy drafts)
- **Lexical over-representation** — *delves* (~25× human rate), *showcasing*, *underscores*, plus comprehensive/notably/crucial/pivotal/leverage/robust/seamless. Evidence: Kobak et al. 2025. Flag **density vs a human baseline**, never a lone instance — and never moralize the word (it marks provenance/RLHF, not bad writing).
- **Formatting** — bold-label bullets everywhere; emoji headers; the summary bow ("In conclusion / Ultimately"); numbered lists for non-sequential items.
- **Syntactic** — participial pileups ("…, ensuring…", "…, allowing…"); "not only… but also"; correlative-conjunction addiction.

### Tier 2 — sophisticated fingerprints (the spine)

Each tagged by evidence status and by how it's measured (see Method).

1. **Not/but antithesis as default move** — "That's not X. That's Y," repeated to fingerprint density. *Observed (not literature-backed); measure by frequency.*
2. **Abstract-noun momentum openers** — prior idea → abstract-noun subject to manufacture motion ("That distinction matters…"). *Observed; frequency.*
3. **Recycled rhetorical-work vocabulary** — precisely, exactly, relentlessly, materially, arguably, worth sitting with. *Literature-backed (Kobak: excess words are 66% style verbs/adjectives); frequency vs baseline.*
   - **3b. Pet metaphors & performed candor** — *borrowed-structure metaphors* (load-bearing, spine, keystone, scaffolding, earns its keep) and *performed candor* ("the honest take," "to be fair," "honestly"). Detection method, not a banlist: learn the author's genuine reach-words first, then flag over-recurrence.
4. **Excessive structural regularity** — nearly every paragraph is common-take → reframe → payoff. *Literature-backed as low burstiness (DetectGPT/Mitchell 2023) and tight sentence-length clustering (Muñoz-Ortiz 2024); measure by **variance**, not count.*
5. **Absence of real noise (KEYSTONE)** — no unearned tangents, no mid-thought run-ons, no non-load-bearing redundancy. Every sentence pulling its weight is itself the tell. *Literature-backed as reduced lexical diversity + homogenization (Sourati 2025); measure by **variance/dispersion**.*

**Missing tells to add (Ripley):** LLM tricolon addiction (distinct from an author who simply likes threes); uniform paragraph *length*; section/heading symmetry. All Tier-2-adjacent, all variance-measured.

**Overlap is real (Ripley P3):** #1 is #4 at sentence scale; #2 feeds #4; #5 subsumes #4. One habit (antithetical reframing) can light up three rows. See de-dup rule below so the score reflects one finding, not three.

## Method: how a tell becomes a verdict

The literature is unanimous on one thing: every robust marker is a **rate/variance over the whole text**, never a single occurrence. So:

- **Presence-tells (#1, #2, #3/3b, Tier 1 lexical):** frequency. Count per ~1,000 words; flag when density crosses device → fingerprint ("once is a device, six times is a fingerprint").
- **Texture-tells (#4, #5, new paragraph-length/symmetry):** dispersion. Measure variance of sentence length, paragraph shape, paragraph length. Low variance = the tell. This is the burstiness idea; sentence-length variance is the hand-checkable proxy.
- **De-dup rule:** entangled tells (#1/#2 as instances, #4 as their aggregate shape, #5 as the envelope) feed the score once, weighted — not once per row. The AI-Tell Score must read as one finding when it is one habit.

### Anti-false-positive guards (non-negotiable, all evidence-backed)
- **Plainness is not a tell.** GPT detectors flag 61%+ of non-native-English essays as AI (Liang et al. 2023). Low perplexity / small vocabulary / short sentences can be authentically human. Never flag simplicity.
- **Em-dashes are folklore.** No study establishes em-dash *presence* as a discriminator; it's a legitimate heavy human habit (Fish's). Only ever consider frequency density, never a single mark.
- **Single tell ≠ verdict.** Density and low variance are the signals; one instance is noise.
- **Provenance ≠ quality.** Over-represented words mark how the text was made, not that it's bad. Flag the pattern; don't moralize.
- **We are not gaming detectors.** Explicit non-goal: no tuning against GPTZero et al. Detector scores are evadable and degrade under paraphrase/RLHF (arXiv 2503.17965). The prose reads human because it is better.

## Modes (both skills): gated default + LFG

Suggestion 1 resolved → applies to **both** review-voice and review-signal.
- **critique** (default) — diagnosis + tell/density table, no rewrite. Stop; wait for authorization.
- **rewrite** — only after the user authorizes.
- **LFG** — first-class one-shot: critique + rewrite in a single pass, no gate. Named mode (`LFG` / "just do it"), not a buried flag.

For review-signal this is two changes, kept distinct in the PR body: (a) **fix a real contradiction** (it currently says both "critique+rewrite default" and "critique first"); (b) **change the default to gated** (a behavior change — one-shot was a legit fast path, so LFG preserves it).

## Ripley synthesis protocol (the reconciler — the point)

`consult-ripley` gains a **dual-review protocol** for "review this properly":
1. Run both lenses.
2. **Reconcile the conflict.** Where signal says cut and voice says the friction is load-bearing, Ripley adjudicates and says which wins and why. This is the only place the two objectives are weighed against each other.
3. Output **one reconciled result** — combined verdict + both scores + a single rewrite (gated), flagging each edit where the lenses disagreed and how she called it. Not two concatenated reports (the failure mode to avoid).

Either lens is still callable alone; dual is the default "do it right" path.

## Guards baked into the skill (register + voice)
- **Register-match to artifact type.** Reference/spec/config docs (a SKILL.md, an API table) *should* be regular and terse — exempt them from the uniformity tells (#4/#5). Uniformity is a tell in an essay, correct in a spec.
- **Author's-voice exemption.** Learn the author's genuine reach-words before flagging recycled ones. Worked example in the skill: **Ripley's own idiolect** (load-bearing, earn its keep, collect the rent, spine) is voice, not tell — the skill must not flag its own author.

## Output format (critique pass)
Job (text's purpose + whose voice) → Verdict (one line: how machine-authored it reads) → **AI-Tell Table** (per tell: measure type, count-or-variance, device/fingerprint call) → AI-Tell Score (de-duped) → Fingerprints (the crossings, with quotes) → What to preserve (genuine voice + load-bearing friction) → *(on authorize / LFG)* Humanized Version + notes on what was left rough on purpose.

## Work surface
1. **New** `skills/review-voice/SKILL.md` — the skill (bulk of the work).
2. **New** `commands/run-review-voice.md` — one-line loader (mirror run-review-signal).
3. **Edit** `personas/ripley-rent-collector.md` — add AI-tell/humanizing expertise in her voice.
4. **Edit** `agents/consult-ripley.md` — humanization triggers + the dual-review synthesis protocol.
5. **Edit** `skills/review-signal/SKILL.md` — cross-link both ways; flip to gated default + LFG; resolve the contradiction.
6. **Edit** `README.md` — version table.
7. **Version bump → 0.18.0** — plugin.json, marketplace.json (`metadata.version` AND `plugins[].version`), README table.
8. **Release** — after merge: `gh release create v0.18.0 --target main --latest`.

Not touched: `consult-expert` routing (Ripley already routed; new skill auto-discovered — confirm, don't pre-edit).

## Surface availability (claude-code-guide finding, 2026-07-26)
- **Claude Code + Cowork:** full skill support; auto-invokes off the `description` frontmatter. The description is written to trigger on "sound more human / less like AI / less like ChatGPT / humanize / de-slop."
- **claude.ai browser:** Skills available (Pro+) — should work.
- **Consumer Desktop app:** marketplace Skills are NOT in the documented availability matrix (personas are). Undocumented, not confirmed. **Action: test on Desktop after cutting v0.18.0.** Reliable Desktop fallback = Ripley via `/consult-expert` (personas work there). No build change needed — the description is the only lever regardless.

## Build sequence
1. Draft `review-voice/SKILL.md` (taxonomy + method + guards).
2. Command loader.
3. review-signal edits (cross-link, gated+LFG, contradiction).
4. Persona + agent (dual-review protocol).
5. Version bump (3 sites) + README.
6. **Dogfood** — run both lenses on the new/changed files, at **register-appropriate** standard.
7. `consult-ripley` dual pass on the skill text before commit.
8. Branch → PR (decouple the two review-signal changes in the body) → merge → cut v0.18.0.

## Acceptance criteria
- `/run-review-voice <file>` runs; critique pass emits Job / Verdict / AI-Tell Table / de-duped Score / Fingerprints / What-to-preserve. Rewrite withheld until authorized or LFG.
- Method is split: presence-tells by frequency, texture-tells by variance; entangled tells de-duped in the score.
- Guards present and prominent: plainness-is-not-a-tell (Liang), em-dash-folklore, provenance≠quality, single-tell≠verdict, not-a-detector-arms-race, register-match exempts spec docs, author's-voice (Ripley's own idiolect) exemption.
- review-signal: gated default + LFG; contradiction resolved; cross-links resolve both ways; behavior change called out in PR + release notes.
- Ripley dual-mode returns ONE reconciled result, not two reports.
- **Register-appropriate dogfood:** the skill's *prose* sections read human; its *reference* sections (tables, toolkit) may be regular. Not held to an essay standard.
- All three version sites read 0.18.0; v0.18.0 release cut after merge.

## Decision log (2026-07-26)
Name `review-voice`. Tier 1 lean. Tier 2 = Fish's five + 3b. Gated default + LFG, both skills. P1 synthesis-first reframe adopted. P2 method split adopted. P3 de-dup adopted. P4 register exemption adopted. P5 Ripley-voice exemption adopted. Research augmentation folded in (below).

---

## Appendix: research findings (sources)

Scope: corpus-level distributional signals. Almost none is reliable on a single document; detector-grade signals (perplexity, burstiness) degrade as models improve and after paraphrase/RLHF. Treat as editing tells that justify a density/variance check, never a verdict.

**Validates existing fingerprints**
- **#3 — strongest evidence.** 2023–24 science "excess words" are ~66% verbs, 18% adjectives — the style-word category #3 targets. Kobak, González-Márquez, Horvát, Lause, *Science Advances* 11(27), 2025 — arXiv 2406.07016.
- **#4 — validated.** Low burstiness (low variance in per-sentence perplexity) is the LLM signature. DetectGPT, Mitchell et al., ICML 2023 — arXiv 2301.11305.
- **#4/#5 sentence level — validated.** LLM sentence lengths cluster 10–30 tokens; human distributions scatter wider. Muñoz-Ortiz, Gómez-Rodríguez, Vilares, *AI Review* 2024 — arXiv 2308.09067.
- **#5 — validated.** LLM polishing homogenizes style; lexical diversity drops (STTR 0.49 human vs 0.42–0.47; MTLD 96.5 vs 57–95). Sourati et al. 2025 — arXiv 2502.11266.
- **#1, #2 — NOT literature-backed.** No paper isolates these rhetorical moves. Keep as author-observed tells; claim no citation.

**New evidence-backed markers**
- Over-representation ratios: *delves* ~25×, *showcasing*/*underscores* ~9×; comprehensive, notably, particularly, crucial, pivotal, insights, enhancing (Kobak 2025). Density check, not a ban.
- The "delve" spike traces to RLHF/annotator preference, not architecture — arXiv 2412.11385. → provenance, not quality.
- Function-word distribution (Burrows' Delta) separates human vs LLM in short samples — arXiv 2507.00838; *PLOS One* 2025 (RF 99.8%). Classifier features, opaque to a human editor — justification, not a hand rule.
- POS skews: LLM more auxiliaries (5.8% vs 3.8%), more pronouns (7.1% vs 5.3%), fewer adjectives (6.7% vs 7.6%), more SBAR clauses (Muñoz-Ortiz 2024).
- Lower emotional range (LLM skews joy/surprise; humans more fear/disgust) — same paper. Corroborates #5, weak alone.

**Debunked / do NOT flag alone**
- Em-dash = AI: folklore. Real kernel (GPT-4o emits more em-dashes) but no peer-reviewed discriminator; human "spot the AI" runs near chance. Density only, never one mark.
- Plain vocabulary / low perplexity / short uniform sentences ≠ AI: detectors flag 61%+ of non-native TOEFL essays as AI. Liang et al., *Patterns* 2023 — arXiv 2304.02819. Core anti-false-positive lesson.
- A lone over-represented word: evidence is about elevated *frequency across a text*, not one instance.
- Any detector score as ground truth: evadable, degrades under RLHF — arXiv 2503.17965.

**Method implications**
- Design every detection as rate/variance over the document, never "contains X."
- Two signals, don't conflate: perplexity-burstiness (variance in predictability, the true detector signal) vs sentence-length variance (coarser human-checkable proxy).
- Reference numbers (corpus-level, model/domain-dependent — shape expectations, NOT cutoffs): STTR ~0.49 vs ~0.42–0.47; MTLD ~96 vs ~57–95; sentence length LLM 10–30 vs human wider. Applying a universal cutoff reproduces the Liang non-native-writer bias.
- The durable finding is reduced variance/diversity — homogenization. That is #4 and #5, and the one thing tightening cannot restore.
