# Approved hierarchy and compatible storage

The logical model is workspace → organization → optional client → project. It is not proof
that an ancestor file is loaded, that every folder is accessible, or that private context may
be copied into a repo. Use explicit roots from the user's request or ask before extending a
single-repository task to an org/workspace audit. A CLI flag declares scope; it does not grant
filesystem permission. Respect denials and report partial results.

Existing LastMileFirst data stays where it is: .claude/org.json, .claude-workspace, .claude/work,
.claude/debt, .claude/archive. Context filenames are chosen independently. AGENTS.md is Codex
context, CLAUDE.md is legacy context; neither implies a migration of work or identity storage.

Organization contracts keep operatives, stack_wisdom, stack_knowledge, and identity fields.
Honor enabled: false for optional support repos. Relative resource paths must stay within
the approved org; do not follow external symlinks or absolute/parent-traversal values.
Only inspect local metadata; account liveness and cross-workspace ownership remain unknown
without separately scoped checks. owns_remotes is a claim registry, not an allowlist:
an unclaimed remote owner is allowed, and organizations sharing an account do not conflict.

The existing .claude-workspace marker has type: studio, external, scratch, or client.
External/scratch exempts identity obligations only, not other project review evidence.
A client container is recognized one level under an org. It holds projects; it is not itself
one. A client nested inside a client is not another supported tier. Report client org.json
and client repository conflicts even when a client is empty. Malformed markers and inaccessible
paths need findings, not silent successful defaults. Do not recurse through arbitrary trees.

Read-only means no filesystem changes, including caches. Do not run canonical audit_identity,
review_claude, organize, or Overwatch CLIs from vendor/; some have auto-discovery and write modes.
The wrapper selects bounded pure rubric functions, not those CLI entry points. No hooks are
installed. Existing review history may be discussed only if an authorized source was actually
read, with provenance and freshness limitations; this pilot's runner does not load it.
