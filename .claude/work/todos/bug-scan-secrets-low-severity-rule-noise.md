# Bug: two low-severity rules generate most of the false positives in a workspace sweep

**Status:** OPEN
**Priority:** medium (does not miss secrets; makes `--all` output expensive to triage)
**Created:** 2026-08-30

## Summary

A full `--all` sweep across a 28-repo workspace produced 93 findings, **none of which were live secrets**. Two rules in `data/common_secret_formats.toml` accounted for the large majority. Because every sweep re-reports them, the human cost of triage is paid again on each run, which is the failure mode that makes people stop reading scan output.

This is a precision problem, not a recall problem. Both fixes below narrow *where* a rule applies; neither weakens detection of a real credential.

## Defect 1 — `lmf-postgres-connection-string` has no allowlist

```toml
regex = '''postgres(?:ql)?://[^:]+:[^@]+@[^/]+'''
```

It matches the standard local test-database URL (`postgres://postgres:postgres@localhost/<db>_test`) that appears in CI config, fixtures, and docs. In one application repo it fired 35 times, all in `tests/` and a config default. Comparable rules already carry a path allowlist — this one was simply never given one. <!-- gitleaks:allow — this line is itself an instance of defect 1 -->

**Proposed fix** — add the allowlist the sibling rules already use, plus a value-level exclusion for credentials that are self-evidently non-secret:

```toml
[rules.allowlist]
description = "Local/test databases and fixture paths"
paths = ['''(?:test|spec|mock|fixture|example|sample|demo)''']
regexes = ['''postgres(?:ql)?://(?:postgres|user|username|root):(?:postgres|password|pass|secret)@(?:localhost|127\.0\.0\.1|db|postgres)''']
```

Apply the same treatment to `lmf-mysql-connection-string`, `lmf-mongodb-connection-string`, and `lmf-redis-connection-string`, which share the shape and the gap.

## Defect 2 — `lmf-hardcoded-password` matches across quote boundaries

```toml
regex = '''(?i)(?:password|passwd|pwd)\s*[:=]\s*["'][^"']{8,}["']'''
```

The `[^"']{8,}` run is not constrained to stay inside the string that opened it. Given a shell line such as:

```sh
sudo -p "Enter your Mac login password: " systemsetup -getremotelogin | grep -q "On"  # gitleaks:allow
```

the rule matches `password: "` as the opener and then consumes forward to the *next* quote on the line — reporting an interactive prompt string as a hardcoded credential. The rule's existing `paths` allowlist does not help, because setup scripts do not live under a test path. <!-- gitleaks:allow — this line is itself an instance of defect 2 -->

**Proposed fix** — require the keyword to be an assignment target rather than trailing prose, and keep the captured value off obvious prompt text:

```toml
regex = '''(?i)(?:^|[\s;{(,])(?:password|passwd|pwd)\s*[:=]\s*["'][^"'\s]{8,}["']'''
```

Excluding whitespace from the value run is the substantive change: real hardcoded passwords rarely contain spaces, prompt strings almost always do. Worth a regression fixture in `tests/` covering the `sudo -p` shape specifically.

## Non-goal: global test-path allowlisting

An earlier framing of this was "allowlist `tests/` globally in `GLOBAL_ALLOWLIST_PATHS`." **Rejected.** That would also suppress the high-severity provider-key rules (`lmf-anthropic-api-key`, `lmf-openai-project-key`, and the gitleaks defaults for AWS/GitHub/Stripe) inside test directories — and a real provider key committed to a test file is a genuine and common incident. Suppression belongs per-rule, scoped to the low-severity rules where a fixture value is indistinguishable from a real one by construction.

## Note for org-rule authors

Custom rules added via `--add-format` inherit no allowlist. Any rule whose format is deliberately reproduced in fixtures (`<prefix>_DEVDEV…`, `<prefix>_FixedToken…`) needs its own `[rules.allowlist]` with `paths` and a `regexes` entry for the fixture shapes, or it becomes a permanent noise source in its own repo. The `--add-format` flow should prompt for this; worth a follow-up.

## Verification

Per-rule `[rules.allowlist]` is already proven end-to-end — `lmf-hardcoded-password` ships one, and `format_loader.py` deliberately emits sub-tables after scalars so nested allowlists survive the merge (see `bug-format-loader-allowlist-serialization.md`). An org-rule allowlist of exactly this shape was applied to a consumer's custom rule and took that repo from 10 findings to clean, confirming the mechanism.

Acceptance: re-run `--all` over a comparable workspace and confirm the two rules above drop to zero findings while a seeded real credential in a test file is still reported.

## Self-demonstrating

The pre-commit hook blocked the first attempt to commit *this file*, flagging three lines at HIGH (public-repo bump): the prose example of defect 1, and both the shell example and the prose description of defect 2. The document describing the two defects is itself an instance of each.

Suppressed with inline `gitleaks:allow` markers rather than reworded, so the triggering text stays intact as a fixture. Same family as `bug-scan-secrets-self-match-on-format-file.md`, and more evidence that these two rules match ordinary technical prose — not just test code.
