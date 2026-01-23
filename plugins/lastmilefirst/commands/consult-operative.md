---
name: consult-operative
description: Consult a private operative - your elite specialists with specialized skills
argument-hint: "<operative-name> <question>"
---

# Consult Operative

Get guidance from your private operatives - elite specialists you've created for competitive advantage.

## Usage

```
/consult-operative razor "Review this authentication flow for vulnerabilities"
/consult-operative nexus "Analyze this data pipeline architecture"
```

## How Operatives Work

Operatives are **private personas** that you create for specialized needs:
- Competitive advantages you don't want public
- Domain-specific expertise (your industry, your codebase)
- Project-specific knowledge
- Experimental persona designs

## Where Operatives Live

The command searches in order:

1. **Project-level**: `.claude/operatives/` (project-specific operatives)
2. **User-level**: `~/.claude/operatives/` (your personal operatives)

## Finding the Operative

When invoked:

1. Parse the operative name from arguments (first word)
2. Look for `<name>.md` in project operatives: `.claude/operatives/<name>.md`
3. If not found, look in user operatives: `~/.claude/operatives/<name>.md`
4. If not found, respond: "Operative '<name>' not found. Create one with `/create-operative`"

## Loading the Operative

Once found, read the operative file and:

1. Adopt the operative's expertise, personality, and communication style
2. Note any base persona they inherit from (load that too if specified)
3. Answer the question fully in character

## Operative File Format

Operatives follow the same format as personas:

```markdown
---
name: razor
base: paloma  # Optional: inherit from a public persona
classification: project  # user | project
created: 2025-01-23
---

# Razor - Security Specialist

You are Razor, a security-focused operative specialized in...

## Your Expertise
...

## Your Communication Style
...
```

## Listing Available Operatives

If called without arguments, list available operatives:

```
/consult-operative
```

Response:
```
## Your Operatives

### Project-level (.claude/operatives/)
- razor - Security penetration specialist
- nexus - Data pipeline architect

### User-level (~/.claude/operatives/)
- ghost - Stealth refactoring expert
- cipher - Cryptography consultant

Use: /consult-operative <name> "your question"
Create new: /create-operative
```

## Differences from Public Experts

| Aspect | `/consult-expert` | `/consult-operative` |
|--------|-------------------|----------------------|
| Source | Public marketplace | Private (user/project) |
| Personas | Generic experts | Your specialists |
| Sharing | Anyone can use | Only you |
| Customization | Fixed | Fully customizable |

## Related Commands

- `/create-operative` - Create a new operative
- `/consult-expert` - Consult public personas
- `/get-started` - Overview of all commands
