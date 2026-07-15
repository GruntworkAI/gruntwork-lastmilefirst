# Feature: scan-secrets honors repo-local `.gitleaks.toml`

**Status:** open
**Priority:** medium
**Created:** 2026-05-04

## Summary

`scan-secrets` always passes `--config <merged_temp>` to gitleaks, which suppresses gitleaks' auto-detection of `.gitleaks.toml` at the repo root. Projects can't ship per-repo custom secret rules that travel with their source.

The current two-tier system (common + org) requires every contributor to install the same rules into their personal `~/.claude/lastmilefirst/secret-formats/org_secret_formats.toml`, which doesn't scale to open-source projects with project-specific token formats.

## Why It Matters

Real example: OpenCanon mints a proxy bearer token with prefix `oc_p1_*` (PRD §1.2 / §2.10.E.1). The format isn't in any default ruleset. Without per-repo config support:

- Solo developer: must remember to add the rule via `--add-format` on every machine they work from
- Open-source contributors at P3+: each contributor must install the rule manually, or accept that their pre-commit hook misses OpenCanon-specific leaks
- CI: must bypass `scan_secrets.py` entirely and call `gitleaks` directly with `--config .gitleaks.toml`

## Proposed Fix

`plugins/lastmilefirst/skills/scan-secrets/scripts/scanner.py` and `format_loader.py`:

1. In `write_merged_config()`, detect if the target repo has a `.gitleaks.toml` at its root (need to thread the `repo_path` through from the caller, since `write_merged_config` currently doesn't know about repo context)

2. If yes, emit an `[extend]` section in the temp config:

   ```toml
   [extend]
   path = "/abs/path/to/repo/.gitleaks.toml"
   useDefault = true
   ```

3. Document the precedence: gitleaks defaults < common rules < org rules < repo-local rules (same-id last-writer-wins)

## Alternative

If threading repo_path through the format_loader feels intrusive, an even simpler approach: in `scanner._run_gitleaks()`, when the cwd is a git repo with `.gitleaks.toml`, append a second `--config` flag — gitleaks supports multiple. Verify that gitleaks' multi-config merge behavior matches what we want.

## Files Affected

- `plugins/lastmilefirst/skills/scan-secrets/scripts/scanner.py`
- `plugins/lastmilefirst/skills/scan-secrets/scripts/format_loader.py`
- `plugins/lastmilefirst/skills/scan-secrets/SKILL.md` (document the new tier)

## Workaround Until Fixed

Projects with custom secret formats should add a CI step that runs gitleaks directly:

```yaml
- name: Secret scan
  uses: gitleaks/gitleaks-action@v2
  with:
    config-path: .gitleaks.toml
```

CI is the strongest defense anyway — runs on every push regardless of contributor's local hooks.

## Notes

Discovered 2026-05-04 during an OpenCanon project audit. Memory at `project_lmf_scan_secrets_repo_config.md`. Related: `bug-format-loader-allowlist-serialization.md` (different but adjacent issue in the same scanner pipeline).
