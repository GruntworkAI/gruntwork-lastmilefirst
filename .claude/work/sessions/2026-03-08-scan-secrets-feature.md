# Session: Secret Scanning for the Unsophisticated User

**Date:** March 8, 2026
**Duration:** ~1 hour
**Output:** lastmilefirst v0.11.0

## The Problem We Set Out to Solve

A friend's org had secrets pushed to a public repo. We scanned all gruntwork repos (clean), but realized there was no ongoing protection. The goal: make secret hygiene automatic and hard to forget, especially for users who don't think about repo visibility.

## Key Design Decision: Public Repo Awareness Everywhere

The central insight was that repo visibility isn't just an audit feature — it needs to be woven throughout the entire experience:

- **Every scan** checks visibility first and bumps severity for public repos
- **Every commit** (via pre-commit hook) reminds you if the repo is public
- **Every session** (via Overwatch) tells you if you're in a public repo

This is "unsophisticated user protection" — the user who most needs protection is the one who doesn't think to check.

## What We Built

### New Skill: scan-secrets (7 files)

| File | Purpose |
|------|---------|
| `SKILL.md` | Full Claude instructions for all modes |
| `data/common_secret_formats.toml` | 16 gitleaks rules covering gaps in defaults |
| `scripts/cli.py` | Entry point with argparse dispatching |
| `scripts/scanner.py` | Core scanning with public repo severity bumping |
| `scripts/format_loader.py` | Two-tier format library (common + org) |
| `scripts/repo_auditor.py` | .gitignore audit, dangerous files, GitHub inventory |
| `scripts/hook_installer.py` | Global pre-commit via core.hooksPath |

### Two-Tier Format Library

Rather than a monolithic config, we split custom gitleaks rules into two tiers:

- **Common** (plugin-shipped): Universal gaps like DB connection strings, .env files, terraform secrets. Updated via `--update-formats`.
- **Org** (user-managed): Organization-specific patterns. Never overwritten by plugin updates.

Storage: `~/.claude/lastmilefirst/secret-formats/` — survives plugin updates.

### Overwatch Integration

Two new session-start checks:
- `check_secret_scan_status()` — alerts if never scanned or 7+ days stale
- `check_repo_visibility()` — alerts when working in a public repo

## Process Notes

- Local repo was behind GitHub (0.9.5 vs 0.10.1) — caught during version bump. Lesson: always `git pull` before modifying plugin source.
- Renamed generic `cli.py` entry points to descriptive names across all skills (v0.11.1): `todos_summary.py`, `scan_secrets.py`, `organize_project.py`.
- Plan was written assuming 0.10.1 base — adapted on the fly after pulling latest.

## Files Changed

### New (8 files)
- `commands/run-scan-secrets.md`
- `skills/scan-secrets/` (7 files)
- `RELEASE-NOTES-0.11.0.md`

### Modified (7 files)
- `hooks/scripts/overwatch.py` — added `last_secret_scan` to default state
- `hooks/scripts/session_start.py` — added 2 new check functions + wired into main()
- `skills/overwatch/SKILL.md` — added scan-secrets to monitoring table
- `.claude-plugin/plugin.json` — version bump + keywords
- `marketplace.json` — version bump
- `README.md` — added command to table
- `CHANGELOG.md` — added 0.11.0 entry
