---
name: organize-claude
description: Audit and scaffold CLAUDE.md files across user, org, and project levels
argument-hint: "[audit|scaffold|sync]"
---

# Organize Claude

Manages CLAUDE.md configuration files across your workspace hierarchy.

## Usage

```
/organize-claude              # Full audit and recommendations
/organize-claude audit        # Check current state only
/organize-claude scaffold     # Create missing files
/organize-claude sync         # Ensure consistency
```

## CLAUDE.md Hierarchy

```
~/Code/                       # USER LEVEL (security boundary)
├── CLAUDE.md                 # User-wide settings
│
├── gruntwork/                # ORG LEVEL
│   ├── CLAUDE.md             # Org-wide patterns
│   │
│   ├── project-a/            # PROJECT LEVEL
│   │   └── CLAUDE.md         # Project-specific
│   └── project-b/
│       └── CLAUDE.md
```

## What This Command Does

1. **Discovers** all CLAUDE.md files in the hierarchy
2. **Validates** structure and required sections
3. **Identifies** inheritance issues or conflicts
4. **Recommends** improvements
5. **Scaffolds** missing files (with confirmation)

## Related Commands

- `/organize-project` - Full project structure setup
- `/review-claude` - Validate configuration quality
