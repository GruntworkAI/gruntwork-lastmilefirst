# Session: Cross-Project Todo Aggregation Feature

**Date:** 2026-01-29
**Project:** lastmilefirst plugin
**Version:** 0.8.0 → 0.9.0

## Summary

Implemented `/run-todos-summary` command for aggregating todos across all projects in a workspace org.

## What Was Built

### New Skill: `todos-summary`

**Files created:**
- `skills/todos-summary/SKILL.md` - Documentation
- `skills/todos-summary/scripts/aggregator.py` - Core logic (OrgConfig, TodoItem, TodoAggregator)
- `skills/todos-summary/scripts/formatters.py` - Output formatters (Terminal, JSON, Compact, Overwatch, Project)
- `skills/todos-summary/scripts/cli.py` - CLI entry point
- `commands/run-todos-summary.md` - Command stub

**Files modified:**
- `hooks/scripts/session_start.py` - Added `check_cross_project_blockers()`

### Configuration

Created `~/.claude/workspace-config.json`:
```json
{
  "workspace": "~/Code",
  "orgs": [
    {"name": "gruntwork", "default": true},
    {"name": "client-work", "sensitive": true}
  ]
}
```

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Implementation | Python | Consistency with Overwatch, cross-platform |
| Scope | Org-first with `--all` option | Prevents context mixing between orgs |
| Terminology | workspace/org/project | Consistent with organize-claude skill |
| Cache TTL | 5 minutes | Fast startup, reasonable freshness |
| Overwatch | Urgent/blocked only | Signal over noise |

## Expert Consultations

- **Charles (CTO)**: Strategic guidance on scope, workspace registry pattern, Overwatch filtering
- **Paloma (Python)**: Implementation patterns, caching strategy, output formats

## CLI Options

```bash
/run-todos-summary                    # Default org
/run-todos-summary --all              # All orgs
/run-todos-summary --org gruntwork    # Specific org
/run-todos-summary --by-project       # Project-centric view
/run-todos-summary --format json      # JSON output
/run-todos-summary --verbose          # Full details
```

## Future Features (Not Implemented)

- Collaboration notes from other users/agents
- GitHub Issues bidirectional sync
- Smart priority inference
- Dependency graph visualization

## Commits

```
437e578 feat(lastmilefirst): Add cross-project todo aggregation
c3fb04d chore(lastmilefirst): Bump version to 0.9.0
```

## Next Steps

1. Update plugin: `/plugin update lastmilefirst@gruntwork-marketplace`
2. Test in new session
3. Consider making `--by-project` the default view
