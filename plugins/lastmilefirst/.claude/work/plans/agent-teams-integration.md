# Agent Teams Integration Plan

**Status:** Workshop Draft (Review Team Findings Incorporated)
**Started:** 2026-02-06
**Last Updated:** 2026-02-06

---

## Context for New Sessions

**What is this?** A working document exploring how to integrate Claude Code's new Agent Teams feature into the lastmilefirst plugin.

**Why does this matter?** Agent Teams provides infrastructure for what we've been approximating with Task tool subagents. It's a natural evolution that aligns with our PARC workflow and expert/operative system.

**Current plugin state (v0.10.1):**
- PARC workflow (Plan -> Allocate -> Review -> Compound)
- 13 public expert personas (Paloma, Adam, Scout, etc.)
- Private operatives system (3-tier: project -> org -> user)
- Stack-wisdom (patterns/lessons) and stack-knowledge (facts/docs)
- Overwatch for proactive monitoring

**Key files to understand the plugin:**
- `plugins/lastmilefirst/README.md` - Full documentation
- `plugins/lastmilefirst/skills/parc/SKILL.md` - PARC workflow
- `plugins/lastmilefirst/personas/` - Expert definitions
- `plugins/lastmilefirst/agents/` - Current subagent implementations

**Agent Teams docs:** https://code.claude.com/docs/en/agent-teams

**The approach:** Workshop concepts in this document, run experiments, capture learnings, THEN formalize into plugin skills. Don't build until we understand.

**Design philosophy:** Apply YAGNI vs YAGWYDI throughout this plan:
- **YAGNI for features** - Don't build speculative skills until experiments prove value
- **YAGWYDI for infrastructure** - Invest in decision frameworks, guardrails, template formats, and patterns that compound

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
| **Shared Task List** | Pending -> In Progress -> Completed with dependencies |
| **Mailbox** | Inter-agent messaging (not just report-back) |
| **Plan Approval** | Lead can require plan approval before implementation |
| **Delegate Mode** | Lead focuses on coordination only |

### Key Differences from Subagents

| Aspect | Subagents (Task tool) | Agent Teams |
|--------|----------------------|-------------|
| Context | Own window, results return to caller | Fully independent, full context window each |
| Communication | Report back only | Teammates message each other via mailbox |
| Coordination | Main agent manages all | Self-coordination + lead |
| Token cost | Lower (summarized results) | Higher (full sessions), ~4-6x multiplier |
| Permissions | Tools declared per agent in frontmatter | All teammates inherit lead's permissions |
| Nesting | Subagents can spawn subagents | Teammates cannot spawn subagents or teams |
| CLAUDE.md | Loaded by parent, not subagent | Each teammate loads independently |
| MCP servers | Not available to subagents | Available to all teammates (e.g., Synthasaurus) |
| Skills | Must be explicitly listed | Loaded from project context |
| Best for | Focused tasks, single-domain questions | Collaboration, debate, parallel exploration |

### When Agent Teams Shine

1. **Research and review** - Multiple perspectives simultaneously
2. **Cross-layer coordination** - Frontend, backend, tests each owned, can negotiate interfaces
3. **Debugging with competing hypotheses** - Test theories in parallel
4. **Tasks requiring debate** - Where experts need to challenge each other's findings

### When Subagents Are Better

1. **Single expert consultations** - One question, one answer
2. **Independent tasks** - Workers report back, don't need to talk
3. **Small scope** - Under 2 parallel tasks (team overhead negates parallelism)
4. **Token-sensitive work** - When cost matters more than depth

### Current Limitations (Experimental)

