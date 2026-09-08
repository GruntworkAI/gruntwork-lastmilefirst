---
name: parc
description: The PARC workflow (Plan, Allocate, Review, Compound). Adaptive guidance for AI-assisted work at every scale, from one exchange to a multi-agent build. Entry points, the five elements, the Compound close with rhyming lessons and the human rung.
---

# PARC Workflow

**P**lan → **A**llocate → **R**eview → **C**ompound

A disciplined workflow for AI-assisted work that scales with task complexity. It applies at every scale: one exchange that produces an answer, and a multi-agent build that produces a system, run the same four steps with different amounts of ceremony.

## Why PARC?

Without structure, AI-assisted development falls into traps:

| Trap | Symptom | PARC Solution |
|------|---------|---------------|
| **Tunnel vision** | AI fixates on one approach | **Plan** with experts first |
| **Wasted cycles** | Work gets thrown away | **Allocate** to right agents |
| **Quality gaps** | Bugs ship, tech debt grows | **Review** thoroughly |
| **Repeated mistakes** | Same problems recur | **Compound** learnings |

PARC isn't bureaucracy. It's leverage. Each step makes the next easier.

---

## Entry points and posture

These rules govern when to speak and where to start. They apply to every substantive request,
not only builds.

**Entry points.** A request enters at Plan. A draft, plan, or analysis handed over for review
enters at Review directly, with no Plan or Allocate. Reviewing a handed artifact means finding
what is weakest and naming it plainly, without softening criticism into hedges. A review that
returns "strong, with a few small notes" has usually not been done.

**Discovery is the first move of Plan.** When the request is exploratory, Plan means
interviewing and widening the frame before narrowing to a solution. Arriving fast is the
failure, not the goal. In every case the proposal precedes the artifact. Three sentences can be
enough. Skipping it cannot.

**Show the work.** State the assumptions being relied on and flag the shaky ones. Confident
output that hides its assumptions is worse than uncertain output that names them, because it
cannot be checked.

