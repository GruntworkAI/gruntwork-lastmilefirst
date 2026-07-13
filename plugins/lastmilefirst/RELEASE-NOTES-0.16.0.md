# lastmilefirst v0.16.0 - The Marketplace Rename

**Released:** July 13, 2026

This release renames the marketplace from `gruntwork-marketplace` to **`gruntwork-lastmilefirst`**. The old generic name implied a catch-all Gruntwork marketplace; in practice it only ever shipped this one plugin. Gruntwork has moved to a **one purpose-driven marketplace per plugin** model (see `gruntwork-travel-skills`), so the marketplace is now named for what it holds.

## ⚠️ Action Required: Re-add the Marketplace

The marketplace's registry key changed, so a one-time re-add is required. A plain `/plugin update` is **not** enough — the marketplace name it's registered under no longer matches.

```bash
# 1. Remove the old marketplace registration
/plugin marketplace remove gruntwork-marketplace

# 2. Add it back under the new name
/plugin marketplace add GruntworkAI/gruntwork-lastmilefirst

# 3. Reinstall the plugin
/plugin install lastmilefirst@gruntwork-lastmilefirst
```

Your GitHub URL redirects, so `git`/`gh` against the old repo name keep working — but the plugin's own scripts now resolve their cache paths under `gruntwork-lastmilefirst`, so the re-add is what makes the new install consistent end-to-end.

## What Changed

- **Marketplace name:** `gruntwork-marketplace` → `gruntwork-lastmilefirst` (in `marketplace.json`).
- **Repository:** renamed on GitHub to `GruntworkAI/gruntwork-lastmilefirst` (old URL permanently redirects).
- **Plugin key:** `lastmilefirst@gruntwork-marketplace` → `lastmilefirst@gruntwork-lastmilefirst`.
- **Cache/runtime paths:** all hardcoded `~/.claude/plugins/**/gruntwork-marketplace/lastmilefirst/**` references in the plugin's scripts, skills, and commands now resolve under `gruntwork-lastmilefirst`.

No feature or behavior changes in this release — it is a rename only.

## Updating

```bash
# See "Action Required" above — a plain update is not sufficient this time.
/plugin marketplace remove gruntwork-marketplace
/plugin marketplace add GruntworkAI/gruntwork-lastmilefirst
/plugin install lastmilefirst@gruntwork-lastmilefirst
```

---

**Full changelog:** See [CHANGELOG.md](./CHANGELOG.md)