- No session resumption with in-process teammates
- Task status can lag
- Shutdown can be slow
- One team per session
- No nested teams (teammates can't spawn subagents)
- Lead is fixed for lifetime
- Can't set per-teammate permissions at spawn time
- Two teammates editing the same file leads to overwrites

---

## Part 2: Decision Framework (YAGWYDI - Infrastructure)

This framework is infrastructure that compounds every future decision about when to use teams vs subagents. Invest in getting this right.

### The Heuristic

> **Use a subagent when you need an ANSWER.**
> **Use a team when you need a CONVERSATION.**

If the work benefits from experts challenging each other, negotiating tradeoffs, or building on each other's output, that's a team. If you just need specialized knowledge applied to a specific question, that's a subagent.

### Decision Matrix

| Scenario | Tool | Why |
|----------|------|-----|
| Single expert question | Subagent | 1 turn, summarization is fine |
| 2 experts, independent questions | 2 subagents | Sequential is fine, cheaper than team |
| 3+ experts, independent questions | Agent Team | Parallelism wins on latency |
| Tasks requiring cross-reference | Agent Team | Teammates need each other's full output |
| Competing hypotheses | Agent Team | Deep independent investigation needed |
| Simple code review (<100 lines) | Single subagent | Not enough surface area for a team |
| Complex review (multi-file, multi-concern) | Agent Team | Multiple lenses, detailed findings |

### Scout's Routing Logic (Future)

Map to Scout's existing complexity levels:

```
L0-L1 (Simple/Moderate): Always subagents
L2 (Complex): Consider Agent Teams, suggest to user
L3-L4 (Expert/Critical): Default to Agent Teams proposal with cost estimate
```

### PARC Allocate: Teams vs Subagents

**Key insight from review:** Most PARC Allocate work is "do task, report back" -- which subagents handle fine. Agent Teams only adds value when allocated workers need to communicate during execution.

```
IF workers report back independently -> Subagents (current, keep as default)
IF workers need to communicate mid-task -> Agent Teams
IF single expert needed -> Direct subagent consult (current)
```

Example where teams help: Paloma building an API endpoint + frontend dev building the React component -- they need to negotiate the API contract. Subagents can't do this.

Example where subagents are fine: Paloma implements backend + Adam configures Terraform -- independent work, report back.

---

## Part 3: Alignment with PARC

### Natural Mapping

```
PARC Step        Agent Teams Feature
-------------    --------------------------------------
Plan             Lead requires plan approval before implementing
Allocate         Lead spawns teammates when they need to coordinate
Review           Multiple reviewer teammates with different lenses
Compound         Lead synthesizes; trigger wisdom capture
```

### How PARC Phases Use Teams

**Plan:** Team lead (the user's session) gathers requirements and proposes team composition. User approves team structure AND estimated cost before spawning.

**Allocate:** Only use teams when workers need inter-task communication. For independent tasks, keep using subagents. The decision framework above governs this.

**Review:** Strongest fit. Independent reviewers with different lenses, can cross-reference findings, debate disagreements. This is the first experiment target.

**Compound:** Lead synthesizes all teammate outputs and drives the existing `/compound` wisdom capture. No new mechanism needed -- the current compound flow already works.

---

## Part 4: Cost Model (YAGWYDI - Infrastructure)

Understanding costs is infrastructure that prevents bill shock and enables informed decisions. These estimates are pre-experiment and should be updated with real data.

### Estimated Token Costs

| Team Configuration | Input Tokens | Output Tokens | Est. Cost (Sonnet) | vs Subagents |
|-------------------|-------------|--------------|-------------------|-------------|
| 4 sequential subagents (baseline) | ~45K-65K | ~12K-16K | ~$0.15-$0.40 | 1x |
| 4-teammate review team | ~120K-230K | ~37K-65K | ~$0.90-$1.65 | **4-6x** |
| 3-teammate debug team | ~200K-350K | ~50K-100K | ~$1.50-$3.00 | **8-10x** |

### Cost Drivers

1. **Duplicate context loading** - Each teammate loads system prompt + CLAUDE.md independently (~15-30K wasted tokens across 4 teammates)
2. **Multi-turn conversations** - Teammates iterate, not single-shot. Each turn re-reads growing context
3. **Inter-teammate messaging** - N teammates sending M messages = N*M message-read events
4. **Growing context per turn** - Turn 1: ~10K input, Turn 5: ~30K input, Turn 10: ~50K+ input

### When the Cost Is Justified

The 4-6x multiplier is worth it when:
- Subagent summarization loses critical fidelity (detailed security audits, nuanced findings)
- Experts need each other's full output to cross-reference
- Parallelism saves significant wall-clock time (3+ independent tasks)
- The task would otherwise trigger the debugging loop circuit breaker

The multiplier is NOT worth it when:
- A single expert can answer the question
- Tasks are sequential (parallelism doesn't help)
- The expected output per agent is under ~1000 tokens

---

## Part 5: Guardrails (YAGWYDI - Infrastructure)

Guardrails are infrastructure that enables responsible use at scale. Build these before any skills.

### Hard Limits

| Guardrail | Default | Maximum | Rationale |
|-----------|---------|---------|-----------|
| Teammates per team | 4 | 6 | Communication overhead grows quadratically |
| Turns per teammate | 5 | 8 | Context window grows linearly per turn |
| Inter-team messages | 8 | 12 | Each message read by N-1 others |
| Token budget per session | 300K | 1M | Hard cap to prevent runaway cost |

### User Confirmation Before Spawn

Before spawning any team, show the user:

```
This problem spans 3 domains. I recommend spawning a 3-teammate
team (Paloma, Adam, Security Reviewer).

Estimated cost: ~$1.00-$1.50 (4-6x more than sequential consultations)
Estimated time: ~45-90 seconds (vs ~90-180 seconds sequential)

Proceed? [y/n]
```

### Graceful Degradation (YAGWYDI - Critical)

Agent Teams is experimental and disabled by default. Every team-capable skill MUST:

1. **Detect** whether `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` is enabled
2. **Fall back** to the existing subagent approach if not enabled
3. **Work identically** (same output format) regardless of which mode runs

This ensures the plugin doesn't break for users who haven't opted into the experiment.

### File Ownership

When teammates work on related code, the lead must assign clear file ownership:
- No two teammates should edit the same file
- Shared config files are owned by one teammate, others read-only
- Lead mediates if ownership conflicts arise

### Recovery Strategy

If a team dies mid-work (session disconnect, teammate failure):
- Completed teammate outputs persist in their task results
- Lead should report partial results, not silently fail
- PARC tracker should be updated to reflect partial completion
- User can re-run with subagents to fill gaps

---

## Part 6: Integration Opportunities

### 6.1 Experts as Teammate Templates (YAGWYDI - Pattern Infrastructure)

**Current:** `/run-consult-expert paloma "question"` spawns a subagent

**Key insight from review:** Single expert consultations MUST remain as subagents. Teammate mode is only for when experts are part of a multi-agent team.

**Open question: How do personas become spawn prompts?**

Current agent definitions (e.g., `consult-paloma.md`) use YAML frontmatter to declare tools and a system prompt that reads the persona file. Agent Teams teammates are spawned via natural language prompts -- no YAML frontmatter mechanism exists.

**First experiment approach:** Just paste existing persona markdown as the spawn prompt. If it works, no new format needed. If it doesn't, adjust at point of use.

**Questions to resolve experimentally:**
- [ ] Do existing persona files work as-is for spawn prompts?
- [ ] How does CLAUDE.md context combine with spawn prompt?
- [ ] Do teammates need shorter/different prompts than subagents?

### 6.2 Scout's Team Coordination Role

**Current:** Scout routes to the right expert via subagent

**Clarification from review:** The user's main session IS the team lead -- Scout can't be "injected" as lead. What we actually want is the main session adopting Scout's coordination behavior when running a team.

**Approach:** Load Scout's coordination instructions (decomposition logic, expert routing) into the team lead context via CLAUDE.md or skill instructions. Not a separate "Scout as Lead" mechanism.

**Questions to resolve experimentally:**
- [ ] Can Scout's routing logic be expressed as team lead instructions?
- [ ] How does Scout decide: subagent vs team? (Use decision framework above)

### 6.3 spawn-review-team (First Experiment Target)

**Current:** `/run-review-project` runs sequentially

**With Agent Teams:** Parallel review with specialized teammates

```
/run-spawn-review-team

Spawns:
+-- Security Reviewer: OWASP, auth, input validation
+-- Performance Reviewer: queries, caching, scaling
+-- Test Coverage Reviewer: missing tests, edge cases
+-- Architecture Reviewer: patterns, coupling, coherence

Each reviews independently, then:
+-- Teammates share findings with each other
+-- Debate disagreements (security vs performance tradeoffs)
+-- Lead synthesizes final report
+-- Compound step: prompt for wisdom capture on significant findings
```

**Why this is the right first experiment:**
- Read-only work (no file conflict risk)
- Clearly parallelizable
- Clear deliverable (unified report)
- The "debate disagreements" step is where teams add value over subagents
- Every reviewer independently recommended this first

**Complexity threshold:** Only worth spawning a team for complex reviews (500+ lines, multi-file, multi-concern). For small PRs (<100 lines), use a single subagent with a combined review prompt.

**Questions to resolve experimentally:**
- [ ] Which review types benefit most from parallelization?
- [ ] How do reviewers with competing findings resolve via mailbox?
- [ ] Does the debate step actually produce insights isolated reviews miss?
- [ ] What's the actual token cost? (Measure and update Part 4)

---

## Part 7: Technical Risks

Identified by the architecture review. These must be understood before building.

### Risk 1: Persona-to-Spawn-Prompt Translation

Subagent definitions use YAML frontmatter (tools, description) + system prompt. Agent Teams spawn prompts are natural language only. Persona files are 150-230 lines -- inlining them into spawn prompts is unwieldy and wastes lead context. Tool restrictions can't be set per-teammate.

**Mitigation:** Experiment with condensed persona summaries as spawn prompts. Measure whether full persona or summary produces better teammate behavior.

### Risk 2: No Subagent Spawning from Teammates

Teammates can't spawn subagents. This breaks the current expert consultation chain (Scout -> Paloma -> potentially others). Each teammate is an island that communicates only via mailbox.

**Mitigation:** Design team compositions that don't require nested delegation. If a teammate needs another expert's input, the lead mediates via mailbox.

### Risk 3: State Reconciliation

PARC persists state to `.claude/work/parc/[task-slug].md`. Agent Teams has its own shared task list in `~/.claude/tasks/{team-name}/`. Two independent state systems with no reconciliation.

**Mitigation:** Decide which is source of truth. Recommendation: PARC tracker remains authoritative, lead updates it based on team task completion.

### Risk 4: Overwatch Integration Gap

Current Overwatch hooks track subagent invocations (`PostToolUse` matcher on `Task`). No equivalent for Agent Teams teammate spawning, messaging, or completion.

**Mitigation:** Identify what Overwatch hooks exist for Agent Teams lifecycle events. If none, this is a gap to track and raise with Claude Code team.

---

## Part 8: Deferred Ideas (YAGNI - Don't Build Yet)

These ideas from the original plan are interesting but speculative. They are captured here for future reference but should NOT be built until experiments prove their value.

### Operatives as Private Teammate Configs
Extend operative format with teammate YAML frontmatter. **Deferred because:** No proven need, and operative privacy in team context is an unresolved concern (teammates share a working directory and can read each other's files).

### Debug Team with Competing Hypotheses
Spawn 3+ teammates, each investigating a different theory. **Deferred because:** 8-10x token cost, unproven that hypotheses converge rather than diverge, most bugs are found by reading code carefully. Consider instead: a single subagent with explicit instructions to test 3 theories sequentially (lighter alternative).

### spawn-parc-team
Team with explicit PARC gates enforced by lead. **Deferred because:** PARC already works as a workflow. Making a dedicated team skill wraps one abstraction around another. If Agent Teams proves useful, PARC can coordinate with it without a dedicated skill.

### Teammates Voting on Wisdom Candidates
Post-team wisdom capture where teammates vote on what's worth documenting. **Deferred because:** The existing `/compound` command already handles wisdom capture. Adding voting is a feature on a feature.

---

## Part 9: Priority Ordering (Corrected)

Original plan had priorities inverted -- skills before the infrastructure they depend on. Corrected with YAGWYDI lens:

### Phase 0: Infrastructure (YAGWYDI - Build Now)

| Item | Purpose | Status |
|------|---------|--------|
| Decision framework | When teams vs subagents | Done (Part 2) |
| Cost model | Estimated token costs | Done (Part 4), needs real data |
| Guardrails design | Limits, confirmation, fallback | Done (Part 5), needs implementation |
| Technical risks | Known blockers and mitigations | Done (Part 7) |

### Phase 1: First Experiment (Next)

| Item | Purpose | Success Criteria |
|------|---------|-----------------|
| Manual parallel review | Test 2-3 teammates using raw persona markdown as spawn prompts on real code | Team produces at least 1 insight that isolated reviews would have missed, in 2 out of 3 uses |
| Measure actual token cost | Compare team vs sequential subagent cost | Update cost model with real numbers |
| Test persona-as-spawn-prompt | Can existing `.md` files work as-is? | Determine if new format is needed |

### Phase 2: First Skill (After Phase 1 Success)

| Item | Purpose | Gate |
|------|---------|------|
| `spawn-review-team` | Formalize parallel review as a plugin skill | Phase 1 experiments successful |
| Graceful degradation | Fall back to subagents when Agent Teams is disabled | Must ship with the skill |
| Scout coordination update | Scout suggests teams for L2+ complexity | Decision framework validated |

### Phase 3: Evaluate Further (After Phase 2 Learnings)

| Item | Purpose | Gate |
|------|---------|------|
| Debug team (simplified) | 3 hypotheses max, lead-mediated | Review team proven valuable |
| Additional team patterns | Based on experiment evidence | Clear user pain identified |
| Teammate template format | Only if personas don't work as-is | Experiment 1 results |

---

## Part 10: Rollout Plan

### Adoption Path (Progressive, Never Forced)

**Phase 0: Awareness** (No code changes)
- This plan document exists and is shared
- Users can manually experiment with Agent Teams using existing personas
- Decision framework available for reference

**Phase 1: One Skill, Opt-In**
- Ship `spawn-review-team` as a single new command
- Clearly labeled as experimental
- First-time use shows cost estimate and asks for confirmation
- Capture every learning in experiment log

**Phase 2: Scout Suggests Teams**
- Update Scout to recognize when a problem would benefit from a team
- Scout proposes team with cost estimate, user always chooses
- Never auto-escalate to teams without user approval

**Phase 3: Full Integration** (If Phase 2 validates)
- Teams become a natural part of PARC Allocate for qualifying tasks
- Additional team patterns based on evidence from Phase 1-2
- Wisdom capture integrated (using existing `/compound`, no new mechanism)

**Success gates between phases:**
- Phase 0 -> 1: At least 3 manual experiments completed with documented learnings
- Phase 1 -> 2: Review team produces unique insights in 2/3 uses at acceptable cost
- Phase 2 -> 3: Users actively choose teams over subagents for qualifying tasks

---

## Part 11: Workshop Log

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
- Winning hypothesis from debug team -> stack-wisdom pattern

**Decisions:**
- Start with document, not code
- Workshop the concepts before implementing
- Use agent teams to improve this plan (meta!)
- Pick this up in a fresh session with fresh context

### Session 2: 2026-02-06 - Simulated Review Team

**Participants:** Michael, Claude (coordinating 4 parallel subagent reviewers)

**What we did:** Ran a simulated review team on the Session 1 plan itself. Four parallel subagent reviewers, each with a different lens:

1. **Architecture Strategist** - Feasibility, technical risks, structural soundness
2. **Code Simplicity Reviewer** - YAGNI, overengineering, what to cut
3. **Product/UX (Dino)** - User experience, adoption, pain points
4. **Performance Oracle** - Token costs, latency tradeoffs, guardrails

**Key findings (all four agreed on):**
- `spawn-review-team` is the right first experiment
- The plan was over-designed for something untested (~420 lines of architecture)
- Priority ordering was inverted (skills before infrastructure)
- Token cost analysis was dangerously thin
- No guardrails existed for preventing runaway token usage

**Architecture reviewer highlights:**
- PARC Allocate doesn't need teams for most cases (workers report back independently)
- Teammates can't spawn subagents -- breaks expert consultation chains
- Scout-as-lead is a role conflict (user's session IS the lead)
- Missing: fallback strategy, Overwatch integration, state reconciliation, error handling

**Simplicity reviewer highlights:**
- Proposed cutting ~55% of the document
- "Plans have gravity -- once written, they pull development toward them"
- Every proposed skill is premature -- zero should be built before experiments
- "The most dangerous sentence is 'This is pure compound engineering' -- that framing justifies complexity without evidence"

**Product reviewer (Dino) highlights:**
- Missing the core question: "What user pain is so acute that teams become the obvious relief?"
- Proposed heuristic: "Subagent for answers, team for conversations"
- No adoption path designed -- needs progressive phases with success gates
- Token cost is a potential adoption dealbreaker if not surfaced in UX
- Debug team: cap at 3 hypotheses max, consider solo investigator as lighter alternative

**Performance reviewer highlights:**
- Concrete cost estimates: teams are 4-6x more expensive than subagents
- A 5-agent debug team could cost $2-$5 (Sonnet) or $10-$25 (Opus) per session
- Parallelism only wins when task count > 2 AND tasks are independent
- Proposed hard limits: max 4 teammates, max 5 turns, max 12 messages, 1M token cap

**Michael's YAGNI/YAGWYDI filter (critical refinement):**
The simplicity reviewer was right about features but wrong to cut infrastructure. Applied the plugin's core tension:

| Apply YAGNI to... | Apply YAGWYDI to... |
|-------------------|---------------------|
| spawn-debug-team (5 agents) | Decision framework (subagent vs team) |
| spawn-parc-team skill | Teammate template format exploration |
| Operative teammate configs | Guardrails and budget system |
| Wisdom voting by teammates | Fallback/graceful degradation strategy |
| All 4 proposed skills (premature) | PARC mapping documentation |
| | Cost model with real estimates |
| | Experiment log structure |

**Meta-observation:** This exercise itself is a data point. Four parallel subagent reviewers couldn't debate each other -- Claude synthesized manually. A true Agent Teams review would have let the architecture reviewer challenge the simplicity reviewer's "cut the debug team" recommendation with structural arguments, and the performance reviewer could have pushed back on Dino's "3 hypotheses max" with latency data. That tension -- wanting the reviewers to talk to each other -- is exactly the signal that a review team is the right first experiment.

**Decisions:**
- Restructured the plan with YAGNI/YAGWYDI filter applied
- Added: Decision Framework, Cost Model, Guardrails, Technical Risks, Rollout Plan
- Deferred: Debug teams, operative configs, PARC team skill, wisdom voting
- Corrected priority ordering: infrastructure first, then experiments, then skills
- First experiment: manual parallel review using raw persona markdown

**Next Steps:**
- [ ] Enable Agent Teams: add `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` to settings
- [ ] Run Experiment 1: manual review team on real code (compare to this session's simulated version)
- [ ] Measure actual token costs and update the cost model
- [ ] Test persona markdown as spawn prompts (do they work as-is?)

---

## Part 12: Experiment Log

### Experiment 0: Simulated Review Team (Subagents)

**Date:** 2026-02-06
**Goal:** Test the review team concept using current subagent infrastructure
**Setup:** 4 parallel Task tool subagents (architecture, simplicity, product, performance) reviewing this plan document
**Results:** All four completed successfully. Produced detailed, independent analyses with clear findings. Required manual synthesis by Claude (lead). Reviewers could not challenge each other's findings.
**Token Usage:** ~185K total across 4 subagents + coordination (estimated)
**Learnings:**
- Parallel subagent reviews work well for independent analysis
- The missing piece is inter-reviewer debate -- manual synthesis loses the tension
- The "competing findings" scenario (simplicity says cut infrastructure, architecture says keep it) is exactly where teams would add value
- YAGNI/YAGWYDI filter was applied by the human (Michael), not by any reviewer -- a team lead could potentially do this
**Wisdom Candidate:** "Simulated review teams via parallel subagents are 80% of the value at 100% of the availability. Reserve real Agent Teams for when debate/cross-reference is critical." (Validate with Experiment 1)

### Experiment 1: [Real Agent Teams Review]

**Date:** [TBD]
**Goal:** Repeat the review team exercise using actual Agent Teams, compare quality and cost to Experiment 0
**Setup:** [Enable Agent Teams, spawn 4 reviewer teammates with persona markdown]
**Results:** [TBD]
**Token Usage:** [TBD - compare to Experiment 0's ~185K]
**Learnings:** [TBD]
**Wisdom Candidate:** [TBD]

---

## Part 13: Formalization Checklist

When ready to codify into plugin:

- [ ] Teammate template format defined (or confirmed unnecessary)
- [ ] At least one skill tested manually (spawn-review-team)
- [ ] Token cost implications measured with real data
- [ ] Failure modes documented and recovery tested
- [ ] PARC integration validated
- [ ] Graceful degradation (fallback to subagents) implemented
- [ ] User cost confirmation UX designed
- [ ] Token budget limits defined and enforced
- [ ] Auto-downgrade to subagents tested for simple cases
- [ ] Overwatch integration gap assessed

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
- [PARC YAGNI/YAGWYDI Balance](../../../skills/parc/SKILL.md) (lines 39-69)
