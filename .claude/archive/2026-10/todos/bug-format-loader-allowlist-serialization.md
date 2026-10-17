# Bug: scan-secrets format_loader mishandles `[rules.allowlist]` sub-tables

**Status:** RESOLVED in v0.14.1 (2026-05-12)
**Priority:** medium
**Created:** 2026-05-04
**Resolved:** 2026-05-12

## Resolution

Fixed alongside two related bugs (basic-string regex quoting, and scanner silent-pass on gitleaks abort) discovered during the OpenCanon `oc_p1_*` rule addition. All three shipped together in plugin v0.14.1.

**Allowlist fix (`format_loader.py:write_merged_config`):** dict-value sub-tables are now collected during the rule's key iteration and emitted *after* all scalars/lists (TOML ordering invariant). Each sub-table's contents are serialized with the same type-dispatch logic as the parent rule's keys.

**Related fixes shipped in the same commit:**
- All string serialization switched from TOML basic strings (`"""..."""`) to literal strings (`'''...'''`) — basic strings were silently mangling regex escape sequences (`\d`, `\s`) and hard-erroring on `\+`.
- `scanner.py` `scan_staged()` and `scan_repo()` now fail-closed when the requested gitleaks report file doesn't exist (gitleaks uses exit 1 ambiguously for both "leaks found" and "config error" — report-file existence is the reliable signal).

**Smoke-tested 2026-05-12:** good config catches a fixture `oc_p1_*` token (exit 1); deliberately malformed config triggers fail-closed with stderr surfaced (exit 1). Three shipped rules with `[rules.allowlist]` (`lmf-hardcoded-password`, `lmf-bearer-token-hardcoded`, `lmf-jwt-secret`) now serialize correctly.

---

## Original report (preserved below for context)


## Summary

`scan-secrets`'s `format_loader.write_merged_config()` produces a malformed gitleaks TOML when a rule contains a nested table like `[rules.allowlist]`. The author left an explicit "Wrong for arrays, handle separately" comment, so this was a known TODO that never landed.

Two shipped common rules use this pattern (`lmf-hardcoded-password` and `lmf-bearer-token-hardcoded`), so test-path allowlists currently don't reach gitleaks correctly.

## Root Cause

`plugins/lastmilefirst/skills/scan-secrets/scripts/format_loader.py:177-179`:

```python
elif isinstance(value, dict):
    # Handle nested tables like [rules.allowlist]
    lines.append(f"[rules.{key}]")  # Wrong for arrays, handle separately
```

The serializer just emits a `[rules.{key}]` header line and moves on. That:

1. Becomes a *new* top-level table in the temp config rather than a sub-table of the current rule
2. Drops the dict's actual contents (the allowlist's `paths`, `regexes`, etc.) — they're never written
3. Likely breaks the parent rule's structure since the next `[[rules]]` header now sits under the orphan `[rules.{key}]` table

## Symptom

Test files containing strings that match `lmf-hardcoded-password` or `lmf-bearer-token-hardcoded` get flagged in scans because the test-path allowlist (`paths = ['(?:test|spec|mock|fixture|example|sample|demo)']`) never reaches gitleaks.

To verify: run the scanner on a repo with a fixture file containing a long hardcoded password literal in a `*test*` path; current behavior flags it, expected behavior is silent.

## Fix Options

1. **Restructure the serializer to track context (recommended):**
   - Split the loop: emit each rule's scalar/list fields, then emit nested table sub-sections (`[rules.allowlist]`, `[rules.entropy]`) with proper key/value pair serialization of their dict contents, then emit the next `[[rules]]` header
   - Need to handle that gitleaks' nested config tables (`[rules.allowlist]` and `[rules.entropy]`) attach to the most-recently-declared `[[rules]]` block

2. **Use a real TOML writer:**
   - Add `tomli-w` to the script's requirements; it handles nested tables correctly
   - Trade-off: a new runtime dep on a tiny library; cleaner serialization

3. **Restrict common rules to flat fields only (workaround, not a fix):**
   - Drop `[rules.allowlist]` from the two affected rules; accept the false positives
   - Document that nested tables aren't supported

## Files Affected

- `plugins/lastmilefirst/skills/scan-secrets/scripts/format_loader.py` (the bug)
- `plugins/lastmilefirst/skills/scan-secrets/data/common_secret_formats.toml` (the two affected rules — would surface as previously-suppressed false positives if scans were re-run after fix)

## Verification

After fix, run `/run-scan-secrets --list-formats` and confirm the two rules' allowlists appear in the loaded data, then run a scan against a fixture repo with hardcoded-password strings in `tests/` paths and confirm they're no longer flagged.

## Notes

Discovered 2026-05-04 during an OpenCanon project audit of scan-secrets coverage for the OpenCanon-specific `oc_p1_*` proxy bearer token format. Memory captured at `bug_lmf_format_loader_allowlist.md`.

Related plugin work surfaced in the same audit: scan_secrets.py doesn't honor repo-local `.gitleaks.toml` (filed separately as `feature-scan-secrets-repo-local-config.md` if/when needed).
