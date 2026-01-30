# Gruntwork Marketplace

Claude Code plugins for Gruntwork development workflows.

## Installation

Run these commands inside a Claude Code session:

```bash
# 1. Add marketplace (one time, interactive)
/plugin marketplace add
# When prompted, enter: GruntworkAI/gruntwork-marketplace

# 2. Install plugins
/plugin install lastmilefirst@gruntwork-marketplace
```

## Updating Plugins

To get the latest plugin versions:

```bash
# Step 1: Refresh marketplace from GitHub
/plugin marketplace update gruntwork-marketplace

# Step 2: Update the plugin
/plugin update lastmilefirst@gruntwork-marketplace
```

**Note:** Running only step 2 won't fetch new versions—Claude Code caches the marketplace index locally.

## Verify Installation

```bash
# Check marketplace is registered
/plugin marketplace list

# Check plugin is installed
/plugin list
```

## Available Plugins

| Plugin | Version | Description |
|--------|---------|-------------|
| [lastmilefirst](plugins/lastmilefirst/) | 0.9.5 | AI expert agents, CLAUDE.md management, project organization |

## About

This marketplace hosts plugins developed by [Gruntwork](https://github.com/GruntworkAI) for Claude Code. Each plugin follows the Last Mile First philosophy: set up the infrastructure for smooth delivery before building features.

## License

MIT
