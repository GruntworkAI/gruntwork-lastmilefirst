---
title: "feat: Unified LMF-stack Architecture"
type: feat
date: 2026-03-28
---

# Unified LMF-stack Architecture

## Overview

Replace the current per-org stack-wisdom repo pattern with a single per-user repository (LMF-stack) that mirrors the workspace directory structure. Each org gets a standardized set of directories for institutional knowledge: philosophy, strategy, wisdom, circuit-breakers, operatives, agents, and style.

This is a foundational architecture change that affects conventions, data migration, and plugin tooling. The result should be teachable, scriptable, and work universally for solo developers, contractors, team members, and LMF advisory clients.

## Problem Statement / Motivation

**Current state is ad-hoc and inconsistent:**
- `gruntwork-stack-wisdom` already acts as a universal repo — it holds CLAUDE.md sources for gruntwork, lastmilefirst.ai, AND waterfield — but its internal structure doesn't reflect this
- Flat, encoded directory naming (`org-gw-claude-file/`, `project-lmf-advisors-claude-file/`) is opaque and hard to navigate
- `organize-orgs` expects per-org repos (`{org}-stack-wisdom`, `{org}-operatives`) that don't exist and haven't been created
- Operatives repos are expected but have never been set up for any org
- No place for org philosophy, strategy, brand assets, or agent definitions
- The pattern can't be taught to LMF clients because it isn't formalized

**What we want:**
- One repo, one `git push`, all institutional knowledge versioned together
- Parallel structure to the workspace — intuitive, self-documenting
- Every org (including "personal") gets the same directory template
- Clear separation: plugin = tooling (how), stack = knowledge (what you know)
- Scriptable first-time setup for new users and LMF clients

## Proposed Solution

### Directory Structure

```
stack/                               # One git repo per user
│
├── personal/                            # Personal org (mandatory)
│   ├── CLAUDE.md                        # User-level preferences
│   │                                    # Symlinked → ~/work/code/CLAUDE.md
│   ├── philosophy/                      # Durable beliefs, values, principles
│   ├── strategy/                        # Time-bound goals, priorities, roadmap
│   ├── wisdom/                          # Hard-won patterns and solutions
│   ├── circuit-breakers/                # Stop signals for debugging loops
│   ├── operatives/                      # Private specialist personas
│   ├── agents/                          # Public/imported specialist definitions
│   └── style/
│       ├── code/                        # Naming conventions, linting configs
│       └── brand/                       # Colors, fonts, logos, design tokens
│
├── gruntwork/                           # Mirrors ~/work/code/gruntwork/
│   ├── CLAUDE.md                        # Org-level context
│   │                                    # Symlinked → ~/work/code/gruntwork/CLAUDE.md
│   ├── philosophy/
│   ├── strategy/
│   ├── wisdom/
│   ├── circuit-breakers/
│   ├── operatives/
│   ├── agents/
│   └── style/
│       ├── code/
│       └── brand/
│
├── lastmilefirst.ai/                    # Mirrors ~/work/code/lastmilefirst.ai/
│   └── (same structure)
│
└── waterfield/                          # Mirrors ~/work/code/Waterfield/
    └── (same structure)
```

### Local Workspace With Symlinks

