# Changelog

All notable changes to the lastmilefirst plugin will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
