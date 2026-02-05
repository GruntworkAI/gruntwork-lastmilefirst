---
name: organize-orgs
description: Set up and manage org-level infrastructure - config, operatives, and stack-wisdom repos
---

# Organize Orgs

Set up and manage your orgs - the top-level containers for related projects, shared operatives, and institutional wisdom.

## What Are Orgs?

An **org** (organization) is a grouping of related projects that share:
- **Context** - Common tech stack, deployment patterns, conventions
- **Operatives** - AI specialists tuned to your domain
- **Wisdom** - Patterns and lessons learned over time

### Everyone Has Orgs

Even solo developers have orgs - they just might not call them that:

| You Might Call It | It's An Org Because... |
|------------------|------------------------|
| "My side projects" | Shared conventions, your personal stack |
| "Work stuff" | Company standards, team knowledge |
| "Client X projects" | Client-specific domain, their patterns |
| "Learning/experiments" | Different risk tolerance, more freedom |

### "Personal" Is An Org

Your personal projects are an org - you're a team of one (plus your AI agents). You have:
- Your preferred tech stack
- Your coding conventions
- Operatives tuned to your style
- Wisdom from your past debugging sessions

Don't skip org setup for personal projects. The infrastructure pays dividends.

## Recommended Structure

```
~/Code/                          # Workspace (security boundary)
├── CLAUDE.md                    # Workspace preferences
│
├── personal/                    # Your personal org
│   ├── CLAUDE.md                # Your standards
│   ├── .claude/
│   │   └── org.json             # Org config
│   ├── personal-operatives/     # Your specialists (git repo)
│   └── personal-stack-wisdom/   # Your hard-won insights (git repo)
│
├── work/                        # Primary work org
│   ├── CLAUDE.md                # Team standards
│   ├── .claude/
│   │   └── org.json
│   ├── work-operatives/         # Team specialists
│   └── work-stack-wisdom/       # Team knowledge
│
└── client-acme/                 # Client-specific org
    ├── CLAUDE.md                # Client conventions
    ├── .claude/
    │   └── org.json
    ├── client-acme-operatives/  # Client domain experts
    └── client-acme-stack-wisdom/# Client-specific patterns
```

## What This Skill Does

### 1. Explains Orgs
On first run (or with `--explain`), walks through what orgs are and why they matter.

### 2. Audits Existing Orgs
Scans workspace for org directories and checks infrastructure:
- Does it have `.claude/org.json`?
- Does it have an operatives repo?
- Does it have a stack-wisdom repo?

### 3. Scaffolds Missing Infrastructure
Creates what's missing:
- `.claude/org.json` from template
- `[org]-operatives/` as git repo with README
- `[org]-stack-wisdom/` as git repo with structure

### 4. Bootstraps New Users
For users without any orgs, offers to create `personal/` and `work/`.

## Usage

```bash
# Full interactive setup (recommended for first time)
/run-organize-orgs

# Explain orgs without making changes
/run-organize-orgs --explain

# Audit only (no changes)
/run-organize-orgs --audit

# Set up a specific org
/run-organize-orgs --org personal
/run-organize-orgs --org work

# Create a new org
/run-organize-orgs --new client-acme
```

## Interactive Flow

### First-Time User

```
$ /run-organize-orgs

============================================================
WHAT ARE ORGS?
============================================================

An org is a container for related projects. Think of it as a
boundary around work that shares context:

  • "personal" - Your side projects, experiments, tools
  • "work" - Your job, company projects, team code
  • "client-x" - A specific client's projects

Even if you work alone, you have orgs. Your personal projects
share your preferences, your patterns, your hard-won lessons.
Setting up org infrastructure means your AI agents can access
that shared context.

Each org gets:
  • org.json     - Configuration (what repos to use)
  • operatives/  - AI specialists for your domain
  • stack-wisdom/ - Patterns and lessons learned

============================================================
SCANNING WORKSPACE: ~/Code
============================================================

Found directories that could be orgs:
  • experiments/  (12 projects, no org infrastructure)
  • freelance/    (3 projects, no org infrastructure)

No orgs with full infrastructure found.

============================================================
RECOMMENDED SETUP
============================================================

For most developers, we recommend starting with two orgs:

  personal/  - Side projects, experiments, personal tools
  work/      - Professional work (job, clients, freelance)

This gives you:
  ✓ Clear separation between personal and professional
  ✓ Different operatives for different contexts
  ✓ Wisdom that stays in the right domain

[P] Create personal/ and work/ orgs (recommended)
[C] Create custom orgs (you specify names)
[M] Migrate existing directories to orgs
[S] Skip for now
```

### Existing User with Gaps

```
$ /run-organize-orgs

============================================================
ORG AUDIT: ~/Code
============================================================

FOUND ORGS:
  ✓ personal/
      org.json:       ✓ exists
      operatives:     ✗ missing (expected: personal-operatives/)
      stack-wisdom:   ✓ exists

  ✓ work/
      org.json:       ✗ missing
      operatives:     ✗ missing (expected: work-operatives/)
      stack-wisdom:   ✗ missing (expected: work-stack-wisdom/)

INFRASTRUCTURE GAPS:
  • personal/ needs: operatives repo
  • work/ needs: org.json, operatives repo, stack-wisdom repo

[F] Fix all gaps (create missing infrastructure)
[I] Interactive (choose what to create)
[A] Audit only (no changes)
```

## Scaffolding Details

### org.json

Created from template with org name substituted:

```json
{
  "name": "personal",
  "operatives": {
    "repo": "personal-operatives"
  },
  "stack_wisdom": {
    "repo": "personal-stack-wisdom"
  },
  "workflow": {
    "complexity_threshold": "moderate",
    "auto_compound": true
  }
}
```

### Operatives Repo

Creates `[org]-operatives/` with:

```
[org]-operatives/
├── .git/
├── README.md
└── .gitkeep
```

README explains what operatives are and how to create them.

### Stack-Wisdom Repo

Creates `[org]-stack-wisdom/` with:

```
[org]-stack-wisdom/
├── .git/
├── README.md
├── stack-wisdom/
│   └── .gitkeep
├── circuit-breakers/
│   └── .gitkeep
└── triggers/
    └── .gitkeep
```

README explains wisdom vs. knowledge and the compound loop.

## Integration

### With organize-claude

`organize-claude` can detect missing org infrastructure and offer to run `organize-orgs`:

```
$ /run-organize-claude

Found org: work/
  ✓ CLAUDE.md exists
  ✗ No org.json (operatives and wisdom not configured)

[O] Run organize-orgs to set up org infrastructure
[S] Skip and continue with CLAUDE.md audit
```

### With organize-project

`organize-project` benefits from org infrastructure being in place - it can reference the org's operatives and wisdom.

### With Overwatch

Overwatch proactively alerts when org infrastructure is missing:

```
-----------------------------------------------------------
|  OVERWATCH                                              |
-----------------------------------------------------------
⚠️ Org 'work' missing infrastructure:
   - No .claude/org.json
   - No work-operatives/ repo

   Run `/run-organize-orgs` to set up
```

This means you'll be reminded at session start if your current org is missing infrastructure - you don't have to remember to run organize-orgs manually.

## Related Skills

- `organize-claude` - CLAUDE.md file hierarchy
- `organize-project` - Project structure (docs/, .claude/)
- `create-operative` - Create operatives (uses org path from org.json)
- `add-wisdom` - Add patterns (uses wisdom repo from org.json)
