---
name: scan-secrets
description: Scan repositories for secrets, credentials, and sensitive data. Includes pre-commit hooks, repo auditing, public repo awareness, and custom secret format libraries.
---

# Scan Secrets

Detect secrets and credentials in git repositories before they become incidents. Combines gitleaks with custom format libraries and public repo awareness.

## Prerequisites

| Tool | Required | Install |
|------|----------|---------|
| **gitleaks** | Yes (v8.19.0+) | `brew install gitleaks` |
| **gh CLI** | For audit/visibility | `brew install gh && gh auth login` |
| **Python 3.9+** | Yes | Ships with macOS |

Check prerequisites before first use:
```bash
gitleaks version && gh auth status && python3 --version
```

## Usage

| Command | Mode | What It Does |
|---------|------|--------------|
| `/run-scan-secrets` | Scan current repo | Full git history scan with merged format rules |
| `/run-scan-secrets --all` | Scan workspace | Walk ~/Code finding all git repos, scan each |
| `/run-scan-secrets --audit` | Audit current repo | .gitignore gaps, dangerous files, visibility check |
| `/run-scan-secrets --audit --github` | Audit GitHub account | List all public repos, flag suspicious names |
| `/run-scan-secrets --audit --github --deep` | Audit GitHub account, per repo | Adds the per-call checks on every listed repo (about eight API calls per repo) |
| `/run-scan-secrets --audit --propose` | Audit plus proposed changes | Itemized list of setting changes with a consequence each; applies nothing |
| `/run-scan-secrets --apply <id> [<id>...]` | Apply named changes | Fresh audit, applies exactly the named items, re-reads, prints before and after |
| `/run-scan-secrets --install-hooks` | Install pre-commit | Global hook via core.hooksPath |
| `/run-scan-secrets --uninstall-hooks` | Remove pre-commit | Restore previous hook config |
| `/run-scan-secrets --add-format` | Add custom format | Interactive: add org-specific secret pattern |
| `/run-scan-secrets --list-formats` | List format rules | Show all active rules with source |
| `/run-scan-secrets --update-formats` | Update common rules | Refresh plugin-shipped rules (preserves org rules) |

## Mode Details

### Default: Scan Current Repo

Scans full git history of the current repository using gitleaks' built-in default rules plus merged custom format rules.

**Steps:**
1. Check repo visibility (public/private) via `gh repo view`
2. If PUBLIC: show warning banner, bump all finding severities
3. Load merged config: gitleaks default rules (`useDefault`) + custom rules (common + org)
4. Run `gitleaks git` with `--redact` on full history
5. Display findings sorted by severity
6. Update overwatch `last_secret_scan` timestamp

**Run:**
```bash
python3 ${SKILL_DIR}/scripts/scan_secrets.py
```

### `--all`: Scan All Workspace Repos

