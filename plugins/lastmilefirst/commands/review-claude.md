---
name: review-claude
description: Validate CLAUDE.md quality, inheritance, and effectiveness
argument-hint: "[file-path]"
---

# Review Claude

Validates CLAUDE.md configuration quality and effectiveness.

## Usage

```
/review-claude                    # Review current project's CLAUDE.md
/review-claude ~/Code/CLAUDE.md   # Review specific file
```

## What Gets Checked

### Structure
- Required sections present
- Proper markdown formatting
- Consistent heading hierarchy

### Content Quality
- Clear, actionable instructions
- No contradictions with parent CLAUDE.md files
- Appropriate scope (not too broad/narrow)

### Inheritance
- Proper `Inherits from` references
- No conflicting instructions across levels
- Appropriate override patterns

### Effectiveness
- Instructions Claude can actually follow
- Specific enough to be useful
- Not so restrictive it blocks work

## Common Issues Detected

- **Over-restriction** - Rules that block legitimate work
- **Vagueness** - Instructions too general to help
- **Conflicts** - Contradictions between levels
- **Staleness** - References to outdated patterns
- **Missing context** - Project info Claude needs

## Output

Quality report with:
- Issues by severity
- Specific line references
- Suggested improvements
- Example rewrites

## Related Commands

- `/organize-claude` - Fix structural issues
- `/consult-expert shannon` - Get Claude Code expertise
