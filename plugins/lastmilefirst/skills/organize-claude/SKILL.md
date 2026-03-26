---
name: organize-claude
description: Audits, validates, and scaffolds Claude configuration files (CLAUDE.md, later SKILL.md, rules) across the workspace hierarchy. Ensures consistency between user, org, and project levels.
---

# Organize Claude

Manages Claude configuration across your development workspace. Currently handles CLAUDE.md files; will extend to SKILL.md and rules in future versions.

## Security Model

**IMPORTANT**: The user-level CLAUDE.md lives at `~/Code/` (not `~/`) to establish a security boundary. Claude's scope is intentionally limited to the Code directory tree.

## Hierarchy (3 Levels)

```
~/Code/                           # USER LEVEL (security boundary)
├── CLAUDE.md                     # User-wide settings, often symlinked to VCS
│
├── gruntwork/                    # ORG LEVEL (optional)
│   ├── CLAUDE.md                 # Org-specific overrides (optional)
│   ├── gruntwork-remail/
│   │   └── CLAUDE.md             # PROJECT LEVEL
│   ├── gruntwork-synthasaurus/
│   │   └── CLAUDE.md
│   └── ...
│
└── client-work/                  # Another org (optional)
    ├── CLAUDE.md                 # Org-specific overrides (optional)
    └── client-project/
        └── CLAUDE.md             # PROJECT LEVEL
```

### Level Responsibilities

| Level | Location | Purpose | Required? |
|-------|----------|---------|-----------|
| User | `~/Code/CLAUDE.md` | Workspace-wide settings, security boundary, project mapping | Yes |
| Org | `~/Code/{org}/CLAUDE.md` | Org-specific conventions, tech stack, deployment patterns | Optional |
| Project | `~/Code/{org}/{project}/CLAUDE.md` | Project-specific commands, architecture, gotchas | Recommended |

## What This Skill Does

### Current (v1 - CLAUDE.md)
1. **Audit** - Scans workspace for all CLAUDE.md files, reports coverage
2. **Validate** - Checks user-level project mappings against actual directories
3. **Scaffold** - Creates missing org/project CLAUDE.md files from templates
4. **Sync** - Updates project mappings when new projects are discovered
5. **Diff** - Identifies contradictions between hierarchy levels

### Future (v2 - Skills)
- Audit SKILL.md files in skills directories
- Validate skill naming, structure, and registration
- Cross-reference skills with CLAUDE.md tool references

### Future (v3 - Rules)
- Audit rules files (.mcp/rules.md, etc.)
- Validate rule syntax and coverage
- Ensure rules align with CLAUDE.md policies

## Project Archetypes

Every project CLAUDE.md should declare its archetype near the top. This controls which sections are expected and reviewed.

| Archetype | When to Use | Key Sections |
|-----------|-------------|-------------|
| **Deployable** | You deploy it somewhere (AWS, Vercel, etc.) | Infrastructure, Cloud Details, Terraform Workspaces, Deployment, Testing |
| **Usable** | You install/run/invoke it (gems, CLIs, plugins, SDKs) | Installation, Configuration, Publishing, Testing |
| **Referenceable** | You read/consult it (knowledge archives, docs) | Content Structure, How to Update |
| **Experimental** | New project, shape TBD | Quick Commands (minimal) |

Format in CLAUDE.md: `## Archetype: Deployable` (right after project description).

When scaffolding a new project, pass `--archetype` to get the right template:

```bash
python3 ${SKILL_ROOT}/scripts/organize_claude.py --scaffold-project myproject --archetype usable
```

## When to Use

- Setting up a new workspace or machine
- Adding a new project to your ecosystem
- Periodic health check (weekly/monthly)
- Before major refactoring across projects
- When `organize-project` reports missing CLAUDE.md

## Conversational Triggers (for Claude Code)

**Claude should proactively offer organize-claude when:**

