---
title: review-claude — Heading-Scoped Matching, Honest Reporting, Split Gotchas
version: 1.3
date: 2026-07-29
status: proposed
type: fix
component: plugins/lastmilefirst/skills/{review-claude,organize-claude,add-wisdom,add-knowledge,parc}
target_version: 0.21.0
refs: ["#10"]
---

# review-claude: Heading-Scoped Matching, Honest Reporting, Split Gotchas (v1.3)

> **v1.3 — deliberate descope (2026-07-29).** v1.0–v1.2 over-built. Issue #10 asks the report to stop
> claiming a content finding it never measured; v1.1/v1.2 answered with exact matching plus a
> 42-string alias map, which required normalization rules, a pre-registration ritual, and a
> differential sweep to make safe. **Every regression the two review rounds caught existed only
> because of exact matching, which existed only because of the alias map.** Remove the map and the
> problems it created never arise.
>
> v1.3 keeps today's lenient substring behavior but scopes it to real headings. Tested against the
> live workspace: **zero regressions**, and the qualified-Gotchas problem v1.2 spent a page on simply
> evaporates — `## Common Gotchas` and `### Deployment Gotchas` already contain "gotchas".
>
> **New in v1.3 (user request):** Gotchas splits into a developer-facing and an operator-facing
> section.
>
> Carried forward from the review rounds: the report rewording, all three rendering sites, the
> three-destination gotchas contradiction, the template file set, and the table schema change.
> Dropped: the alias map, normalization rules, colon handling, pre-registration, the differential
> sweep, and user-extensible aliases.

## Problem

### P1 — Section presence is a raw substring test (issue #10)

`review_claude.py:182` decides presence with `if section_header in content` — `in` on the whole file.

- **False positives.** A file that mentions `## Testing` in prose or inside a fenced code block counts
  as having the section. Scaffolded files are the worst case: their YAML frontmatter literally lists
  every required header (`- header: "## Testing"`), so a freshly scaffolded empty project passes.
- **The report overstates what it measured.** `Present: 0 sections` asserts a content finding from a
  heading-name check. `gruntwork-lastmilefirst/CLAUDE.md` reported `Present: 0 / Missing: 6` while
  documenting its release process under `## CRITICAL: Version Bumping`.
- **`--suggest` compounds it**, generating stubs for sections that exist under other names.

Of 13 flagged files in the 2026-07-28 run, exactly one finding survived scrutiny — a genuinely absent
Gotchas section in 5 projects — and it was buried.

### P2 — Three sources disagree on where gotchas belong

| Source | Says gotchas go in |
|---|---|
| `skills/add-wisdom/SKILL.md:18`, `skills/parc/SKILL.md:319` | stack-wisdom |
| `skills/add-knowledge/SKILL.md` — "specific to how this project/client works" | stack-**knowledge** |
| `skills/review-claude/SKILL.md:100-102`, the templates, `plugins/lastmilefirst/README.md:25` | project CLAUDE.md |

No rule reconciles them. Writing three Gotchas sections on 2026-07-28 (griffith `4b934e1`,
lastmilefirst `9382ba5`, travel-skills `e545d5d`) required inventing one ad hoc.

### P3 — One Gotchas section serves two audiences

A trap that bites someone *changing* the repo and a trap that bites someone *deploying or using* it
are different content for different readers, currently piled into one table. This mirrors a split the
workspace already makes — `docs/` for users and deployers, `.claude/work/` for developers — so the
CLAUDE.md section should make it too.

## Scope

**In:** heading-scoped matching, honest report wording, the gotchas placement rule, the Gotchas split,
the template table schema.

**Out:** exact-match/alias-map machinery (see the v1.2 revision note for why); the content probe that
would separate "renamed" from "genuinely missing" (issue #10, bullet 3 — a heading with an empty body
still counts as present); user-extensible aliases; retrofitting existing files to the new table schema.

This plan **refs** issue #10 rather than closing it.

## Design

### Phase 1 — Heading-scoped matching

**1a. Extract real headings.** New helper in `review_claude.py`:

```python
def extract_headings(content: str) -> list[str]:
    """ATX headings only, casefolded. Fenced code blocks excluded."""
```

Track ``` and ~~~ fences and skip their contents. YAML frontmatter needs no special handling — its
`- header: "## Testing"` lines are not ATX headings and are already excluded.

**1b. Match by substring against headings, not against the file.**

```python
name = expected.lstrip("#").strip().casefold()
matched = any(name in h for h in headings)
```

This is deliberately the *same leniency* the tool has today, narrowed to real headings. That is the
whole fix for P1: it removes the false positives without breaking a single file that passes now.

Verified against the live workspace — every file that passes today still passes, including the three
the review rounds flagged as regression risks under exact matching:

| File | Heading | Satisfies |
|---|---|---|
| takesmanship | `### Deployment` | `## Deployment` |
| `~/Code/CLAUDE.md` | `## Core Philosophy: Compound Engineering` | `## Core Philosophy` |
| promptasaurus | `## Testing Strategy`, `## Deployment Instructions` | `## Testing`, `## Deployment` |

