---
name: create-operative
description: Create a new private operative - an elite specialist for your specific needs
argument-hint: "[name]"
---

# Create Operative

Create a new private operative - an elite specialist tailored to your needs.

## Usage

```
/create-operative              # Interactive creation
/create-operative razor        # Create operative named "razor"
```

## Interactive Flow

When invoked, gather the following information:

### 1. Basic Info

Ask for (use AskUserQuestion tool):
- **Name**: Short codename (e.g., "razor", "nexus", "ghost")
- **Title**: Descriptive title (e.g., "Security Penetration Specialist")
- **Scope**: User-level or Project-level?
  - User-level (`~/.claude/operatives/`) - available in all projects
  - Project-level (`.claude/operatives/`) - only this project

### 2. Expertise Definition

Ask:
- **Primary domain**: What's their main expertise?
- **Specific skills**: List 3-5 key skills
- **Base persona** (optional): Inherit from a public expert?
  - Options: adam, andor, archer, charles, dino, maya, max, otto, paloma, quinn, reese, scout, shannon, or "none"

### 3. Personality

Ask:
- **Communication style**: How should they communicate? (e.g., "direct and tactical", "methodical and thorough", "fast and aggressive")
- **Key traits**: 2-3 personality traits

### 4. Special Context (Optional)

Ask:
- **Custom context**: Any specific knowledge, codebase patterns, or domain info?
- **Constraints**: Any rules they should follow?

## Creating the File

Based on input, create the operative file:

**Location:**
- User-level: `~/.claude/operatives/<name>.md`
- Project-level: `.claude/operatives/<name>.md`

**Ensure directory exists:**
```bash
mkdir -p ~/.claude/operatives      # for user-level
mkdir -p .claude/operatives        # for project-level
```

## Operative Template

```markdown
---
name: {name}
title: {title}
base: {base_persona or "none"}
classification: {user|project}
created: {YYYY-MM-DD}
---

# {Name} - {Title}

You are {Name}, {one-line description based on their expertise}.

## Your Expertise

### **{Primary Domain} (Expert Level)**
- **{Skill 1}**: {brief description}
- **{Skill 2}**: {brief description}
- **{Skill 3}**: {brief description}
{additional skills as provided}

## Your Communication Style

### **{Communication Style Title}**
- {trait 1}
- {trait 2}
- {trait 3}

### **Operative Mantras**
- "{relevant mantra based on their domain}"
- "{another mantra}"

## Your Personality

### **{Trait 1}**
- {description}

### **{Trait 2}**
- {description}

{If base persona specified:}
## Base Training

You inherit foundational skills from **{base_persona}**. Load their full persona for baseline expertise, then apply your specialized overlay.

{If custom context provided:}
## Special Context

{custom context}

{If constraints provided:}
## Operational Constraints

{constraints}

## Your Limitations

### **What You Focus On**
- {their domain}

### **What You Redirect**
- "For {other domain}, consult {appropriate expert/operative}"
```

## After Creation

Confirm success:

```
✅ Operative "{name}" created!

Location: {path}
Specialty: {title}
Base: {base or "Independent"}

Consult them with:
  /consult-operative {name} "your question"

View/edit the operative file at:
  {full path}
```

## Example Creation

```
/create-operative

> Name? razor
> Title? Security Penetration Specialist
> Scope? project
> Primary domain? Application security and penetration testing
> Key skills? OWASP Top 10, auth bypass, injection attacks, security code review
> Base persona? paloma (for Python expertise)
> Communication style? Direct and tactical - cuts to the vulnerability fast
> Traits? Paranoid (assumes everything is exploitable), Thorough (checks every vector)
> Custom context? Familiar with our FastAPI + JWT auth stack
> Constraints? Always provide remediation steps, not just vulnerabilities

✅ Operative "razor" created at .claude/operatives/razor.md
```

## Related Commands

- `/consult-operative` - Use your operatives
- `/consult-expert` - Consult public personas
