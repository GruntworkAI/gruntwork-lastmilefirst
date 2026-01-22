---
name: review-claude
description: Reviews existing CLAUDE.md files against expected sections and suggests additions for gaps. Part of the review-* skill family for project quality checks.
---

# Review Claude

Reviews CLAUDE.md files at all hierarchy levels (user, org, project) against expected sections defined in templates. Identifies gaps and optionally generates suggestions for missing content.

## When to Use

- Periodic health check of CLAUDE.md coverage
- Before major project work to ensure context is complete
- After creating CLAUDE.md from template to fill in gaps
- When Claude seems to miss project context (may indicate missing sections)

## Conversational Triggers

**Claude should proactively offer review-claude when:**

| Trigger | Claude Should Say |
|---------|-------------------|
| CLAUDE.md exists but Claude misses context | "I notice I'm missing some project context. Want me to review your CLAUDE.md for gaps?" |
| User mentions deployment/infrastructure issues | "Should I check if your CLAUDE.md has the infrastructure sections filled in?" |
| Starting work in unfamiliar project | "Let me review this project's CLAUDE.md to see if all sections are complete." |
| User asks about project conventions | "I can review your CLAUDE.md files for completeness. Want me to check?" |

## Commands

```bash
# Review all CLAUDE.md files in workspace
python ${SKILL_ROOT}/scripts/review_claude.py

# Review and auto-generate suggestions for gaps
python ${SKILL_ROOT}/scripts/review_claude.py --suggest

# Review a specific file
python ${SKILL_ROOT}/scripts/review_claude.py --file ~/Code/gruntwork/project/CLAUDE.md

# Generate suggestions for a specific file
python ${SKILL_ROOT}/scripts/review_claude.py --file ~/Code/gruntwork/project/CLAUDE.md --suggest
```

## Output

```
============================================================
CLAUDE.MD REVIEW
============================================================

Workspace: /Users/you/Code

USER-LEVEL CLAUDE.MD REVIEW
------------------------------------------------------------

  Code/CLAUDE.md: All sections present ✓

ORG-LEVEL CLAUDE.MD REVIEW
------------------------------------------------------------

  gruntwork/CLAUDE.md: All sections present ✓

PROJECT-LEVEL CLAUDE.MD REVIEW
------------------------------------------------------------

  gruntwork-remail/CLAUDE.md:
    Present: 4 sections
    Missing: 3 sections
      - ### Cloud Details (AWS/GCP region and account table)
      - ### Terraform Workspaces (Workspace to environment mapping)
      - ## Gotchas (Learned-the-hard-way issues table)

============================================================
REVIEW SUMMARY
============================================================
  Files reviewed: 8
  Files with gaps: 1

Generate suggestions for files with gaps? [y/N]: y
  ✓ /Users/you/Code/gruntwork/gruntwork-remail/CLAUDE.md.suggestions

✓ Generated 1 suggestion files.
```

## Suggest Mode

When gaps are found, `--suggest` generates a `.suggestions` file containing template content for missing sections:

```markdown
# Suggested additions for gruntwork-remail/CLAUDE.md
# Review and adapt these sections, then append to your file.

============================================================
# MISSING: ### Cloud Details
# Purpose: AWS/GCP region and account table
============================================================

### Cloud Details

| Setting | Value |
|---------|-------|
| **Provider** | (AWS/GCP/etc) |
| **Region** | (region) |
| **Account/Project** | (account ID) |
```

Review the suggestions and manually copy relevant parts to your CLAUDE.md.

## Expected Sections

Sections are defined in template frontmatter (single source of truth):

**User-level:**
- Workspace Organization
- Core Philosophy
- Project Directory Mapping
- Development Workflow
- Quick Debugging Checklist

**Org-level:**
- Security & Compliance
- Naming Conventions
- Approved Tools & Resources
- Tech Stack
- Projects

**Project-level:**
- Development Environment
- Infrastructure
- Cloud Details
- Terraform Workspaces
- Deployment
- Gotchas
- Testing

## Future Enhancement

When CLAUDE.md files exceed ~200 lines with path-specific sections, review-claude will recommend considering Claude Rules for context efficiency.

## Related Skills

- `organize-claude` - Audit hierarchy and scaffold missing files
- `review-docs` - Review documentation quality
- `review-work` - Review work artifacts
- `review-all` - Run all review skills
