# Agent Teams Integration Plan

**Status:** Workshop Draft
**Started:** 2026-02-06
**Last Updated:** 2026-02-06

---

## Context for New Sessions

**What is this?** A working document exploring how to integrate Claude Code's new Agent Teams feature into the lastmilefirst plugin.

**Why does this matter?** Agent Teams provides infrastructure for what we've been approximating with Task tool subagents. It's a natural evolution that aligns with our PARC workflow and expert/operative system.

**Current plugin state (v0.10.1):**
- PARC workflow (Plan → Allocate → Review → Compound)
- 13 public expert personas (Paloma, Adam, Scout, etc.)
- Private operatives system (3-tier: project → org → user)
- Stack-wisdom (patterns/lessons) and stack-knowledge (facts/docs)
- Overwatch for proactive monitoring

**Key files to understand the plugin:**
- `plugins/lastmilefirst/README.md` - Full documentation
- `plugins/lastmilefirst/skills/parc/SKILL.md` - PARC workflow
- `plugins/lastmilefirst/personas/` - Expert definitions
- `plugins/lastmilefirst/agents/` - Current subagent implementations

**Agent Teams docs:** https://code.claude.com/docs/en/agent-teams

**The approach:** Workshop concepts in this document, run experiments, capture learnings, THEN formalize into plugin skills. Don't build until we understand.

---

## Overview

Claude Code released Agent Teams - a system for coordinating multiple Claude Code instances working together. This document explores how lastmilefirst can leverage Agent Teams to enhance the PARC workflow and our expert/operative system.

**Goal:** Learn by doing, document as we go, then codify into plugin functionality.

---

## Part 1: Understanding Agent Teams

### What Agent Teams Provides

| Component | Description |
|-----------|-------------|
| **Team Lead** | Main session that coordinates work |
| **Teammates** | Independent Claude instances with own context |
| **Shared Task List** | Pending → In Progress → Completed with dependencies |
| **Mailbox** | Inter-agent messaging (not just report-back) |
| **Plan Approval** | Lead can require plan approval before implementation |
| **Delegate Mode** | Lead focuses on coordination only |

### Key Differences from Subagents

| Aspect | Subagents (Task tool) | Agent Teams |
|--------|----------------------|-------------|
| Context | Own window, results return to caller | Fully independent |
| Communication | Report back only | Teammates message each other |
| Coordination | Main agent manages all | Self-coordination + lead |
| Token cost | Lower (summarized results) | Higher (full sessions) |
| Best for | Focused tasks | Collaboration, debate, parallel exploration |

### When Agent Teams Shine

1. **Research and review** - Multiple perspectives simultaneously
2. **New modules** - Teammates own separate pieces
3. **Debugging with competing hypotheses** - Test theories in parallel
4. **Cross-layer coordination** - Frontend, backend, tests each owned

### Current Limitations (Experimental)

- No session resumption with in-process teammates
- Task status can lag
- Shutdown can be slow
- One team per session
- No nested teams
- Lead is fixed for lifetime

---

## Part 2: Alignment with PARC

### Natural Mapping

```
PARC Step        Agent Teams Feature
─────────────    ──────────────────────────────────────
Plan             Lead requires plan approval before implementing
Allocate         Lead spawns teammates, assigns via shared task list
Review           Multiple reviewer teammates with different lenses
Compound         Lead synthesizes; trigger wisdom capture
```

### PARC-Aware Team Lead

The team lead could enforce PARC gates:

```
Phase: PLAN
├── Lead gathers requirements
├── Lead proposes team composition
├── User approves team structure
└── Gate: Team structure approved

Phase: ALLOCATE
├── Lead spawns teammates with personas
├── Lead assigns tasks via shared list
├── Teammates claim and execute
└── Gate: All tasks completed

Phase: REVIEW
├── Lead synthesizes teammate outputs
├── Lead spawns review teammates if needed
├── Cross-review between teammates
└── Gate: Quality criteria met

Phase: COMPOUND
├── Lead identifies patterns worth capturing
├── Prompts for wisdom/operative creation
└── Gate: Learnings documented (or explicitly skipped)
```

---

## Part 3: Integration Opportunities

### 3.1 Experts as Teammate Templates

