---
name: organize-project
description: Set up standard project structure with docs, plans, and work directories
argument-hint: "[path]"
---

# Organize Project

Creates a standard project structure optimized for AI-assisted development.

## Usage

```
/organize-project              # Current directory
/organize-project ~/Code/myapp # Specific path
```

## Standard Structure Created

```
project/
├── CLAUDE.md              # Project-specific Claude instructions
├── README.md              # Project documentation
├── docs/                  # Documentation
│   ├── architecture/      # ADRs, system design
│   └── guides/            # How-to guides
├── plans/                 # Feature plans, specs
└── .claude/
    └── work/              # Active work items
        ├── todos/         # Task tracking
        ├── plans/         # In-progress plans
        └── sessions/      # Session notes
```

## Behavior

1. **Check existing structure** - Don't overwrite existing files
2. **Create missing directories** - Add standard folders
3. **Scaffold CLAUDE.md** - If missing, create with project context
4. **Report what was created** - List all new files/directories

## After Completing Organization

Update overwatch state to record this organization:
```bash
${PLUGIN_ROOT}/hooks/scripts/update-state.sh organize
```

This resets the "days since last organize" counter.

## Related Commands

- `/organize-claude` - Focus on CLAUDE.md hierarchy specifically
- `/review-project` - Check project health after organizing
- `/overwatch` - Check monitoring status
