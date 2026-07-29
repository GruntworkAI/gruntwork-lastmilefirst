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

## Gotchas

Every entry here cost a debugging session. The common shape: **the failure is silent — you get a plausible-looking success, not an error.**

| Issue | Symptom | Cause / fix |
|-------|---------|-------------|
| **`claude plugin update` leaves the OLD version loaded** | Update reports success, then a skill behaves like the previous version. | The CLI prints "Restart to apply changes" — the running session keeps the old code. Run `/reload-plugins` (user-typed; Claude can't invoke it) before using the skill; it reloads in place and preserves session context, unlike a full restart. Learned 2026-07-28 updating 0.18.0 → 0.20.0: scanning before the reload would have run 0.18.0's pre-modernization `gitleaks detect` path and produced a wrong scan that still looked clean. |
| **scan-secrets reads INSTALLED formats, not the shipped copy** | Ship a rule fix, re-scan, see no change. | Scans load `~/.claude/lastmilefirst/secret-formats/common_secret_formats.toml`, not `plugins/lastmilefirst/skills/scan-secrets/data/`. After any rule change, run `/run-scan-secrets --update-formats`. This preserves org rules; it only refreshes the common tier. |
| **Version check passes while cached files are stale** | Reported version is current, behavior is not. | Verify the cached *file contents*, not just the version number. If they're stale: `claude plugin uninstall <plugin>@<marketplace> && claude plugin install <plugin>@<marketplace>`. |
| **Adding a persona requires four files, not one** | New expert works via one entry point, missing from another. | README, the `run-consult-expert` command, `skills/consult-expert/SKILL.md`, and the persona file must be touched **together**. Drift found 2026-05-21: SKILL.md was missing 6 Key Hires and pointed at the wrong persona path (fixed in `ca4ee22`). |
| **scan-secrets hook is pre-commit only** | A commit that passed the hook still pushes secrets. | There is no pre-push hook. A `--no-verify` commit, or one made before the hook was installed, reaches the remote unchecked. Pre-push coverage is a tracked enhancement, not a shipped feature. |
| **Editing the cache instead of source** | Changes vanish on the next `/plugin update`. | Source is `~/Code/gruntwork/gruntwork-lastmilefirst/plugins/lastmilefirst/`. `~/.claude/plugins/cache/…` is install output — correct to *run* from, never to edit. Always `git pull` before starting. |
| **Not every skill works on Desktop** | A skill silently does nothing in the consumer app. | Personas (via `consult-expert`) work on Desktop. Overwatch and the filesystem skills (organize/scan/todos/review) are Claude-Code-only. Whether Skills auto-trigger on Desktop is still untested.