| Trigger | Claude Should Say |
|---------|-------------------|
| Working in a project without CLAUDE.md | "This project doesn't have a CLAUDE.md file. Want me to create one?" |
| Starting work in a new org/project | "Before we start, let me check if this project has a CLAUDE.md." |
| User mentions missing project context | "I can scaffold a CLAUDE.md to capture this project's context." |
| Setting up a new workspace | "Want me to audit your CLAUDE.md coverage across the workspace?" |

**Example conversational flow:**

```
User: Let's work on gruntwork-leamo

Claude: I see gruntwork-leamo doesn't have a CLAUDE.md file yet.
This would help me understand the project's infrastructure, deployment
patterns, and gotchas. Want me to:
  [C] Create a CLAUDE.md from template
  [S] Skip for now
```

**For reviewing existing files and suggesting additions, use the `review-claude` skill.**

## Audit Report

```
$ /run-organize-claude

CLAUDE CONFIGURATION AUDIT
==============================================================

Workspace: ~/Code
User Level: ~/Code/CLAUDE.md
  → symlink to gruntwork-stack-wisdom/user-claude-file/CLAUDE.md ✓

ORG COVERAGE
--------------------------------------------------------------
  ✗ gruntwork/CLAUDE.md         MISSING (10 projects below)
  ✗ client-work/CLAUDE.md       MISSING (0 projects below)

PROJECT COVERAGE: gruntwork/ (10 projects)
--------------------------------------------------------------
  ✓ gruntwork-promptasaurus    (3 files: root, backend, frontend)
  ✓ gruntwork-remail
  ✓ gruntwork-synthasaurus
  ✓ gruntwork-calvin
  ✓ gruntwork-cookie-monster
  ✗ gruntwork-ai-team          MISSING
  ✗ gruntwork-infrastructure   MISSING
  ✗ gruntwork-leamo            MISSING
  ✗ gruntwork-unstacker        MISSING
  ✗ gruntwork-website          MISSING

Coverage: 5/10 (50%)

PROJECT MAPPING VALIDATION (user-level)
--------------------------------------------------------------
Projects in ~/Code/CLAUDE.md but not on disk:
  (none)

Projects on disk but missing from mapping:
  ✗ calvin         → add: | calvin | ~/Code/gruntwork/gruntwork-calvin |
  ✗ cookie-monster → add: | cookie-monster | ~/Code/gruntwork/gruntwork-cookie-monster |
  ✗ leamo          → add: | leamo | ~/Code/gruntwork/gruntwork-leamo |

POTENTIAL CONTRADICTIONS
--------------------------------------------------------------
  (none detected)

[A] Audit only (no changes)
[O] Scaffold missing org-level files
[P] Scaffold missing project-level files
[U] Update user-level project mappings
[F] Full sync (all of the above)
[Q] Quit
```

## Scaffold Templates

### Workspace-Level Template

```markdown
# Development Workspace

## Security Boundary

This CLAUDE.md establishes the security boundary for Claude. Everything under ~/Code/ is accessible; nothing outside is.

## PARC Workflow (Default)

Claude follows the PARC workflow for all development work:

**P**lan → **A**llocate → **R**eview → **C**ompound

| Step | Purpose | Scales With Complexity |
|------|---------|------------------------|
| **Plan** | Think before doing | Light for trivial, thorough for complex |
| **Allocate** | Delegate to right agents | Skip for simple, orchestrate for complex |
| **Review** | Verify correctness | Always (tests, validation) |
| **Compound** | Capture learnings | When insights are hard-won |

**Key principle:** YAGNI for features, YAGWYDI for infrastructure.

For strict enforcement: `/run-strict-parc`

## Org Structure

| Org | Purpose |
|-----|---------|
| personal/ | Side projects, experiments, personal tools |
| work/ | Professional work |

Each org has:
- `CLAUDE.md` - Org conventions
- `.claude/org.json` - Org config
- `[org]-operatives/` - AI specialists
- `[org]-stack-wisdom/` - Patterns and lessons

## Workspace Conventions

### Naming
- snake_case for code (matches Python backend as source of truth)
- kebab-case for files and URLs

### Before Any Task
1. Check stack-wisdom: `/run-search-wisdom [topic]`
2. Assess complexity (trivial → complex)
3. Apply appropriate PARC ceremony

### After Significant Work
1. Offer to compound learnings
2. Consider: wisdom, operative, CLAUDE.md update?
```

