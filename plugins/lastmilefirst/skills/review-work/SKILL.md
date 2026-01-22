---
name: review-work
description: Review .claude/work/ for stale items, archive candidates, and GitHub issue opportunities
---

# Review Work

Analyzes the `.claude/work/` directory (todos, plans, sessions) for quality and hygiene.

## Prerequisites

Requires organized project structure (`docs/`, `.claude/work/`, etc.).

If structure is missing, respond:
> "Run `/organize` first to create the standard structure."

See [organize/SKILL.md](../organize/SKILL.md) for required structure.

## What This Skill Checks

### 1. Todos (.claude/work/todos/)

**Staleness**
- Items with no updates in 14+ days
- Items with `status: pending` that are old
- Items with `status: in_progress` that seem stalled

**Archive Candidates**
- Items with `status: complete` older than 7 days
- Items marked as won't-do or cancelled

**GitHub Issue Candidates**
- Bugs that need tracking
- Features that need discussion
- Items that would benefit from external visibility

**Misplaced Content**
- Documentation that belongs in `docs/`
- Technical debt that belongs in `.claude/debt/`
- Plans that belong in `plans/`

### 2. Plans (.claude/work/plans/)

**Staleness**
- Plans older than 30 days with no implementation
- Plans referencing completed features
- Abandoned/superseded plans

**Archive Candidates**
- Completed plans (feature shipped)
- Rejected/cancelled plans

**Missing Implementation**
- Plans with no corresponding code changes
- Plans that should become GitHub issues/milestones

### 3. Sessions (.claude/work/sessions/)

**Archive Candidates**
- Session files older than 30 days
- One-off analysis that's no longer relevant

**Extraction Opportunities**
- Insights that should become documentation
- Patterns that should go to stack-wisdom
- Bugs found that should become issues

### 4. Debt (.claude/debt/)

**Review Status**
- Items that have been resolved
- Items that should become GitHub issues
- Items that need prioritization

## How to Run

### Step 1: Inventory Each Directory

For each subdirectory, list:
- Filename
- Last modified date
- Status (if applicable from YAML frontmatter)
- Brief description

### Step 2: Analyze Content

**For todos**: Check YAML frontmatter for status, read content for context
**For plans**: Check if feature was implemented, if plan is still relevant
**For sessions**: Check age, determine if content should be extracted
**For debt**: Check if still applicable, prioritize

### Step 3: Check GitHub Issues

Run `gh issue list` to:
- Avoid duplicate recommendations
- Link existing issues to local items
- Identify items that exist locally but not in GitHub

### Step 4: Generate Report

```markdown
# Work Review: [Project Name]

## Summary
- Todos: X (Y stale, Z complete)
- Plans: X (Y stale)
- Sessions: X (Y archive candidates)
- Debt: X items

## Todos

### Stale (no update in 14+ days)
| File | Status | Last Modified | Recommendation |
|------|--------|---------------|----------------|
| fix-login.md | pending | 2024-12-01 | Review or close |

### Ready to Archive
- completed-task.md (complete, 10 days old)

### GitHub Issue Candidates
- bug-email-sync.md → Create issue with `bug` label

### Misplaced
- api-notes.md → Move to docs/

## Plans

### Stale
- feature-auth.md (45 days, not implemented)
  - Recommendation: Archive or create GitHub milestone

### Ready to Archive
- feature-dashboard.md (shipped 2024-12-01)

## Sessions

### Archive Candidates
- session-2024-11-15.md (41 days old)
- debug-session-old.md (60 days old)

### Extract to Documentation
- session-2024-12-20.md: Contains useful API patterns
  - Recommendation: Extract to docs/api.md

### Extract to Stack Wisdom
- debug-ecs-timeout.md: Contains reusable pattern
  - Recommendation: Add to gruntwork-stack-wisdom

## Debt

### Resolved (can remove)
- old-migration-debt.md (migration completed)

### Needs GitHub Issue
- performance-debt.md → Create issue for tracking

## Recommendations (Priority Order)
1. Archive X completed todos
2. Create GitHub issues for Y items
3. Move Z misplaced files
4. Extract patterns from sessions
```

### Step 5: Offer Actions

After presenting report, offer to:
- Archive old/completed items (via `/organize`)
- Create GitHub issues for candidates
- Move misplaced content
- Extract patterns to stack-wisdom

## Integration

- **`/organize`**: Handles the actual archiving
- **`/review-docs`**: Companion for docs/ review
- **`/review-all`**: Runs both review skills
- **`/compound-engineering:file-todos`**: For advanced todo management

## Notes

- Non-destructive: Reports first, acts on approval
- Respects YAML frontmatter status fields
- Checks GitHub issues to avoid duplicates
- Recommends stack-wisdom extractions for reusable patterns
