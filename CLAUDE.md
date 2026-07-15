# Gruntwork LastMileFirst

Purpose-driven Claude Code marketplace for the `lastmilefirst` plugin (PARC workflow, AI expert agents, workspace organization, Claude configuration management).


## Archetype: Usable

## CRITICAL: Version Bumping

**When bumping a plugin version, you MUST update ALL of these files:**

1. `plugins/<plugin-name>/.claude-plugin/plugin.json` - The plugin's own version
2. `.claude-plugin/marketplace.json` - BOTH `metadata.version` AND `plugins[].version` (what Claude Code reads!)
3. `README.md` - The version table

**Why this matters:** Claude Code reads the marketplace.json to determine available versions. If you only update plugin.json, users will see stale versions when running `/plugin update`. Keep all three marketplace `version` fields (metadata + every plugin entry) equal to the plugin version — a drifted `metadata.version` is a bug (was found at `1.0.0` while the plugin was `0.16.0`, 2026-07-14).

**CRITICAL: cut a GitHub release/tag for the CONSUMER surface (learned 2026-07-14).** Merging to `main` makes the new version available in **Claude Code** (it resolves the marketplace from the default branch). But the **claude.ai / Claude Desktop** consumer app resolves a plugin via its GitHub **release/tag**, NOT the default branch — with no release/tag, a Desktop install **404s / "release not found."** So the version bump is not fully released until you cut the tag. Do it every bump.

### Version Bump Checklist

```bash
# After updating plugin.json version to X.Y.Z:
# 1. Update marketplace.json (sets BOTH metadata.version and plugins[].version)
sed -i '' 's/"version": "[^"]*"/"version": "X.Y.Z"/' .claude-plugin/marketplace.json

# 2. Update README.md table
# Find the plugin row and update the version number

# 3. Commit all three files together, open a PR, merge to main
git add plugins/<name>/.claude-plugin/plugin.json .claude-plugin/marketplace.json README.md
git commit -m "chore(<plugin-name>): Bump version to X.Y.Z"

# 4. AFTER the merge to main: cut the GitHub release/tag (required for Desktop/consumer installs)
gh release create vX.Y.Z --target main --latest --title "vX.Y.Z" --notes "..."
```

## Repository Structure

```
gruntwork-lastmilefirst/
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
