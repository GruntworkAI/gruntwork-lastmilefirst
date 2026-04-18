---
name: run-audit-plugin
description: Audit a Claude Code plugin (URL or local path) using Griffith's static analyzer
argument-hint: "<source> [--strict] [--json]"
---

Load and execute the `audit-plugin` skill for full implementation.

**Source:** git URL, `owner/repo` shorthand, or local path.
**Use cases:** pre-install vetting (URL) or post-install re-audit (local path).
**Flags:** `--strict` enables noisier rules; `--json` emits raw Griffith JSON.