**The five elements are Plan's completeness test.** A well-formed request names most of five:
role, context, task, constraints, success. Use them in two directions that pull opposite ways.
Receiving a request, do not audit it. Answer on the best reading, then name the one missing
element that changed the answer ("I assumed a two-year bet with a small team; say if it is a
weekend project and the answer changes"). Success is the element most often missing and the one
to ask for when the answer turns on it. Authoring a prompt for another model (a skill, a
subagent brief, a system prompt), use all five as a checklist on your own output. An empty
success slot in a prompt you wrote is a defect you control.

**Every cycle closes on Compound.** A cycle is a unit of work that produced an artifact or a
decision: code, a document, an analysis, a plan. Once per cycle, not once per message. When
nothing was applied, nothing rhymes, and nothing is new, the close is one line. The ceremony
scales with what was found, not with the phase.

**Escape hatches.** "Quick question," "no PARC," or the equivalent drops the ceremony and
answers directly. The trivial tier in Adaptive Guidance does the same implicitly. There is no
separate hatch for the Compound close; those two cover the cases where it is wrong.

---

## Plan

*Think before doing*

### What Planning Means

- Start in discovery when the request is exploratory (see Entry points and posture)
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
| **Python/FastAPI** | Paloma | none |
| **TypeScript/React** | Paloma | none |
| **AWS Infrastructure** | Adam | none |
| **Architecture/Design** | Archer | Charles |
| **AI/ML Integration** | Andor | none |
| **Security** | security-sentinel | Paloma |
| **DevOps/CI/CD** | Otto | Adam |
| **QA Strategy** | Quinn | none |
| **Product/UX** | Dino | none |
| **Research/Evaluation** | Reese | none |
| **Process/Methodology** | Maya | Scout |
| **Claude Code/Skills** | Shannon | none |
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

*Capture learnings for future leverage, and keep the human learning too*

### What Compounding Means

Every hard-won insight should make future work easier. Compounding is how leverage builds over
time. Two things compound: the system (wisdom, skills, operatives, context) and the person. A
codebase and a toolset keep getting more capable on their own. The person's ability to judge
them does not, unless something forces the learning. Compound does both, every cycle.

### The Compound close

Three questions, in this order, before anything is written. Spaced repetition is recall, not
re-reading, so the first question is a retrieval.

1. **Did we apply an old lesson?** Search wisdom and knowledge with the cycle as the query
   (project, files touched, prompts, skills used) and surface the matches. The user confirms
   which were used. Each confirmation writes `last_applied:` with today's date on the entry.
   That date is the ledger: applied last week needs nothing, never applied in six months is
   forgotten or dead.
2. **Does anything rhyme?** The same search, scored against what was learned rather than what
   was done. A rhyme is the promotion signal (see Rhyming lessons).
3. **Is there anything new to compound?** Route it through the fork table. "Nothing" is an
   acceptable answer and has to be said out loud.

The order matters. Asking what is new first produces a lesson that already exists. Asking what
was applied first primes the search, and the rhyme question catches the duplicate before it is
written.

When all three come back empty, the close is one line:

> Compound: nothing applied, no rhymes, nothing new.

### Forks, not rungs

The routing question is "what kind of thing did we learn?" Magnitude decides only whether to
capture at all. The destination depends on the shape of the thing, never on escalation.

| Learned | Home | Tool |
|---|---|---|
| A fact about how something works or is configured | stack-knowledge | `/run-add-knowledge` |
| A lesson, pattern, or gotcha that generalizes | stack-wisdom | `/run-add-wisdom` |
| A gotcha bound to one repo | that project's CLAUDE.md gotchas section | edit it |
| A repeatable procedure | a skill | new or extended SKILL.md |
| Something Claude must know every session | context (CLAUDE.md at the right level) | Shannon decides the level |
| Judgment in a domain, across many problems | an operative | `/run-create-operative` |
| A line of work with its own roadmap | a project | `/run-organize-project` |
| A repo learning in the ce-compound shape | `docs/solutions/` | `ce-compound`, where installed |

Two forks are judgment calls rather than type matches, so each gets a test.

**Skill or context.** Context if Claude needs to *know* it every session: a rule, a constraint,
a fact about the environment. Skill if Claude needs to *do* it on demand: a procedure with
steps, inputs, and an output. A thing that is both gets a one-line pointer in context and the
procedure in a skill.

**Operative or project.** An operative encodes judgment: how to think about a domain, applied
across many problems. A project encodes work: a roadmap, a repo, deliverables. The work may
later produce the operative. The operative never substitutes for the work.

### Rhyming lessons

A lesson that recurs is a procedure or a rule that never got written down. Before any wisdom or
knowledge write, run the rhyme check (`/run-search-wisdom`, `/run-search-knowledge`) and act on
the outcome:

| Outcome | Action |
|---|---|
| No rhyme | Write the entry. First occurrence. |
| One rhyme | Do not write a second entry. Promote: route through the skill-or-context fork. Add `rhymes_with:` on the original pointing at this occurrence, and `promoted_to:` once the skill or rule exists. |
| Rhyme with an entry already promoted | The promotion did not hold. Fix the skill or the rule. Do not add a third copy. |

This is the debugging circuit breaker (same error seen twice escalates) applied to learning.

### The human rung

The system compounding while the person does not is the failure this rung exists to prevent.
The rung is a contract with two implementations, and it runs for MODERATE and HIGH cycles.

**The contract**, reduced from the four practices in Every's "To Read, Or Not to Read the Code":

1. Walk the mechanics of what was built: where it starts, what happens next, where the data goes.
2. Recover why one safeguard or design choice exists.
3. Predict before seeing: a short quiz taken before the explanation, so the gap between the
   guess and the mechanism is visible.

**Preferred: `ce-explain`** (compound-engineering plugin), in diff mode with "Quiz me." It does
all three with a prediction protocol and leaves a durable artifact. Its recap mode covers the
weekly review ("what happened this week?"). Use it for HIGH cycles and weekly recaps. It is
present when it appears in the session's available skills; do not probe the filesystem for it.

**Fallback: three questions in chat.** No artifact, no run directory. Ask the prediction
question first, walk the mechanics, then name one design rationale. Use it when ce-explain is
not installed, and by default for MODERATE cycles, where ce-explain's ceremony is more than the
moment warrants.

Two prompts from the same article belong in the close as questions, not mechanisms: what is
the measurable learning goal for this cycle, and is this a task the person has been routing
around for years and should do by hand once.

### Stack-Wisdom

```
/run-add-wisdom "OAuth implementation gotchas"
```

Good wisdom includes the problem and how to recognize it, the solution and why it works,
prevention for next time, and trigger keywords for search. Entries carry `last_applied:`,
`rhymes_with:`, and `promoted_to:` when those apply.

### Operatives

```
/run-create-operative
```

An operative is the judgment fork: several related problems solved, substantial domain
knowledge, future projects that will need it, and knowledge specific to the org.

### CLAUDE.md Updates

```
/run-consult-expert shannon "Should this OAuth pattern go in our CLAUDE.md?"
```

Shannon decides the level: a project-specific gotcha goes in the project CLAUDE.md, an org-wide
pattern in the org CLAUDE.md, a personal preference in the workspace CLAUDE.md.

### Compound Checklist

```markdown
## Compound: [Cycle Name]

### The close
- [ ] Applied: [entries confirmed, `last_applied` written] or none
- [ ] Rhymes: [entry and action] or none
- [ ] New: [learned thing and its fork] or nothing

### Human rung (MODERATE and HIGH)
- [ ] Prediction taken before the explanation
- [ ] Mechanics walked, one rationale recovered
- [ ] Learning goal for the cycle: [stated]

### Nothing to compound?
Say so in one line. If a cycle took significant effort and all three questions came back
empty, ask once: "Did we miss an insight?"
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
Compound: The close, one line unless something was found
```

**MODERATE** (multi-file, some unknowns)
```
Plan:     Think through approach, YAGNI/YAGWYDI check
Allocate: Use appropriate agents
Review:   Tests + reviewer agent
Compound: The close, forks, and the human rung in chat
```

**HIGH** (architectural, unfamiliar, cross-cutting)
```
Plan:     Full planning with experts, document plan
Allocate: Scout orchestrates, multiple agents
Review:   Comprehensive: tests, reviewers, E2E, Quinn
Compound: The close, forks, and ce-explain with Quiz me where installed
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
- [ ] Applied: check wisdom for prior OAuth entries, mark `last_applied`
- [ ] Rhymes: PKCE gotcha rhymes with the 2026-03 token-refresh entry? promote if so
- [ ] New: OAuth provider quirks → wisdom; auth setup steps → skill?
- [ ] Human rung: ce-explain on the auth diff, Quiz me
```

---

## Related Commands

| Step | Commands |
|------|----------|
| **Plan** | `/run-consult-expert scout/maya/archer`, `/run-search-wisdom` |
| **Allocate** | `/run-consult-expert [specialist]`, `/run-consult-operative` |
| **Review** | `/review`, test runners, reviewer agents |
| **Compound** | `/run-search-wisdom` (the close), `/run-add-wisdom`, `/run-add-knowledge`, `/run-create-operative`, `ce-explain` where installed |
