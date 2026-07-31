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
| **Deployable** | Dev Environment, Infrastructure, Cloud Details, Terraform Workspaces, Deployment, Dev Gotchas, Deployment Gotchas, Testing |
| **Usable** | Dev Environment, Installation, Configuration, Testing, Publishing, Dev Gotchas, Usage Gotchas |
| **Referenceable** | Content Structure, How to Update, Gotchas |
| **Experimental** | Quick Commands |
| **No archetype** | Section checks skipped; finding reported to add archetype |

Projects without an archetype get a "no archetype declared" finding instead of being checked against the full Deployable template. This avoids false positives for non-deployable projects.

## How Section Matching Works

**A section counts as present when a real heading contains its name.** Matching runs against
extracted ATX headings, not the raw file — so `## Testing` inside a fenced code block, in prose, or
in a scaffolded file's `required_sections:` frontmatter does **not** count. (Before 0.21.0 the check
was `section_header in content` over the whole file, which counted all three.)

Matching is deliberately lenient about the heading's exact wording. All of these satisfy their
section without any configuration:

| Heading in your file | Satisfies |
|----------------------|-----------|
| `### Deployment` | `## Deployment` (level is not significant) |
| `## Deployment Instructions` | `## Deployment` |
| `## Testing Strategy` | `## Testing` |
| `## Core Philosophy: Compound Engineering` | `## Core Philosophy` |
| `## Gotchas (Learned the Hard Way)` | a Gotchas section |

A short alias list covers genuine **renames**, where the canonical word is absent entirely —
`## Common Pitfalls to Avoid` satisfies a Gotchas section via `Pitfalls`, and `## Common Commands`
satisfies `## Quick Commands` via `Commands`. Alias matches are reported distinctly:

```
Gotchas → via "common pitfalls to avoid" ✓
```

That distinction matters: the section is documented, but under a name the convention does not use.
The summary counts these separately as `Files passing only via alias`.

**What this check does not do:** it does not read section bodies. A heading with an empty or
placeholder body counts as present. The report says "no heading found for" rather than "missing"
precisely because heading presence is all it measures.

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