No normalization rules, no colon handling, no level rules — substring matching subsumes all of them.

**1c. A short alias list**, for genuine renames substring matching cannot reach:

```python
SECTION_ALIASES = {
    "## Gotchas":            ["Pitfalls", "Known Issues", "Troubleshooting"],
    "## Dev Gotchas":        ["Gotchas", "Pitfalls", "Known Issues", "Troubleshooting"],
    "## Deployment Gotchas": ["Gotchas", "Pitfalls", "Known Issues", "Troubleshooting"],
    "## Usage Gotchas":      ["Gotchas", "Pitfalls", "Known Issues", "Troubleshooting"],
    "## Quick Commands":     ["Commands"],
}
```

Five keys, not forty-two. Aliases are matched the same way (substring against headings), so
`## Common Pitfalls to Avoid` resolves through `Pitfalls` and `## Common Commands` through `Commands`.

Add an alias only when a real file needs it. The alias list is where wrong matches hide — substring
scoping cannot catch a bad alias, because a bad alias looks exactly like an intended win. Adjudicate
each against the canonical section's own description in `ARCHETYPE_SECTIONS`. (v1.2 carried
`Architecture` → `## Infrastructure`; it failed this test — Infrastructure means "cloud provider,
region, account details" — and is not in the list above.)

**1d. Three-state result.** `present` / `present_via_alias` / `missing`.

**1e. Reword the report at all three rendering sites.**

| Site | Change |
|---|---|
| `show_review_report` (~230-231) | `Missing: N sections` → `no heading found for: …`; alias hits render as `Gotchas → via "Common Pitfalls to Avoid" ✓` |
| the `--file` branch in `main()` (~374-385) | same vocabulary; its `if not review["missing"]` short-circuit must not print bare "has all expected sections" when sections matched only via alias |
| the summary counter in `main()` (~457) | `Files with gaps: N` → `Files with unmatched sections: N` |

The no-gap branch matters: a file whose sections all resolve via alias currently prints one
`All sections present ✓` line and is excluded from the gap list, so alias reliance is invisible
exactly where it is total.

**1f. `--suggest` skips alias-matched sections.**

**1g. Tests.** Add `skills/review-claude/tests/` following the existing `skills/audit-plugin/tests/`
pattern, covering the verification rows below. Small — the design is small.

### Phase 2 — Split Gotchas by audience

Replace the single `## Gotchas` requirement in `ARCHETYPE_SECTIONS`:

