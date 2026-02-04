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

### Org-Level Template

```markdown
# {Org Name} Development Context

## Overview

{Org description - personal projects, client work, etc.}

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

## Commands

```bash
# Full audit (default)
python ${SKILL_ROOT}/scripts/organize_claude.py

# Scaffold specific level
python ${SKILL_ROOT}/scripts/organize_claude.py --scaffold-org gruntwork
python ${SKILL_ROOT}/scripts/organize_claude.py --scaffold-project gruntwork-leamo

# Update user-level mappings only
python ${SKILL_ROOT}/scripts/organize_claude.py --update-mappings

# Dry run
python ${SKILL_ROOT}/scripts/organize_claude.py --dry-run

# Reconfigure
python ${SKILL_ROOT}/scripts/organize_claude.py --setup
```

**Note:** For reviewing existing CLAUDE.md files and suggesting additions, use the `review-claude` skill.

## Configuration

On first run, the skill prompts for configuration:

```
$ /run-organize-claude

============================================================
ORGANIZE-CLAUDE SETUP
============================================================

This skill manages CLAUDE.md files across your workspace.
Let's configure your environment.

WORKSPACE PATH
----------------------------------------
The workspace is your security boundary - the root directory
where Claude operates. Your user-level CLAUDE.md lives here.

Choose a location that is:
  - Broad enough to include everything Claude needs to work on
  - Narrow enough to keep Claude isolated from sensitive areas
  - NOT your home directory (~) - that's too broad!

Examples: ~/Code, ~/Projects, ~/dev

Workspace path: ~/Code

ORG DIRECTORIES
----------------------------------------
Orgs are subdirectories that group related projects.
Examples: 'personal', 'work', 'client-acme', 'opensource'

Enter org names (comma-separated), or leave blank to scan for directories:

Org names: personal, work

CONFIGURATION SUMMARY
----------------------------------------
  Workspace: /Users/you/Code
  Orgs: personal, work

Save this configuration? [Y/n]: y

  Config saved to ~/.config/organize-claude/config.json
```

Config is stored at `~/.config/organize-claude/config.json`:

```json
{
  "workspace": "/Users/you/Code",
  "orgs": ["personal", "work"],
  "created": "2025-01-12T..."
}
```

### Config Commands

```bash
# Show current config
python ${SKILL_ROOT}/scripts/organize_claude.py --show-config

# Reconfigure
python ${SKILL_ROOT}/scripts/organize_claude.py --setup

# Override workspace for one run
python ${SKILL_ROOT}/scripts/organize_claude.py --workspace ~/OtherCode
```

## Integration with organize-project

The `organize-project` skill checks CLAUDE.md status:

```
$ /run-organize-project

Pre-flight: Checking CLAUDE.md...
  ✗ This project has no CLAUDE.md file

[C] Create CLAUDE.md first (runs run-organize-claude --scaffold-project)
[S] Skip and continue with project organization
[Q] Quit
```

## Related Skills

- `review-claude` - Review CLAUDE.md files for gaps, suggest additions
- `organize-project` - In-project file organization (calls this skill)
- `review-docs` - Reviews documentation quality
- `consult-expert` - Consults AI personas for guidance
