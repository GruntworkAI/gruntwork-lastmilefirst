---
name: strict-parc
description: Enforce strict PARC discipline - explicit gates between Plan, Allocate, Review, and Compound
---

# Strict PARC

Enforces the full PARC workflow with explicit gates. No skipping steps, no implicit progression.

## When to Use Strict PARC

Use strict mode when:
- **Critical features** - Payments, auth, data integrity
- **Unfamiliar domain** - New technology, client's codebase
- **High-stakes changes** - Production systems, migrations
- **Team onboarding** - Teaching the PARC discipline
- **Regulated work** - Compliance, audit trails needed
- **You've been burned** - Previous shortcuts caused problems

## How It Works

Strict PARC creates a tracking file and enforces gates:

```
/run-strict-parc "Implement payment processing"
```

1. **Creates tracker** at `.claude/work/parc/[task-slug].md`
2. **Blocks progression** until each phase is explicitly completed
3. **Requires sign-off** before moving to next phase
4. **Prompts for compound** before allowing completion

## The Gates

### Gate 1: Plan → Allocate

**Cannot allocate until:**
- [ ] Problem statement documented
- [ ] Approach decided (with alternatives considered)
- [ ] YAGNI check completed
- [ ] YAGWYDI check completed
- [ ] Success criteria defined
- [ ] Relevant wisdom searched
- [ ] Experts consulted (if needed)

**Sign-off prompt:**
> "Plan is documented. Ready to move to Allocate? [Y/N]"

### Gate 2: Allocate → Review

**Cannot review until:**
- [ ] Work broken into tasks
- [ ] Agents/operatives assigned
- [ ] All allocated work completed
- [ ] No blockers outstanding

**Sign-off prompt:**
> "All allocated work is complete. Ready for Review? [Y/N]"

### Gate 3: Review → Compound

**Cannot compound until:**
- [ ] Tests pass (unit, integration, E2E as applicable)
- [ ] Code review complete (reviewer agents or human)
- [ ] Security review complete (if applicable)
- [ ] Validation against success criteria
- [ ] Staging/preview tested (if applicable)

**Sign-off prompt:**
> "Review complete. All checks pass. Ready to Compound? [Y/N]"

### Gate 4: Compound → Done

**Cannot mark done until:**
- [ ] Wisdom capture considered (prompted)
- [ ] Operative creation considered (prompted)
- [ ] CLAUDE.md updates considered (prompted)
- [ ] Explicit "nothing to compound" if skipping

**Sign-off prompt:**
> "Have you captured all learnings? [Y/N]"

## Tracker File Format

Created at `.claude/work/parc/[task-slug].md`:

```markdown
# PARC: [Task Name]

**Started:** [timestamp]
**Status:** Plan | Allocate | Review | Compound | Done

---

## Plan

**Status:** ◯ Pending | ⏳ In Progress | ✓ Complete

### Problem Statement
[What we're solving and why]

### Approach
[How we'll solve it]

**Alternatives considered:**
- [Alternative 1] - rejected because [reason]
- [Alternative 2] - rejected because [reason]

### YAGNI Check
- Is this the simplest solution? [Yes/No] - [reasoning]
- Are we solving a real problem? [Yes/No] - [evidence]

### YAGWYDI Check
- Is this infrastructure worth investing in? [Yes/No] - [reasoning]
- Will this compound future value? [Yes/No] - [how]

### Success Criteria
- [ ] Criterion 1
- [ ] Criterion 2
- [ ] Criterion 3

### Wisdom Searched
- [x] Searched: "[query]" - [results or "no matches"]

### Experts Consulted
- [Expert]: [summary of input]

**Plan Sign-off:** ◯ Pending

---

## Allocate

**Status:** ◯ Pending | ⏳ In Progress | ✓ Complete

### Task Breakdown
| Task | Agent/Operative | Status |
|------|-----------------|--------|
| [Task 1] | [Agent] | ◯ |
| [Task 2] | [Agent] | ◯ |

### Execution Log
- [timestamp] Started [task] with [agent]
- [timestamp] Completed [task]

**Allocate Sign-off:** ◯ Pending

---

## Review

**Status:** ◯ Pending | ⏳ In Progress | ✓ Complete

### Testing
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] E2E tests pass
- [ ] Edge cases covered

### Code Review
- [ ] [Reviewer agent]: [status]
- [ ] Security review: [status]

### Validation
- [ ] Meets success criteria
- [ ] Works in staging
- [ ] Stakeholder approval

**Review Sign-off:** ◯ Pending

---

## Compound

**Status:** ◯ Pending | ⏳ In Progress | ✓ Complete

### Wisdom Capture
- [ ] Debugging insights? [Added: filename / None]
- [ ] Gotchas discovered? [Added: filename / None]
- [ ] Patterns worth reusing? [Added: filename / None]

### Operative Consideration
- [ ] Domain expertise built? [Yes/No]
- [ ] Operative created? [Name / Not needed]

### Documentation
- [ ] CLAUDE.md updates? [Yes/No - what]
- [ ] README updates? [Yes/No - what]

**Compound Sign-off:** ◯ Pending

---

## Completion

**Completed:** [timestamp]
**Total Duration:** [time]
**Wisdom Added:** [list or "none"]
**Operatives Created:** [list or "none"]
```

## Strict Mode Behaviors

### Blocking

When in strict mode, Claude will refuse to proceed without sign-off:

> **User:** "Just implement the payment handler"
>
> **Claude (strict mode):** "We're in strict PARC mode. The Plan phase isn't complete yet - we still need to:
> - [ ] Define success criteria
> - [ ] Complete YAGWYDI check
>
> Would you like to complete the Plan, or override strict mode?"

### Override

Users can override with explicit acknowledgment:

```
/run-strict-parc --override "Skip to implementation, I'll plan as I go"
```

This logs the override in the tracker for accountability.

### Resuming

Strict PARC state persists across sessions:

```
/run-strict-parc --status              # Show current PARC tasks
/run-strict-parc --resume payment-processing  # Resume a task
```

## Usage

```bash
# Start strict PARC for a task
/run-strict-parc "Implement payment processing"

# Check status of active PARC tasks
/run-strict-parc --status

# Resume an existing PARC task
/run-strict-parc --resume [task-slug]

# Override a gate (logged)
/run-strict-parc --override "Reason for skipping"

# Complete and archive
/run-strict-parc --complete
```

## Integration

Strict PARC uses all the same tools as regular PARC:

| Phase | Tools |
|-------|-------|
| Plan | `/run-search-wisdom`, `/run-consult-expert`, plan mode |
| Allocate | Task agents, `/run-consult-operative`, Scout |
| Review | Test runners, reviewer agents, Quinn |
| Compound | `/run-add-wisdom`, `/run-create-operative`, Shannon |

The difference is enforcement, not tooling.

## Related

- `parc` skill - The underlying PARC workflow (non-strict)
- `/run-search-wisdom` - Search before planning
- `/run-consult-expert scout` - Orchestration help