| Archetype | Gotchas sections |
|---|---|
| deployable | `## Dev Gotchas`, `## Deployment Gotchas` |
| usable | `## Dev Gotchas`, `## Usage Gotchas` |
| referenceable | `## Gotchas` (unchanged — a knowledge archive isn't deployed or invoked) |
| experimental | none (unchanged) |

The second name is archetype-specific because "deployment" is meaningless for a plugin and "usage" is
meaningless for a website. `ARCHETYPE_SECTIONS` already varies this way — Deployable gets
`## Deployment`, Usable gets `## Installation`.

**What goes where:**
- **Dev Gotchas** — hazards for someone changing this repo. "Editing the plugin cache instead of
  source; changes vanish on the next update."
- **Deployment / Usage Gotchas** — hazards for someone deploying, installing, or invoking it.
  "`claude plugin update` leaves the old version loaded until `/reload-plugins`."

**Migration is soft: a plain `## Gotchas` satisfies both halves** (via the aliases in 1c). This is the
one intentional many-to-one mapping — the undivided form covers both audiences, so splitting the
requirement must not newly flag the eleven projects that already have a Gotchas section. New projects
get the split from the templates; existing ones are nudged, not punished.

Verified on the live workspace: with the split plus the 1c aliases, **12 of 23 project files have
unmatched sections, down from 13, with no file newly flagged for Gotchas.**

Optionally retrofit the three sections written on 2026-07-28 — griffith and lastmilefirst are
entirely dev-facing, travel-skills is mixed. Not required.

### Phase 3 — Gotchas placement rule

Add to `skills/organize-claude/SKILL.md`; cross-reference from `review-claude/SKILL.md`,
`add-wisdom/SKILL.md`, and `add-knowledge/SKILL.md`:

> **Gotchas: CLAUDE.md, stack-wisdom, or stack-knowledge?**
> - **Project CLAUDE.md** — specific to *this* repo, needed in context while working here.
>   "Don't test against the Travel Agent calendar, it's wired to Flighty."
> - **stack-wisdom** — generalizes across projects. "osv-scanner 2.x needs `--no-ignore` or it
>   silently skips subdirectory lockfiles."
> - **stack-knowledge** — not a gotchas destination. Knowledge holds reference facts; a trap with a
>   symptom and a fix is wisdom or CLAUDE.md.
> - **Both** CLAUDE.md and wisdom when a repo-specific instance has a generalizable cause: actionable
>   form in CLAUDE.md, pattern in wisdom, linked.
>
> Test: *would this still be true in a different repo?* Yes → wisdom. No → CLAUDE.md.
> Then: *does it bite someone changing the repo, or someone running it?* → Dev vs Deployment/Usage.
>
> **If a project's gotchas live in stack-wisdom, keep a one-line section pointing at the wisdom
> entry.** The section stays required; the pointer satisfies it.

Qualify the three contradicting sources to point at this rule.

### Phase 4 — Templates

Four files carry the Gotchas table — name them explicitly, since the `project-*.md.template` glob
matches five and the natural "four archetypes" reading picks the wrong four:

- `project-claude.md.template` (~117) — the fallback for un-archetyped projects
- `project-deployable.md.template` (~96) — split into Dev + Deployment
- `project-usable.md.template` (~65) — split into Dev + Usage
- `project-referenceable.md.template` (~35) — stays single
- `project-experimental.md.template` — no Gotchas table; untouched

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
| 1 | Fenced code | `## Testing` only inside a ``` block → unmatched |
| 2 | Frontmatter | a scaffolded file's `- header: "## Testing"` line → unmatched |
| 3 | Prose | "## Installation" in a sentence → unmatched |
| 4 | Deeper level | takesmanship's `### Deployment` satisfies `## Deployment` |
| 5 | Qualified heading | `## Testing Strategy` satisfies `## Testing`; `## Core Philosophy: Compound Engineering` satisfies `## Core Philosophy` |
| 6 | Alias | `## Common Pitfalls to Avoid` satisfies a Gotchas section via `Pitfalls` |
| 7 | Split migration | a file with only `## Gotchas` satisfies both `## Dev Gotchas` and `## Deployment Gotchas` |
| 8 | Split, divided | a file with both split sections satisfies both, and neither is reported via alias |
| 9 | **No regressions** | full workspace run: no file gains an unmatched section it does not have today |
| 10 | Alias-only reporting | a file matching only via alias still prints its alias hits, including on the no-gap path |
| 11 | `--suggest` | no stub for an alias-matched section |
| 12 | organize-claude unaffected | scaffolding still emits all sections; `parse_template_frontmatter` consumers unchanged |

Row 9 is the one that matters. Substring scoping should make it trivially true — if it isn't, the
design drifted back toward exact matching.

## Risks

| Risk | Mitigation |
|---|---|
| **A wrong alias masks a real gap** | The only defense is per-alias adjudication against the canonical description (1c). Keep the list at five keys; add only when a real file needs it. |
| Lenient matching passes a loosely-related heading | Accepted. It is today's behavior, the report now describes what it checked, and a false pass is cheaper than the false-negative flood exact matching produced. |
| Splitting Gotchas flags existing projects | `## Gotchas` satisfies both halves (Phase 2). Verified: no file is newly flagged. |
| `archetypes.py` is shared with organize-claude | `SECTION_ALIASES` is a new module-level dict; the Gotchas split edits `ARCHETYPE_SECTIONS` values only. Verification 12 guards the consumers. |

## Open questions

1. Should a section match require a non-empty body? Currently no — leamo's `## Commands` body is
   `*(To be filled in as we build)*` and counts as present. Scope expansion beyond #10; deferred.
2. Should `--suggest` emit a rename hint toward the canonical name on alias matches?
3. Should user- and org-level headers get aliases, or is aliasing project-archetype-only?

## Deferred to follow-up issues

- **User-extensible aliases** (`section_aliases` in the shared config). Sound idea — every alias here
  comes from one workspace — but `setup_config` rebuilds the config wholesale so `--setup` would
  delete the key, merge semantics are undefined, and nothing documents the feature. Needs its own
  pass.
- **The content probe** that separates "renamed" from "genuinely missing" (issue #10, bullet 3).

## Sequencing

Phase 1 (code + tests) → Phase 2 (split) → Phase 4 (templates) → Phase 3 (docs). Single branch, single
PR, version bump to 0.21.0, `gh release create v0.21.0 --target main --latest` after merge per the
repo release checklist.

Issue #7 (TruffleHog / non-gitleaks backend) stays open and out of scope.
