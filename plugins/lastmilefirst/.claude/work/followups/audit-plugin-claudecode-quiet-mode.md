# Followup: silence drift-notice under `CLAUDECODE=1`

**Status: deferred. UX decision.**

**Surfaced during:** code review of `feat/audit-plugin-phase-1.5` on
2026-04-20 (merged commit `769b3db`).

## Context

The envelope walker in `_apply_untrusted_envelope` emits an
informational `audit_plugin: notice: ...` line on stderr when the
wrapper's pinned untrusted paths are not mirrored by Griffith's own
`untrusted_fields` list. This is a drift-detection signal — if
Griffith adds a new field the wrapper doesn't know about, or vice
versa, the notice surfaces it.

The notice looks like:

```
audit_plugin: notice: wrapper's pinned untrusted paths not in payload
list: ['marketplace.path', 'marketplace.source', 'plugin.path', ...]
— may indicate Griffith drift.
```

In a Claude Code session, stderr renders as a gray italic block. The
notice is useful for Michael-as-developer but adds cognitive load
for Michael-as-user (or any future user) who just wants to see the
plugin audit result.

## Why deferred

Claude Code sets `CLAUDECODE=1` in the subprocess environment. We
could use that signal to suppress the notice in session contexts —
the notice still prints when the wrapper is run from a terminal or
CI, preserving the drift-detection signal where developers care
about it.

But silencing a notice that's been useful in catching real drift
(the B-1 blocker cycle relied on it) has a cost:

- Claude-in-session is a common path; silencing means the drift
  signal gets hidden from the most frequent run mode
- A better fix might be to move the drift-notice out of the hot
  path entirely — e.g., run it once at install time as a
  self-check, not on every audit
- Silencing by env-var couples the wrapper to Claude Code
  specifically; not a good long-term pattern

The cleaner fix is probably: (a) keep the notice on the terminal
path, (b) downgrade to a debug-only emission under `CLAUDECODE=1`
OR behind `LMF_AUDIT_PLUGIN_DEBUG=1`. Needs a call on which.

## Trigger conditions to revisit

- A Claude Code session user complains about noise before running
  audit-plugin
- Drift-notice fires in a real scenario and we need to decide
  whether to surface it (argues against silencing)
- Wrapper gains a proper install-time self-check (makes the
  runtime notice redundant)

## Scope when we revisit

- Pick the signal: `CLAUDECODE=1` (easy), `LMF_AUDIT_PLUGIN_DEBUG=1`
  (more deliberate), or `isatty` check on stderr (environment-
  agnostic)
- Preserve the notice in CI and terminal contexts
- Add one regression test: stderr stays quiet under the gate; stays
  loud in its absence

## Related

- PR: feat/audit-plugin-phase-1.5 (merged `769b3db`)
- Notice emitter: `plugins/lastmilefirst/skills/audit-plugin/scripts/audit_plugin.py::_apply_untrusted_envelope`
