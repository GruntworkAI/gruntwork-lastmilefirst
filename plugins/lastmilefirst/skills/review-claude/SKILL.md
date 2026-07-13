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

**Boundary with `review-signal` (Ripley):** `review-claude` decides *what belongs* in CLAUDE.md and *where* (placement, hierarchy, completeness). `review-signal` reviews *how* the prose is written (signal density, anti-slop, voice). Run `review-claude` first to fix structure, then Ripley to tighten the language inside it.

## Conversational Triggers

**Claude should proactively offer review-claude when:**

| Trigger | Claude Should Say |
|---------|-------------------|
| CLAUDE.md exists but Claude misses context | "I notice I'm missing some project context. Want me to review your CLAUDE.md for gaps?" |
| User mentions deployment/infrastructure issues | "Should I check if your CLAUDE.md has the infrastructure sections filled in?" |
| Starting work in unfamiliar project | "Let me review this project's CLAUDE.md to see if all sections are complete." |
| User asks about project conventions | "I can review your CLAUDE.md files for completeness. Want me to check?" |

## Claude Workflow

This skill uses **Claude as the conversational layer**. The script runs non-interactively; Claude presents results and offers next steps.

### Step 1: Run review

```bash
python3 ${SKILL_ROOT}/scripts/review_claude.py
```

Present the review summary. Highlight files with gaps and what sections are missing.

### Step 2: Offer suggestions

If gaps were found, ask: "I found gaps in N files. Want me to generate suggestion templates?"

```bash
# Generate suggestions for all files with gaps
python3 ${SKILL_ROOT}/scripts/review_claude.py --suggest

# For a specific file
python3 ${SKILL_ROOT}/scripts/review_claude.py --file PATH --suggest
```

## Commands Reference

```bash
# Review all CLAUDE.md files in workspace (report only)
python3 ${SKILL_ROOT}/scripts/review_claude.py

# Review and auto-generate suggestions for gaps
python3 ${SKILL_ROOT}/scripts/review_claude.py --suggest

# Review a specific file
python3 ${SKILL_ROOT}/scripts/review_claude.py --file ~/Code/gruntwork/project/CLAUDE.md

# Generate suggestions for a specific file
python3 ${SKILL_ROOT}/scripts/review_claude.py --file ~/Code/gruntwork/project/CLAUDE.md --suggest
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

## Archetype-Aware Review

Project-level reviews are archetype-aware. The review detects `## Archetype: X` in each project's CLAUDE.md and checks only the sections relevant to that archetype.

| Archetype | Checked Sections |
|-----------|-----------------|
| **Deployable** | Dev Environment, Infrastructure, Cloud Details, Terraform Workspaces, Deployment, Gotchas, Testing |
| **Usable** | Dev Environment, Installation, Configuration, Testing, Publishing, Gotchas |
| **Referenceable** | Content Structure, How to Update, Gotchas |
| **Experimental** | Quick Commands |
| **No archetype** | Section checks skipped; finding reported to add archetype |

Projects without an archetype get a "no archetype declared" finding instead of being checked against the full Deployable template. This avoids false positives for non-deployable projects.

## Expected Sections

**User-level** (from template frontmatter):
- Workspace Organization
- Core Philosophy
- Project Directory Mapping
- Development Workflow
- Quick Debugging Checklist

**Org-level** (from template frontmatter):
- Security & Compliance
- Naming Conventions
- Approved Tools & Resources
- Tech Stack
- Projects

**Project-level** (archetype-specific — see table above)

## Update Overwatch

After completing the review, update Overwatch state for each level reviewed:

```bash
# Project-level CLAUDE.md
python3 ~/.claude/plugins/marketplaces/gruntwork-lastmilefirst/plugins/lastmilefirst/hooks/scripts/update_state.py review_claude

# Org-level CLAUDE.md
python3 ~/.claude/plugins/marketplaces/gruntwork-lastmilefirst/plugins/lastmilefirst/hooks/scripts/update_state.py review_claude --scope org

# User-level CLAUDE.md
python3 ~/.claude/plugins/marketplaces/gruntwork-lastmilefirst/plugins/lastmilefirst/hooks/scripts/update_state.py review_claude --scope global
```

Run whichever levels were actually reviewed in the session.

## Future Enhancement

When CLAUDE.md files exceed ~200 lines with path-specific sections, review-claude will recommend considering Claude Rules for context efficiency.

## Related Skills

- `organize-claude` - Audit hierarchy and scaffold missing files
- `review-docs` - Review documentation quality
- `review-work` - Review work artifacts
- `review-all` - Run all review skills
