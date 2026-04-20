# Followup: consider widening Griffith discovery to include Poetry venv

**Status: deferred. Security decision, not a bug fix.**

**Surfaced during:** code review of `feat/audit-plugin-phase-1.5` on
2026-04-20 (merged commit `769b3db`).

## Context

`find_griffith()` in `scripts/audit_plugin.py` discovers the Griffith
binary through three paths, in order:

1. `GRIFFITH_BIN` environment variable (with allow-list prefix
   containment check)
2. `PATH` lookup via `shutil.which('griffith')`
3. `DEV_GRIFFITH` fallback at `~/Code/gruntwork/gruntwork-griffith/
   .venv/bin/griffith`, gated behind `LMF_ALLOW_DEV_GRIFFITH=1`

The dev fallback hardcodes Michael's personal Poetry venv path. This
works for the current single-developer workflow but fails for any
contributor whose Poetry venv lives elsewhere — which is common:

- Poetry's default behavior on macOS creates the venv in
  `~/Library/Caches/pypoetry/virtualenvs/<project>-<hash>-py3.X`
- `poetry env info --path` reveals the actual location; not always
  `.venv/` in the project root
- Users with `poetry config virtualenvs.in-project true` get `.venv/`
  inside the project; default users don't

## The security tradeoff

Widening discovery has a real cost:

- Auto-discovering a Poetry venv means running `poetry env info` or
  walking the poetry cache — touching user state that Griffith
  shouldn't need to know about
- Any discovered binary must still pass the containment check;
  Poetry cache paths aren't in the allow-list today
- A malicious Poetry venv on `PATH` is a thing — users who've run
  `poetry shell` in an untrusted repo could have a compromised
  `griffith` binary active

Today's posture is intentional: explicit `GRIFFITH_BIN=/path` is the
supported contributor workflow, and `LMF_ALLOW_DEV_GRIFFITH` is the
Michael-specific escape hatch.

## Why deferred

This is a security decision masquerading as a convenience
improvement. The right design requires:

1. Deciding whether Poetry cache paths belong in the allow-list
   (they're user-writable; that's a "no" for most auditors)
2. Deciding whether `poetry env info --path` output is authoritative
   (it is, but only for the specific project — adds complexity)
3. Fingerprinting / version-pinning the discovered Griffith binary
   (do we care if the user has multiple Griffith versions across
   venvs?)

None of these have a right answer today. Keep the current posture
until we have multiple contributors asking for this.

## Trigger conditions to revisit

- Second contributor asks "how do I point audit-plugin at my dev
  Griffith?" and finds `LMF_ALLOW_DEV_GRIFFITH` insufficient
- Griffith itself adopts a standard install mechanism (pipx,
  homebrew tap, etc.) that makes `shutil.which` reliable
- `GRIFFITH_BIN` gets documented in SKILL.md and contributors
  successfully use it (confirms the explicit path is enough)

## Related

- PR: feat/audit-plugin-phase-1.5 (merged `769b3db`)
- Implementation: `plugins/lastmilefirst/skills/audit-plugin/scripts/audit_plugin.py::find_griffith`
- Allow-list prefixes: `_allowed_griffith_prefixes()`
