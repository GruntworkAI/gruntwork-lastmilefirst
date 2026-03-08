---
name: scan-secrets
description: Scan repositories for secrets, credentials, and sensitive data. Includes pre-commit hooks, repo auditing, public repo awareness, and custom secret format libraries.
---

# Scan Secrets

Detect secrets and credentials in git repositories before they become incidents. Combines gitleaks with custom format libraries and public repo awareness.

## Prerequisites

| Tool | Required | Install |
|------|----------|---------|
| **gitleaks** | Yes | `brew install gitleaks` |
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
| `/run-scan-secrets --install-hooks` | Install pre-commit | Global hook via core.hooksPath |
| `/run-scan-secrets --uninstall-hooks` | Remove pre-commit | Restore previous hook config |
| `/run-scan-secrets --add-format` | Add custom format | Interactive: add org-specific secret pattern |
| `/run-scan-secrets --list-formats` | List format rules | Show all active rules with source |
| `/run-scan-secrets --update-formats` | Update common rules | Refresh plugin-shipped rules (preserves org rules) |

## Mode Details

### Default: Scan Current Repo

Scans full git history of the current repository using gitleaks with merged custom format rules.

**Steps:**
1. Check repo visibility (public/private) via `gh repo view`
2. If PUBLIC: show warning banner, bump all finding severities
3. Load merged format config (common + org rules)
4. Run `gitleaks detect` with `--redact` on full history
5. Display findings sorted by severity
6. Update overwatch `last_secret_scan` timestamp

**Run:**
```bash
python3 ${SKILL_DIR}/scripts/cli.py
```

### `--all`: Scan All Workspace Repos

Walks `~/Code/` two levels deep finding git repos, scans each.

**Run:**
```bash
python3 ${SKILL_DIR}/scripts/cli.py --all
```

### `--audit`: Repo Hygiene Audit

Checks a single repo for:
- **Visibility**: Public vs private (via gh CLI)
- **.gitignore coverage**: Checks for required patterns (.env, *.pem, *.key, *.tfstate, etc.)
- **Dangerous committed files**: Searches git history for files that should never be committed

**Run:**
```bash
python3 ${SKILL_DIR}/scripts/cli.py --audit
```

### `--audit --github`: GitHub Account Audit

Scans your entire GitHub account (personal + orgs):
- Lists all public repos with last push date
- Flags repos with suspicious names (containing "internal", "private", "secret", "config", etc.)
- Shows org repos separately

**Run:**
```bash
python3 ${SKILL_DIR}/scripts/cli.py --audit --github
```

### `--install-hooks`: Pre-commit Hook

Installs a global pre-commit hook that scans staged changes before every commit.

**How it works:**
- Sets `git config --global core.hooksPath` to `~/.claude/lastmilefirst/git-hooks/`
- Hook calls `cli.py --pre-commit` which runs `gitleaks protect --staged`
- If secrets found: blocks commit, shows findings
- If repo is public: adds reminder line to every commit output
- Detects and warns about existing `core.hooksPath` before overriding

**Run:**
```bash
python3 ${SKILL_DIR}/scripts/cli.py --install-hooks
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
python3 ${SKILL_DIR}/scripts/cli.py --list-formats
```

### `--update-formats`: Refresh Common Rules

Copies the latest `common_secret_formats.toml` from the plugin to the user's format directory. Never touches org rules.

**Run:**
```bash
python3 ${SKILL_DIR}/scripts/cli.py --update-formats
```

## Secret Format Libraries

Two-tier system for custom gitleaks rules:

| Tier | File | Location | Updated By |
|------|------|----------|------------|
| Common | `common_secret_formats.toml` | `~/.claude/lastmilefirst/secret-formats/` | Plugin (via `--update-formats`) |
| Org | `org_secret_formats.toml` | `~/.claude/lastmilefirst/secret-formats/` | User (via `--add-format`) |

**Merge order:** Common loads first, then Org. Rules with the same `id` — org wins (last writer).

**Format:** Native gitleaks TOML. No translation layer needed.

### Common Rules (Plugin-Shipped)

Cover gaps in gitleaks defaults:
- Database connection strings (postgres, mysql, mongodb, redis)
- High-entropy env var values
- Committed .env files
- Terraform tfvars with secret-like values
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
| Scan timestamp | After scan completes | Updates `last_secret_scan` in overwatch state |

## Related Skills

- `/run-review-project` — Broader project quality review
- `/run-overwatch` — Check all monitoring status
