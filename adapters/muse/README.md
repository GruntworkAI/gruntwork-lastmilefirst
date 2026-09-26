# Muse adapter for the LastMileFirst plugin

> **Muse user looking to install and use this?** Read
> [README-MUSE-USERS.md](README-MUSE-USERS.md): this file is the builder's
> view of how the port is constructed.

This directory builds a **Muse-optimized skill package** from the canonical
Claude Code plugin. No hand-duplicated content.

> **What is Muse?** Muse is Meta's AI assistant (muse.ai), and this package
> targets its workspace skills system. The adapter is maintained by GruntworkAI
> as a best-effort port of the LastMileFirst plugin; it is not an official Meta
> product, and it implies no partnership. Adding it here commits the plugin to
> tracking Muse as a second platform for these skills, nothing more.

## Observed interfaces (as of 2026-09-25)

Meta publishes no developer platform, SDK, or skill marketplace for Muse, and
the interfaces this adapter targets are **observed from the environment, not
documented**: `~/workspace/skills/` as the skills path, the `muse.*` tool
namespace (`muse.memory_search`), `subagent.spawn` for subagents, scheduled
jobs, skills loading fresh each turn, and durable memory surfaced through
`MEMORY.md` (there is no documented memory write API; the file is the
agent-visible durable store). These are real, working interfaces in the VM —
not guesses — but they are not public API and can change without notice.
`build.py --check` only verifies the package matches its sources; it cannot
detect platform drift. If Muse changes, update `mapping.toml` and the date on
this note.

## Layout

```
adapters/muse/
  README.md          # this file
  mapping.toml       # mechanism translations (Claude Code-isms -> Muse equivalents)
  build.py           # applies mapping.toml to canonical sources -> dist/
  adapter/           # hand-written Muse-specific design (copied verbatim into dist/)
    skills/
      lastmilefirst/
        SKILL.md             # operational core: PARC for Muse
        bin/scan-secrets     # thin wrapper around the canonical scanner (no copied code)
        references/
          overwatch-muse.md  # Overwatch checks mapped to cron/hooks
  dist/              # generated at install time; gitignored, never committed
    skills/
      lastmilefirst/
        SKILL.md             # from adapter/
        bin/scan-secrets     # from adapter/
        references/
          parc-full.md       # generated from plugins/lastmilefirst/skills/parc/SKILL.md
          review-docs.md     # generated from .../skills/review-docs/SKILL.md
          review-voice.md    # generated from .../skills/review-voice/SKILL.md
          voice-sheet-example.md  # generated from .../skills/review-voice/voice-sheet-example.md
          scan-secrets.md    # generated from .../skills/scan-secrets/SKILL.md
          personas.md        # generated roster of plugins/lastmilefirst/personas/*.md
          overwatch-muse.md  # from adapter/
```

## The rule

**Copy nothing. Refactor the mechanism, keep the judgment.**

- The PARC phases, the review rubrics, YAGNI-vs-YAGWYDI, the Compound close.
  Platform-agnostic, they live once, in `plugins/lastmilefirst/skills/`.
- `mapping.toml` translates only *mechanism*: slash commands become subagent
  spawns, `~/.claude` becomes `~`, wisdom commands become `muse.memory_search`.
- `SKILL.md` (the operational core) is hand-written because it describes how
  *Muse* works. That prose doesn't exist in the plugin and shouldn't.

## Regenerating

```bash
python3 adapters/muse/build.py           # regenerate dist/
python3 adapters/muse/build.py --check   # fail if dist/ is stale
python3 adapters/muse/build.py --lint    # fail on leftover Claude Code-isms in the output
```

`--check` is the freshness contract: the generated package can never silently
drift from the canonical sources. `--lint` is the correctness contract: no
slash commands or product names survive the translation (fenced code examples
are exempt). Wire both into CI or an Overwatch-style scheduled check.

## What's ported in this slice

Slice 1: PARC as the default working method + review checklists
(`review-docs`, `review-voice`). Slice 2: secret-scanning (canonical scripts
run via `bin/scan-secrets`; needs `gitleaks` on PATH). Slice 3: the 16 expert
personas as subagent briefs (`references/personas.md` roster). Slice 4:
Overwatch checks mapped to scheduled jobs (`references/overwatch-muse.md`;
design plus a ready-to-paste recipe, nothing scheduled without the user's go-ahead).

## Installing into a Muse workspace

Build, then copy:

```bash
python3 adapters/muse/build.py
cp -r adapters/muse/dist/skills/lastmilefirst/ ~/workspace/skills/
```

The skill then shapes how that Muse agent plans, reviews, and compounds
learnings.