### Org-Level Template

```markdown
# {Org Name} Development Context

## Overview

{Org description - personal projects, client work, etc.}

## PARC Workflow

Claude follows the PARC workflow, scaling with task complexity:

| Step | What | When to Emphasize |
|------|------|-------------------|
| **Plan** | Think before doing | Complex features, unfamiliar domains |
| **Allocate** | Delegate to right agents | Multi-domain work, parallelizable tasks |
| **Review** | Verify correctness | All changes (tests, code review, validation) |
| **Compound** | Capture learnings | Hard-won insights, new patterns |

**YAGNI vs YAGWYDI:**
- YAGNI for features (don't overbuild)
- YAGWYDI for infrastructure (invest in scaffolding that compounds)

**For critical work:** Use `/run-strict-parc` to enforce explicit gates.

## Org Resources

| Resource | Location | Purpose |
|----------|----------|---------|
| Operatives | `{org}-operatives/` | Org-specific AI specialists |
| Stack-wisdom | `{org}-stack-wisdom/` | Patterns and lessons learned |
| Config | `.claude/org.json` | Org settings |

## Org-Specific Conventions

Inherits from ~/Code/CLAUDE.md with these additions/overrides:

### Tech Stack
- {Primary languages and frameworks}

### Deployment Patterns
- {Org-specific deployment approaches}

### Code Quality
```bash
# Standard commands for this org
{linting, testing, etc.}
```

## Projects in This Org

| Project | Description | Status |
|---------|-------------|--------|
{Auto-generated from directory scan}

---

*See ~/Code/CLAUDE.md for workspace-wide conventions*
```

### Project-Level Template

```markdown
# {Project Name}

## Overview

{One-line description}

## Quick Commands

```bash
# Development
{start dev server, etc.}

# Testing
{test commands}

# Deployment
{deploy commands}
```

## Architecture

{Brief architecture description}

## Key Files

- `src/` - Source code
- `tests/` - Test suite

## Project-Specific Notes

{Gotchas, known issues, etc.}

---

*Inherits from ~/Code/CLAUDE.md and ~/Code/{org}/CLAUDE.md*
```

## Inheritance Model

Settings cascade down the hierarchy:

```
User Level (~/Code/CLAUDE.md)
├── Workspace-wide policies (snake_case, security)
├── Project directory mapping
├── Tool references (compound-engineering, Synthasaurus)
└── Common patterns (venv checks, deployment types)
    │
    ▼
Org Level (~/Code/gruntwork/CLAUDE.md) [optional]
├── Org-specific tech stack
├── Org deployment patterns
└── Project listing for this org
    │
    ▼
Project Level (~/Code/gruntwork/project/CLAUDE.md)
├── Project-specific commands
├── Architecture details
└── Gotchas and known issues
```

**Override Rules:**
- Project can override org settings
- Org can override user settings
- Explicit > inherited (if specified at lower level, it wins)
- Contradictions are flagged for review

## Claude Workflow

This skill uses **Claude as the conversational layer**. The script runs non-interactively with CLI flags; Claude gathers user intent and passes the right arguments.

### Step 1: Check for config

```bash
python3 ${SKILL_ROOT}/scripts/organize_claude.py --show-config
```

**If no config exists**, ask the user conversationally:
1. "What's your workspace root directory?" (e.g., `~/Code`)
2. "What are your org directories?" (or offer to auto-detect)

Then run setup with their answers:

