# Feature: Overwatch says when the pre-push hook is not installed

**Status:** open
**Priority:** medium
**Created:** 2026-10-09

## Summary

0.37.0 ships a pre-push hook, but only `/run-scan-secrets --install-hooks` writes it, and a user who
upgrades without re-running the installer has a guard the release notes describe as shipped and that is
not armed. The session-start hook already knows the hooks directory (`hook_installer.HOOKS_DIR`) and
whether `core.hooksPath` points at it; it does not say anything when the pre-push file is missing.

## Proposed change

Session start, in any git repo: when the global `core.hooksPath` is set to the plugin's hooks directory
and `pre-push` is absent there (or `pre-commit` is), print
`ACTION REQUIRED: the lastmilefirst pre-push hook is not installed; run /run-scan-secrets --install-hooks`.
Silent when `core.hooksPath` is unset (the user never installed hooks) or points elsewhere (a repo-local
husky or lefthook setup, which the 0.37.0 review noted bypasses both dispatchers and is a separate gap).

## Notes

Raised by the adversarial reviewer in the 0.37.0 code review (run 20261009-173148). Related residual
from the same review, not addressed here: a repo-local `core.hooksPath` never runs either global
dispatcher, and `hook_status` reads only the global setting.
