# run-plugin-inventory

Display installed Claude Code plugins with versions, component counts, and usage statistics.

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
