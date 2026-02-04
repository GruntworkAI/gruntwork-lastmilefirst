---
name: todos-summary
description: Aggregate and display todos across all projects in workspace orgs, with filtering by priority and state.
---

# Todos Summary

Aggregates todos from `.claude/work/todos/` across all projects in your workspace orgs, providing a unified view of pending work.

## Terminology

Consistent with other lastmilefirst skills:

| Term | Definition | Example |
|------|------------|---------|
| **Workspace** | Root directory (security boundary) | `~/Code` |
| **Org** | Subdirectory grouping related projects | `personal`, `client-work` |
| **Project** | Individual project within an org | `gruntwork-remail` |

## Triggers

This skill should be suggested when:
- User asks "what's next?" or "what should I work on?"
- User asks to "show todos" or "pending tasks"
- User wants to see work across projects
- At session start (via Overwatch) when urgent/blocked items exist

## Usage

```bash
/run-todos-summary                    # Default org (gruntwork)
/run-todos-summary --all              # All orgs in workspace
/run-todos-summary --org gruntwork    # Specific org
/run-todos-summary --format json      # JSON output
/run-todos-summary --verbose          # Full item details
```

## Workspace Configuration

Configure your workspace at `~/.claude/workspace-config.json`:

```json
{
  "workspace": "~/Code",
  "orgs": [
    {"name": "gruntwork", "default": true},
    {"name": "client-work", "sensitive": true}
  ],
  "exclude_patterns": ["node_modules", ".git", "venv"]
}
```

### Configuration Properties

| Property | Description |
|----------|-------------|
| `workspace` | Root directory path (supports ~) |
| `orgs[].name` | Directory name within workspace |
| `orgs[].default` | Use this org when none specified |
| `orgs[].sensitive` | Mark as containing sensitive data |

If no config file exists, the skill auto-detects orgs from `~/Code/`.

## Todo Format

### YAML Frontmatter

Todos in `.claude/work/todos/*.md` should have frontmatter:

```yaml
---
status: pending|ready|complete
priority: p1|p2|p3|urgent|high|normal|low
blocks: [project-name]
blocked_by: [project-name#issue-id]
tags: [tag1, tag2]
---
```

### Inline Tags

For quick markup, use inline tags anywhere in the file:

- `[URGENT]` - Marks as high priority
- `[BLOCKED-BY:project#id]` - Marks as blocked
- `[BLOCKS:project]` - Marks as blocking another project

## Output Formats

### Terminal (default)

```
CROSS-PROJECT TODO SUMMARY (gruntwork)
==================================================

URGENT (2)
  [gruntwork-remail] Fix rate limiting false positives (3d)
  [gruntwork-calvin] Voice auth token expiring in prod (1d)

BLOCKED (1)
  [gruntwork-remail] Prod deploy (waiting: infrastructure#vpc)

ACTIVE (8)
  [gruntwork-promptasaurus] 3 pending
  [gruntwork-griffith] 2 pending
  [gruntwork-stack-wisdom] 3 pending

STALE (5 items, 2 shown)
  [gruntwork-unstacker] Add pagination (14d)
  [gruntwork-cookie-monster] Refactor engine (21d)

Run /run-todos-summary --verbose for full details
```

### Compact (for Overwatch)

```
[gruntwork] 2 urgent, 1 blocked (11 total)
   ! [gruntwork-remail] Fix rate limiting false positives
```

### Project (--by-project)

```
PROJECT STATUS (gruntwork)
==================================================

gruntwork-remail (4 todos) - 1 urgent, 1 blocked
  - [urgent] Fix rate limiting false positives (3d)
  - [blocked] Prod deploy (waiting: infrastructure#vpc)
  - [active] Implement email threading
  ... and 1 more

gruntwork-calvin (2 todos) - 1 urgent
  - [urgent] Voice auth token expiring
  - [active] Add Gemini 2.0 support

gruntwork-promptasaurus (3 todos) - 1 stale
  - [active] Add streaming support
  - [active] Improve prompt templates
  - [stale] Documentation updates (21d)

Summary: 9 todos across 3 projects (2 urgent, 1 blocked)
Run with --verbose for full details
```

### JSON

Full structured output for programmatic use.

## State Classification

Todos are classified into states:

| State | Criteria |
|-------|----------|
| **urgent** | Priority is `urgent`, `p1`, or `high`; OR has `[URGENT]` tag |
| **blocked** | Has `blocked_by` entries; OR has `[BLOCKED-BY:...]` tag |
| **stale** | Modified more than 7 days ago |
| **active** | Everything else (pending, not blocked, not stale) |

## Caching

Results are cached for 5 minutes at `~/.claude/cache/todo-aggregator.json`.

Use `--no-cache` to force a fresh scan.

## Overwatch Integration

At session start, Overwatch shows a compact summary if there are urgent or blocked items:

```
2 urgent todo(s) across projects
   [gruntwork-remail] Fix rate limiting false positives
1 blocked todo(s) need attention
   Run /run-todos-summary for details
```

## CLI Options

| Option | Description |
|--------|-------------|
| `-o, --org NAME` | Scan specific org |
| `--all` | Scan all orgs in workspace |
| `-f, --format FORMAT` | Output format: terminal, json, compact, overwatch, project |
| `--by-project` | Group output by project (shortcut for `--format project`) |
| `--no-cache` | Force fresh scan |
| `-v, --verbose` | Show all items (terminal/project only) |
| `--list-orgs` | List configured orgs |

## Implementation

```bash
# Run the CLI directly
python ${SKILL_ROOT}/scripts/cli.py

# With options
python ${SKILL_ROOT}/scripts/cli.py --all --format json
```

## Startup Behavior

At session start, Overwatch checks for urgent/blocked items:

1. **If urgent/blocked items exist**: Show alert with details
2. **If no alerts**: Claude should offer:
   - "Want a project summary?" → run `/run-todos-summary --by-project`
   - "Or dive into a specific project?"

This keeps startup fast while surfacing important blockers.

## Future Features

- **Collaboration notes**: Show notes/changes left by other users or agents
- **GitHub Issues sync**: Bidirectional sync with issue trackers
- **Smart priority inference**: Auto-detect urgency from content
- **Dependency graph**: Visualize cross-project blockers

## Related Skills

- `organize-claude` - Manages workspace and org configuration
- `review-work` - Review todos in current project for staleness
- `organize-project` - Organize project structure including todos
