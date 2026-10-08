---
title: Overwatch project checks fire only for a project, at its root
version: 1.0
date: 2026-10-08
status: built
type: fix
component: hooks/scripts/session_start.py, hooks/scripts/overwatch.py, hooks/tests/test_project_checks.py (new), skills/overwatch/SKILL.md, CLAUDE.md, README.md
target_version: 0.36.2
refs:
  - ~/Code/drafts/LMF plug in/LMF-Overwatch-context-and-intent-plan.docx (the 2026-10-07 applicability-gate plan this supersedes)
  - .claude/work/todos/feature-skill-environment-declarations.md (the long-term capability axis; unchanged by this fix)
  - PR #35 feat/codex-adapter (independent; touches session_start.py only in the org-infrastructure check)
  - https://claude.com/docs/plugins/platform-support (hooks load in Cowork and Claude Code, are ignored in Chat; checked 2026-10-07)
---

# Overwatch project checks fire only for a project, at its root (v1.0)

> **v1.0 (2026-10-08).** Written after reproducing the reported false alarms by running the
> session-start hook directly from four directories. Replaces a larger plan (2026-10-07) that
> proposed an applicability policy module, a per-conversation intent question, and surface
> detection. The reproduction showed the problem is two checks reading the current directory
> instead of the resolved project, so that design is set aside.

## Problem

### P1. Project-element alerts fire where there is no project

Overwatch's session-start hook emits "ACTION REQUIRED: No CLAUDE.md in this project. Run
/run-organize-project to scaffold" whenever the current directory lacks a `CLAUDE.md`. The check
never asks whether the directory is a project. The dispatcher already knows: `resolve_context`
returns no project for a directory outside a configured org, and the review, organize, scan,
and archetype checks all skip on that condition. The CLAUDE.md check does not, and because it
is an ACTION REQUIRED line it also triggers the DIRECTIVE that tells Claude to present it before
doing anything else.

Reproduced 2026-10-08 by running the hook from `~/Code/drafts` and `~/Downloads`: both produce
the alert and the directive. A Cowork task opened on any folder outside the workspace gets the
same, since hooks load in Cowork. A conversation that was never about a project is told to
scaffold one. The user reported exactly this: occasional alerts about missing project elements
in chats that were not project based.

### P2. Below a project root, the alert fires for the wrong directory

From `gruntwork-stack-wisdom/setup-scripts` the project resolves correctly (the review and scan
alerts name it), and the CLAUDE.md check fires anyway because it looks in the current directory
rather than at the project root it just resolved. The archetype check has the same shape from
the other side: in a subdirectory it finds no `CLAUDE.md` and stays silent, so a project with no
archetype is never flagged from inside its own tree.

### P3. The docs say Overwatch is Claude-Code-only, and it is not

The repository `CLAUDE.md` gotchas table says Overwatch and the filesystem skills are
Claude-Code-only. The current platform matrix says hooks load in Cowork and Claude Code and are
ignored in Chat. The claim is narrower than the truth and points anyone reproducing P1 at the
wrong surface.

## Decisions

**D1. No intent question, no surface detection.** The superseded plan proposed asking "is this a
project that would benefit from LMF conventions?" once per conversation, remembering the answer,
and detecting Desktop versus browser. None of that is needed. Whether a directory is a project is
already answered by the organize-claude config (workspace root plus org list), and hooks cannot
see conversation state in any case, so a remembered answer would have had to be written to disk.
The correct behavior outside a project is silence on project elements.

**D2. Silence, not a notice, outside the workspace.** A one-line "not a project, checks skipped"
was considered. It would appear in every non-project session, which is the noise the fix is
removing. A new directory under a configured org still resolves as a project and still gets the
CLAUDE.md alert at its root, so the new-project prompt in the user's workspace `CLAUDE.md`
keeps working where it should.

**D3. The project root is the workspace joined with the state key.** `resolve_context` returns
the key (`org/project` or `org/client/project`) relative to the workspace. One helper in
`overwatch.py` turns a context and config into the root path, or `None`. Checks that need a
project receive that path instead of reading `Path.cwd()`.

**D4. Git status and the workspace sweep stay as they are.** The uncommitted-files check reads
git from the current directory, which is accurate wherever it runs and is not a project claim.
The workspace-wide secret-scan reminder is deliberately ungated (dispatcher comment, v0.24.0)
because the repos it exists for are the ones nobody opens.

**D5. The capability axis is a separate, open todo.** `feature-skill-environment-declarations`
remains the long-term answer to what Overwatch may alert about on a given surface. This fix
does not touch it.

## Units

**U1. Root helper and check signatures.** Add `project_root(ctx, config) -> Optional[Path]` to
`overwatch.py`. Change `check_claude_md` and `check_archetype` to take the project directory;
both return `None` when it is `None`. Pass the root to `check_overwatch_guidance` as its `cwd`
so the project's own `CLAUDE.md` is searched from a subdirectory. In `main`, compute the root
once and gate the CLAUDE.md check on it the way the archetype check already is.

**U2. Tests.** New `hooks/tests/test_project_checks.py` using the throwaway-workspace pattern
from `test_resolve_and_summary.py`. Cases: subdirectory of a project with no root `CLAUDE.md`
(alert), subdirectory of a project with a root `CLAUDE.md` (no alert), project root with a
`CLAUDE.md` lacking an archetype reached from a subdirectory (archetype warning), org root (no
alert), client directory (no alert), unlisted directory inside the workspace (no alert),
directory outside the workspace (no alert), and `project_root` for flat, nested, and empty
contexts.

**U3. Prose.** Repository `CLAUDE.md` gotchas row: hooks run in Claude Code and Cowork, not
Chat, and project checks are evaluated at the resolved project root. Overwatch `SKILL.md`: a
short "Where it runs" note under How It Works. Plugin `README.md` line 35: each Claude Code or
Cowork session, inside a configured project.

**U4. Release.** `CHANGELOG.md` Fixed entry; bump to 0.36.2 in `plugin.json`,
`marketplace.json` (both fields), and the README version table. Release tag after merge, per
the repository checklist.

## Acceptance

- Running the hook from `~/Downloads`, `~/Code/drafts`, an org root, and a client directory
  emits no project-element alert and no DIRECTIVE from one.
- Running it from a subdirectory of a project without a root `CLAUDE.md` emits the alert
  naming that project; with a root `CLAUDE.md` it does not.
- The hooks suite passes (315 tests before this change) plus the new file.
- No change to git-status, workspace-sweep, plugin-update, or workspace-summary output.

## Out of scope

The Codex adapter (PR #35), the Muse adapter, any intent or enrollment persistence, surface
detection, and the capability-declaration todo.
