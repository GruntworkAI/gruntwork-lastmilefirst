# Changelog

All notable changes to the lastmilefirst plugin will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **`audit-plugin` skill and `/run-audit-plugin` command** — wrapper around [Griffith](https://github.com/GruntworkAI/gruntwork-griffith) for plugin evaluation. Shells out to `griffith analyze <source> --json`, parses the result, and renders a markdown summary in the Claude session.
  - Accepts git URLs, `owner/repo` GitHub shorthand, and local paths — supports both pre-install vetting and post-install re-audit
  - `--strict` flag passes through to enable broader (noisier) security rules
  - `--json` flag emits raw Griffith JSON for scripting / comparison
  - Auto-discovers `griffith` binary: PATH first, then `~/Code/gruntwork/gruntwork-griffith/.venv/bin/griffith` dev fallback; clear install instructions if neither
  - Escapes untrusted plugin content (names, paths, finding text) in code fences to prevent prompt injection into the surrounding Claude session
  - Validates `schema_version` before rendering; warns on unknown versions
  - Renders risk-level banner, inventory table, severity breakdown, footprint + efficiency rating, architecture pattern + recommendations, and findings detail grouped by severity (cap 10 per group)

## [0.14.1] - 2026-05-12

### Fixed
- **`scan-secrets` pre-commit hook silently no-op'd for any rule containing regex escapes** — three reinforcing bugs combined so the hook printed "No secrets detected in staged changes" while gitleaks had aborted during config load. The pre-commit secret scan provided no real defense for an unknown period.
  - `format_loader.py` now serializes string values as TOML literal strings (`'''...'''`) instead of basic strings (`"""..."""`); basic strings interpret backslash sequences, which either hard-errored on `\+` or silently mangled `\s`/`\w` in regex values.
  - `format_loader.py` now serializes dict-value sub-tables (e.g. `[rules.allowlist]`) with their contents, emitted after the parent rule's scalars/lists (per TOML ordering invariant). Previously the dict's contents were dropped entirely, so three shipped rules (`lmf-hardcoded-password`, `lmf-bearer-token-hardcoded`, `lmf-jwt-secret`) lost their test-path allowlists.
  - `scanner.py` `scan_staged` and `scan_repo` now fail-closed when the requested `--report-path` file doesn't exist after gitleaks runs. Gitleaks uses exit code 1 ambiguously for both "leaks found" and "config load failure"; report-file existence is the reliable signal that the scan actually completed.
  - Smoke-tested end-to-end: good config + fixture `oc_p1_*` token → caught (exit 1); deliberately malformed config → fail-closed with stderr surfaced (exit 1).

### Changed
- Aligned version drift across `plugin.json` (was 0.14.0), `marketplace.json` (was 0.11.1), and `README.md` (was 0.10.1) — all now `0.14.1`.

## [0.13.0] - 2026-03-24

### Added
- **Per-Project/Per-Org Overwatch State Tracking** — Overwatch now tracks review, organize, and scan timestamps independently for each project and org, replacing the old single-global-timestamp model
  - State file upgraded to v2 format with `global`, `orgs`, and `projects` scopes
  - Lazy, automatic migration from v1 — no user action needed
  - `update_state.py` rewritten with `--scope` (project/org/global) and `--key` args, auto-detects current project from CWD
  - `update_state.py status` shows current project/org/global state; `--all` shows everything tracked
  - Session start alerts are now context-aware: show project name in messages, skip project-scoped alerts when at workspace root

- **CLAUDE.md Review Tracking** — new `last_review_claude` field tracked at all three levels (user, org, project) with 30-day staleness threshold

- **Skill Overwatch Integration** — `review-project`, `organize-project`, `review-claude`, and `organize-orgs` skills now include an "Update Overwatch" step so state gets recorded after each run

### Changed
- `scan-secrets` now records `last_secret_scan` per-project instead of globally
- `session_start.py` resolves current org/project context before generating alerts
- `overwatch.py` exports new functions: `resolve_context()`, `get_scoped_state()`, `update_scoped_state()`, `update_project_state()`, `update_org_state()`
- `update_state_field()` preserved for backward compatibility (operates on global scope)

## [0.11.0] - 2026-03-06

### Added
- **Secret Scanning** - `/run-scan-secrets` for detecting secrets and credentials
  - Full git history scanning via gitleaks with custom format rules
  - `--all` mode scans entire workspace (all repos under ~/Code/)
  - `--audit` mode checks .gitignore gaps, dangerous committed files, repo visibility
  - `--audit --github` inventories all public repos across GitHub account and orgs
  - `--install-hooks` / `--uninstall-hooks` for global pre-commit hook via `core.hooksPath`
  - `--add-format` interactive flow for org-specific secret patterns
  - `--list-formats` / `--update-formats` for format library management
  - Two-tier format library: common (plugin-shipped) + org (user-managed) in `~/.claude/lastmilefirst/secret-formats/`
  - 16 custom gitleaks rules covering DB connection strings, env vars, terraform, hardcoded creds, webhooks, keys, JWT
  - All output redacted by default to prevent secondary leaks

- **Public Repo Awareness** - woven throughout the plugin
  - Every scan checks repo visibility; public repos get warning banner + severity bump
  - Pre-commit hook reminds on every commit to a public repo
  - Overwatch session start alerts when working in a public repo
  - GitHub account audit flags repos with suspicious names (internal, private, secret, config)

- **Overwatch Integration**
  - `check_secret_scan_status()` — alerts if never scanned or 7+ days stale
  - `check_repo_visibility()` — alerts when working in a public repo
  - `last_secret_scan` field in overwatch state

## [0.10.1] - 2026-02-05

### Added
- **Stack-Knowledge System** - Complement to stack-wisdom for facts and documentation
  - `search-knowledge` skill - find facts, documentation, reference material
  - `add-knowledge` skill - capture client, project, product, domain, and reference knowledge
  - Knowledge types: Client, Project, Product, Domain, Reference
  - Local storage backend (default)
  - Adapter interface for community backends (Confluence, Notion, Sharepoint)
  - `templates/knowledge-adapter.md` - contribution guide for backend adapters
  - `org.json` updated with `stack_knowledge` configuration section

- **Documentation**
  - Stack-Knowledge section in README
  - Knowledge vs Wisdom comparison table

## [0.10.0] - 2026-02-04

### Added
- **PARC Workflow** - Plan, Allocate, Review, Compound
  - Default operating mode for Claude - scales ceremony to task complexity
  - YAGNI vs YAGWYDI tension: YAGNI for features, YAGWYDI for infrastructure
  - `parc` skill documenting the workflow
  - `/run-strict-parc` command for enforced discipline with explicit gates
  - PARC tracking files in `.claude/work/parc/`

- **Org-Level Infrastructure**
  - `organize-orgs` skill - explains orgs, scaffolds infrastructure
  - Orgs as first-class concept (even "personal" is an org)
  - Recommended structure: `personal/` and `work/` orgs
  - `.claude/org.json` configuration file for each org

- **Org-Level Operatives**
  - Three-tier lookup: Project → Org → User
  - Operatives repo per org: `[org]-operatives/`
  - Updated `consult-operative` with org discovery
  - Updated `create-operative` with org-level option

- **Stack-Wisdom System**
  - Wisdom vs Knowledge distinction (patterns vs facts)
  - `search-wisdom` skill - find patterns, insights, circuit breakers
  - `add-wisdom` skill - capture hard-won lessons
  - Stack-wisdom repo per org: `[org]-stack-wisdom/`
  - Templates: `wisdom-pattern.md`, `operatives-readme.md`, `stack-wisdom-readme.md`

- **Overwatch Enhancements**
  - Org infrastructure check (missing org.json, operatives, wisdom repos)
  - Alerts at session start when org infrastructure incomplete
  - Integration with organize-orgs for remediation

- **CLAUDE.md Templates**
  - Workspace-level template includes PARC workflow
  - Org-level template includes PARC, org resources section
  - Templates scaffold PARC-by-default

- **Documentation**
  - Philosophy article link: "Last Mile First: Fast Alone, Far Together"
  - PARC Workflow section in README
  - Stack-Wisdom section in README

### Changed
- `organize-claude` now detects missing org infrastructure and suggests `organize-orgs`
- Plugin description updated to highlight PARC workflow

## [0.9.7] - 2026-02-04

### Fixed
- Windows compatibility: hooks now try `python` before `python3` for cross-platform support
- Added `run.py` launcher script for reliable Python detection across Windows/macOS/Linux

## [0.9.1] - 2026-01-29

### Fixed
- Stop hook JSON validation error (converted from prompt to command type)

## [0.9.0] - 2026-01-29

### Added
- **Cross-project todo aggregation** (`/run-todos-summary`)
  - Scans `.claude/work/todos/` across all projects in an org
  - Multiple output formats: terminal, json, compact, project
  - `--by-project` flag for project-centric view
  - State classification: urgent, blocked, active, stale
  - Overwatch integration shows urgent/blocked at session start
- Workspace configuration at `~/.claude/workspace-config.json`
  - Defines workspace root and org directories
  - Consistent terminology with organize-claude skill
- 5-minute cache for fast repeated queries

## [0.8.0] - 2026-01-29

### Changed
- **BREAKING**: Rewritten Overwatch hooks from Bash to Python for cross-platform support
- Requires Python 3.9+ (previously shell-only)
- Full Windows native support (no longer requires WSL or Git Bash)

### Added
- Cross-platform file locking (`fcntl` on Unix, `msvcrt` on Windows)
- Proper type hints throughout Python code
- UTF-8 encoding on all file operations

### Fixed
- Race condition when logging invocations (now uses file locking)
- Race condition when pruning invocation logs (now uses file locking)
- State file corruption under concurrent access

### Removed
- Bash hook scripts (replaced by Python equivalents)
  - `session-start.sh` → `session_start.py`
  - `update-state.sh` → `update_state.py`
  - `log-invocation.sh` → `log_invocation.py`
  - `check-plugin-updates.sh` (merged into `session_start.py`)
  - `usage-report.sh` (merged into `session_start.py`)

## [0.7.1] - 2026-01-28

### Fixed
- Path traversal vulnerability in operative loading (LMFA-2025-001)
- Predictable temp file location (LMFA-2025-002)
- State file race conditions with flock (LMFA-2025-003)

### Added
- SECURITY.md with formal security advisories
- Plugin update checker for all installed plugins
- Invocation tracking with weekly usage statistics

## [0.7.0] - 2026-01-27

### Added
- Initial Overwatch system with session-start hooks
- Plugin update notifications
- Uncommitted changes detection
- Stale todo reminders
- CLAUDE.md presence checks

## [0.6.0] - 2026-01-20

### Added
- Private operatives system
- Create and consult custom AI personas
- User-level and project-level operative storage

## [0.5.0] - 2026-01-15

### Added
- Public expert agents (Adam, Andor, Charles, Dino, Max, Paloma, Shannon)
- Key hire agents (Maya, Archer, Scout, Quinn, Reese, Otto)
- Scout coordinator for multi-agent orchestration

## [0.4.0] - 2026-01-10

### Added
- Review skills (review-claude, review-project, review-docs, review-work)
- Organize skills (organize-claude, organize-project)
- Get-started onboarding skill

## [0.3.0] - 2026-01-05

### Added
- Initial plugin structure
- Command routing system
- Skill execution framework
