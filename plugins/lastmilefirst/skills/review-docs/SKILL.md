---
name: review-docs
description: Review docs/ folder for duplication, staleness, gaps, and misplaced content
---

# Review Docs

Analyzes the `docs/` directory for documentation quality issues.

## Prerequisites

Requires organized project structure (`docs/`, `.claude/work/`, etc.).

If structure is missing, respond:
> "Run `/organize` first to create the standard structure."

See [organize/SKILL.md](../organize/SKILL.md) for required structure.

## What This Skill Checks

### 1. Duplication
- Files covering the same topic
- Overlapping content between files
- Copy-pasted sections

### 2. Staleness
- Outdated instructions or commands
- References to deprecated features
- Old dates or version numbers
- Broken links or references

### 3. Consolidation Opportunities
- Multiple small files that could merge
- Fragmented information across files
- Related content that should be together

### 4. Missing Documentation
Check if these common docs exist:
- `api.md` - API reference/endpoints
- `deployment.md` - Deployment instructions
- `development.md` - Local dev setup
- `architecture.md` - System design
- `testing.md` - Test instructions
- `security.md` - Security considerations

Recommend creation for missing essential docs based on project type.

### 5. Misplaced Content
Identify content that belongs elsewhere:
- TODOs/tasks → `.claude/work/todos/`
- Technical debt notes → `.claude/debt/`
- Session notes/analysis → `.claude/work/sessions/`
- Plans/PRDs → `.claude/work/plans/`

### 6. GitHub Issue Candidates
Identify items that should become GitHub issues:
- Bug descriptions in docs
- Feature requests mentioned
- Known issues lists
- "TODO: fix this" comments
- Technical debt items that need tracking

## How to Run

### Step 1: Inventory
List all files in `docs/` with:
- Filename, size, last modified date
- Brief description of content

### Step 2: Content Analysis
Read each file and identify:
- Main topic/purpose
- Overlap with other docs
- Signs of staleness
- Misplaced content (todos, debt, plans)
- Items that should be GitHub issues

### Step 3: Check for Missing Docs
Based on project structure, identify missing essential documentation.

### Step 4: Check GitHub Issues
Run `gh issue list` to see existing issues, avoid recommending duplicates.

### Step 5: Generate Report

```markdown
# Documentation Review: [Project Name]

## Summary
- Total files: X
- Total lines: X
- Oldest file: X (modified: date)

## Issues Found

### Duplication
- [file1] and [file2]: Both cover [topic]
  - Recommendation: Merge into single file

### Staleness
- [file]: References [outdated thing]
  - Recommendation: Update to current

### Missing Documentation
- No API documentation found
  - Recommendation: Create docs/api.md
- No architecture overview
  - Recommendation: Create docs/architecture.md

### Misplaced Content
- [file] line X: Contains TODO that belongs in .claude/work/todos/
- [file] line X: Technical debt note → .claude/debt/

### GitHub Issue Candidates
- [file] line X: "Known bug: [description]"
  - Recommendation: Create issue with label `bug`
- [file] line X: "TODO: implement [feature]"
  - Recommendation: Create issue with label `enhancement`

### Consolidation Opportunities
- Rename to simpler names: REMAIL_DEPLOY_GUIDE.md → deployment.md

## Recommendations (Priority Order)
1. [Highest impact action]
2. ...
```

### Step 6: Offer Actions
After presenting report, offer to:
- Create missing documentation (scaffold)
- Move misplaced content to correct locations
- Create GitHub issues for candidates
- Fix duplication/staleness

## Creating GitHub Issues

When user approves issue creation, use the compound-engineering file-todos skill to manage the workflow:

1. First, create a local todo file in `.claude/work/todos/` with the issue details
2. Use `/compound-engineering:file-todos` to triage and manage
3. For items ready for GitHub, use the triage workflow to create issues

Alternatively, for direct issue creation:
```bash
gh issue create --title "[type]: [description]" \
  --body "Found in docs/[file].md

[Details]

---
*Created via /review-docs*" \
  --label [appropriate-label]
```

## Integration with Other Skills

- **`/organize`**: Run first to ensure proper structure before review
- **`/review-work`**: Companion skill for reviewing .claude/work/
- **`/review-all`**: Runs both review-docs and review-work

## Notes

- Non-destructive by default: Reports first, acts on approval
- Checks existing GitHub issues to avoid duplicates
- Focuses on actionable improvements
