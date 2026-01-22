---
name: organize-project
description: Enforces consistent project structure with docs/ for reference documentation and .claude/ for working artifacts. Integrates with organize-claude for configuration management.
---

# Organize Project

Establishes and maintains a consistent project structure separating static documentation from working artifacts.

## Pre-Flight Check: CLAUDE.md

Before organizing project structure, this skill checks for CLAUDE.md configuration:

```
$ /organize-project

Pre-flight: Checking CLAUDE.md configuration...
  ✗ This project has no CLAUDE.md file

[C] Create CLAUDE.md first (runs organize-claude --scaffold-project)
[S] Skip and continue with project organization
[Q] Quit
```

**Why?** Projects should have a CLAUDE.md documenting:
- Infrastructure details (AWS region, account)
- Development commands
- Deployment procedures
- Known gotchas

Use `organize-claude` to scaffold missing CLAUDE.md files.

## Target Structure

```
root/
├── CLAUDE.md                # Project configuration (checked first!)
├── README.md                # Project overview (stays at root)
├── docs/                    # Static reference documentation
│   ├── deployment.md
│   ├── infrastructure.md
│   ├── api.md
│   ├── testing.md
│   ├── security.md
│   └── ...
└── .claude/                 # Working artifacts (ephemeral)
    ├── work/
    │   ├── todos/           # Task lists, issues
    │   ├── plans/           # Implementation plans, PRDs, features
    │   └── sessions/        # Session summaries, analysis, reviews
    ├── debt/                # Technical debt tracking
    └── archive/             # Archived artifacts by date
        └── YYYY-MM/
```

## What This Skill Does

1. **Checks** for CLAUDE.md (offers to create if missing)
2. **Creates** the target directory structure if missing
3. **Migrates** scattered documentation to `docs/`
4. **Migrates** working artifacts to `.claude/work/`
5. **Migrates** technical debt files to `.claude/debt/`
6. **Archives** old files (>30 days) to `.claude/archive/YYYY-MM/`
7. **Creates symlinks** for backwards compatibility when migrating legacy directories

## When to Use

- Setting up a new project
- Project root has scattered markdown files
- No `docs/` or `.claude/` structure exists
- Want to establish consistent organization
- Need to archive old working files

## Migration Patterns

### Documentation (root → docs/)

| Pattern | Example |
|---------|---------|
| `*DEPLOYMENT*.md`, `*DEPLOY*.md` | deployment.md |
| `*INFRASTRUCTURE*.md`, `*INFRA*.md` | infrastructure.md |
| `*API*.md`, `*API_DOCS*.md` | api.md |
| `*TESTING*.md`, `*TEST_GUIDE*.md` | testing.md |
| `*SECURITY*.md` | security.md |
| `*ARCHITECTURE*.md` | architecture.md |
| `*GUIDE*.md` (not session/work related) | guides |

**Note:** `README.md` and `CLAUDE.md` stay at root.

### Working Artifacts (root → .claude/work/)

| Pattern | Destination |
|---------|-------------|
| `SESSION_*.md`, `*_SESSION.md` | work/sessions/ |
| `TODO*.md`, `*_TODO.md` | work/todos/ |
| `ISSUE*.md`, `*_ISSUE.md` | work/todos/ |
| `PLAN*.md`, `*_PLAN.md` | work/plans/ |
| `PRD*.md`, `FEATURE*.md` | work/plans/ |
| `*_ANALYSIS*.md`, `*_REVIEW*.md` | work/sessions/ |
| `*_PROGRESS.md`, `*_STATUS.md` | work/sessions/ |
| `SYNTHASAURUS_*.md` | work/sessions/ |
| `screenshot*.png` | work/sessions/ |

### Technical Debt (root → .claude/debt/)

| Pattern | Example |
|---------|---------|
| `*TECH_DEBT*.md` | tech-debt.md |
| `*TECHNICAL_DEBT*.md` | technical-debt.md |
| `DEBT*.md` | debt tracking |

### Legacy Directory Migration

If these directories exist at project root (not symlinks):
- `plans/` → `.claude/work/plans/` + symlink
- `todos/` → `.claude/work/todos/` + symlink
- `sessions/` → `.claude/work/sessions/` + symlink

## Archive Criteria

| Location | Criteria |
|----------|----------|
| `.claude/work/sessions/*` | Modified >30 days ago |
| `.claude/work/plans/*` | Modified >30 days ago |
| `.claude/work/todos/*` | `status: complete` AND modified >30 days ago |

### Protected (Never Archived)

- Files modified in last 7 days
- TODOs with `status: in_progress` or `status: pending`

## Interactive Flow

```
$ /organize-project

Pre-flight: Checking CLAUDE.md configuration...
  ✓ CLAUDE.md exists

Checking project structure...

Documentation:
  ✗ docs/ (missing)

Working artifacts:
  ✓ .claude/
  ✗ .claude/work/todos/
  ✗ .claude/work/plans/
  ✗ .claude/work/sessions/
  ✗ .claude/debt/

Found scattered files in root:
  Documentation:
    - DEPLOYMENT_GUIDE.md → docs/
    - API_DOCUMENTATION.md → docs/

  Work artifacts:
    - SESSION_2025-01-15.md → .claude/work/sessions/
    - TODO.md → .claude/work/todos/
    - FEATURE_AUTH.md → .claude/work/plans/

[O] Organize (create structure and migrate)
[Q] Quit

> O

Creating structure...
  ✓ docs/
  ✓ .claude/work/todos/
  ✓ .claude/work/plans/
  ✓ .claude/work/sessions/
  ✓ .claude/debt/

Migrating files...
  → DEPLOYMENT_GUIDE.md → docs/deployment-guide.md
  → API_DOCUMENTATION.md → docs/api-documentation.md
  → SESSION_2025-01-15.md → .claude/work/sessions/
  → TODO.md → .claude/work/todos/
  → FEATURE_AUTH.md → .claude/work/plans/

✅ Organized. 5 files migrated.
```

## How to Run

```bash
python ${SKILL_ROOT}/scripts/organize.py
```

Or for a specific project:

```bash
python ${SKILL_ROOT}/scripts/organize.py /path/to/project
```

Skip CLAUDE.md check:

```bash
python ${SKILL_ROOT}/scripts/organize.py --skip-claude-check
```

## Technical Details

**Age calculation:** File modification time (mtime)

**Conflict resolution:** Append timestamp suffix `_1705123456` if target exists

**Archive structure:**
```
.claude/archive/
└── 2025-01/
    ├── plans/
    ├── sessions/
    └── todos/
```

## Implementation Notes

- Interactive only - always asks for confirmation before changes
- Files are moved, not copied
- Archive serves as rollback mechanism
- Symlinks maintain backwards compatibility for legacy directories
- CLAUDE.md check can be skipped with `--skip-claude-check` flag

## Related Skills

- `organize-claude` - Manages CLAUDE.md hierarchy (user, org, project levels)
- `review-docs` - Reviews documentation quality
- `review-work` - Reviews work artifacts
