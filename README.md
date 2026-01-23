# Gruntwork Marketplace

Claude Code plugins for Gruntwork development workflows.

## Installation

```bash
# Add marketplace (one time)
claude plugin marketplace add https://github.com/GruntworkAI/gruntwork-marketplace

# Install plugins
claude plugin install lastmilefirst@gruntwork-marketplace
```

## Updating Plugins

To get the latest plugin versions, you need to update the marketplace first, then update the plugin:

```bash
# Step 1: Refresh marketplace from GitHub
/plugin marketplace update gruntwork-marketplace

# Step 2: Update the plugin
/plugin update lastmilefirst
```

Running only step 2 won't fetch new versions—Claude Code caches the marketplace index locally.

## Available Plugins

| Plugin | Version | Description |
|--------|---------|-------------|
| [lastmilefirst](plugins/lastmilefirst/) | 0.6.0 | AI expert agents, CLAUDE.md management, project organization |

## About

This marketplace hosts plugins developed by [Gruntwork](https://github.com/GruntworkAI) for Claude Code. Each plugin follows the Last Mile First philosophy: set up the infrastructure for smooth delivery before building features.

## License

MIT
