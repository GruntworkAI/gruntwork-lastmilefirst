---
name: audit-plugin
description: Audit a Claude Code plugin before installing (or re-audit an installed one). Wraps Griffith's static analyzer — inventory, security scan, context footprint, and architecture assessment. Use for pre-install vetting of URLs/shorthand, or post-install drift detection on local paths.
---

# Audit Plugin

Evaluate a Claude Code plugin using Griffith's static analyzer. Surfaces four dimensions of analysis:

1. **Inventory** — what components the plugin contains (agents, commands, skills, hooks, MCP servers)
2. **Security** — risky patterns (shell execution, credential refs, settings tampering) across 22 ReDoS-safe regex rules
3. **Footprint** — always-on baseline vs on-demand max context cost, with efficiency rating
4. **Architecture** — classification (agent-heavy / skill-first / mcp-based / hybrid) with recommendations

## Prerequisites

| Tool | Required | Install |
|------|----------|---------|
| **griffith** | Yes | `git clone https://github.com/GruntworkAI/gruntwork-griffith && cd gruntwork-griffith && poetry install` |
| **git** | Yes (for URL sources) | Ships with macOS / `apt install git` |
| **Python 3.11+** | Yes | Ships with macOS |

The wrapper auto-discovers griffith in this order:
1. `griffith` on PATH
2. `~/Code/gruntwork/gruntwork-griffith/.venv/bin/griffith` (dev mode)
3. Error with install instructions

## Usage

| Command | What It Does |
|---------|--------------|
| `/run-audit-plugin <url>` | Clone (hardened) and audit a plugin at its source — pre-install vetting |
| `/run-audit-plugin <owner/repo>` | GitHub shorthand — same as URL |
| `/run-audit-plugin <local-path>` | Audit an already-on-disk plugin — post-install re-check |
| `/run-audit-plugin <source> --strict` | Enable broader (noisier) security rules |
| `/run-audit-plugin <source> --json` | Emit raw JSON report (for scripting / comparison) |

**Source types:**
- Git URL: `https://github.com/EveryInc/every-marketplace`
- SSH URL: `git@github.com:org/repo.git`
- GitHub shorthand: `EveryInc/every-marketplace`
- Local plugin dir: `~/Code/my-plugin` or `~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/`
- Marketplace root: any of the above pointing at a `.claude-plugin/marketplace.json` + `plugins/` layout → yields one report per plugin

## How it works

1. **Prereq check** — locates the `griffith` binary (PATH or dev install)
2. **Shell out** — runs `griffith analyze <source> --json` with optional `--strict`
3. **Parse JSON** — validates schema_version and extracts key fields
4. **Render in session** — produces a human-readable summary with:
   - Risk level highlighted
   - Finding counts by severity
   - Footprint rating with primary driver
   - Architecture pattern + recommendations
   - Untrusted fields wrapped in escaped blocks to prevent prompt injection into Claude's context

## Script

```bash
python3 ${SKILL_DIR}/scripts/audit_plugin.py <source> [--strict] [--json]
```

## Handling untrusted content

Plugin content (names, descriptions, file paths, match context) is treated as untrusted input. The script:

- Wraps every untrusted string in code-fence blocks so Claude doesn't interpret them as instructions
- Honors Griffith's `untrusted_fields[]` list from the JSON schema
- Surfaces critical / high findings prominently; truncates low-severity lists

## Error handling

- Missing griffith: exit with install instructions (exit code 1)
- Clone failure: shows git stderr; exit code 1
- Invalid source: shows specific error (refused protocol, not found); exit code 1
- Scan runtime failure: surfaces griffith stderr; exit code 1

## Integration with Overwatch

Future enhancement (not Phase 1): record `last_plugin_audit` per scanned plugin in Overwatch state. Would enable session-start alerts like "5 installed plugins haven't been audited in 30+ days."

## Related Skills

- `/run-scan-secrets` — runs gitleaks on repos (analogous pattern: shell out + render)
- `/run-plugin-inventory` — lighter-weight listing of installed plugins
- `/run-review-project` — broader project review (docs + CLAUDE.md + structure)

## Known limitations (Phase 1 of the wrapper)

- **Static analysis only** — no LLM-based review of skill content for prompt injection. See `analysis_scope: ["static"]` in Griffith's JSON output.
- **Subprocess findings can appear noisy** — legitimate plugins that use git / gh / python (like lastmilefirst itself) will show `subprocess-in-hooks` findings. Griffith's follow-up queue includes AST-based refinement to reduce these.
- **No baseline-diff drift detection yet** — local-path mode produces a point-in-time snapshot. Automated diff-based drift detection is Griffith Phase 1.5.
- **No cross-plugin comparison yet** — `griffith compare` is deferred.
