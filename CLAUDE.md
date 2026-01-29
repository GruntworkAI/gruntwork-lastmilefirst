# Gruntwork Marketplace

Claude Code plugin marketplace for Gruntwork development workflows.

## CRITICAL: Version Bumping

**When bumping a plugin version, you MUST update ALL of these files:**

1. `plugins/<plugin-name>/.claude-plugin/plugin.json` - The plugin's own version
2. `.claude-plugin/marketplace.json` - The marketplace index (what Claude Code reads!)
3. `README.md` - The version table

**Why this matters:** Claude Code reads the marketplace.json to determine available versions. If you only update plugin.json, users will see stale versions when running `/plugin update`.

### Version Bump Checklist

```bash
# After updating plugin.json version to X.Y.Z:
# 1. Update marketplace.json
sed -i '' 's/"version": "[^"]*"/"version": "X.Y.Z"/' .claude-plugin/marketplace.json

# 2. Update README.md table
# Find the plugin row and update the version number

# 3. Commit all three files together
git add plugins/<name>/.claude-plugin/plugin.json .claude-plugin/marketplace.json README.md
git commit -m "chore(<plugin-name>): Bump version to X.Y.Z"
```

## Repository Structure

```
gruntwork-marketplace/
├── .claude-plugin/
│   └── marketplace.json    # INDEX FILE - lists all plugins with versions
├── plugins/
│   └── lastmilefirst/      # Plugin source
│       ├── .claude-plugin/
│       │   └── plugin.json # Plugin metadata & version
│       ├── commands/
│       ├── skills/
│       ├── agents/
│       └── ...
└── README.md               # Also contains version table
```

## Adding a New Plugin

1. Create directory under `plugins/<plugin-name>/`
2. Add `.claude-plugin/plugin.json` with name, version, description
3. Add entry to `.claude-plugin/marketplace.json` plugins array
4. Add row to README.md version table