Walks `~/Code/<org>/<repo>` finding git repos, and one level further inside a
client directory (`~/Code/<org>/<client>/<repo>`), then scans each. A client
directory is one marked `type: client`; see
[Workspace Markers](../organize-orgs/SKILL.md#workspace-markers). Each repo's
scan is recorded under its path relative to `~/Code/`, which is the key
Overwatch reads. A client directory that is itself a repo (a layout mistake
Overwatch warns about) is still scanned, as `<org>/<client>`. If the workspace
layout loader cannot be imported, the walk falls back to `~/Code/<org>/<repo>`
only and prints a line saying client directories are not being descended.

**Run:**
```bash
python3 ${SKILL_DIR}/scripts/scan_secrets.py --all
```

### `--audit`: Repo Hygiene Audit

Checks a single repo for:
- **Visibility**: Public vs private (via gh CLI)
- **GitHub protections**: whether GitHub's own secret scanning and push protection are enabled
- **Per-call checks**: rulesets on the default branch and release tags, Dependabot alerts, Actions policy, workflow token, webhooks, deploy keys (see the posture section below)
- **.gitignore coverage**: Checks for required patterns (.env, *.pem, *.key, *.tfstate, etc.)
- **Dangerous committed files**: Searches git history for files that should never be committed

**Run:**
```bash
python3 ${SKILL_DIR}/scripts/scan_secrets.py --audit
```

### `--audit --github`: GitHub Account Audit

Scans your entire GitHub account (personal + orgs):
- Lists all public repos with last push date
- Flags repos with suspicious names (containing "internal", "private", "secret", "config", etc.)
- Shows org repos separately

**Run:**
```bash
python3 ${SKILL_DIR}/scripts/scan_secrets.py --audit --github
python3 ${SKILL_DIR}/scripts/scan_secrets.py --audit --github --deep   # plus per-call checks per repo
```

`--deep` runs the seven per-call checks on every listed repo. That is about eight API calls per repo (the repo read plus seven checks), plus one more per ruleset and one for the selected-actions list where it applies. A running count prints to stderr. On an account with many repos, mind the API rate limit (5,000 calls an hour for an authenticated user).

### `--install-hooks`: Pre-commit Hook

Installs a global pre-commit hook that scans staged changes before every commit.

**How it works:**
- Sets `git config --global core.hooksPath` to `~/.claude/lastmilefirst/git-hooks/`
- Hook calls `scan_secrets.py --pre-commit` which runs `gitleaks git --pre-commit --staged`
- If secrets found: blocks commit, shows findings
- If repo is public: adds reminder line to every commit output
- Detects and warns about existing `core.hooksPath` before overriding

**Run:**
```bash
python3 ${SKILL_DIR}/scripts/scan_secrets.py --install-hooks
```

### `--add-format`: Add Custom Format (Interactive)

When user runs this mode, Claude guides them through adding a custom secret format:

1. Ask what kind of secret they want to detect
2. Help them write the regex pattern
3. Generate the gitleaks TOML rule
4. Write it to `~/.claude/lastmilefirst/secret-formats/org_secret_formats.toml`
5. Verify it works with a test string

**Example interaction:**
```
User: /run-scan-secrets --add-format
Claude: What kind of secret do you want to detect?
User: Our internal API tokens start with "gw_live_" followed by 40 hex chars
Claude: I'll add this rule to your org formats:

[[rules]]
id = "gruntwork-api-token"
description = "Gruntwork internal API token"
regex = '''gw_live_[0-9a-f]{40}'''
tags = ["org", "api-token"]
keywords = ["gw_live_"]
```

Read the org formats file, append the new rule, and write it back:
```bash
ORG_FILE="$HOME/.claude/lastmilefirst/secret-formats/org_secret_formats.toml"
```

### `--list-formats`: List Format Rules

Shows all active rules from both tiers with source indicator (common vs org).

**Run:**
```bash
python3 ${SKILL_DIR}/scripts/scan_secrets.py --list-formats
```

### `--update-formats`: Refresh Common Rules

Copies the latest `common_secret_formats.toml` from the plugin to the user's format directory. Never touches org rules.

**Run:**
```bash
python3 ${SKILL_DIR}/scripts/scan_secrets.py --update-formats
```

## GitHub Protections (Posture Check)

The content scan asks *"is there a secret in this repo?"*. This asks *"is GitHub's own safety net switched on?"* — a different layer, and one this plugin cannot substitute for:

| Protection | What it does |
|---|---|
| **Secret scanning** | GitHub detects branded credentials and notifies the issuing vendor through the partner program. For many providers that means automatic revocation. |
| **Push protection** | Blocks the push server-side, before the secret reaches the remote. Unlike the pre-commit hook, `--no-verify` cannot get past it. |

Both are **free on public repositories**, and both can be off — repository-level push protection is **disabled by default**.

**Where it appears:**

| Surface | Behavior |
|---|---|
| `--audit` | Full posture block beside the visibility line, including tier-gated fields, then the per-call checks below |
| `--all` | Account-wide pass over every public repo, including ones never cloned |
| Session start | ACTION REQUIRED when the current public repo is missing a protection |

**Repository settings, read from the same API call.** The response that carries the two protections also carries the settings below. They are cached with the posture at session start and printed in `--audit`, but they are policy choices rather than faults, so none of them is alerted on. Each reads **unknown** when the field is absent from the response.

| Setting | Source field(s) | Where it appears |
|---|---|---|
| Merge methods allowed | `allow_squash_merge`, `allow_merge_commit`, `allow_rebase_merge` | `--audit` only, not alerted |
| Auto-merge | `allow_auto_merge` | `--audit` only, not alerted |
| Delete branch on merge | `delete_branch_on_merge` | `--audit` only, not alerted |
| Forking | `allow_forking` | `--audit` only, not alerted |
| Wiki, Discussions, Projects | `has_wiki`, `has_discussions`, `has_projects` | `--audit` only, not alerted |
| Dependabot security updates | `security_and_analysis.dependabot_security_updates` (admin only) | `--audit` only, not alerted |
| Web commit sign-off required | `web_commit_signoff_required` | `--audit` only, not alerted |

These are readable without admin and are shown for private repos too; only the two protections above are skipped on private repos.

**Three states, not two.** GitHub omits the `security_and_analysis` block entirely for callers without admin on a repo. Absence is treated as **unknown**, never as *disabled* — otherwise the check would fire on every contributor for every repo they do not own. Unknown is always silent.

**What is deliberately not checked:**

- **Private repos** — secret scanning there requires paid GitHub Secret Protection, so an alert would be permanently unfixable. They short-circuit after the one `gh api` call (visibility and posture arrive together).
- **Forks and repos without admin access** — you cannot change those settings, so they are not your finding.
- **`non_provider_patterns` and `validity_checks`** — tier-gated, so they read `disabled` forever on a free public repo. Shown in `--audit`, never alerted on. Generic-pattern detection is what this plugin's own `lmf-*` rules cover.

**Fixing a finding.** The alert carries the command; nothing is changed for you. Secret scanning must be enabled for push protection to be accepted, and one PATCH carrying both keys works:

```bash
gh api -X PATCH repos/OWNER/REPO \
  -F 'security_and_analysis[secret_scanning][status]=enabled' \
  -F 'security_and_analysis[secret_scanning_push_protection][status]=enabled'
```

**Accounts** for the `--all` pass are derived from each org's identity contract (`<org>/.claude/org.json` → `identity.github_account`), so a new org is picked up automatically. Listing another account's *public* repos works from any authenticated identity, so this never calls `gh auth switch` — which is machine-global and would silently repoint every other shell.

### Per-call checks (`--audit` only)

Each of these costs its own API call, so they run when you ask (`--audit`) and never at session start. Every line is a measurement; none is alerted on.

| Check | Endpoint(s) | Printed |
|---|---|---|
| Default-branch rulesets | `repos/{r}/rulesets`, then `rulesets/{id}` per ruleset; `branches/{default}/protection` | active rulesets targeting the default branch; whether they block force pushes, block deletion, require a pull request; classic protection on or none |
| Release-tag rulesets | same listing, tag targets | active rulesets whose pattern covers `refs/tags/v*` (or `~ALL`); whether they block updates and deletion. When the repo ships `.claude-plugin/marketplace.json`, one clause adds that consumer installs resolve from this tag |
| Dependabot alerts | `repos/{r}/vulnerability-alerts` | on (204) or off (404) |
| Actions policy | `repos/{r}/actions/permissions` (+ `selected-actions`) | enabled; allowed actions class; GitHub-owned, verified, pattern count when selected |
| Workflow token | `repos/{r}/actions/permissions/workflow` | default permissions; can approve pull requests |
| Webhooks | `repos/{r}/hooks` | count; count with no secret; count with SSL verification off |
| Deploy keys | `repos/{r}/keys` | count; count writable |

Any other non-2xx reads as **unknown** and prints one line saying so, never a finding. Two 404s carry meaning by API contract: `vulnerability-alerts` 404 is "off", and a branch-protection 404 whose message is "Branch not protected" is "none" (any other 404 there is a permissions answer, so unknown). A 403 whose message asks for an upgrade prints **not available on this plan** (rulesets and branch protection on a private repo owned by a personal account on a free plan), so it is not read as a gap.

### Proposing and applying changes (`--propose`, `--apply`)

`--audit --propose` adds an itemized list after the per-call block. Each item has an id, the setting, the current value, the value it would take, the reason, and the consequence. Items already in place are left out. Nothing is written.

`--apply <id> [<id>...]` runs a fresh audit, applies exactly the named items, re-reads each one through the same GET the audit uses, and prints before and after. An unknown id is an error and nothing is applied. `--apply` with no ids prints the proposal and applies nothing. Applying an item that is already in place is a no-op that says "already set". A repo your account does not administer gets no proposal and nothing is applied. None of this runs at session start.

**Default items** (the baseline; none changes who can push or merge):

| Id | Change | Consequence |
|---|---|---|
| `ruleset-main` | Ruleset "protect main" on `~DEFAULT_BRANCH`: `deletion`, `non_fast_forward` (no pull request rule) | Blocks force pushes to and deletion of the default branch; direct pushes still work |
| `ruleset-tags` | Ruleset "protect release tags" on `refs/tags/v*`: `update`, `deletion` | Existing `v*` tags cannot be moved or deleted; new tags can still be created |
| `dependabot-alerts` | `PUT vulnerability-alerts` | Alerts on known-vulnerable dependencies; no code changes |
| `dependabot-updates` | `PUT automated-security-fixes` | Dependabot opens fix pull requests; nothing merges without a person |
| `actions-selected` | Allowed actions `selected`, GitHub-owned and verified allowed (existing patterns kept) | Workflows using an action outside that set stop running until it is allowed |
| `delete-branch-on-merge` | `delete_branch_on_merge: true` | Head branches are deleted after merge (restorable) |
| `wiki-off` | `has_wiki: false` | Wiki tab hidden; content is kept |

**Consider items** (change who can push or merge, or how; applied only when named, never part of the default set):

| Id | Change | Consequence |
|---|---|---|
| `ruleset-main-pr` | Ruleset "require pull request on main": `pull_request` rule, 0 approvals | Direct pushes to the default branch are blocked, including doc commits |
| `merge-commit-only` | Merge commits only; squash and rebase off | Keeps the original author line on fork pull requests; squash and rebase merges no longer offered |
| `forking-off` | `allow_forking: false` (private repos only; GitHub does not allow it on public repos) | No new forks |

A setting whose current value cannot be read (unknown, or not available on this plan) is listed under "Not proposed" and is not applied if named.

**Beyond these checks:** [GitHub hygiene for shared repositories](../../docs/github-hygiene-for-shared-repos.md) covers what this posture check measures for you and what only a person can set (email privacy and two-factor are not readable through the API).

## Secret Format Libraries

Two-tier system for custom gitleaks rules:

| Tier | File | Location | Updated By |
|------|------|----------|------------|
| Common | `common_secret_formats.toml` | `~/.claude/lastmilefirst/secret-formats/` | Plugin (via `--update-formats`) |
| Org | `org_secret_formats.toml` | `~/.claude/lastmilefirst/secret-formats/` | User (via `--add-format`) |

**Merge order:** Common loads first, then Org. Rules with the same `id` — org wins (last writer).

**Format:** Native gitleaks TOML. No translation layer needed.

**Coverage:** The merged config sets `[extend] useDefault = true`, so scans run gitleaks' full built-in ruleset (AWS keys, GitHub PATs, Stripe/Google keys, etc.) *in addition to* the custom formats below. The custom rules supplement the defaults — they do not replace them.

### Common Rules (Plugin-Shipped)

Cover gaps in gitleaks defaults:
- Database connection strings (postgres, mysql, mongodb, redis)
- High-entropy env var values
- Committed .env files
- Terraform tfvars with secret-like values
- Committed Terraform state files (flagged once per file, not per line)
- Hardcoded password assignments
- Bearer token headers in code
- Webhook URLs (Slack, Discord)
- Private key files (PEM, PKCS8)
- JWT secret assignments

### Org Rules (User-Managed)

Add patterns specific to your organization:
- Internal token formats (`myorg_live_[a-z0-9]{32}`)
- Custom API key prefixes
- Internal service URLs with embedded tokens
- Proprietary secret formats

## Severity Classification

| Level | Examples | Action |
|-------|----------|--------|
| **CRITICAL** | AWS keys, private keys, database URLs with creds | Immediate rotation required |
| **HIGH** | API tokens, webhook URLs, JWT secrets | Rotate and review access |
| **MEDIUM** | Hardcoded passwords (test excluded), env var secrets | Review and remediate |
| **LOW** | Generic high-entropy strings, possible false positives | Investigate |

**Public repo bump:** In public repos, all severities are bumped one level (MEDIUM→HIGH, HIGH→CRITICAL).

## Public Repo Awareness

This skill is designed to protect unsophisticated users from accidentally exposing secrets in public repos.

**Every scan** checks visibility first:
- PUBLIC repos get a prominent warning banner
- All findings get severity bumped
- Recommendations include making repo private

**Pre-commit hook** on public repos:
- Prints "Reminder: you are committing to a PUBLIC repository" on every commit

**Overwatch integration** (session start):
- Shows "You're working in a PUBLIC repo (owner/name)" at session start

## Output

All output uses `--redact` to avoid the scan report itself becoming a secondary leak. Secrets are shown as `REDACTED` in findings.

## Overwatch Integration

The scan-secrets skill integrates with Overwatch:

| Check | Trigger | Alert |
|-------|---------|-------|
| Scan freshness | Every session start | "Never scanned" or "N days since last scan" |
| Repo visibility | Every session start | "You're working in a PUBLIC repo" |
| GitHub protections | Every session start (cached 24h) | "PUBLIC repo has push protection disabled" + the enable command |
| Scan timestamp | After scan completes | Updates `last_secret_scan` in overwatch state |

## Related Skills

- `/run-review-project` — Broader project quality review
- `/run-overwatch` — Check all monitoring status