**Current:** `/run-consult-expert paloma "question"` spawns a subagent

**With Agent Teams:** Personas become spawn prompts for full teammates

```markdown
# Teammate Template: Paloma

**Spawn Prompt:**
You are Paloma, a full-stack engineer specializing in Python/FastAPI
and React/TypeScript. You write elegant, type-safe code. You're known
for solving state management issues that stump others.

**Best For:**
- Python backend work
- React state management debugging
- Full-stack feature implementation

**Typical Tasks:**
- Implement API endpoints
- Debug async/state issues
- Review Python/TypeScript code
```

**Questions to explore:**
- [ ] How do spawn prompts differ from persona definitions?
- [ ] Should personas include "teammate mode" instructions?
- [ ] How does CLAUDE.md context combine with spawn prompt?

### 3.2 Scout as Team Lead

**Current:** Scout routes to the right expert via subagent

**With Agent Teams:** Scout becomes the natural team lead

```
User: "I need to add authentication to the API"

Scout (as lead):
├── Analyzes: cross-cutting (backend + frontend + security)
├── Proposes team:
│   ├── Paloma teammate: API implementation
│   ├── Adam teammate: Infrastructure (if Lambda auth)
│   └── Security reviewer teammate: Audit the approach
├── Creates shared task list
├── Spawns teammates
└── Coordinates and synthesizes
```

**Questions to explore:**
- [ ] Does Scout need different instructions as lead vs subagent?
- [ ] How does Scout decide: subagent vs teammate vs team?
- [ ] Should Scout explain its team composition reasoning?

### 3.3 Operatives as Private Teammate Configs

**Current:** Operatives are private persona files consulted via subagent

**With Agent Teams:** Operatives become private teammate templates

```
~/[org]/[org]-operatives/
├── razor.md              # Persona (current)
└── razor-teammate.md     # Teammate config (new?)

# Or extend persona format:
---
name: razor
title: Security Penetration Specialist
base: paloma
teammate:
  spawn_prompt: |
    You are Razor, a security specialist...
  best_for:
    - Security reviews
    - Penetration testing approach
    - Auth system design
  typical_tasks:
    - Review for OWASP top 10
    - Audit authentication flows
---
```

**Questions to explore:**
- [ ] Extend persona format or separate teammate config?
- [ ] How do operatives inherit from base personas in teammate mode?
- [ ] Private teammate templates in same location as operatives?

### 3.4 Review Skill → spawn-review-team

**Current:** `/run-review-project` runs sequentially

**With Agent Teams:** Parallel review with specialized teammates

```
/run-spawn-review-team

Spawns:
├── Security Reviewer: OWASP, auth, input validation
├── Performance Reviewer: queries, caching, scaling
├── Test Coverage Reviewer: missing tests, edge cases
└── Architecture Reviewer: patterns, coupling, coherence

Each reviews independently, then:
├── Teammates share findings with each other
├── Debate disagreements
├── Lead synthesizes final report
└── Prompt for wisdom capture on significant findings
```

**Questions to explore:**
- [ ] Which review types benefit most from parallelization?
- [ ] How do reviewers with competing findings resolve?
- [ ] Should reviewers see each other's findings?

### 3.5 Debug Team with Competing Hypotheses

**Inspired by:** Agent Teams documentation example

```
/run-spawn-debug-team "Users report app exits after one message"

Spawns 3-5 teammates, each with a hypothesis:
├── Teammate 1: Connection handling issue
├── Teammate 2: State management bug
├── Teammate 3: Event loop problem
├── Teammate 4: Race condition
└── Teammate 5: Configuration issue

Protocol:
├── Each investigates their hypothesis
├── Share evidence with team
├── Actively try to disprove each other
├── Converge on most likely cause
└── Winner's solution becomes wisdom pattern
```

**This is pure compound engineering:**
- Competition produces better answers
- Winning hypothesis becomes reusable pattern
- The process itself is captured as wisdom

### 3.6 Wisdom Integration

**After team completes work:**

