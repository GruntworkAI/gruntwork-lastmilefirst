# Plan: Resolve 4 scan-secrets + Overwatch bugs (v0.14.2)

**Created:** 2026-05-17
**Status:** Approved — implementing direct to main, no branch, hand-verified
**Outcome:** Single plugin release `v0.14.2` resolving the four bugs filed earlier today

## Context

The 2026-05-17 workspace audit surfaced four plugin bugs that together make the Overwatch workspace summary and scan-secrets output unreliable. All four were filed as todos earlier in the session; this plan converts them into a single coordinated fix.

Source todos:
- `.claude/work/todos/bug-overwatch-activity-blind-freshness.md`
- `.claude/work/todos/bug-scan-secrets-node-modules-noise.md`
- `.claude/work/todos/bug-scan-secrets-self-match-on-format-file.md`
- `.claude/work/todos/bug-scan-secrets-all-mode-state-update.md`

## Scope / file-touch map

| Bug | File(s) | Approach |
|---|---|---|
| 2+3 (vendor noise + self-match) | `plugins/lastmilefirst/skills/scan-secrets/scripts/format_loader.py` | Inject a `[allowlist] paths = [...]` block into the merged gitleaks config covering vendor dirs (`node_modules/`, `.venv/`, `vendor/`, `dist/`, `build/`, `.next/`, `.terraform/`) and the plugin's own `data/*.toml` |
| 4a (--all doesn't update state) | `plugins/lastmilefirst/skills/scan-secrets/scripts/scan_secrets.py` | After each repo scan in the `--all` loop, call the same per-project state-update path the single-repo flow uses, with key `{org}/{project_dir.name}` |
| 4b (--full double-print) | `plugins/lastmilefirst/hooks/scripts/session_start.py` | Trace from `if __name__ == "__main__":`; likely a duplicate `_render` call inside the `--full` branch — gate it |
| 1 (activity-blind freshness) | `plugins/lastmilefirst/hooks/scripts/session_start.py` (and possibly `update_state.py` for cache schema) | Cache `last_commit_ts` per project in state; in the freshness checks, flag stale only when `last_commit_ts > last_scan` |

## Order of work

1. **Bugs 2 + 3** — smallest surface, biggest immediate signal-quality win
2. **Bug 4a** — restores trust in `--all` mode
3. **Bug 1** — most architecturally interesting; depends on a state-schema addition (`last_commit_ts`)
4. **Bug 4b** — trivial cleanup once we're already in `session_start.py` for bug 1

## Version + release

Bump plugin from `v0.14.1` → `v0.14.2`. None of these are breaking.

Per `~/Code/gruntwork/gruntwork-marketplace/CLAUDE.md`, update all three places:
- `plugins/lastmilefirst/.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json`
- `README.md` version table

Commit pattern: separate commit per bug fix (4 commits) + one version-bump commit + push to main. Direct-to-main per session decision; no branch.

## Verification (hand-tested, no new test suite)

| Fix | Smoke check |
|---|---|
| 2+3 | `python3 scan_secrets.py` in `gruntwork-marketplace`: expect 0 findings (was 3 from self-match). In `gruntwork-website`: expect < 20 (was 779 from `node_modules`) |
| 4a | `scan_secrets.py --all` then `session_start.py --full`: "Never scanned for secrets" list should be empty for all 23 scanned repos |
| 1 | Touch a file in one repo + commit; rerun `session_start.py --full`: only that repo should appear in "stale" (`stale_scanned` / `stale_reviewed`); dormant repos should not |
| 4b | `session_start.py --full`: report renders once, not twice |

If any smoke check fails, fix and re-test before moving on.

## Out of scope

- Repo-local `.gitleaks.toml` support (`feature-scan-secrets-repo-local-config.md`) — adjacent, shares the same `write_merged_config()` surface, but is its own design decision. Leave for a future change.
- Updating the existing four bug-todo files to "RESOLVED" status — do that as part of the same release commit batch.

## Risk / concerns

- **Bug 1 latency:** Shelling out to `git log -1 --format=%ct` per project on every session start adds startup time on workspaces with many repos. Mitigation: cache `last_commit_ts` in state, refresh only when explicitly probed (e.g., on each `update_state.py` call), not every session start.
- **Allowlist coverage:** The vendor-dir list could miss something less common (e.g., `target/` for Rust, `_build/` for Elixir). Acceptable — start with the JS/Python/Terraform-heavy set and add as needed.
- **Backwards compat:** The state schema gets a new optional `last_commit_ts` field per project. Missing field = `0` (treat as "no cached value, recompute"). No migration needed.
