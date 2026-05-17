# Bug: scan-secrets flags its own `common_secret_formats.toml` rule regexes

**Status:** OPEN
**Priority:** medium (only affects scanning the marketplace repo itself, but PUBLIC)
**Created:** 2026-05-17

## Summary

Running `scan-secrets` against `gruntwork/gruntwork-marketplace` (a PUBLIC repo) produces 3 HIGH-severity findings — all inside the plugin's own `data/common_secret_formats.toml` file. The regex *patterns* the rules define are matched by the rules they define.

From the 2026-05-17 scan output:

```
HIGH * lmf-mysql-connection-string    ...rets/data/common_secret_formats.toml  22
HIGH * lmf-redis-connection-string    ...rets/data/common_secret_formats.toml  36
HIGH * lmf-pkcs8-key                  ...rets/data/common_secret_formats.toml  123
```

These are false positives but they show up as HIGH on a PUBLIC repo (the severity bump from PUBLIC repo handling makes it worse). A user seeing this without context might think the plugin itself leaked credentials.

## Root Cause

`plugins/lastmilefirst/skills/scan-secrets/data/common_secret_formats.toml` contains regex examples like:

```toml
regex = '''mysql://[^:]+:[^@]+@[^/]+/'''
```

When gitleaks scans the marketplace repo's git history, the regex source code itself matches the regex pattern (because the pattern is, by design, intended to match strings like `mysql://user:pass@host/`).

The plugin's merged config has no allowlist excluding the format-definition files themselves.

## Symptom

Anyone running `scan-secrets` against `gruntwork-marketplace` (or any future repo that vendors the plugin's TOML files) gets these spurious findings. Combined with the PUBLIC-repo severity bump (`MEDIUM → HIGH`), they look alarming.

## Fix Options

1. **Self-exclude the plugin's data dir (recommended):**
   - Inject an allowlist path regex into the merged config:
     ```toml
     [allowlist]
     paths = [
       '''plugins/lastmilefirst/skills/scan-secrets/data/.*\.toml''',
     ]
     ```
   - Could also exclude generically: `.*secret.*formats.*\.toml`, `\.gitleaks\.toml`, `\.gitleaksignore` — anyone shipping rule files would benefit

2. **Add per-rule allowlist regex entries:**
   - Each rule that contains its own regex as example text gets an allowlist entry that suppresses self-match
   - More precise but tedious; option 1 is enough

3. **Move regex examples to comments only:**
   - Strip example strings from the TOML, document them in `references/` markdown instead
   - Doesn't generalize — any downstream user shipping format rules will hit the same issue

Option 1 + a small "if you ship custom rules, see ..." doc note is the right tradeoff.

## Files Affected

- `plugins/lastmilefirst/skills/scan-secrets/scripts/format_loader.py` (add global path allowlist to merged config)
- `plugins/lastmilefirst/skills/scan-secrets/data/common_secret_formats.toml` (no changes needed if allowlist covers the path)

## Verification

After fix:
- `python3 scan_secrets.py` run inside `gruntwork-marketplace`: 0 findings expected
- Run inside a fixture repo that contains a *real* mysql conn string: still 1 finding
- `--list-formats` output should still show all rules (allowlist doesn't drop rules, just suppresses matches in specific paths)

## Notes

Discovered 2026-05-17 during the same workspace audit. Related to `bug-scan-secrets-node-modules-noise.md` — both are "scan output usability" issues, both fix in the same `format_loader.py` config-injection point. Consider doing them together.

Also touches the surface area of `feature-scan-secrets-repo-local-config.md` (which adds `[extend]` for per-repo `.gitleaks.toml`). All three changes converge on `write_merged_config()` — worth coordinating the design so the merged config grows additively (defaults → common → org → repo-local) with allowlists composing correctly across tiers.

Related upstream: this is a known gitleaks pattern — projects that ship gitleaks configs typically allowlist their own `.gitleaks.toml` to avoid self-match. We should do the same for our format file.
