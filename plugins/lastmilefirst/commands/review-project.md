---
name: review-project
description: Overall project health check - structure, docs, work items, and configuration
argument-hint: "[quick|full]"
---

# Review Project

Comprehensive project health assessment.

## Usage

```
/review-project           # Full review
/review-project quick     # High-level summary only
/review-project full      # Deep analysis with recommendations
```

## What Gets Reviewed

### Structure
- Standard directories present
- File organization
- Naming conventions

### Documentation
- README completeness
- CLAUDE.md configuration
- Architecture docs

### Work Items
- Todo staleness
- Plan status
- Session hygiene

### Code Health
- Test coverage indicators
- Lint/type check status
- Dependency freshness

## Output

**Quick mode:** Traffic light summary (green/yellow/red per area)

**Full mode:** Detailed report with:
- Specific issues found
- Prioritized recommendations
- Suggested next actions

## After Completing Review

Update overwatch state to record this review:
```bash
${PLUGIN_ROOT}/hooks/scripts/update-state.sh review
```

This resets the "days since last review" counter.

## Related Commands

- `/organize-project` - Fix structure issues
- `/review-work` - Deep dive on work items
- `/review-docs` - Deep dive on documentation
- `/review-claude` - Deep dive on Claude config
- `/overwatch` - Check monitoring status
