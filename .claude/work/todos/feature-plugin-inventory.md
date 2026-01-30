# Feature: run-plugin-inventory command

**Status:** complete
**Priority:** low
**Created:** 2026-01-29

## Summary

Add a `/run-plugin-inventory` command that displays installed plugins and their versions directly in the terminal, without requiring navigation through the interactive plugin UI.

## Motivation

The built-in `/plugin list` opens an interactive UI where users must click through to see version information. A quick terminal output would be more convenient for checking versions.

## Proposed Behavior

```bash
/run-plugin-inventory
```

Output:
```
Installed Plugins
=================

lastmilefirst@gruntwork-marketplace
  Version: 0.9.3
  Location: ~/.claude/plugins/cache/gruntwork-marketplace/lastmilefirst/0.9.3/
  Skills: 25
  Commands: 15

compound-engineering@every-marketplace
  Version: 1.2.0
  Location: ~/.claude/plugins/cache/every-marketplace/compound-engineering/1.2.0/
  Skills: 40
  Commands: 20
```

## Implementation Notes

- Query `~/.claude/plugins/cache/` directory structure
- Read `plugin.json` from each installed plugin
- Count skills and commands directories
- Could add `--json` flag for machine-readable output

## Files to Create

- `skills/plugin-inventory/SKILL.md`
- `skills/plugin-inventory/scripts/inventory.py`
- `commands/run-plugin-inventory.md`
