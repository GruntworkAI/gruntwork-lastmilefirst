# lastmilefirst v0.11.0 - The Secret Scanning Release

**Released:** March 6, 2026

This release adds secret scanning as a first-class capability — on-demand repo scanning, pre-commit prevention, GitHub account auditing, and custom secret format libraries.

## Why This Release

A friend's org had secrets pushed to a public repo. We scanned all our repos (clean), but realized there was no ongoing protection. This release makes secret hygiene automatic and hard to forget.

## What's New

### Secret Scanning (`/run-scan-secrets`)

Full git history scanning powered by gitleaks with custom format libraries that cover gaps in gitleaks' defaults:

```
/run-scan-secrets              # Scan current repo
/run-scan-secrets --all        # Scan all workspace repos
/run-scan-secrets --audit      # Audit .gitignore, dangerous files, visibility
/run-scan-secrets --install-hooks  # Global pre-commit hook
```

All output is **redacted by default** — the scan report itself can never be a secondary leak.

### Public Repo Awareness

Repo visibility isn't just an audit feature — it's woven throughout:

- **Every scan** checks visibility first. Public repos get a warning banner and all finding severities bumped (MEDIUM→HIGH, HIGH→CRITICAL)
- **Pre-commit hook** prints "Reminder: you are committing to a PUBLIC repository" on every commit to a public repo
- **Overwatch session start** shows "You're working in a PUBLIC repo (owner/name)" so you never forget

### GitHub Account Audit

Scan your entire GitHub presence for exposure:

```
/run-scan-secrets --audit --github
```

Lists every public repo across your account and orgs, flags repos with suspicious names (containing "internal", "private", "secret", "config"), and shows last push dates.

### Custom Secret Format Libraries

Two-tier system for gitleaks rules beyond the defaults:

| Tier | File | Managed By |
|------|------|------------|
| **Common** | `common_secret_formats.toml` | Plugin (updated via `--update-formats`) |
| **Org** | `org_secret_formats.toml` | You (via `--add-format` or manual edit) |

**Common rules** ship with the plugin and cover: database connection strings, high-entropy env vars, committed .env files, terraform tfvars, hardcoded passwords, Bearer tokens, webhook URLs (Slack/Discord), PEM/PKCS8 keys, JWT secrets.

**Org rules** are yours — add patterns for internal token formats, custom API key prefixes, proprietary secret formats. Never overwritten by plugin updates.

```
/run-scan-secrets --add-format     # Interactive: Claude helps write the rule
/run-scan-secrets --list-formats   # See all active rules with source
```

Storage: `~/.claude/lastmilefirst/secret-formats/` (survives plugin updates).

### Global Pre-Commit Hook

One command installs a pre-commit hook that applies to **all repos** immediately:

```
/run-scan-secrets --install-hooks
```

Uses `git config --global core.hooksPath` — no per-repo setup needed. Scans staged changes with merged format rules before every commit. Blocks the commit if secrets are found.

### Overwatch Integration

Two new checks at every session start:

| Check | Alert |
|-------|-------|
| Scan freshness | "Never scanned" or "N days since last scan" |
| Repo visibility | "You're working in a PUBLIC repo (owner/name)" |

### New Command

| Command | Purpose |
|---------|---------|
| `/run-scan-secrets` | Scan repos for secrets, credentials, and sensitive data |

## Updating

```bash
# Refresh marketplace
/plugin marketplace update gruntwork-marketplace

# Update plugin
/plugin update lastmilefirst@gruntwork-marketplace

# Run your first scan
/run-scan-secrets

# Install pre-commit protection
/run-scan-secrets --install-hooks
```

## What's Next

- Scheduled scanning (weekly automatic scans via cron)
- Slack/webhook notifications on findings
- Team format library sharing across orgs

---

**Full changelog:** See [CHANGELOG.md](./CHANGELOG.md)
