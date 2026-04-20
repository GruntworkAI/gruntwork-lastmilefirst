---
name: run-audit-plugin
description: Audit a Claude Code plugin (URL or local path) using Griffith's static analyzer — renders inventory, security, footprint, architecture, dependencies, and (default on) Tier 2 CVE findings.
argument-hint: "<source> [--strict] [--no-sca] [--markdown|--agent-summary|--json] [--save-json PATH|--no-save] [--timeout SEC]"
---

Load and execute the `audit-plugin` skill for full implementation.

**Source:** git URL, `owner/repo` shorthand, or local path.
**Use cases:** pre-install vetting (URL) or post-install re-audit (local path).

**Flags:**
- `--strict` — enables noisier security rules
- `--no-sca` — skip Tier 2 CVE scanning (default is ON; requires `osv-scanner` installed)
- `--markdown` / `--agent-summary` / `--json` — output mode. Auto-selects `--agent-summary` when `CLAUDECODE=1` (structured JSON for Claude branching); otherwise defaults to `--markdown`. `--json` emits raw unescaped Griffith JSON (tooling only — do not feed directly to an LLM).
- `--save-json PATH` / `--no-save` — control result persistence. Default caches to `$TMPDIR/griffith-audit-<sha>.json` so follow-up questions skip re-invocation.
- `--timeout SEC` — override subprocess wall-clock (default 60s, 180s with `--sca`; also via `LMF_GRIFFITH_TIMEOUT_SEC`)

**Environment:**
- `GRIFFITH_BIN` — absolute path override for the griffith binary (containment-checked)
- `LMF_ALLOW_DEV_GRIFFITH=1` — enable the `~/Code/gruntwork/gruntwork-griffith/.venv/bin/griffith` dev-mode fallback
- `LMF_GRIFFITH_TIMEOUT_SEC` — default subprocess timeout override
