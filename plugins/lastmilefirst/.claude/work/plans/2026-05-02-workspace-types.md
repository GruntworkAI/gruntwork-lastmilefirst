---
title: Workspace Directory Type Taxonomy
status: draft
date: 2026-05-02
author: Fish (with Claude)
audience: lastmilefirst plugin contributors
related:
  - skills/overwatch
  - skills/scan-secrets
  - skills/organize-claude
  - skills/organize-orgs
---

# Workspace Directory Type Taxonomy

## Problem

Today the lastmilefirst plugin treats every directory under the user's workspace root (`~/Code/`) as an "org" subject to the same hygiene standards: each org needs a `CLAUDE.md`, each project needs a `CLAUDE.md`, and everything gets secret-scanned.

That assumption breaks for two real cases already in Fish's workspace:

- **`~/Code/drafts/`** — a personal scratch directory for draft artifacts. Not an org. Not a place where org/project CLAUDE.md or review hygiene applies.
- **`~/Code/every/`** — a container for cloned external (third-party) repos pulled down for local use. Fish doesn't maintain those projects, so the project-level CLAUDE.md requirement does not apply. Secret scanning *does* still apply (a leak from Fish's local copy is still Fish's leak), but other hygiene checks should be skipped.

Today both cases produce false-positive Overwatch alerts ("project missing CLAUDE.md", "needs review") that the user has to mentally filter every session. The system should encode the distinction instead of forcing the user to.

## Goals

1. **One taxonomy** that covers Fish's current four directory types and is extensible to client engagements that come and go.
2. **Per-directory marker file** at the org root so the convention travels with the directory and survives across machines / cloud-sync / future workspace moves (the LMF-stack epic is in flight; org dirs may move to `~/work/code/`).
3. **Skill-by-skill behavior changes** so the four affected skills (overwatch, scan-secrets, organize-claude, organize-orgs) all honor the marker.
4. **Backward-compatible default** — no marker = treat as Studio, so existing orgs (gruntwork, lastmilefirst.ai) continue to work without any change.

## Non-goals

- **Per-project markers.** Org-level marker only for v1. Project-level types (e.g., experimental vs deployable) are already handled by `organize-claude` archetypes.
- **A general-purpose `.claude/` config directory at the org root.** This spec defines exactly one marker file. If we accumulate more org-level config later, we can roll it into a `.claude-workspace.toml` directory or YAML at that point.
- **Cross-machine sync of the marker.** The marker lives in the directory; if the directory is in Dropbox/iCloud, it syncs. If it's not, it doesn't. Out of scope for this spec.

## The four types

| Type | Examples | What it is | CLAUDE.md required? | Secret scan? | Review hygiene? |
|------|----------|------------|---------------------|--------------|-----------------|
| **Studio** *(default)* | `gruntwork/`, `lastmilefirst.ai/` | Original work owned and shipped by Fish | Yes (org + project) | Yes | Yes |
| **Client** | (formerly `Waterfield/`) | Engagement-based work; Fish owns the work product while engaged | Yes while active; archived when paused | Yes | Yes |
| **External** | `every/` | Cloned third-party code Fish does not maintain | No | Yes (local-leak risk is still real) | No |
| **Scratch** | `drafts/` | Personal working surface, ephemeral artifacts | No | No (configurable) | No |

**Studio is the default** so that any org without a marker behaves exactly as it does today.

## The `.claude-workspace` marker

A YAML file dropped at the org root (e.g., `~/Code/every/.claude-workspace`).

### Schema

```yaml
# Required
type: studio | client | external | scratch

# Optional human-readable note (1 line) shown in Overwatch summaries and skill output
note: ""

# Optional behavior overrides (each field defaults per type — see table below)
claude_md: required | optional | skip
secret_scan: true | false
review: required | skip

# Optional metadata for Client / External
# - For Client: useful for archival decisions
# - For External: useful for tracking why the third-party repo is here
status: active | paused | archived   # Client only
upstream: ""                          # External only — URL of the upstream repo
```

### Type defaults

| Field | Studio | Client | External | Scratch |
|-------|--------|--------|----------|---------|
| `claude_md` | `required` | `required` | `skip` | `skip` |
| `secret_scan` | `true` | `true` | `true` | `false` |
| `review` | `required` | `required` | `skip` | `skip` |

Per-org `claude_md` / `secret_scan` / `review` overrides win when present.

### Validation

