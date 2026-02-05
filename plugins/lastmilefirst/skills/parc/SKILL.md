---
name: parc
description: The PARC workflow - Plan, Allocate, Review, Compound - adaptive guidance for AI-assisted development
---

# PARC Workflow

**P**lan → **A**llocate → **R**eview → **C**ompound

A disciplined workflow for AI-assisted development that scales with task complexity.

## Why PARC?

Without structure, AI-assisted development falls into traps:

| Trap | Symptom | PARC Solution |
|------|---------|---------------|
| **Tunnel vision** | AI fixates on one approach | **Plan** with experts first |
| **Wasted cycles** | Work gets thrown away | **Allocate** to right agents |
| **Quality gaps** | Bugs ship, tech debt grows | **Review** thoroughly |
| **Repeated mistakes** | Same problems recur | **Compound** learnings |

PARC isn't bureaucracy - it's leverage. Each step makes the next easier.

---

## Plan

*Think before doing*

### What Planning Means

- Understand the problem fully
- Consider approaches (not just the first one)
- Check existing wisdom (`/run-search-wisdom`)
- Consult experts if domain is unfamiliar
- Define what "done" looks like

### The YAGNI vs YAGWYDI Tension

Planning requires balancing two voices:

**YAGNI (You Aren't Gonna Need It)**
> Don't overbuild. Solve the problem you have, not problems you imagine.

- Is this the simplest thing that could work?
- Are we solving a real problem or an imagined one?
- Can we defer this decision until we know more?

**YAGWYDI (You're Gonna Wish You Did It)**
> Some investments pay compound returns. Don't skimp on infrastructure.

- Will we regret not having this later?
- Is this a one-time cost with ongoing benefits?
- Will this make future work significantly easier?

**The Balance:**

| Apply YAGNI to... | Apply YAGWYDI to... |
|-------------------|---------------------|
| Features and functionality | Infrastructure and scaffolding |
| Speculative requirements | Testing and quality gates |
| Premature optimization | Patterns and wisdom capture |
| Over-engineering | Operatives and shared knowledge |

**Planning Prompts:**
1. "Is this the simplest approach that solves the actual problem?" (YAGNI)
2. "Will we regret not doing this properly six months from now?" (YAGWYDI)
3. "Is this feature complexity or infrastructure investment?" (Balance)

### Complexity Assessment

Before diving in, assess complexity:

| Signal | Complexity | Ceremony Level |
|--------|------------|----------------|
| Single file, clear fix | Trivial | Minimal |
| Few files, understood domain | Low | Light |
| Multiple files, some unknowns | Moderate | Standard |
| Cross-cutting, architectural | High | Full PARC |
| New system, unfamiliar domain | High | Full PARC + experts |

### Planning Tools

| Tool | When to Use |
|------|-------------|
| **Claude plan mode** | Multi-step implementations |
| **Scout** (`/run-consult-expert scout`) | Decompose complex work, route to specialists |
| **Maya** (`/run-consult-expert maya`) | Process questions, methodology decisions |
| **Archer** (`/run-consult-expert archer`) | Architecture decisions, system design |
| **Domain experts** | Unfamiliar technical territory |
| **`/run-search-wisdom`** | Check if we've solved this before |

### Plan Output

For complex tasks, document the plan:

```markdown
## Plan: [Task Name]

### Problem
What we're solving and why it matters.

### Approach
How we'll solve it (and why this approach over alternatives).

### YAGNI Check
- Simplest solution? Yes/No - [reasoning]
- Solving real problem? Yes/No - [evidence]

### YAGWYDI Check
- Infrastructure investment? Yes/No - [what and why]
- Future leverage? Yes/No - [how it compounds]

### Success Criteria
- [ ] Criterion 1
- [ ] Criterion 2

### Agents Needed
- [Agent] for [responsibility]
```

---

## Allocate

*Delegate to the right agents*

### What Allocation Means

- Break work into manageable chunks
- Assign to agents with relevant expertise
- Decide parallel vs sequential execution
- Orchestrate and monitor progress

### Scout as Orchestrator

For complex work, **Scout** should coordinate:

```
/run-consult-expert scout "Coordinate implementation of OAuth authentication"
```

Scout will:
- Decompose the work into tasks
- Route tasks to appropriate specialists
- Identify parallelizable work
- Track progress and dependencies
- Flag blockers and suggest pivots

### Agent Mapping

| Domain | Primary Agent | Backup |
|--------|---------------|--------|
| **Python/FastAPI** | Paloma | — |
| **TypeScript/React** | Paloma | — |
| **AWS Infrastructure** | Adam | — |
| **Architecture/Design** | Archer | Charles |
| **AI/ML Integration** | Andor | — |
| **Security** | security-sentinel | Paloma |
| **DevOps/CI/CD** | Otto | Adam |
| **QA Strategy** | Quinn | — |
| **Product/UX** | Dino | — |
| **Research/Evaluation** | Reese | — |
| **Process/Methodology** | Maya | Scout |
| **Claude Code/Skills** | Shannon | — |
| **Cross-domain/Unclear** | Scout → routes | Charles |

### Your Operatives

Check org operatives for specialized knowledge:

```
/run-consult-operative
```

Operatives encode your domain expertise - prefer them when the domain matches.

### Parallel vs Sequential

**Parallelize when:**
- Tasks are independent
- No shared state or dependencies
- Speed matters more than token cost

**Sequence when:**
- Task B depends on Task A's output
- Shared files that could conflict
- Need to learn from first task before second

**Example parallel allocation:**
```
# These can run simultaneously
Task: consult-paloma for backend OAuth implementation
Task: consult-adam for infrastructure secrets management
Task: security-sentinel for auth security review
```

**Example sequential allocation:**
```
# Must be sequential - each builds on previous
1. Archer: Design the auth architecture
2. Paloma: Implement based on Archer's design
3. Quinn: Design test strategy for implementation
```

---

## Review

*Verify the work is correct*

### What Review Means

Review is the quality gate. It encompasses:

| Activity | What It Checks |
|----------|----------------|
| **Testing** | Does the code work correctly? |
| **Evaluation** | Does it meet requirements? |
| **Code Review** | Is it maintainable and secure? |
| **E2E Validation** | Does it work in the real system? |

### Quinn for QA Strategy

For significant features, consult Quinn on test strategy:

```
/run-consult-expert quinn "What's the test strategy for this OAuth implementation?"
```

Quinn will help with:
- What to test (and what not to)
- Unit vs integration vs E2E balance
- Edge cases to cover
- Acceptance criteria validation

### E2E Testing

**Prefer E2E tests when:**
- User-facing features
- Integration points between systems
- Critical paths (auth, payments, data integrity)
- "Works on my machine" risk is high

**E2E checklist:**
- [ ] Happy path works end-to-end
- [ ] Error states handled gracefully
- [ ] Performance acceptable under load
- [ ] Works in staging environment

### Code Review Agents

Use specialized reviewers based on the code:

| Code Type | Reviewer Agent | Focus |
|-----------|----------------|-------|
| **TypeScript** | kieran-typescript-reviewer | Quality, patterns, types |
| **Python** | kieran-python-reviewer | Quality, idioms, typing |
| **Rails** | kieran-rails-reviewer, dhh-rails-reviewer | Conventions, Rails way |
| **Security-sensitive** | security-sentinel | Vulnerabilities, OWASP |
| **Performance-critical** | performance-oracle | Bottlenecks, scaling |
| **Architecture changes** | architecture-strategist | Design, boundaries |
| **Data/migrations** | data-integrity-guardian | Safety, integrity |

**Invoke reviewers after implementation:**
```
Task: kieran-typescript-reviewer to review the OAuth frontend code
Task: security-sentinel to audit the authentication flow
```

### Review Checklist

```markdown
## Review: [Feature Name]

### Testing
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] E2E tests pass (if applicable)
- [ ] Edge cases covered

### Code Quality
- [ ] Reviewer agent approved
- [ ] No security issues flagged
- [ ] Performance acceptable

### Validation
- [ ] Meets success criteria from Plan
- [ ] Works in staging/preview
- [ ] Stakeholder approval (if needed)

### Ready to ship?
- [ ] All checks pass → Proceed to Compound
- [ ] Issues found → Back to Allocate
- [ ] Wrong approach → Back to Plan
```

---

## Compound

*Capture learnings for future leverage*

### What Compounding Means

Every hard-won insight should make future work easier. Compounding is how you build leverage over time.

**Ask after every significant task:**
1. Did we learn something worth remembering?
2. Did we build expertise worth encoding?
3. Should we update existing patterns?

### Compound Triggers

| Trigger | Compound Action |
|---------|-----------------|
| Debugging took 30+ minutes | Add to stack-wisdom |
| Discovered a gotcha | Add to stack-wisdom |
| Built domain expertise | Consider operative |
| Found better pattern | Update existing wisdom |
| Solved novel problem | Document approach |
| Made architectural decision | Record in ADR or wisdom |

### Stack-Wisdom

Capture patterns and insights:

```
/run-add-wisdom "OAuth implementation gotchas"
```

Good wisdom includes:
- The problem and how you recognize it
- The solution and why it works
- Prevention for next time
- Trigger keywords for search

### Operatives

When you've built deep expertise in a domain:

```
/run-create-operative
```

Consider an operative when:
- You've solved multiple related problems
- Domain knowledge is substantial
- Future projects will need this expertise
- The knowledge is specific to your org

### CLAUDE.md Updates

For project or org-level learnings, consider updating CLAUDE.md:

```
/run-consult-expert shannon "Should this OAuth pattern go in our CLAUDE.md?"
```

Shannon can help decide:
- Project-specific gotcha → Project CLAUDE.md
- Org-wide pattern → Org CLAUDE.md
- Personal preference → Workspace CLAUDE.md

### Compound Checklist

```markdown
## Compound: [Feature Name]

### Wisdom Capture
- [ ] Any debugging insights? → `/run-add-wisdom`
- [ ] Any gotchas discovered? → `/run-add-wisdom`
- [ ] Any patterns worth reusing? → `/run-add-wisdom`

### Operative Consideration
- [ ] Built significant domain expertise?
- [ ] Will future projects need this?
- [ ] Worth encoding as an operative? → `/run-create-operative`

### Documentation
- [ ] CLAUDE.md updates needed? → Shannon
- [ ] README updates needed?
- [ ] ADR for architectural decisions?

### Nothing to compound?
That's fine for trivial tasks. But if a task took significant effort and there's nothing to compound, ask: "Did we miss an insight?"
```

---

## Adaptive Guidance

PARC scales with complexity. Not every task needs full ceremony.

### Guidance Levels

**TRIVIAL** (typo fix, simple change)
```
Plan:     Skip (just do it)
Allocate: Direct execution
Review:   Quick verify
Compound: Skip
```

**LOW** (clear feature, understood domain)
```
Plan:     Brief consideration
Allocate: Maybe suggest an agent
Review:   Run tests
Compound: Offer if non-obvious solution
```

**MODERATE** (multi-file, some unknowns)
```
Plan:     Think through approach, YAGNI/YAGWYDI check
Allocate: Use appropriate agents
Review:   Tests + reviewer agent
Compound: Prompt for wisdom if applicable
```

**HIGH** (architectural, unfamiliar, cross-cutting)
```
Plan:     Full planning with experts, document plan
Allocate: Scout orchestrates, multiple agents
Review:   Comprehensive: tests, reviewers, E2E, Quinn
Compound: Always prompt, likely multiple captures
```

---

## Using PARC

### Explicit Invocation

```bash
# Start PARC workflow for a task
/run-parc "Implement user authentication with OAuth"

# Jump to a specific step
/run-parc --step plan
/run-parc --step review
/run-parc --step compound "Always check terraform workspace"
```

### Implicit Application

Claude should apply PARC principles automatically, scaling to complexity.

**Trivial task:**
> User: "Fix the typo in the README"
> Claude: *Just fixes it, no ceremony*

**Moderate task:**
> User: "Add email validation to the signup form"
> Claude: "Let me check if we have existing validation patterns... [searches wisdom]. I'll implement this with proper error handling and add tests."

**Complex task:**
> User: "Implement OAuth authentication"
> Claude: "This is a significant feature. Let me plan the approach first - I'll check our existing patterns, consult security-sentinel on best practices, and outline the implementation before we start coding."

---

## PARC State Tracking

For complex tasks, track PARC progress:

```markdown
## PARC: Implement OAuth Authentication

### Plan ✓
- Consulted: Archer (design), security-sentinel (best practices)
- Approach: OAuth 2.0 with PKCE, Google and GitHub providers
- YAGNI: Skipping Apple Sign-In for now (no demand)
- YAGWYDI: Building reusable auth patterns for future projects
- Success criteria: Users can sign up/in via OAuth, secure token handling

### Allocate ✓
- Scout: Coordinating overall implementation
- Paloma: Backend auth routes and token handling
- Adam: Secrets management in AWS
- security-sentinel: Security review

### Review ◯
- [ ] Unit tests (Paloma)
- [ ] Integration tests (Paloma)
- [ ] E2E auth flow (Quinn strategy)
- [ ] Security audit (security-sentinel)
- [ ] Staging validation

### Compound ◯
- [ ] OAuth gotchas → stack-wisdom
- [ ] Auth patterns → stack-wisdom
- [ ] Consider auth-specialist operative?
```

---

## Related Commands

| Step | Commands |
|------|----------|
| **Plan** | `/run-consult-expert scout/maya/archer`, `/run-search-wisdom` |
| **Allocate** | `/run-consult-expert [specialist]`, `/run-consult-operative` |
| **Review** | `/review`, test runners, reviewer agents |
| **Compound** | `/run-add-wisdom`, `/run-create-operative` |
