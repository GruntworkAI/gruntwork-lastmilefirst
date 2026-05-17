# Bug: scan-secrets produces thousands of `node_modules/` findings

**Status:** OPEN
**Priority:** high (makes scan output unreadable)
**Created:** 2026-05-17

## Summary

Workspace scans surface enormous finding counts driven almost entirely by `node_modules/` content rather than actual project code. From the 2026-05-17 workspace run:

| Repo | Findings | Likely real |
|---|---|---|
| gruntwork-remail | 6,194 | a handful (the `.env.DEV/.STG/.PRD/.LCL` triplet) |
| gruntwork-promptasaurus | 3,974 | unknown — buried in noise |
| gruntwork-website | 779 | unknown — buried in noise |
| gruntwork-unstacker | 26 | mostly `@types/node/crypto.d.ts` |

The unstacker tail confirms it: `MEDIUM lmf-hardcoded-password ...node_modules/@types/node/crypto.d.ts:787` and similar across `keyv/README.md`, `commander/Readme.md`, etc. These are vendored package contents that the user did not write and cannot remediate.

## Root Cause (to verify)

`gitleaks detect` scans git history. The fact that `node_modules/` content shows up in findings means one of:

1. **`node_modules/` was committed to the repo at some point** — likely for early-stage deployment artifacts that were later gitignored
2. **The scan-secrets script invokes gitleaks against the working tree, not just history** — would need to inspect `plugins/lastmilefirst/skills/scan-secrets/scripts/scanner.py` to confirm
3. **gitleaks lacks a default `node_modules/` exclude in our config** — gitleaks honors `.gitleaksignore` and `paths` rules but doesn't auto-exclude common vendor dirs

Most likely a combination: some repos historically committed `node_modules/`, AND our config doesn't filter vendor paths from the report.

## Symptom

- Workspace scan reports are unscannable by a human (6,194 findings in one repo)
- Real findings get buried (the actual `.env.DEV` postgres URL in remail is invisible among 6,194 lines)
- Users start ignoring scan results — defeats the purpose

## Fix Options

1. **Add a built-in path exclude list to merged gitleaks config (recommended, fast):**
   - Inject a global allowlist into `format_loader.write_merged_config()` that excludes `node_modules/`, `.venv/`, `vendor/`, `dist/`, `build/`, `.next/`, `.terraform/`, `*.min.js`, `*.min.css`
   - Implementation: prepend an `[allowlist]` block (gitleaks top-level allowlist) with `paths = [...]` regexes
   - This filters findings even if the paths exist in git history

2. **Respect `.gitignore` at scan time:**
   - Pass `--no-ignore` opposite — i.e., have scan-secrets read `.gitignore` and pass matching paths to gitleaks's allowlist
   - More flexible but more work; option 1 covers 95% of cases

3. **Surface "ignorable" findings separately:**
   - Post-process gitleaks JSON output; bucket findings by "in vendor path" vs "in source"
   - Print vendor count as one summary line, source findings in detail

## Files Affected

- `plugins/lastmilefirst/skills/scan-secrets/scripts/format_loader.py` (add global allowlist injection)
- `plugins/lastmilefirst/skills/scan-secrets/data/common_secret_formats.toml` (or a sibling `common_excludes.toml`)
- `plugins/lastmilefirst/skills/scan-secrets/scripts/scanner.py` (if reformatting output)

## Verification

After fix, re-run `python3 .../scan_secrets.py --all` on Michael's workspace:
- gruntwork-website findings should drop from 779 to single digits
- gruntwork-remail findings should drop from 6,194 to ~5 (the real env files)
- The actual real-world secrets should be visible at a glance

## Notes

Discovered 2026-05-17 during the same workspace audit that surfaced the Overwatch freshness bug and the self-match bug. Recommend fixing all three together as a "scan output usability" mini-epic.

The companion bug (scan-secrets matching its own `common_secret_formats.toml` regex patterns) is filed separately as `bug-scan-secrets-self-match-on-format-file.md` since the fix is targeted differently.

**Shared surface area with `feature-scan-secrets-repo-local-config.md`:** both proposals touch `format_loader.write_merged_config()`. The feature adds an `[extend]` section for per-repo `.gitleaks.toml`; this bug adds a global `[allowlist] paths`. The feature also gives users a workaround for this bug (projects can ship their own `[allowlist]` rules in repo-local config) — but the global built-in default is still worth shipping so every project doesn't have to reinvent the same node_modules/.venv/dist exclusion list. Land them together or coordinate the design.
