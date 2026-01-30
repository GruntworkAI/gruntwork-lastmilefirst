# run-plugin-inventory

Display installed Claude Code plugins with versions, component counts, and usage statistics.

## IMPORTANT: Auto-Execute

**When this command is invoked, Claude MUST immediately run:**

```bash
# Find latest version and run
PLUGIN_DIR=$(ls -d ~/.claude/plugins/cache/gruntwork-marketplace/lastmilefirst/*/ 2>/dev/null | sort -V | tail -1)
python3 "${PLUGIN_DIR}skills/plugin-inventory/scripts/inventory.py" [any args]
```

Do NOT just display this documentation - execute the script and show the output.

## Usage

```
/run-plugin-inventory [options]
```

## Options

- `--verbose`, `-v`: Show install paths, timestamps, git commit SHA
- `--usage`, `-u`: Show detailed usage breakdown by skill/command name
- `--json`: Output as JSON for scripting/automation
- `--since DAYS`: Filter usage stats to last N days (default: 7)

## Examples

```bash
# Basic inventory
/run-plugin-inventory

# Detailed view with paths and timestamps
/run-plugin-inventory --verbose

# Full usage breakdown
/run-plugin-inventory --usage --since 30

# JSON output for scripting
/run-plugin-inventory --json
```
