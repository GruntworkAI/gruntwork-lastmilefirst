---
name: review-project
description: Complete project review - docs, work artifacts, and cross-cutting concerns. For CLAUDE.md review, use review-claude.
---

# Review Project

Comprehensive project review combining `/run-review-docs` and `/run-review-work` with cross-cutting analysis.

**Note:** This reviews project artifacts (docs, work items). For reviewing CLAUDE.md files, use `/run-review-claude`.

## Prerequisites

Requires organized project structure (`docs/`, `.claude/work/`, etc.).

If structure is missing, respond:
> "Run `/run-organize-project` first to create the standard structure."

See [organize-project/SKILL.md](../organize-project/SKILL.md) for required structure.

## What This Skill Does

1. **Run `/run-review-docs`** - Analyze docs/ directory
2. **Run `/run-review-work`** - Analyze .claude/work/ directory
3. **Cross-cutting analysis** - Find issues spanning both areas

## Cross-Cutting Checks

### Consistency
- Documentation references todos that don't exist
- Todos reference documentation that's missing
- Plans reference features not documented

### Completeness
- Features in code without documentation
- Documented features without implementation
- Debt items without remediation plans

### Health Score
Calculate overall project hygiene:
- Documentation coverage
- Stale item percentage
- Archive backlog
- GitHub issue sync status

## How to Run

### Step 1: Run Sub-Reviews
Execute both review skills and collect their reports.

### Step 2: Cross-Reference Analysis

Check for disconnects:
- Docs mentioning "see TODO" → verify todo exists
- Todos referencing "update docs" → verify docs updated
- Plans marked complete → verify docs reflect feature

### Step 3: Calculate Health Score

```markdown
## Project Health Score: [X/100]

| Category | Score | Details |
|----------|-------|---------|
| Documentation | 80 | 4/5 essential docs present |
| Todo Hygiene | 60 | 2 stale, 3 ready to archive |
| Plan Currency | 90 | 1 stale plan |
| Session Cleanup | 70 | 3 old sessions |
| Debt Tracking | 85 | All items current |
| GitHub Sync | 50 | 5 items not in GitHub |
```

### Step 4: Generate Combined Report

```markdown
# Complete Project Review: [Project Name]

## Health Score: X/100

## Executive Summary
- X issues found across docs and work
- Y items ready for immediate action
- Z items need GitHub issues

## Documentation Review
[Output from /run-review-docs]

## Work Artifacts Review
[Output from /run-review-work]

## Cross-Cutting Issues

### Broken References
- docs/api.md line 45: References "see TODO-123" but file not found
- .claude/work/todos/feature-x.md: Says "update docs" but docs unchanged

### Sync Gaps
- 5 local todos not tracked in GitHub
- 2 GitHub issues have no local tracking

## Recommended Actions (Priority Order)

### Immediate (Today)
1. Archive 3 completed todos
2. Create 2 GitHub issues for bugs

### This Week
3. Update stale documentation
4. Review abandoned plans

### When Time Permits
5. Extract session insights to docs
6. Consolidate duplicate content

## Quick Commands
- Archive completed: `/run-organize-project --yes`
- Create issues: `gh issue create ...`
- Sync with GitHub: Review and create missing issues
```

### Step 5: Offer Actions

Present prioritized action list and offer to execute:
1. Quick wins (archiving, moving files)
2. Issue creation
3. Content updates

## Integration

- **`/run-organize-project`**: Run first to ensure structure, or after to archive
- **`/run-review-docs`**: Standalone docs review
- **`/run-review-work`**: Standalone work review
- **`/run-review-claude`**: Review CLAUDE.md files for gaps
- **compound-engineering**: For advanced workflows

## When to Use

- Weekly project hygiene check
- Before major releases
- Onboarding to understand project state
- After extended development sprints

## Notes

- Comprehensive but may take longer than individual reviews
- Provides holistic view of project health
- Identifies issues that single reviews would miss