- `type:` is required and must be one of the four enum values.
- `claude_md` / `secret_scan` / `review` must match their enum / boolean shapes if present.
- `status:` is only meaningful when `type: client`; ignored otherwise (warn, don't error).
- `upstream:` is only meaningful when `type: external`; ignored otherwise (warn, don't error).
- Unknown top-level keys: warn and ignore (forward-compatible).

### Discovery

Skills look for `<workspace>/<org>/.claude-workspace`. If found:

1. Parse YAML; on parse error, log warning and treat as Studio default (don't fail loudly — a broken marker is still better than blocking the workflow).
2. Apply type defaults, then layer field overrides.
3. Use the resolved config for all per-skill decisions below.

If the file is missing entirely, the org is treated as Studio (current behavior).

## Skill-by-skill behavior

### `overwatch`

State file already tracks per-org and per-project status (v2 format, per memory). Add to the per-org record:
- `workspace_type:` — populated from marker, defaults to `studio`
- `claude_md_check:` — `applicable` | `not_applicable` (driven by resolved `claude_md`)
- `secret_scan_check:` — `applicable` | `not_applicable`
- `review_check:` — `applicable` | `not_applicable`

Session-start summary lines change:
- "10/22 missing CLAUDE.md" becomes "10/N missing CLAUDE.md (M orgs not applicable)" so the denominator reflects only orgs where the check applies.
- External and scratch dirs no longer appear in CLAUDE.md / review counts.
- An External org with `secret_scan: true` (the default) still appears in scan-freshness counts.

### `scan-secrets`

`--all` mode (`scan_workspace`) currently walks every `~/Code/{org}/{project}/` with `.git/`. Update:
- For each org, resolve the marker and check `secret_scan`. If `false`, skip the entire org subtree.
- Print one-line per skipped org so the user sees what was excluded: `every/* (external — secret_scan disabled)` or `drafts/* (scratch — secret_scan disabled)`.

Single-repo scan (default mode) is unaffected — if the user explicitly cd's in and runs the scan, honor that intent.

### `organize-claude`

`scan_orgs(workspace)` (organize_claude.py:50) currently returns every non-hidden subdir as an org. Update:
- Continue to enumerate all subdirs.
- For each, resolve the marker.
- If resolved `claude_md == skip`, exclude the org from "missing CLAUDE.md" findings.
- Still surface "missing CLAUDE.md at the *org* level" for `external` orgs that the user wants tagged with a minimal `CLAUDE.md` describing what's there — but only if `claude_md == required`. With the default of `skip` for External, this is opt-in.

### `organize-orgs`

When the user runs `/run-organize-orgs` for a new org:
- Detect missing marker; ask the user which of the four types this is.
- Write the marker before scaffolding any further files.
- Skip all subsequent scaffolding (CLAUDE.md, config, etc.) for `scratch` and `external` types.

### `review-claude` / `review-project`

Both currently iterate orgs/projects assuming Studio rules. Update:
- Skip review entirely for orgs where resolved `review == skip`.
- Print one-line per skipped org for transparency.

(Lower priority than the four above; can ship in a follow-up.)

## Migration / rollout

### Phase 0 — spec lock (this doc)

User reviews; we adjust the spec. No code changes.

### Phase 1 — schema + reader library

- New module `lastmilefirst/scripts/workspace_types.py` (or similar shared location):
  - `load_org_marker(org_path: Path) -> ResolvedConfig`
  - Type defaults table + override resolution
  - YAML parse with safe failure
- Unit tests for the resolver (golden cases per type, override behavior, unknown-key warnings).

### Phase 2 — wire skills

- Update `scan-secrets` `scanner.scan_workspace`
- Update `organize-claude` `scan_orgs` + the missing-CLAUDE.md count surface
- Update `overwatch` summary builder + state-file schema bump (v3 format if the per-org additions warrant it — otherwise additive fields under v2)

### Phase 3 — drop markers in Fish's workspace

- `~/Code/drafts/.claude-workspace` → `type: scratch`
- `~/Code/every/.claude-workspace` → `type: external`
- (Existing orgs keep working without markers; can be backfilled with explicit `type: studio` later if we want explicitness.)

### Phase 4 — update workspace docs

- `~/Code/CLAUDE.md` workspace organization section: add a paragraph explaining the four types and the marker convention.
- Plugin `README.md` (if relevant): document the marker schema.

### Phase 5 — capture in stack-wisdom

- The taxonomy itself is a reusable pattern (any developer with both first-party and cloned/scratch dirs benefits). Capture as a wisdom doc once the rollout is stable.

## Open questions

1. **Should `studio` and `client` collapse to one type?** They have identical hygiene defaults today. Keeping them separate gives Client a `status: paused | archived` field that matters for the Waterfield-style on-again / off-again pattern. Lean: keep separate; the cost is one enum value.
2. **Should the marker also live at the *user* level** (`~/Code/.claude-workspace`) for declaring workspace-wide defaults? Probably yes long-term, but out of scope here — the existing `~/Code/CLAUDE.md` already serves this purpose informally.
3. **Should `claude_md: optional` be removed?** It's a middle ground that could just collapse to `skip`. Lean: keep, in case future archetypes need a "we'd like one but it's not flagged as missing" middle state.
4. **External + secret-scan: do we want to scan history or only current tree?** Currently `--all` scans full history. For an external clone where Fish doesn't control the upstream, history scan is noise (any past leak is the upstream's problem). But: the local copy *includes* the history, and a leaked credential in history is still a credential. Lean: full history; document the rationale.

## Risks

- **Marker drift across machines.** If Fish has the same workspace on multiple machines and the marker is in `.gitignore` or not synced, behavior diverges. Mitigation: document that markers should be either committed (for Studio/Client orgs that have their own git repo) or kept in a synced location.
- **Forward-compat with LMF-stack restructure.** The active LMF-stack epic (per memory) plans to move `~/Code/` → `~/work/{code,stack}/`. Markers move with their directories — no special handling needed, but the spec should mention this so the eventual move planner doesn't need to special-case marker handling.
- **Plugin install/update path.** Markers are user-data, not plugin-shipped. Plugin updates must never overwrite or touch them. (Same model as `org_secret_formats.toml`.)

## Acceptance criteria

- [ ] User can drop `.claude-workspace` with `type: scratch` in `~/Code/drafts/` and Overwatch stops flagging it.
- [ ] User can drop `.claude-workspace` with `type: external` in `~/Code/every/` and `organize-claude` stops flagging missing project CLAUDE.md, while `scan-secrets --all` continues to scan it.
- [ ] Existing orgs without markers behave identically to today.
- [ ] Overwatch session-start summary shows accurate denominators (e.g., "10/19 missing CLAUDE.md (3 orgs not applicable)").
- [ ] `organize-orgs` prompts for type when scaffolding a new org.
- [ ] Spec is captured in stack-wisdom once rollout is stable.

## Change log

- **2026-05-02:** Draft v0 written.
