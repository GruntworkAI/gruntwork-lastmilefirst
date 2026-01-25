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
| Expert roster sync | Every session | User CLAUDE.md missing experts or operatives |

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

## Expert Roster Sync Check

This check ensures the user's CLAUDE.md has an up-to-date expert consultation section.

### What It Checks

1. **Section exists**: Look for "AI Expert Consultation" or "Expert Consultation" in user CLAUDE.md
2. **All experts listed**: Compare against current personas in plugin:
   ```bash
   ls ~/.claude/plugins/cache/gruntwork-marketplace/lastmilefirst/*/personas/*.md | xargs -I{} basename {} .md
   ```
3. **All operatives listed**: Check for any operatives not mentioned:
   ```bash
   ls ~/.claude/operatives/*.md .claude/operatives/*.md 2>/dev/null
   ```

### Expected Experts (Current Roster)

**Founding Team:** charles, adam, paloma, andor, dino, max, shannon
**Key Hires:** scout, maya, archer, quinn, reese, otto

### Alert Conditions

- ⚠️ "Expert consultation section missing from user CLAUDE.md"
- ⚠️ "Expert [name] exists but not in CLAUDE.md roster"
- ⚠️ "Operative [name] exists but not mentioned in CLAUDE.md"
- ⚠️ "Expert [name] listed in CLAUDE.md but persona file not found" (stale reference)

### How to Fix

Run this to see current vs documented:
```bash
# Current experts
ls ~/.claude/plugins/cache/gruntwork-marketplace/lastmilefirst/*/personas/*.md 2>/dev/null | xargs -I{} basename {} .md | sort

# Current operatives
ls ~/.claude/operatives/*.md .claude/operatives/*.md 2>/dev/null | xargs -I{} basename {} .md | sort

# Check CLAUDE.md for expert section
grep -A 50 "Expert Consultation" ~/Code/CLAUDE.md | head -60
```

Then update user CLAUDE.md to match, or run `/run-consult-expert shannon` for help restructuring.
