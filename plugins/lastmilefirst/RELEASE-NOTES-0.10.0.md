# lastmilefirst v0.10.0 - The PARC Release

**Released:** February 4, 2026

This release introduces the PARC workflow and org-level infrastructure - the biggest update to lastmilefirst since launch.

## What's New

### The PARC Workflow

PARC is now the default operating mode for Claude when using lastmilefirst:

**P**lan → **A**llocate → **R**eview → **C**ompound

Instead of jumping straight into code, Claude now:
1. **Plans** the approach (consulting experts when needed)
2. **Allocates** work to the right agents
3. **Reviews** thoroughly (tests, code review, validation)
4. **Compounds** learnings into reusable artifacts

The ceremony scales with complexity - trivial tasks skip most steps, complex features get full treatment.

**The key insight:** YAGNI for features (don't overbuild), YAGWYDI for infrastructure (invest in scaffolding that compounds).

For critical work, use `/run-strict-parc` to enforce explicit gates between phases.

### The Compound Step: Operatives and Stack-Wisdom

The Compound step isn't vague "capture learnings" - it produces two concrete artifact types:

| Artifact | What It Encodes | Created Via |
|----------|-----------------|-------------|
| **Operatives** | Domain expertise | `/run-create-operative` |
| **Stack-Wisdom** | Patterns and lessons | `/run-add-wisdom` |

**Operatives** are AI specialists that encode domain expertise. When you've solved enough problems in a domain, you create an operative that knows what you know. Future sessions consult that operative instead of learning from scratch.

**Stack-Wisdom** encodes patterns, gotchas, and hard-won insights. When debugging takes 30 minutes, you add the solution to wisdom. Future sessions search wisdom and solve it in 30 seconds.

These are the **units of compounding** - every significant task should consider whether it produced expertise (operative) or insight (wisdom) worth preserving.

### Org-Level Infrastructure

Your orgs now have dedicated infrastructure for operatives and wisdom:

```
~/Code/
├── personal/                    # Even solo work is an "org"
│   ├── .claude/org.json         # Org config
│   ├── personal-operatives/     # Your AI specialists (git repo)
│   └── personal-stack-wisdom/   # Your hard-won lessons (git repo)
└── work/
    ├── .claude/org.json
    ├── work-operatives/
    └── work-stack-wisdom/
```

Run `/run-organize-orgs` to set this up. It explains what orgs are (yes, "personal" counts - you're a team of one plus AI agents) and scaffolds the infrastructure.

### New Commands

| Command | Purpose |
|---------|---------|
| `/run-organize-orgs` | Set up org infrastructure |
| `/run-search-wisdom` | Find patterns before starting work |
| `/run-add-wisdom` | Capture insights after completing work |
| `/run-strict-parc` | Enforce PARC with explicit gates |

### Overwatch Now Detects Missing Infrastructure

At session start, Overwatch alerts you if your current org is missing:
- `.claude/org.json`
- Operatives repo
- Stack-wisdom repo

No more forgetting to set up org infrastructure.

## Updating

```bash
# Refresh marketplace
/plugin marketplace update gruntwork-marketplace

# Update plugin
/plugin update lastmilefirst@gruntwork-marketplace

# Set up your org infrastructure
/run-organize-orgs
```

## Philosophy

For deeper background on why we built this, see [Last Mile First: Fast Alone, Far Together](https://outsideshot.substack.com/p/last-mile-first-fast-alone-far-together).

## What's Next

- Python implementation for Overwatch org detection hooks
- Cross-org wisdom sharing (`/run-share-wisdom`)
- PARC analytics (how much time saved by compounding?)

---

**Full changelog:** See [CHANGELOG.md](./CHANGELOG.md)
