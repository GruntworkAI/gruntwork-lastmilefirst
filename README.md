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

# 3. Activate in the current session
/reload-plugins
```

## Updating Plugins

To get the latest plugin versions:

```bash
# Step 1: Refresh marketplace from GitHub
/plugin marketplace update gruntwork-lastmilefirst

# Step 2: Update the plugin
/plugin update lastmilefirst@gruntwork-lastmilefirst

# Step 3: Activate the new version in the current session
/reload-plugins
```

**Note:** Running only step 2 won't fetch new versions—Claude Code caches the marketplace index locally.

### Migrating from the old marketplace name (one time)

If you installed before **v0.16.0**, your marketplace is still registered as
`gruntwork-marketplace` (the old name). A plain `/plugin update` will **not**
work after the rename—removing the old marketplace orphans the plugin, so you
must re-install rather than update:

```bash
/plugin marketplace remove gruntwork-marketplace
/plugin marketplace add GruntworkAI/gruntwork-lastmilefirst
/plugin install lastmilefirst@gruntwork-lastmilefirst   # install, NOT update
/run-scan-secrets --install-hooks                       # refresh the pre-commit and pre-push hooks
/reload-plugins                                          # activate in this session
```

**Optional cleanup:** delete the now-orphaned old cache directory so the
secret-scan hooks (pre-commit and pre-push) can't fall back to a stale version:

```bash
rm -rf ~/.claude/plugins/cache/gruntwork-marketplace
```

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
| [lastmilefirst](plugins/lastmilefirst/) | 0.38.0 | Opinionated structure and workflow for projects built by people and coding agents. Includes PARC, expert agents, operatives, stack-wisdom, and stack-knowledge. |

## Other runtimes

The plugin is built for Claude Code, and two generated packages carry parts of it elsewhere.
Both are built from the plugin sources with a `build.py` and a `mapping.toml`, never copied by
hand, and neither is part of this marketplace.

| Adapter | What it carries | Status |
|---------|-----------------|--------|
| [adapters/muse](adapters/muse/) | PARC, the review and scan lenses, and the persona roster as a Muse skill package | Best-effort port against observed, undocumented interfaces |
| [adapters/codex](adapters/codex/) | PARC and read-only project, org, and context reviews as Codex skills | Bounded pilot; not verified in a live Codex session |

## About

This marketplace hosts plugins developed by [Gruntwork](https://github.com/GruntworkAI) for Claude Code. Each plugin follows the Last Mile First philosophy: set up the infrastructure for smooth delivery before building features.

## License

MIT
