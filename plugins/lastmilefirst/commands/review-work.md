---
name: review-work
description: Review todos, plans, and sessions for staleness and hygiene
argument-hint: "[todos|plans|sessions|all]"
---

# Review Work

Analyzes `.claude/work/` directory for stale items, archive candidates, and improvement opportunities.

## Usage

```
/review-work           # Review everything
/review-work todos     # Focus on todos only
/review-work plans     # Focus on plans only
/review-work sessions  # Focus on sessions only
```

## What Gets Checked

### Todos
- **Stale items** - No updates in 14+ days
- **Archive candidates** - Completed items older than 7 days
- **GitHub issue candidates** - Bugs/features needing tracking
- **Misplaced content** - Items belonging elsewhere

### Plans
- **Stale plans** - 30+ days with no implementation
- **Completed plans** - Ready to archive
- **Abandoned plans** - Superseded or cancelled

### Sessions
- **Old sessions** - 7+ days, candidates for summary
- **Valuable insights** - Worth extracting to docs
- **Context to preserve** - Before archiving

## Output

Produces a hygiene report with:
- Items needing attention (prioritized)
- Recommended actions
- Archive candidates
- Potential GitHub issues

## Prerequisites

Requires organized project structure. Run `/organize-project` first if needed.
