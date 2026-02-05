---
name: search-wisdom
description: Search org stack-wisdom for patterns, insights, and hard-won lessons
---

# Search Wisdom

Search your org's stack-wisdom repository for patterns, insights, and hard-won lessons.

## Wisdom vs. Knowledge

**This skill searches wisdom, not knowledge.**

| Wisdom | Knowledge |
|--------|-----------|
| Patterns and practices | Facts and data |
| Lessons learned | Reference documentation |
| Gotchas and pitfalls | API specifications |
| Insights from experience | Datasets and configs |
| "What we learned" | "What exists" |

For facts and datasets, use `/run-search-knowledge` (future skill). For patterns and insights, use this skill.

## Usage

```
/run-search-wisdom terraform workspace
/run-search-wisdom "resource already exists"
/run-search-wisdom python venv gotcha
```

## How Stack-Wisdom Works

Stack-wisdom is your org's institutional insight - patterns that took time to learn, captured so future sessions (and teammates) benefit immediately. It's not documentation; it's distilled experience.

### Three Types of Wisdom

| Type | Location | Purpose |
|------|----------|---------|
| **Patterns** | `stack-wisdom/` | Solutions to recurring problems |
| **Circuit Breakers** | `circuit-breakers/` | Detection for critical failures |
| **Triggers** | `triggers/` | Keywords that signal specific issues |

## Finding the Wisdom Repo

1. Discover org root (walk up to find CLAUDE.md in direct child of workspace)
2. Read `[org-root]/.claude/org.json` for `stack_wisdom.repo` setting
3. If no config, use convention: `[org-name]-stack-wisdom/`

**Example for `~/Code/work/webapp/`:**
- Org root: `~/Code/work/`
- Config: `~/Code/work/.claude/org.json`
- Wisdom repo: `~/Code/work/work-stack-wisdom/` (from config or convention)

## Search Algorithm

When invoked with a query:

1. **Locate the wisdom repo** using org discovery
2. **Search pattern files** in `stack-wisdom/`:
   - Match against file names
   - Match against file contents (problem, symptoms, triggers)
3. **Search circuit breakers** in `circuit-breakers/`:
   - Match against trigger keywords
4. **Rank results** by relevance:
   - Exact keyword match in triggers: highest
   - Match in symptoms section: high
   - Match in problem description: medium
   - Match in file name: lower

## Output Format

```markdown
## Wisdom Found: [query]

### Exact Matches
- **terraform-workspace-check.md** - Pattern: Terraform Workspace Check
  - Triggers: "resource already exists", "unexpected changes in plan"
  - Insight: Always check workspace before plan/apply

### Related Patterns
- **pre-migration-database-syndrome.md** - Pattern: Pre-Migration Database Syndrome
  - Insight: Database connection issues after migration changes

### No matches?
Consider capturing this as new wisdom with `/run-add-wisdom`
```

## Proactive Search

Claude should search wisdom proactively when:

- User mentions error messages or symptoms
- Starting infrastructure work (check for gotchas)
- Debugging loops detected (2+ failed attempts)
- User seems stuck or frustrated

**Example proactive trigger:**
> User: "Why does terraform keep trying to recreate this resource?"
> Claude: *searches wisdom for "terraform recreate resource"*
> Found: terraform-workspace-check.md - suggests checking `terraform workspace show`

## When No Wisdom Exists

If search returns no results for a problem worth remembering:

1. Help solve the problem
2. Offer to capture the insight: "Should I add this to stack-wisdom with `/run-add-wisdom`?"

This is the "compound" loop - every hard-won insight can become future wisdom.

## Related Commands

- `/run-add-wisdom` - Capture new patterns and insights
- `/run-consult-expert` - Get expert help when wisdom doesn't cover it
- `/run-review-work` - Reviews work and suggests wisdom extractions
