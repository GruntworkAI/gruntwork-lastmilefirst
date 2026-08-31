# Plan: check GitHub's own secret-scanning posture on public repos

**Status:** APPROVED 2026-08-30 — in build
**Created:** 2026-08-30
**Type:** feature (scan-secrets + Overwatch)

## Problem

The plugin scans repo *contents* for secrets but never asks whether GitHub's own defenses are switched on. Those are a different and complementary layer:

- **Secret scanning** — GitHub detects branded credentials (AWS, Stripe, GitHub PATs) and notifies the issuing vendor through the partner program, which for many providers means automatic revocation.
- **Push protection** — blocks the push server-side *before* the secret reaches the remote. Unlike our pre-commit hook, `--no-verify` does not defeat it.

Both are **free on public repos** and both can be off. Repository-level push protection is **disabled by default**; only user-level protection for personal accounts is on by default, and that does not cover other contributors.

A manual sweep on 2026-08-30 found one of five public repos in a workspace with both settings disabled — public, active, and unguarded, with no signal anywhere that this was the case. Nothing in the plugin would ever have surfaced it. That is the gap.

This is a **posture** check, not a content check. It answers "is the safety net switched on?", which the existing content scan cannot.

## Design

### One call, not two

`gh repo view --json` exposes no security fields (`isSecurityPolicyEnabled` and `securityPolicyUrl` are about SECURITY.md, not secret scanning). The REST endpoint returns both facts together:

```bash
gh api repos/{owner}/{repo}   # → .visibility and .security_and_analysis.*
```

Measured at ~340ms. `session_start.check_repo_visibility()` already shells out to `gh repo view` on every session start, so **switching that one call to `gh api` yields the new signal at no added latency.** This is the whole reason the feature is cheap.

Fields consumed:

| Field | Use |
|---|---|
| `.visibility` | replaces the existing `gh repo view` result |
| `.security_and_analysis.secret_scanning.status` | enabled / disabled |
| `.security_and_analysis.secret_scanning_push_protection.status` | enabled / disabled |

### Three states, not two

`security_and_analysis` is **absent entirely** for callers without admin on the repo. Treating absent as "disabled" would fire a false alarm at every contributor on every repo they don't own — the exact noise failure documented in `bug-scan-secrets-low-severity-rule-noise.md`. So:

| State | Condition | Behavior |
|---|---|---|
| `enabled` | status is `enabled` | silent |
| `disabled` | status is `disabled` | alert |
| `unknown` | key absent, non-zero exit, `gh` missing, timeout | **silent**, reported only in `--audit` verbose output |

### Scope: public AND owned only

- **Private repos are skipped entirely.** Secret scanning on private repos requires paid GitHub Secret Protection. Flagging them would be a permanent, unfixable alert — noise by construction.
- **Repos the user cannot administer are skipped**, which the `unknown` state handles naturally: no admin, no `security_and_analysis`, no alert.
- Forks and third-party remotes fall out for the same reason. Consistent with the `owns_remotes` claim-registry semantics — the directory is the governance signal, and settings you cannot change are not your finding.

## Surfaces

1. **`--audit`** — add a "GitHub protections" block beside the existing visibility line. Reports all three states, including `unknown` with the reason, since audit is explicitly diagnostic.
2. **`--all`** — one summary line naming public repos with protections off. Cost is one call per *public* repo only; private repos short-circuit before the call.
3. **Overwatch session start** — alert when the current repo is public, owned, and has either setting disabled.

Proposed alert text:

```
ACTION REQUIRED: PUBLIC repo (owner/name) has GitHub push protection disabled.
Enable: gh api -X PATCH repos/owner/name \
  -F 'security_and_analysis[secret_scanning][status]=enabled' \
  -F 'security_and_analysis[secret_scanning_push_protection][status]=enabled'
```

ACTION REQUIRED rather than WARNING is justified because the condition is rare, unambiguous, fixable by one pasteable command, and **self-extinguishing** — once fixed it never fires again. It fails the noise test only if it recurs, which it cannot.

Enabling secret scanning first is required; push protection depends on it. A single PATCH carrying both keys works (verified 2026-08-30).

### Caching

Follow the existing `plugin_update_cache` precedent in `overwatch-state.json` under `global`. Cache per repo under `projects.<org>/<repo>.github_protections` with a timestamp; re-check at most once every 24h. Session start must stay fast, and posture changes rarely.

## Non-goals

- **Do not auto-enable.** Changing a repo's security settings is the user's call, and the plugin has no business mutating GitHub config from a session-start hook. Emit the command; let the human run it.
- **Do not flag `secret_scanning_non_provider_patterns` or `validity_checks`.** Both are tier-gated; on a free public repo they read `disabled` permanently. Alerting on them would be unfixable noise. Worth a one-line mention in `--audit` output only, since generic-pattern detection is precisely what our own `lmf-*` rules cover — that division of labor is useful for a reader to understand.
- **Do not check private repos**, per Scope above.

## Tests

Under `skills/scan-secrets/tests/` (new file — the skill currently has no test dir; `hooks/tests/` and the other suites carry their own `conftest.py`, and per the repo's Dev Gotchas the suites cannot be run in one command).

Fixtures for the `gh api` JSON:
1. public + both enabled → no alert
2. public + push protection disabled → alert
3. public + scanning disabled → alert
4. private → no call made at all (assert the subprocess is never invoked)
5. `security_and_analysis` key absent → `unknown`, no alert
6. `gh` missing / non-zero exit / timeout → `unknown`, no alert, no traceback

## Acceptance

- A public repo with protections off produces exactly one session-start alert carrying a working command.
- Enabling the settings silences it on the next session.
- A private repo, a fork, and a repo without admin access each produce nothing.
- No added session-start latency versus today, since the existing `gh repo view` call is replaced rather than supplemented.

## Resolved: `--all` covers the whole account

**Decision (Fish, 2026-08-30): `--all` should check every public repo on the account, not only the ones cloned locally.** The motivating gap would have been missed by a clone-only sweep if that repo had happened not to be checked out, and posture is a property of the repo on GitHub rather than of the working copy.

Implications:

- `--all` gains an account-wide pass using the same `gh repo list --visibility public` plumbing that `--audit --github` already uses.
- **Which accounts?** Derive them from the per-org identity contracts (`<org>/.claude/org.json` → `identity.github_account`), deduped. This avoids hardcoding and picks up new orgs automatically.
- **Multi-account works without switching.** `gh auth switch` is machine-global and must never be called from a scan. It is not needed here: listing another account's *public* repos succeeds from any authenticated identity. Posture for repos the caller cannot administer resolves to `unknown` and stays silent, exactly as designed.
- Output separates the two passes: local repos with findings, then account-wide posture, so a public repo that is never cloned still surfaces.
- Cost is one list call per account plus one `gh api` call per public repo. Private repos are never called.
