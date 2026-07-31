---
title: review-claude — Heading-Aware Section Matching + Gotchas Placement Guidance
version: 1.2
date: 2026-07-29
status: proposed
type: fix
component: plugins/lastmilefirst/skills/{review-claude,organize-claude,add-wisdom,add-knowledge,parc}
target_version: 0.21.0
refs: ["#10"]
---

# review-claude: Heading-Aware Section Matching + Gotchas Placement Guidance (v1.2)

> **v1.2 revision (2026-07-29):** Second `ce-doc-review` round. Fourteen findings applied, four of
> them structural:
>
> 1. **The anti-cheat mechanism was circular.** v1.1's pre-registered control table was built by
>    applying the proposed alias map to headings that had just been read, so any faithful
>    implementation reproduces it by construction. It tested implementation fidelity, not alias
>    correctness. Replaced with a **differential sweep** (Phase 0).
> 2. **Two more regressions found, same class as the one v1.1 fixed.** The user-level `~/Code/CLAUDE.md`
>    (`## Core Philosophy: Compound Engineering`) and promptasaurus (`## Testing Strategy`,
>    `## Deployment Instructions`) all pass today only because the expected header is a *prefix* of the
>    real one. Three instances across two rounds, none found by searching — so assume more. The sweep
>    exists to find them mechanically.
> 3. **User-extensible aliases (v1.1's 1c) are cut** to a follow-up issue. That one sub-feature
>    generated five of this round's fourteen findings — none about whether it's a good idea, all about
>    it being underspecified.
> 4. **One alias was wrong and is now dropped.** `Architecture` → `## Infrastructure` failed
>    adjudication: the archetype defines Infrastructure as "cloud provider, region, account details";
>    a section named Architecture describes code structure. Keeping it would have hidden opencanon's
>    genuine gap while the control table confirmed the hiding.
>
> Prior round-1 fixes were verified as landed by two reviewers. Product-lens was not re-run in round 2.

## Problem

Two defects, found by running `review-claude` across the workspace on 2026-07-28 (26 files,
13 flagged) and then triaging the output by hand.

### P1 — Section presence is a raw substring test (issue #10)

`review_claude.py:182` decides presence with:

```python
for section_header, description in expected_sections:
    if section_header in content:
```

`in` on the whole file. Not heading-aware, no aliasing. Consequences:

- **False negatives dominate.** `gruntwork-lastmilefirst/CLAUDE.md` reported `Present: 0 / Missing: 6`
  while containing a documented release process under `## CRITICAL: Version Bumping` +
  `### Version Bump Checklist`. Same for travel-skills (117 lines), griffith (155), cookie-monster
  (282), opencanon (120) — all reported `Present: 0`.
- **False positives are possible.** A file that merely *mentions* `## Testing` in prose or inside a
  fenced code block counts as having the section. Scaffolded files are the worst case: their YAML
  frontmatter literally lists every required header (`- header: "## Testing"`), which is the dominant
  current source of spurious passes.
- **Accidental matches mask the real rule.** `"## Deployment" in content` is also true for
  `### Deployment` and for `## Deployment Instructions`, because the expected string is a substring of
  the real heading. An unknown number of files pass today only by that accident, and every one is a
  regression candidate under exact matching. This constrains the fix more than anything else — see
  Phase 0.
- **The report overstates what was measured.** "Present: 0 sections" asserts a content finding from a
  heading-name check.
- **`--suggest` compounds it**, generating stubs for sections that already exist under other names.

Of 13 flagged files in that run, exactly one finding survived scrutiny (a genuinely absent Gotchas
section in 5 projects) — and it was buried.

### P2 — LMF contradicts itself on where gotchas belong

| Source | Says gotchas go in |
|---|---|
| `skills/add-wisdom/SKILL.md:18`, `skills/parc/SKILL.md:319` | stack-wisdom |
| `skills/add-knowledge/SKILL.md` — "specific to how this project/client works" test | stack-**knowledge** |
| `skills/review-claude/SKILL.md:100-102`, the project templates | project CLAUDE.md |
| `plugins/lastmilefirst/README.md:25` | project CLAUDE.md |

Three destinations, no rule. Writing the three Gotchas sections on 2026-07-28 (griffith `4b934e1`,
lastmilefirst `9382ba5`, travel-skills `e545d5d`) required inventing one ad hoc.

Related: the shipped template table is `| Issue | Cause | Solution |`. **Symptom is the column you
search by** — when you're stuck you know what you're seeing, not what's causing it. The schema omits
the only usable index.

## Scope

**In:** P1 code fix, P2 doc resolution, template schema change.

**Out:**
- The content/keyword probe separating "renamed" from "genuinely missing" (issue #10, bullet 3). A
  heading with an empty body still counts as present — see Open Question 1.
- **User-extensible aliases.** Deferred to a follow-up issue; see "Deferred: user-extensible aliases".
- `review-signal` / Ripley boundary changes.
- Retrofitting existing CLAUDE.md files to the new table schema.

This plan **refs** issue #10 rather than closing it.

## Design

### Phase 0 — Differential sweep (do this before and after the code change)

The design's central risk is not laxity, it is **strictness**: exact matching breaks every file that
passes today only because the expected header is a substring of the real one. Three such files were
found across two review rounds — takesmanship, the user-level file, and promptasaurus — none by
searching for them. There are probably more.

So the baseline is generated mechanically, not by hand:

1. **Before any code change**, record the current check's per-file, per-section result across every
   CLAUDE.md the tool scans (user, both orgs, all projects). This is the "before" set.
2. **After the change**, record the same. This is the "after" set.
3. **Diff them.** Every section that flips is classified:
   - `unmatched → matched` — the intended win. Confirm the heading genuinely covers the section.
   - `matched → unmatched` — **a regression.** Must be either aliased or explicitly accepted with a
     written reason. No silent flips.
   - No change — fine.

This replaces v1.1's hand-derived control table, which was circular: its predictions were produced by
applying the proposed alias map to headings the author had just read, so any faithful implementation
reproduced it by construction. It could only test implementation fidelity. The sweep is generated
from the code's actual behavior on both sides, so it tests the *outcome*.

**Known regressions the sweep must surface** (found by review; listed so a sweep that misses them is
itself suspect):

| File | Heading | Expected section | Passes today via |
|---|---|---|---|
| takesmanship | `### Deployment` | `## Deployment` | substring |
| `~/Code/CLAUDE.md` | `## Core Philosophy: Compound Engineering` | `## Core Philosophy` | prefix |
| promptasaurus | `## Testing Strategy` | `## Testing` | prefix |
| promptasaurus | `## Deployment Instructions` | `## Deployment` | prefix |

**The sweep is also the regression test.** It is encoded in the pytest module (Phase 1g), not run once
by hand — otherwise it cannot survive the first alias change, and the map is expected to grow.

### Phase 1 — Heading-aware matching with aliases

**1a. Extract headings, ignoring fenced code blocks.**

```python
def extract_headings(content: str) -> set[str]:
    """ATX headings only, normalized, fenced code blocks excluded."""
```

**Normalization:**
1. Strip trailing `#` characters
2. Strip a trailing parenthetical — `## Gotchas (Learned the Hard Way)` → `Gotchas`
3. Collapse whitespace, casefold

**Colon candidates.** A heading containing a colon yields three match candidates: the full normalized
form, the pre-colon segment, and the post-colon segment. A section matches if *any* candidate equals
the canonical name or one of its aliases. This resolves `## Core Philosophy: Compound Engineering` →
`Core Philosophy` (pre-colon) and `## CRITICAL: Version Bumping` → `Version Bumping` (post-colon)
with one rule instead of two directional ones.

v1.1's directional "strip a leading `WORD:`" rule is dropped. It rewrote `## Archetype: <X>` in all 23
project files into a live match candidate, for a benefit already delivered by the
`Version Bump Checklist` alias.

**Collision check (required):** the archetype marker is the one heading present in every file, so its
segments must not collide with any canonical name or alias. `Archetype`, `Usable`, `Deployable`,
`Referenceable`, `Experimental` — none appear in the map. Verification 9 asserts this and must be
re-run whenever an alias is added.

**Never strip arbitrary words.** `## Testing Strategy` does not become `Testing` — it is matched by
an explicit alias instead. Steps 2 and the colon split are the only decompositions, both bounded by
punctuation.

**Comparison is exact equality on a normalized candidate, never containment.** Containment would
silently widen every list — `Structure` would match `Repository Structure`, `Commands` would match
`Commands Reference`.

**Heading level is NOT significant.** Canonical headers match at any level. Sections are distinguished
by *name*, so level adds nothing — and requiring it would newly flag takesmanship.

**1b. Central alias map** — one dict in `archetypes.py`, keyed by canonical header.

Deliberately not added to the `(header, description)` tuples or template frontmatter: two independent
section sources (`ARCHETYPE_SECTIONS`, and template frontmatter via `parse_template_frontmatter`) both
emit canonical headers, so a map keyed by canonical header covers both without changing either data
shape.

```python
SECTION_ALIASES: dict[str, list[str]] = {
    "## Development Environment": ["Development", "Setup", "Local Development", "Commands",
                                   "Quick Commands", "Getting Started"],
    "## Installation":            ["Install"],
    "## Configuration":           ["Config", "Settings", "Environment Variables"],
    "## Testing":                 ["Tests", "Test Strategy", "Testing Strategy"],
    "## Publishing":              ["Releases", "Release Process", "Releases & packaging",
                                   "Cutting a release", "Version Bumping",
                                   "Version Bump Checklist"],
    "## Infrastructure":          ["Cloud", "Hosting"],
    "### Cloud Details":          ["Accounts & Regions", "Cloud Accounts"],
    "### Terraform Workspaces":   ["Workspaces", "Environments"],
    "## Deployment":              ["Deploy", "Deploying", "Shipping",
                                   "Deployment Instructions"],
    "## Content Structure":       ["Layout", "Repository Structure", "Structure"],
    "## How to Update":           ["Updating", "Contributing", "Maintenance"],
    "## Quick Commands":          ["Commands", "Common Commands"],
    "## Gotchas":                 ["Pitfalls", "Known Issues", "Common Issues", "Troubleshooting",
                                   "Common Gotchas", "Deployment Gotchas",
                                   "Common Pitfalls to Avoid"],
}
```

**Every alias must be adjudicated against the canonical section's own description in
`ARCHETYPE_SECTIONS`, not against a vague sense that the names are related.** The sweep cannot catch a
wrong alias — a wrong alias produces a `unmatched → matched` flip that looks exactly like an intended
win. Adjudication is the only defense, and it is a human step.

One alias failed adjudication and was removed: **`Architecture` → `## Infrastructure`.** Infrastructure
is defined as "cloud provider, region, account details"; a section named Architecture describes code
structure. It fired for opencanon and takesmanship, and keeping it would have marked a genuine
Infrastructure gap as documented. `Test Strategy` → `## Testing` ("test commands") is the next
weakest and should be re-examined if it ever masks a gap.

Two constraints on the map:

- **A heading may satisfy at most one canonical section** — first match in canonical order wins.
  Without this, a lone `## Getting Started` would close both `Development Environment` and
  `Installation` for a Usable project. `Getting Started` is therefore listed only under the former.
- **When two headings in one file alias the same section, the first in document order is reported.**
  Real cases exist: leamo-platform has both `## Local Development` and `## Commands`; takesmanship has
  both `## Common Gotchas` and `## Troubleshooting`. Without a tie-break, the report's
  `via "<heading>"` output is nondeterministic.

**On the qualified-Gotchas entries.** `Common Gotchas`, `Deployment Gotchas`, and
`Common Pitfalls to Avoid` are literal headings in takesmanship, remail, and promptasaurus. Under
exact equality they must be enumerated, and enumerating observed strings is whack-a-mole. Revisit a
bounded word-boundary `<Qualifier> Gotchas` suffix rule when a **fourth** qualified form appears in a
project whose archetype actually requires the section — not on list length, which is a poor proxy.
(calvin's `## Known Gotchas` does not count: calvin is Experimental, which does not require Gotchas,
so that alias could never fire. It is omitted from the map.)

**1c. Three-state result.** `present` / `missing` becomes `present` / `present_via_alias` / `missing`.

**1d. Reword the report — at all three rendering sites.** The wording lives in three places, and the
single-file path is the one most verification rows exercise:

| Site | What changes |
|---|---|
| `show_review_report` (~230-231) | `Missing: N sections` → "no heading found for"; alias hits render as `Publishing → via "Releases & packaging" ✓` |
| the `--file` branch in `main()` (~374-385) | same vocabulary; its `if not review["missing"]` short-circuit must not print bare "has all expected sections" when sections matched only via alias |
| the summary counter in `main()` (~457) | `Files with gaps: N` → `Files with unmatched sections: N`, plus `Files passing only via alias: N` |

**The no-gap branch matters most.** A file whose every section resolves through aliases currently
prints one `All sections present ✓` line and is excluded from the gap list — so "aliases are reported
distinctly" fails precisely where alias reliance is total.

**1e. `--suggest` skips alias-matched sections.**

**1f. `--config PATH` override.** Needed so the sweep and its tests run against a known config rather
than whatever is on the machine.

**1g. Tests — required, not optional.** Add `skills/review-claude/tests/` following the existing
`skills/audit-plugin/tests/` pattern, encoding Verifications 2-10 as unit tests plus the Phase 0
differential sweep. Without this the sweep is a one-shot ritual that cannot survive the first alias
addition, and the map is explicitly expected to grow.

### Phase 2 — Gotchas placement rule

Add to `skills/organize-claude/SKILL.md` and cross-reference from `review-claude/SKILL.md`,
`add-wisdom/SKILL.md`, and `add-knowledge/SKILL.md`:

> **Gotchas: CLAUDE.md, stack-wisdom, or stack-knowledge?**
> - **Project CLAUDE.md** — the trap is specific to *this* repo and you need it in context while
>   working here. "Don't test against the Travel Agent calendar, it's wired to Flighty."
> - **stack-wisdom** — the lesson generalizes across projects. "osv-scanner 2.x needs `--no-ignore`
>   or it silently skips subdirectory lockfiles."
> - **stack-knowledge** — not a gotchas destination. Knowledge holds reference facts; a trap with a
>   symptom and a fix is wisdom or CLAUDE.md.
> - **Both** CLAUDE.md and wisdom is legitimate when a repo-specific instance has a generalizable
>   cause: put the actionable form in CLAUDE.md, the pattern in wisdom, and link them.
>
> Test: *would this still be true in a different repo?* Yes → wisdom. No → CLAUDE.md.
>
> **If a project's gotchas live in stack-wisdom, keep a one-line `## Gotchas` section pointing at the
> wisdom entry.** The section stays required; the pointer satisfies it.

Fix the contradiction at its sources: `add-wisdom/SKILL.md:18` and `parc/SKILL.md:319` route all
gotchas to wisdom unconditionally; `add-knowledge/SKILL.md` routes anything project-specific to
knowledge. Qualify all three.

### Phase 3 — Template table schema

Four files carry the table — name them explicitly, since the `project-*.md.template` glob matches five
and the natural "four archetypes" reading picks the wrong four:

- `project-claude.md.template` (~117) — **the fallback** for un-archetyped projects
- `project-deployable.md.template` (~96)
- `project-usable.md.template` (~65)
- `project-referenceable.md.template` (~35)
- `project-experimental.md.template` — no Gotchas table; intentionally untouched

```diff
-| Issue | Cause | Solution |
-|-------|-------|----------|
+| Issue | Symptom | Cause / fix |
+|-------|---------|-------------|
```

Plus the same table in `organize_claude.py:420`. Add above each: *"Lead with the symptom — it's what
you'll be searching by when you hit this again."*

## Verification

| # | Check | Expected |
|---|-------|----------|
| 1 | **Differential sweep** | Every `matched → unmatched` flip is either aliased or accepted in writing. Zero unexplained regressions. |
| 2 | Regression: level | takesmanship's `### Deployment` still satisfies `## Deployment` |
| 3 | Regression: pre-colon | `## Core Philosophy: Compound Engineering` still satisfies `## Core Philosophy` |
| 4 | Regression: prefix | promptasaurus's `## Testing Strategy` and `## Deployment Instructions` still satisfy their sections |
| 5 | Post-colon | `## CRITICAL: Version Bumping` satisfies the `Version Bumping` alias |
| 6 | **Containment guard** | leamo's `## Architecture Overview` does **not** satisfy anything |
| 7 | Fenced code | `## Testing` only inside a ``` block → unmatched |
| 8 | Frontmatter | a scaffolded file's `- header: "## Testing"` YAML line → unmatched |
| 9 | **Archetype-marker collision** | no segment of `## Archetype: <X>` matches any canonical name or alias, for all four archetype values |
| 10 | One-heading-one-section | a lone `## Getting Started` satisfies `Development Environment` only |
| 11 | Tie-break | leamo-platform reports the first of `## Local Development` / `## Commands` in document order |
| 12 | Qualified Gotchas | promptasaurus / remail / takesmanship each match `## Gotchas` via alias |
| 13 | Dropped alias | opencanon's `## Architecture` does **not** satisfy `## Infrastructure` — that gap stays visible |
| 14 | Alias-only reporting | a file matching every section via alias still prints its alias hits and appears in `Files passing only via alias` |
| 15 | `--suggest` | no stub for an alias-matched section |
| 16 | organize-claude unaffected | scaffolding still emits all sections; `parse_template_frontmatter` consumers unchanged |

Checks 1, 6, 9, and 13 are the ones that can actually fail. 1 is the whole anti-regression story; 6
guards against containment leaking in; 9 guards the one heading present in every file; 13 asserts a
deliberately-removed alias stays removed.

## Risks

| Risk | Mitigation |
|---|---|
| **A wrong alias masks a real gap** | The sweep cannot catch this — a wrong alias looks like an intended win. Only per-alias adjudication against the canonical description defends against it, and that is a human step (1b). `Architecture` was caught this way; `Test Strategy` is the next weakest. |
| Exact matching breaks files passing by substring accident | The differential sweep finds them mechanically instead of relying on reviewers noticing (Phase 0). |
| Aliases become a way to pass without documenting anything | Reported distinctly at both report branches (1d). Does not cover empty-bodied sections — Open Question 1. |
| Enumerated qualified-Gotchas aliases keep growing | Revisit a bounded suffix rule on the fourth qualified form in an archetype that requires the section. |
| Normalization drops meaning | Only trailing `#`, trailing parenthetical, and a colon split. Never arbitrary words. |
| `archetypes.py` is shared with organize-claude | `SECTION_ALIASES` is a new module-level dict; no change to `ARCHETYPE_SECTIONS` or `get_sections_for_archetype`, and no new imports. Verification 16 guards it. |
| Three changes in one release revert as a unit | Sequence code → templates → docs; templates and docs carry no runtime behavior. |

## Deferred: user-extensible aliases

v1.1 proposed merging a `section_aliases` map from `~/.config/organize-claude/config.json`. Cut from
0.21.0 and tracked as a follow-up issue. The idea is sound — every alias here is a heading name from
one workspace, and a marketplace user with different naming habits gets the same false-negative flood
— but the mechanism needs decisions this plan should not rush:

- `setup_config` rebuilds the config dict wholesale, so `--setup` would silently delete the key.
  That path is the documented recovery when no config is found, and the pending `~/Code` → `~/work/code`
  move forces it.
- "Merge over the built-in map" reads as per-key replacement, so adding one Gotchas alias would drop
  the other seven.
- A user key absent from the built-in map would be a silent no-op.
- The documented config schema lists only `workspace`, `orgs`, `created`; nothing tells a user the
  feature exists.
- User-local aliases make the qualified-Gotchas revisit trigger unobservable to the maintainer.

The follow-up should also decide whether alias hits are source-labelled (built-in vs user) in the
report, which is what would make naming variants in the wild visible.

## Open questions

1. **Should a section match require a non-empty body?** Currently no — a heading with a `TBD` stub
   counts as present. leamo's `## Commands` body is `*(To be filled in as we build)*`. Requiring body
   content would make the check about documentation rather than headings, but it is a scope expansion
   beyond issue #10 and needs a definition of "placeholder-only". **Deferred.**
2. Should `--suggest` emit a rename hint toward the canonical name on alias matches?
3. Should user- and org-level canonical headers get alias vocabulary, or is aliasing
   project-archetype-only? The sweep will answer this empirically for the current workspace.

## Sequencing

Phase 0 "before" snapshot → Phase 1 (code + tests) → Phase 0 "after" snapshot and diff → Phase 3
(templates) → Phase 2 (docs). Single branch, single PR, version bump to 0.21.0,
`gh release create v0.21.0 --target main --latest` after merge per the repo release checklist.

Issue #7 (TruffleHog / non-gitleaks backend) stays open and out of scope.