```bash
# With explicit orgs:
python3 ${SKILL_ROOT}/scripts/organize_claude.py --setup --workspace ~/Code --orgs "gruntwork,work"

# Auto-detect orgs from workspace subdirectories:
python3 ${SKILL_ROOT}/scripts/organize_claude.py --setup --workspace ~/Code
```

### Step 2: Run audit

```bash
python3 ${SKILL_ROOT}/scripts/organize_claude.py
```

Present the results conversationally. Highlight missing org/project CLAUDE.md files and mapping gaps.

### Step 3: Offer actions based on findings

Based on audit output, suggest specific commands:

- Missing org files: "I can scaffold CLAUDE.md for [org]. Want me to?"
  ```bash
  python3 ${SKILL_ROOT}/scripts/organize_claude.py --scaffold-org ORGNAME
  python3 ${SKILL_ROOT}/scripts/organize_claude.py --scaffold-all-orgs
  ```

- Missing project files: "These projects need CLAUDE.md. Create them?" Ask "What kind of project is this?" and offer the four archetypes.
  ```bash
  python3 ${SKILL_ROOT}/scripts/organize_claude.py --scaffold-project PROJNAME --archetype deployable
  python3 ${SKILL_ROOT}/scripts/organize_claude.py --scaffold-all-projects
  ```

- Mapping gaps: "Your project directory mapping is out of date. Update it?"
  ```bash
  python3 ${SKILL_ROOT}/scripts/organize_claude.py --update-mappings
  ```

- Everything needs work: "Want me to do a full sync?"
  ```bash
  python3 ${SKILL_ROOT}/scripts/organize_claude.py --full-sync --yes
  ```

### Step 4: Confirm results

Run audit again to show the updated state.

## Commands Reference

```bash
# Config management
python3 ${SKILL_ROOT}/scripts/organize_claude.py --show-config
python3 ${SKILL_ROOT}/scripts/organize_claude.py --setup --workspace ~/Code --orgs "org1,org2"
python3 ${SKILL_ROOT}/scripts/organize_claude.py --setup --workspace ~/Code  # auto-detect orgs
python3 ${SKILL_ROOT}/scripts/organize_claude.py --add-org neworg
python3 ${SKILL_ROOT}/scripts/organize_claude.py --remove-org oldorg

# Audit (default, read-only)
python3 ${SKILL_ROOT}/scripts/organize_claude.py
python3 ${SKILL_ROOT}/scripts/organize_claude.py --dry-run

# Scaffold specific items
python3 ${SKILL_ROOT}/scripts/organize_claude.py --scaffold-org gruntwork
python3 ${SKILL_ROOT}/scripts/organize_claude.py --scaffold-project gruntwork-leamo
python3 ${SKILL_ROOT}/scripts/organize_claude.py --scaffold-project gruntwork-leamo --archetype deployable

# Scaffold all missing
python3 ${SKILL_ROOT}/scripts/organize_claude.py --scaffold-all-orgs
python3 ${SKILL_ROOT}/scripts/organize_claude.py --scaffold-all-projects

# Full sync (scaffold all + show mapping updates)
python3 ${SKILL_ROOT}/scripts/organize_claude.py --full-sync --yes

# Update mappings
python3 ${SKILL_ROOT}/scripts/organize_claude.py --update-mappings
```

## Configuration

Config is stored at `~/.config/organize-claude/config.json`:

```json
{
  "workspace": "/Users/you/Code",
  "orgs": ["personal", "work"],
  "created": "2025-01-12T..."
}
```

**Note:** For reviewing existing CLAUDE.md files and suggesting additions, use the `review-claude` skill.

## Related Skills

- `organize-orgs` - Set up org infrastructure (org.json, operatives, wisdom repos)
- `review-claude` - Review CLAUDE.md files for gaps, suggest additions
- `organize-project` - In-project file organization (calls this skill)
- `review-docs` - Reviews documentation quality
- `consult-expert` - Consults AI personas for guidance