```
Lead: "The team identified that Terraform workspace mismatch
was the root cause. This took 3 teammates investigating
different hypotheses before convergence.

This pattern could save future debugging time.
Should I add it to stack-wisdom?"

Options:
1. Add as pattern (symptoms, solution, prevention)
2. Add as circuit breaker (early detection)
3. Add as trigger keywords
4. Skip - not generalizable
```

**Questions to explore:**
- [ ] How does lead identify "wisdom-worthy" outcomes?
- [ ] Should teammates vote on wisdom candidates?
- [ ] Can the debate itself be captured as wisdom?

---

## Part 4: Proposed New Skills

### Priority 1: Foundation

| Skill | Purpose | Complexity |
|-------|---------|------------|
| `spawn-expert-team` | Spawn team from expert personas | Medium |
| `spawn-review-team` | Parallel code review | Medium |

### Priority 2: Advanced

| Skill | Purpose | Complexity |
|-------|---------|------------|
| `spawn-debug-team` | Competing hypothesis investigation | High |
| `spawn-parc-team` | Team with explicit PARC gates | High |

### Priority 3: Infrastructure

| Skill | Purpose | Complexity |
|-------|---------|------------|
| Teammate templates | Extend persona format | Low |
| Team lead instructions | Scout as team lead | Medium |
| Wisdom integration | Post-team compound step | Medium |

---

## Part 5: Workshop Log

### Session 1: 2026-02-06 - Initial Analysis

**Participants:** Michael, Claude

**Prior context:** Just finished implementing stack-knowledge system (v0.10.1), which complements stack-wisdom. The wisdom vs knowledge distinction ("will this help in a different project someday?" vs "specific to this project/client") is fresh.

**How we got here:**
1. Michael shared Agent Teams announcement URL
2. Claude fetched and analyzed the documentation
3. Identified natural alignment with PARC and our expert system
4. Discussed integration opportunities
5. Decided to create workshop document before any code

**Key insights from discussion:**
- Agent Teams is what we were approximating with Task tool subagents
- Scout is a natural team lead (already designed as coordinator)
- Personas could become "teammate templates" with spawn prompts
- The "competing hypotheses" pattern is pure compound engineering
- Winning hypothesis from debug team → stack-wisdom pattern

**Decisions:**
- Start with document, not code
- Workshop the concepts before implementing
- Use agent teams to improve this plan (meta!)
- Pick this up in a fresh session with fresh context

**Open Questions:**
1. Should we try Agent Teams on a real task first?
2. Which skill to prototype first?
3. How experimental is too experimental to build on?
4. How do spawn prompts differ from our existing persona definitions?
5. Token cost tradeoffs - when is a team worth it vs subagents?

**Next Steps:**
- [ ] Enable Agent Teams: add `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` to settings
- [ ] Try spawn-review-team concept manually on a real PR/code
- [ ] Document learnings in Experiment Log below
- [ ] Consider: spawn a team to debate/improve this plan itself

---

## Part 6: Experiment Log

### Experiment 1: [Title]

**Date:** [TBD]
**Goal:** [What we're testing]
**Setup:** [How we configured it]
**Results:** [What happened]
**Learnings:** [What we learned]
**Wisdom Candidate:** [Pattern worth capturing?]

---

## Part 7: Formalization Checklist

When ready to codify into plugin:

- [ ] Teammate template format defined
- [ ] At least one skill tested manually
- [ ] Token cost implications understood
- [ ] Failure modes documented
- [ ] PARC integration validated
- [ ] Wisdom capture flow tested

---

## Appendix A: Agent Teams Configuration

```json
// settings.json
{
  "env": {
    "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"
  }
}
```

## Appendix B: Related Documentation

- [Agent Teams Docs](https://code.claude.com/docs/en/agent-teams)
- [Subagents Comparison](https://code.claude.com/docs/en/sub-agents)
- [lastmilefirst PARC Workflow](../../../skills/parc/SKILL.md)
- [Expert Personas](../../../personas/)

## Appendix C: Token Cost Considerations

Agent Teams uses significantly more tokens:
- Each teammate is a full Claude session
- Scales with number of teammates
- Worth it for: research, review, debugging with hypotheses
- Overkill for: sequential tasks, same-file edits, simple fixes

**Rule of thumb:** If teammates need to debate or challenge each other, Agent Teams. If they just need to do work and report back, subagents.
