# Gruntwork LastMileFirst

Marketplace for the `lastmilefirst` Claude Code plugin.

## Installation

Run these commands inside a Claude Code session:

```bash
# 1. Add marketplace (one time, interactive)
/plugin marketplace add
# When prompted, enter: GruntworkAI/gruntwork-lastmilefirst

# 2. Install plugins
/plugin install lastmilefirst@gruntwork-lastmilefirst
```

## Updating Plugins

To get the latest plugin versions:

```bash
# Step 1: Refresh marketplace from GitHub
/plugin marketplace update gruntwork-lastmilefirst

# Step 2: Update the plugin
/plugin update lastmilefirst@gruntwork-lastmilefirst
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
| [lastmilefirst](plugins/lastmilefirst/) | 0.16.1 | PARC workflow, AI expert agents, org-level operatives, stack-wisdom, and stack-knowledge |

## About

This marketplace hosts plugins developed by [Gruntwork](https://github.com/GruntworkAI) for Claude Code. Each plugin follows the Last Mile First philosophy: set up the infrastructure for smooth delivery before building features.

## License

MIT
