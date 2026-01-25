---
name: overwatch
description: Check overwatch status, manage alerts, and configure proactive monitoring
---

# Overwatch

Manage the lastmilefirst overwatch system - proactive monitoring and reminders.

## Usage

```
/run-overwatch              # Show current status and alerts
/run-overwatch status       # Same as above
/run-overwatch reset        # Reset all timers (start fresh)
/run-overwatch check        # Force run all checks now
```

## What Overwatch Monitors

| Check | Frequency | Alert Threshold |
|-------|-----------|-----------------|
| Uncommitted changes | Every session | Any uncommitted files |
| Project review | Every session | 7+ days since `/run-review-project` |
| Project organize | Every session | 14+ days since `/run-organize-project` |
| Plugin updates | Weekly | 7+ days since last check |
| Stale todos | Every session | Any todos older than 14 days |
| Missing CLAUDE.md | Every session | No CLAUDE.md in project |

## How It Works

1. **SessionStart hook** runs checks when Claude Code starts
2. **PostToolUse hooks** track file edits during session
3. **Stop hook** suggests committing if changes were made
4. **State file** at `~/.claude/lastmilefirst/overwatch-state.json` tracks timestamps

## Commands That Update State

When you run these commands, overwatch records the timestamp:
- `/run-review-project` → updates `last_review`
- `/run-organize-project` → updates `last_organize`
- `claude /plugin update` → updates `last_plugin_check`

## Manual State Update

```bash
# After running review
~/.claude/plugins/cache/gruntwork-marketplace/lastmilefirst/*/hooks/scripts/update-state.sh review

# After organizing
~/.claude/plugins/cache/gruntwork-marketplace/lastmilefirst/*/hooks/scripts/update-state.sh organize

# Check current state
~/.claude/plugins/cache/gruntwork-marketplace/lastmilefirst/*/hooks/scripts/update-state.sh status
```

## Behavior

When `/run-overwatch` or `/run-overwatch status` is called:

1. Run the session-start checks manually
2. Display current state timestamps
3. Show any active alerts
4. Suggest next actions if needed

When `/run-overwatch reset` is called:

1. Reset all timestamps to 0
2. Confirm reset complete

When `/run-overwatch check` is called:

1. Force run all checks regardless of state
2. Display full report
