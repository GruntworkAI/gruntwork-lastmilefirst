# Todo: Update manifest descriptions to match the README framing

**Status:** DONE 2026-09-24 (shipped in 0.34.0, feat/review-org)
**Priority:** low
**Created:** 2026-09-21

## Summary

The plugin README now opens by saying what the plugin is for: an opinionated plugin for projects where people and coding agents both do the work, organized around the question "what if someone else wants to contribute to this project?" The three manifest description strings still describe it as a feature list. Update them with the next version bump (0.32.0 or whatever comes next).

## Why this was held

Changing the strings without a bump would leave `main` and the `v0.31.0` release tag carrying different descriptions under the same version number. Desktop/consumer installs resolve from the tag, so the two surfaces would disagree.

## Requested Change

`plugins/lastmilefirst/.claude-plugin/plugin.json`, `description`, and `.claude-plugin/marketplace.json`, `plugins[].description`:

```
Opinionated structure and workflow for projects built by people and coding agents: project structure, tiered CLAUDE.md, PARC workflow, AI expert agents, org-level operatives and stack-wisdom, and Overwatch drift checks.
```

`.claude-plugin/marketplace.json`, `metadata.description`:

```
Marketplace for the lastmilefirst plugin: opinionated structure and workflow for projects built by people and coding agents.
```

## Also

The GitHub repo description is set in GitHub's settings (i.e. not in a file). Done 2026-09-21, with wording the author approved. Do not overwrite it when updating the manifests:

```
Opinionated Claude Code plugin for projects built by people and coding agents. Sets up the structure that lets someone else contribute, then identifies drift as the project ages.
```