```
~/work/                                  # Workspace root (NOT a git repo)
├── code/                                # All source repos
│   ├── CLAUDE.md                        # Symlink → ../stack/personal/CLAUDE.md
│   ├── personal/                        # Personal projects
│   │   └── ...
│   ├── gruntwork/                       # Org dir (NOT a git repo)
│   │   ├── CLAUDE.md                    # Symlink → ../../stack/gruntwork/CLAUDE.md
│   │   ├── gruntwork-remail/            # Project git repo (own remote)
│   │   │   ├── CLAUDE.md               # Regular file (portable, in project repo)
│   │   │   └── ...
│   │   └── gruntwork-leamo/             # Project git repo
│   │       └── ...
│   ├── lastmilefirst-ai/               # Org dir (normalized from lastmilefirst.ai)
│   │   ├── CLAUDE.md                    # Symlink → ../../stack/lastmilefirst-ai/CLAUDE.md
│   │   └── lmf-advisors/               # Project git repo
│   │       └── ...
│   └── waterfield/                      # Org dir (lowercased from Waterfield)
│       ├── CLAUDE.md                    # Symlink → ../../stack/waterfield/CLAUDE.md
│       └── client-project/              # Project git repo (client's GitHub)
│           └── ...
│
└── stack/                               # Git repo (github.com/{user}/stack)
    ├── personal/                        # Personal org (mandatory)
    │   ├── CLAUDE.md                    # Source for ~/work/code/CLAUDE.md
    │   └── (full org template)
    ├── gruntwork/
    │   ├── CLAUDE.md                    # Source for ~/work/code/gruntwork/CLAUDE.md
    │   └── (full org template)
    ├── lastmilefirst-ai/
    │   └── ...
    └── waterfield/
        └── ...
```

### Symlinks (Predictable Pattern)

