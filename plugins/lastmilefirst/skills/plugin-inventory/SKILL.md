---
name: plugin-inventory
description: Display installed Claude Code plugins with versions, component counts, and usage statistics directly in the terminal.
---

# Plugin Inventory

Displays installed Claude Code plugins with versions and usage stats directly in the terminal, without requiring navigation through the interactive plugin UI.

## IMPORTANT: Auto-Execute

**When this skill is invoked via `/run-plugin-inventory`, Claude MUST immediately run the script:**

```bash
python3 ${SKILL_ROOT}/scripts/inventory.py [any args passed to command]
```

Do NOT just display this documentation - execute the script and show the output to the user.

## Usage

```bash
/run-plugin-inventory              # Basic inventory
/run-plugin-inventory --verbose    # Include paths, timestamps, git SHA
/run-plugin-inventory --usage      # Detailed usage breakdown
/run-plugin-inventory --json       # Machine-readable JSON output
/run-plugin-inventory --since 30   # Usage stats for last 30 days
```

## Sample Output

```
Installed Plugins
────────────────────────────────────────────────────────────

lastmilefirst@gruntwork-marketplace  v0.9.4
  AI expert agents, CLAUDE.md management, project organization
  Skills: 13 | Commands: 15

  Usage (last 7 days):
    skill: 17  agent: 5
    Total: 22
  Last invocation: 2 hours ago

compound-engineering@every-marketplace  v2.28.0
  AI-powered development tools for code review and automation
  Skills: 15 | Commands: 24 | Agents: 28

────────────────────────────────────────────────────────────
2 plugins installed | 22 invocations (last 7 days)
```

## Options

| Option | Description |
|--------|-------------|
| `--json` | Output as JSON for scripting/automation |
| `--verbose`, `-v` | Show install paths, timestamps, git commit SHA |
| `--usage`, `-u` | Show detailed usage breakdown by skill/command name |
| `--since DAYS` | Filter usage stats to last N days (default: 7) |

## Data Sources

### Plugin Information
- `~/.claude/plugins/installed_plugins.json` - Installed plugins and versions
- `{plugin}/.claude-plugin/plugin.json` - Plugin metadata

### Usage Statistics
- `~/.claude/lastmilefirst/invocations.log` - Skill/command invocation log

**Note:** Usage tracking is currently only available for the lastmilefirst plugin.

## JSON Output Format

```json
{
  "plugins": [
    {
      "key": "lastmilefirst@gruntwork-marketplace",
      "name": "lastmilefirst",
      "version": "0.9.4",
      "description": "...",
      "install_path": "~/.claude/plugins/cache/...",
      "installed_at": "2026-01-24T05:32:39.816Z",
      "last_updated": "2026-01-29T22:31:20.971Z",
      "git_commit_sha": "abc123...",
      "components": {
        "skills": 13,
        "commands": 15,
        "agents": 0
      }
    }
  ],
  "usage": {
    "days": 7,
    "total_invocations": 22,
    "by_skill": {
      "skill": 17,
      "agent": 5
    }
  }
}
```

## How to Run

```bash
python ${SKILL_ROOT}/scripts/inventory.py
python ${SKILL_ROOT}/scripts/inventory.py --verbose --usage
python ${SKILL_ROOT}/scripts/inventory.py --json
```

## Related Skills

- `overwatch` - Proactive monitoring including usage summary at session start
