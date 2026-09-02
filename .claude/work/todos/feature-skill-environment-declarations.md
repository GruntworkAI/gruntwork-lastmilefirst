# Feature: skills should declare which environments they can run in

**Status:** OPEN
**Priority:** medium (correctness of skill triggering; grows with each new surface)
**Created:** 2026-09-01

## The problem

A skill's frontmatter carries `name` and `description` and nothing about where it can actually run. So every skill looks equally available everywhere, and the harness has no basis for filtering.

The consequences are already visible rather than hypothetical:

- `organize-project`, `scan-secrets`, and the other filesystem skills are meaningless without a filesystem, but nothing stops them being offered in a chat context.
- Overwatch flags workspace hygiene on surfaces that have no workspace, so its alerts are noise there rather than signal.
- The personas are pure prose and work anywhere, but they are indistinguishable in metadata from skills that need `Task`, `Bash`, and a git checkout.

The knowledge exists and is written down in prose ("on Desktop the personas work; Overwatch and the filesystem skills are Claude Code only"). It is just not anywhere a program can read it.

## Why it is getting worse

The surface count is growing. Claude Code, Desktop, claude.ai, and now managed agent runtimes, which have a sandbox and no plugin system at all. Every new surface multiplies the number of places a skill can be offered wrongly.

Being offered wrongly is not a cosmetic problem. A skill that cannot run either fails confusingly or, worse, half-runs and reports success from an environment where its checks were meaningless. Overwatch alerting about missing CLAUDE.md files on a surface with no repositories teaches the user to ignore Overwatch, which costs more than the false alert.

## Shape of a fix

Declarative frontmatter the harness can filter on. Two candidate axes, and capability is probably the better one:

```yaml
requires: [filesystem, git, subagents, plugin_host]
```

Capability rather than environment name, because a capability list survives a new surface arriving. An environment allowlist has to be edited every time something is added, and the edit will be forgotten.

An environment list may still be wanted alongside it for cases that are about product tier rather than capability, such as an API existing only on an enterprise plan.

Whichever axis, three things follow: skills with no declaration default to available, so nothing breaks on adoption; the harness filters what it offers rather than failing at invocation; and Overwatch reads the same declarations to decide what it is entitled to alert about.

## Worth noting

The personas are the case that motivates this from the other direction. They are portable prose with no tool dependency at all, and they are the most useful thing in the plugin on a surface that has nothing else. Being able to say so in metadata is what would let a non-Claude-Code runtime pick them up deliberately.

That is not hypothetical either: a managed agent runtime can attach uploaded skills, and the prose lenses (`review-voice`, `review-signal`, the personas) are exactly the subset that would work there.