Only code-root and org-level CLAUDE.md files are symlinked. Never into project git repos (breaks for other collaborators who don't have the stack).

```
~/work/code/CLAUDE.md                      → ../stack/personal/CLAUDE.md
~/work/code/gruntwork/CLAUDE.md            → ../../stack/gruntwork/CLAUDE.md
~/work/code/lastmilefirst-ai/CLAUDE.md     → ../../stack/lastmilefirst-ai/CLAUDE.md
~/work/code/waterfield/CLAUDE.md           → ../../stack/waterfield/CLAUDE.md
```

Formula: `~/work/code/{org}/CLAUDE.md → ../../stack/{org}/CLAUDE.md`
No exceptions — every org in code has a matching org in stack, including `personal/`.

## Technical Approach

### Key Design Decisions

#### 1. Everything scoped to an org — no top-level content

The `personal/` org is mandatory. There is no content at the LMF-stack root level. This means every piece of content has an org scope, eliminating ambiguity about "is this cross-org or uncategorized?"

#### 2. CLAUDE.md vs. stack directories

| | CLAUDE.md | Stack directories |
|---|---|---|
| **Loaded** | Every session, automatically | On demand, when searched |
| **Content** | One-liners, pointers, essential context | Detailed references, full write-ups |
| **Cost** | Expensive context — keep lean | Cheap to store, cheap to ignore |
| **Example** | "We use snake_case everywhere" | Full naming convention guide with 30 rules |

CLAUDE.md points to stack dirs: "For coding conventions see style/code/. For deployment runbooks see wisdom/."

#### 3. Directory purpose and access patterns

| Directory | Purpose | Lifespan | Access pattern |
|-----------|---------|----------|----------------|
| `philosophy/` | Beliefs, values, principles — the "why" behind decisions | Durable, rarely changes | Judgment calls, trade-offs, tone |
| `strategy/` | Goals, priorities, bets, roadmap themes | Time-bound (quarterly/yearly) | Prioritization, scope, "is this aligned?" |
| `wisdom/` | Hard-won patterns, solutions, lessons learned | Accumulates over time | Searched when solving problems |
| `circuit-breakers/` | Stop signals — symptoms that mean you're in a loop | Accumulates, updated on incidents | Checked automatically during debugging |
| `operatives/` | Private specialist personas with proprietary knowledge | Evolves with org knowledge | Consulted via `/run-consult-operative` |
| `agents/` | Public/imported specialist definitions | May be imported from plugins | Consulted via agent routing |
| `style/code/` | Naming conventions, linting configs, language idioms | Prescriptive, evolves slowly | Code review, generation |
| `style/brand/` | Colors, fonts, logos, CSS, design tokens | Per org identity | UI generation, design work |

#### 4. Operatives vs. agents

| | Operatives | Agents |
|---|---|---|
| **Visibility** | Private to you/your org | Public, shareable, importable |
| **Knowledge** | Proprietary domain context | General expertise |
| **Portability** | Tied to your org | Transferable across orgs |
| **Example** | "Knows our Leamo architecture" | "Reviews Rails with DHH conventions" |

#### 5. Philosophy vs. strategy

| | Philosophy | Strategy |
|---|---|---|
| **Lifespan** | Durable — rarely changes | Time-bound — quarterly, yearly |
| **Content** | Beliefs, values, principles | Goals, priorities, bets |
| **Claude uses it for** | Judgment calls, trade-offs | Prioritization, scope decisions |
| **Example** | "Build for compound returns" | "Q2 2026: Launch marketplace, acquire 10 beta users" |

Strategy entries should have dates in filename or frontmatter (e.g., `2026-q2-goals.md`) so tooling can distinguish current from stale.

#### 6. Plugin vs. stack separation

| In the plugin | In the stack |
|---------------|-------------|
| PARC workflow | Philosophy entries |
| Skills (organize, review, search) | Strategy documents |
| Hooks (session_start, overwatch) | Wisdom patterns |
| Expert persona definitions (public) | Operative definitions (private) |
| Templates and scaffolding scripts | Brand assets and style guides |
| Circuit breaker detection logic | Circuit breaker definitions |

The plugin *reads from* the stack. The stack doesn't need to know about the plugin.

#### 7. Project-level CLAUDE.md stays in project repos

Project CLAUDE.md files are regular files in their project git repos, not symlinked from LMF-stack. This ensures portability — anyone cloning the project gets the CLAUDE.md without needing LMF-stack.

Exception: solo/private projects where only you clone the repo may optionally symlink from LMF-stack for central management.

#### 8. GitHub / source control setup

- LMF-stack is **one private GitHub repo** per user
- Recommended remote: `github.com/{username}/stack` (or org-specific GitHub if preferred)
- All content is versioned together — one commit history, one backup
- `.gitignore` should exclude any local-only files (API keys, scratch notes)
- README.md at root explains the structure for new users and future-you

### Implementation Phases

#### Phase 0: Workspace Restructure (`~/Code/` → `~/work/`)

**Goal:** Move to the new workspace layout before creating the stack, so all paths are correct from day one.

**New layout:**
```
~/work/
├── code/                    # All source repos (was ~/Code/)
│   ├── personal/            # Personal projects (new)
│   ├── gruntwork/           # Unchanged
│   ├── lastmilefirst-ai/    # Renamed from lastmilefirst.ai/
│   └── waterfield/          # Renamed from Waterfield/
└── stack/                   # Institutional knowledge (new, created in Phase 2)
    ├── personal/
    ├── gruntwork/
    ├── lastmilefirst-ai/
    └── waterfield/
```

**Naming convention:** All lowercase everywhere. Dots normalized to hyphens. `lastmilefirst.ai/` → `lastmilefirst-ai/`, `Waterfield/` → `waterfield/`. Code and stack org dirs always match exactly.

**Tasks:**

- [ ] Verify no tools or configs depend on `~/Code/` path (shell aliases, IDE projects, cron jobs, etc.)
- [ ] Create `~/work/` directory
- [ ] Move `~/Code/` contents → `~/work/code/` (preserve git repos, symlinks break intentionally)
- [ ] Rename org dirs to lowercase/normalized:
  - `lastmilefirst.ai/` → `lastmilefirst-ai/`
  - `Waterfield/` → `waterfield/`
- [ ] Create `~/work/code/personal/` for personal projects
- [ ] Update shell profile if any aliases reference `~/Code/`
- [ ] Update lastmilefirst plugin workspace detection in `session_start.py` (`~/Code/` → `~/work/code/`)
- [ ] Update user-level CLAUDE.md: workspace organization section, project directory mapping table (all paths change from `~/Code/` to `~/work/code/`)
- [ ] Update org-level CLAUDE.md files if they reference workspace paths
- [ ] Update auto-memory `MEMORY.md` and any memory files with hardcoded paths
- [ ] Remove old symlinks (they'll point to `~/Code/` which no longer exists)
- [ ] Do NOT create new symlinks yet — that's Phase 2 with the new stack structure
- [ ] Verify Claude Code session starts cleanly from `~/work/code/`
- [ ] Commit plugin and CLAUDE.md changes

**Rollback:** `mv ~/work/code/* ~/Code/` and revert plugin changes. Low risk since git repos are self-contained.

#### Phase 1: Finalize Conventions and Document

**Goal:** Lock down naming, structure, and best practices before any code changes.

**Tasks:**

- [ ] Finalize stack directory name: `stack` (confirmed — lives at `~/work/stack/`)
- [ ] Finalize personal org name: `personal/` (confirmed)
- [ ] Document the standard org directory template (the 8 dirs)
- [ ] Document the CLAUDE.md vs. stack dir principle ("every session" vs "on demand")
- [ ] Document the symlink convention (formula, exceptions)
- [ ] Document philosophy vs. strategy distinction with examples
- [ ] Document operatives vs. agents distinction with examples
- [ ] Document strategy entry dating convention (frontmatter with timeframe)
- [ ] Write README.md template for new stack repos
- [ ] Write per-directory README.md templates (what goes here, examples)
- [ ] Define `.gitignore` for stack repos
- [ ] Define org.json v2 schema that points to LMF-stack subdir instead of separate repo
- [ ] Document the GitHub setup recommendation (private repo, naming)
- [ ] Create a "LMF-stack quickstart" guide suitable for LMF clients

**Deliverables:**
- `stack/README.md` template
- Per-directory README templates
- Updated org.json schema
- Quickstart guide

#### Phase 2: Migrate gruntwork-stack-wisdom → LMF-stack

**Goal:** Restructure existing content into the new layout without losing git history or breaking symlinks.

**Pre-migration inventory:**

Current `gruntwork-stack-wisdom` content to migrate:

| Current location | New location |
|-----------------|-------------|
| `claude/claude-md-files/user-claude-file/CLAUDE.md` | `personal/CLAUDE.md` |
| `claude/claude-md-files/org-gw-claude-file/CLAUDE.md` | `gruntwork/CLAUDE.md` |
| `claude/claude-md-files/org-lmf-claude-file/CLAUDE.md` | `lastmilefirst.ai/CLAUDE.md` |
| `claude/claude-md-files/org-wti-claude-file/CLAUDE.md` | `waterfield/CLAUDE.md` |
| `claude/claude-md-files/project-lmf-advisors-claude-file/CLAUDE.md` | `lastmilefirst.ai/projects/LMF-Advisors/CLAUDE.md` (or stays in project repo) |
| `stack-wisdom/*.md` (14 entries) | Triage per-org: `gruntwork/wisdom/`, `personal/wisdom/`, etc. |
| `circuit-breakers/*.md` | Triage per-org or `personal/circuit-breakers/` |
| `claude/claude-skills/*` | Stays in plugin (not stack content) |
| `claude/claude-commands/*` | Stays in plugin (not stack content) |
| `plans/` | Archive or move to relevant org `strategy/` |
| `setup-scripts/` | Stays in plugin or archive |
| `archive/` | Archive (don't migrate) |

**Migration tasks:**

- [ ] Create new `stack` repo locally at `~/work/stack/` with the full directory structure
- [ ] Initialize git, create GitHub remote
- [ ] Move CLAUDE.md files to new org-scoped locations
- [ ] Triage and move wisdom entries to appropriate org dirs
- [ ] Triage and move circuit-breaker entries to appropriate org dirs
- [ ] Move any philosophy-worthy content from CLAUDE.md into `philosophy/` dirs
- [ ] Move any strategy-worthy content into `strategy/` dirs
- [ ] Extract brand assets (if any) into `style/brand/` dirs
- [ ] Extract code style docs (e.g., snake_case convention) into `style/code/` dirs
- [ ] Create `personal/` org with user-level content
- [ ] Update all symlinks to point to new locations
  - `~/work/code/CLAUDE.md` → `stack/personal/CLAUDE.md`
  - `~/work/code/gruntwork/CLAUDE.md` → `../stack/gruntwork/CLAUDE.md`
  - `~/work/code/lastmilefirst.ai/CLAUDE.md` → `../stack/lastmilefirst.ai/CLAUDE.md`
  - `~/work/code/Waterfield/CLAUDE.md` → `../stack/waterfield/CLAUDE.md`
- [ ] Verify all symlinks resolve correctly
- [ ] Verify Claude Code loads CLAUDE.md files correctly at each level
- [ ] Decide fate of `gruntwork-stack-wisdom`: archive, redirect, or delete
- [ ] Update workspace CLAUDE.md project directory mapping to include LMF-stack
- [ ] Commit and push to GitHub

**Rollback plan:** Keep `gruntwork-stack-wisdom` intact until migration is verified. Symlinks can be reverted in one command.

#### Phase 3: Update lastmilefirst Plugin

**Goal:** Plugin scaffolds, validates, and searches the new LMF-stack structure.

**3a. Update org.json schema and template**

Current org.json:
```json
{
  "name": "gruntwork",
  "operatives": { "repo": "gruntwork-operatives" },
  "stack_wisdom": { "repo": "gruntwork-stack-wisdom" }
}
```

New org.json (v2):
```json
{
  "name": "gruntwork",
  "stack": {
    "repo": "stack",
    "org_dir": "gruntwork"
  }
}
```

- [ ] Define org.json v2 schema
- [ ] Support both v1 and v2 during transition (read old format, recommend upgrade)
- [ ] Update org.json template in `plugins/lastmilefirst/templates/`

**3b. Update session_start.py / Overwatch**

- [ ] Update `check_org_infrastructure()` to look for LMF-stack instead of per-org repos
- [ ] Check for stack repo existence
- [ ] Check for org subdir within LMF-stack
- [ ] Check for required dirs within org subdir (philosophy, wisdom, etc.)
- [ ] Remove alerts for missing `{org}-operatives` and `{org}-stack-wisdom` repos
- [ ] Add alert for missing stack repo with setup recommendation
- [ ] Add alert for org present in workspace but missing from LMF-stack

**3c. Implement organize-orgs script**

Currently organize-orgs has SKILL.md but no implementation. Build it with four distinct modes:

**Core infrastructure:**

- [ ] `scripts/organize_orgs.py` — main implementation
- [ ] `--audit` flag: report only, no changes
- [ ] `--org {name}` flag: set up a specific org
- [ ] `--new {name}` flag: create a new org from scratch
- [ ] `--setup` flag: new-machine mode (create symlinks for existing LMF-stack)
- [ ] `--migrate` flag: migrate from old gruntwork-stack-wisdom structure

**Mode 1: First-time setup (no LMF-stack exists)**

- [ ] Create stack repo at `~/work/stack/`
- [ ] Initialize git repo
- [ ] Scaffold `personal/` org with full directory template
- [ ] Ask about additional orgs (scan workspace for org-like dirs)
- [ ] Create org dirs with full template structure
- [ ] Create symlinks from workspace/org to LMF-stack
- [ ] **Guided CLAUDE.md creation:** Walk user through customizing the org CLAUDE.md template (this is the one file that must be correct for Claude to work well)
- [ ] **Optional brand quick-win:** "Do you already have brand colors, logo, or fonts? I can drop those in style/brand/ now."
- [ ] Generate root README.md from template

**Mode 2: Add org (LMF-stack exists, adding new org)**

- [ ] Create org dir with all 8 subdirs
- [ ] Generate per-directory README.md guides (see Content Onboarding below)
- [ ] Scaffold CLAUDE.md from org template
- [ ] **Guided CLAUDE.md customization:** Walk through key sections
- [ ] Create symlink from workspace org dir to LMF-stack
- [ ] Commit to stack repo

**Mode 3: New machine setup (LMF-stack cloned, no symlinks)**

- [ ] Detect LMF-stack exists but symlinks are missing
- [ ] Read LMF-stack directory to discover orgs
- [ ] For each org, check if corresponding workspace dir exists
- [ ] Create symlinks for orgs that exist in workspace
- [ ] Warn (don't error) for orgs not found in workspace
- [ ] Report summary: "Created N symlinks, skipped M orgs (not in workspace)"

**Mode 4: Migration (old structure → LMF-stack)**

- [ ] Detect `{org}-stack-wisdom` repos in workspace
- [ ] Map old structure to new (see Phase 2 migration table)
- [ ] Copy/move content to LMF-stack locations
- [ ] Re-point symlinks from old paths to new paths
- [ ] Validate all symlinks resolve
- [ ] Report summary with rollback instructions
- [ ] Keep old repo intact until user confirms (don't delete)

**Content onboarding approach:**

Each directory gets a `README.md` that doubles as a guide:
- What goes here (one paragraph)
- Examples of good entries
- How to add new content (which skill to use, or manual)
- Links to related skills (`/run-add-wisdom`, `/compound`, etc.)

The setup creates structure + guides. Only CLAUDE.md gets guided content creation during setup. Everything else (philosophy, strategy, wisdom, style) accumulates organically over time through daily skill usage (`/compound`, `/run-add-wisdom`, `/run-consult-operative`, etc.).

Per-directory README.md templates needed:
- [ ] `philosophy/README.md` — "Your durable beliefs and values. Add entries when you articulate why you make the choices you do."
- [ ] `strategy/README.md` — "Time-bound goals and priorities. Date your entries. Review quarterly."
- [ ] `wisdom/README.md` — "Hard-won patterns. Use `/run-add-wisdom` or `/compound` after solving tricky problems."
- [ ] `circuit-breakers/README.md` — "Stop signals. Add when you catch a debugging loop that should have been caught earlier."
- [ ] `operatives/README.md` — "Private specialist personas. Use `/run-create-operative` to build one."
- [ ] `agents/README.md` — "Public/imported specialists. Can be shared across orgs or imported from others."
- [ ] `style/code/README.md` — "Naming conventions, linting configs, language idioms for this org."
- [ ] `style/brand/README.md` — "Colors, fonts, logos, design tokens. Drop assets here for Claude to reference during UI work."

**3d. Update search and add skills**

- [ ] Update `search-wisdom` to search `stack/{org}/wisdom/` instead of `{org}-stack-wisdom/stack-wisdom/`
- [ ] Update `add-wisdom` to write to `stack/{org}/wisdom/`
- [ ] Add `search-philosophy` or extend search to cover philosophy and strategy dirs
- [ ] Update `consult-operative` to find operatives in `stack/{org}/operatives/`
- [ ] Update `create-operative` to write to `stack/{org}/operatives/`

**3e. Update organize-claude**

- [ ] Update CLAUDE.md source detection to look in LMF-stack
- [ ] Update symlink creation to point to LMF-stack paths

**3f. Update review-claude**

- [ ] Update to validate that CLAUDE.md sources in LMF-stack match expected org template
- [ ] Add checks for recommended stack dirs (philosophy, wisdom, etc.)

**3g. Update compound skill**

- [ ] When capturing a new learning via `/compound`, route to correct `stack/{org}/wisdom/`

## Resolved Design Decisions (from SpecFlow Analysis)

All open questions have been resolved through discussion. Decisions are recorded here for reference.

| # | Question | Decision |
|---|----------|----------|
| Q1 | Where does the stack repo live? | `~/work/stack/` — peer to `~/work/code/` under workspace root |
| Q2 | How do skills discover the stack? | Convention-based: walk up to find `~/work/`, then `stack/` is always a sibling of `code/`. Override via org.json v2 for non-standard setups. |
| Q3 | How does cross-org wisdom work? | Cross-org wisdom lives in `personal/wisdom/`. Search always includes `personal/` regardless of current org. |
| Q4 | Operatives: stack vs `~/.claude/operatives/`? | Stack is source of truth. Migrate existing operatives. `~/.claude/operatives/` symlinks to `stack/personal/operatives/` for backward compatibility. |
| Q5 | Case sensitivity in org dirs? | **All lowercase everywhere** — both stack and workspace dirs. `Waterfield/` → `waterfield/`, `lastmilefirst.ai/` → `lastmilefirst-ai/`. Rename workspace dirs during Phase 0. |
| Q6 | Multi-machine / reconnecting symlinks? | Not a separate mode. `organize-orgs` detects stack exists but symlinks are missing, and offers to create them as part of normal flow. |
| Q7 | Non-wisdom content in gruntwork-stack-wisdom? | `gruntwork-stack-wisdom` stays as a project repo under `~/work/code/gruntwork/`. Only CLAUDE.md sources and wisdom/circuit-breaker content move to the stack. Everything else (`.claude/work/`, plans, archive, setup-scripts) stays in that repo. |
| Q8 | LMF client repo ownership? | Client gets their own stack repo on their GitHub. Your knowledge about them goes in your stack under their org dir. Their institutional knowledge goes in theirs. |
| Q9 | Philosophy/strategy: context or on-demand? | On-demand search, like wisdom. CLAUDE.md gets a **short paragraph per philosophy entry** (2-3 sentences — the belief and why it matters). Full articulations live in `philosophy/`. |
| Q10 | Special characters in org names? | Normalize: dots → hyphens, all lowercase. `lastmilefirst.ai` → `lastmilefirst-ai`. 1:1 mapping between code and stack dirs. |

### Additional decisions from discussion:

- **`personal/` org exists in both code and stack.** `~/work/code/personal/` holds personal projects. `~/work/stack/personal/` holds personal knowledge. Every stack org maps 1:1 to a code org with no exceptions.
- **Workspace restructure is Phase 0.** `~/Code/` → `~/work/code/` before any stack work begins, so all paths are correct from day one.
- **All structural dirs are lowercase:** `work/`, `code/`, `stack/`, `personal/`, org names. Only exception: none.
- **No setup wizard needed.** `/run-organize-orgs` with Claude as the conversational layer IS the setup experience. A quickstart doc covers the concept for self-service users.

## Alternative Approaches Considered

**1. Keep per-org repos (status quo)**
- Rejected: Already not working — repos don't exist, the pattern hasn't been adopted, and gruntwork-stack-wisdom is already serving as a universal repo informally.

**2. Per-org repos but actually create them**
- Rejected: More repos to manage, more git remotes, more things to push. Doesn't work well for client orgs where you don't control infrastructure.

**3. No personal org — top-level content is cross-org**
- Rejected: Creates ambiguity about whether top-level content is "cross-org" or "uncategorized." Forcing `personal/` keeps everything scoped.

**4. Store operatives in plugin, not stack**
- Rejected: Operatives contain proprietary domain knowledge specific to your org. They're knowledge, not tooling. They belong with wisdom, philosophy, and strategy.

## Acceptance Criteria

### Functional Requirements

- [ ] stack repo exists with documented directory structure
- [ ] All existing CLAUDE.md files migrated and symlinked to new locations
- [ ] All existing wisdom entries migrated to appropriate org dirs
- [ ] `personal/` org exists with user-level content
- [ ] All org dirs have the standard 8-directory template
- [ ] Symlinks resolve correctly at workspace root and all org levels
- [ ] Claude Code loads CLAUDE.md files correctly at each hierarchy level

### Plugin Requirements

- [ ] `organize-orgs` has a working implementation script
- [ ] `organize-orgs` can create a new LMF-stack from scratch (first-time setup)
- [ ] `organize-orgs` can add a new org to an existing LMF-stack
- [ ] `organize-orgs` can audit and report gaps
- [ ] Overwatch detects missing LMF-stack and missing org dirs
- [ ] `search-wisdom` finds entries in new locations
- [ ] `add-wisdom` writes to new locations
- [ ] `consult-operative` and `create-operative` use new locations
- [ ] org.json v2 schema works; v1 still readable during transition

### Quality Gates

- [ ] All existing symlinks verified after migration
- [ ] Claude Code session start works correctly with new structure
- [ ] Overwatch alerts are accurate (no false positives from old pattern)
- [ ] Plugin version bumped (marketplace.json, plugin.json, README.md)
- [ ] README.md in LMF-stack explains structure clearly
- [ ] Quickstart guide tested with a fresh setup scenario

## Dependencies & Prerequisites

- Current `gruntwork-stack-wisdom` content must be inventoried before migration
- Plugin source must be edited in `~/work/code/gruntwork/gruntwork-marketplace/plugins/lastmilefirst/` (not cache)
- Git pull plugin source before making changes
- Plugin version bump required (coordinate with any other pending changes)

## Risk Analysis & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Broken symlinks after migration | Medium | High — Claude loses context | Keep old repo intact until verified. Script symlink creation. |
| Plugin reads wrong paths during transition | Medium | Medium — false Overwatch alerts | Support v1 and v2 org.json simultaneously |
| Wisdom entries mis-triaged to wrong org | Low | Low — can move later | Review triage decisions before committing |
| LMF clients confused by structure | Low | Medium — adoption friction | Quickstart guide, scripted setup |
| Strategy entries go stale without cleanup | Medium | Low — misleading context | Date convention in filenames, periodic review |

## Future Considerations

- **Shared/team stack-wisdom:** A team could have their own LMF-stack (or equivalent) that complements personal ones. The plugin could support reading from multiple stacks.
- **Stack search across all orgs:** `/run-search-wisdom` could optionally search all orgs, not just the current one.
- **Stack export/import:** Export an org's agents or wisdom for sharing. Import public agent definitions from a registry.
- **Strategy lifecycle:** Tooling to flag stale strategy entries and prompt for refresh (quarterly review).
- **Operative promotion:** Graduate a private operative to a public agent when the knowledge becomes generalizable.
- **Project-level stack dirs:** If a project accumulates enough wisdom, it could get its own wisdom/circuit-breakers dirs within `stack/{org}/projects/{project}/`.

## References & Research

### Internal References

- Current stack-wisdom structure: `~/work/code/gruntwork/gruntwork-stack-wisdom/`
- Plugin source: `~/work/code/gruntwork/gruntwork-marketplace/plugins/lastmilefirst/`
- organize-orgs SKILL.md: `plugins/lastmilefirst/skills/organize-orgs/SKILL.md`
- session_start.py org checks: `plugins/lastmilefirst/hooks/scripts/session_start.py:360-394`
- org.json template: `plugins/lastmilefirst/templates/org.json`
- CLAUDE.md symlink sources: `gruntwork-stack-wisdom/claude/claude-md-files/`

### Design Decisions From This Session

- Parallel workspace structure chosen over flat/encoded naming
- `personal/` org mandatory — no top-level content
- Philosophy vs strategy as separate dirs (durable vs time-bound)
- Operatives (private) vs agents (public) as separate dirs
- Style splits into code/ and brand/
- Plugin = tooling, stack = knowledge
- Project CLAUDE.md stays in project repos for portability
