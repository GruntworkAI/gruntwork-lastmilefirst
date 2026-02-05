# {{ORG_NAME}} Operatives

Private AI specialists for {{ORG_NAME}} projects.

## What Are Operatives?

Operatives are AI personas you create for specialized needs:

- **Domain experts** - Know your industry, your clients, your tech stack
- **Process specialists** - Embody your team's best practices
- **Quality gatekeepers** - Enforce your standards automatically

Unlike public experts (Paloma, Adam, etc.), operatives are private - your competitive advantage, your institutional knowledge, your secret sauce.

## Creating Operatives

```bash
/run-create-operative
```

Or create a markdown file directly in this directory following the template.

## Using Operatives

```bash
# List available operatives
/run-consult-operative

# Consult a specific operative
/run-consult-operative razor "Review this authentication flow"
```

## Operative Template

```markdown
---
name: operative-name
title: One-Line Description
base: paloma  # Optional: inherit from public expert
created: {{DATE}}
---

# Operative Name - Title

You are [Name], a specialist in [domain]...

## Your Expertise

- Skill 1
- Skill 2

## Your Communication Style

[How you communicate]

## Your Limitations

[What you defer to others]
```

## This Repo

This repository is shared across all {{ORG_NAME}} projects. Changes here affect all projects in the org.

Managed by the [lastmilefirst](https://github.com/GruntworkAI/gruntwork-marketplace) plugin.
