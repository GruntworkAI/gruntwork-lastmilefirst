# Session: Making Agentic Development a Walk in the PARC

**Date:** February 4, 2026
**Duration:** ~2 hours
**Output:** lastmilefirst v0.10.0

## The Problem We Set Out to Solve

After publishing "Last Mile First: Fast Alone, Far Together," a gap became clear: the article described the *infrastructure* to avoid AI development traps (tunnel vision, debugging loops, project chaos), but not the *workflow discipline* for using that infrastructure session-to-session.

The question: How do you consistently follow a process that compounds value over time?

## The PARC Framework

We designed a 4-step workflow:

| Step | Purpose | Key Insight |
|------|---------|-------------|
| **P**lan | Think before doing | Balance YAGNI vs YAGWYDI |
| **A**llocate | Delegate to agents | Scout orchestrates, specialists execute |
| **R**eview | Verify correctness | Tests, code review, E2E validation |
| **C**ompound | Capture learnings | Produces Operatives and Stack-Wisdom |

### The YAGNI vs YAGWYDI Tension

This was a key design insight. Two competing voices in the Plan step:

- **YAGNI** (You Aren't Gonna Need It) - Don't overbuild features
- **YAGWYDI** (You're Gonna Wish You Did It) - Invest in infrastructure that compounds

The balance: YAGNI for features, YAGWYDI for scaffolding. Don't add speculative functionality, but do capture patterns and build operatives.

### Compound Has Concrete Units

The Compound step isn't vague "capture learnings." It produces two specific artifact types:

1. **Operatives** - Encoded domain expertise (reusable AI specialists)
2. **Stack-Wisdom** - Encoded patterns and lessons (searchable insights)

These are the "units of compounding." Every significant task should consider whether it produced expertise (operative) or insight (wisdom) worth preserving.

## Org-Level Infrastructure

We realized operatives and stack-wisdom need to live at the org level, not just user or project level:

```
~/Code/
├── personal/                    # You + AI agents = a team
│   ├── .claude/org.json
│   ├── personal-operatives/     # Git repo
│   └── personal-stack-wisdom/   # Git repo
└── work/
    ├── .claude/org.json
    ├── work-operatives/
    └── work-stack-wisdom/
```

Key insight: **"Personal" is an org.** Even solo developers have institutional knowledge worth preserving. You're not alone - you're a team of one plus AI agents.

## Design Decisions

### PARC Should Be "On By Default"

We debated whether to have a `/run-parc` command. Decided against it - PARC is how Claude *thinks*, not a command you invoke. It's embedded in CLAUDE.md templates so it's always active.

But we added `/run-strict-parc` for when you want enforced discipline with explicit gates between phases.

### Adaptive Guidance Based on Complexity

PARC scales ceremony to task complexity:

| Complexity | Plan | Allocate | Review | Compound |
|------------|------|----------|--------|----------|
| Trivial | Skip | Direct | Quick verify | Skip |
| Moderate | Brief | Suggest agents | Run tests | Offer if novel |
| Complex | Full planning | Orchestrate | Thorough | Always prompt |

### Config vs Convention

For org.json, operatives repo, and stack-wisdom repo:
- Check for explicit config first
- Fall back to convention (`[org]-operatives/`, `[org]-stack-wisdom/`)

This allows customization without requiring configuration.

## What We Built

### New Skills
- `organize-orgs` - Explains orgs, scaffolds infrastructure
- `search-wisdom` - Find patterns before starting work
- `add-wisdom` - Capture insights after completing work
- `parc` - Documents the workflow (not invoked, just reference)
- `strict-parc` - Enforced PARC with explicit gates

### New Commands
- `/run-organize-orgs`
- `/run-search-wisdom`
- `/run-add-wisdom`
- `/run-strict-parc`

### Updated Skills
- `consult-operative` - 3-tier lookup (Project → Org → User)
- `create-operative` - Org-level option
- `organize-claude` - Detects missing org infrastructure
- `overwatch` - Alerts on missing org.json, operatives, wisdom repos

### Templates
- `org.json` - Org configuration
- `wisdom-pattern.md` - Template for new wisdom
- `operatives-readme.md` - README for new operatives repos
- `stack-wisdom-readme.md` - README for new wisdom repos
- Workspace/Org CLAUDE.md templates include PARC by default

## The Compound Loop in Action

This session itself demonstrated the compound loop:

1. **Encountered a problem** - No workflow discipline for lastmilefirst
2. **Planned** - Designed PARC, debated naming (PARC vs PACE vs PRAC)
3. **Allocated** - Claude implemented while consulting the "user" (Michael) for design decisions
4. **Reviewed** - Verified skills referenced correct commands, changelogs accurate
5. **Compounded** - This session summary, release notes, potential article

## Quotable Insights

> "Personal is an org. You're not alone - you're a team of one plus AI agents."

> "YAGNI for features, YAGWYDI for infrastructure."

> "The Compound step produces two concrete artifacts: Operatives (domain expertise) and Stack-Wisdom (patterns and lessons). These are the units of compounding."

> "PARC isn't a command you invoke - it's how Claude thinks."

## Article Outline: "Making Agentic Development a Walk in the PARC"

### Hook
The first article (Last Mile First) described the infrastructure. But infrastructure without discipline is like a gym membership without a workout routine.

### The Problem
AI velocity without AI discipline leads to:
- Same mistakes repeated
- Knowledge trapped in chat logs
- No compounding of insights

### The Solution: PARC
Walk through the four steps with examples.

### The Key Tension: YAGNI vs YAGWYDI
Explain when to apply each.

### The Units of Compounding
Operatives and Stack-Wisdom as concrete artifacts.

### Personal Is An Org
Why even solo developers should set up org infrastructure.

### Getting Started
```bash
/plugin update lastmilefirst@gruntwork-marketplace
/run-organize-orgs
```

### What's Next
Future enhancements: cross-org sharing, PARC analytics.

---

*Session recorded for posterity and potential article fodder.*
