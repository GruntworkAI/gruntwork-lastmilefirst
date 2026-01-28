---
name: consult-operative
description: Consult a private operative - your elite specialists with specialized skills
---

# Consult Operative

Get guidance from your private operatives - elite specialists you've created for competitive advantage.

## Usage

```
/run-consult-operative razor "Review this authentication flow for vulnerabilities"
/run-consult-operative nexus "Analyze this data pipeline architecture"
/run-consult-operative                # List available operatives
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
2. **SECURITY: Validate the operative name**
   - REJECT if name contains `..` (path traversal)
   - REJECT if name starts with `/` or `~` (absolute paths)
   - REJECT if name contains `\` (Windows path separator)
   - Subdirectories are allowed (e.g., `security/razor`)
   - If invalid, respond: "Invalid operative name. Names cannot contain '..' or start with '/' or '~'."
3. Look for `<name>.md` in project operatives: `.claude/operatives/<name>.md`
4. If not found, look in user operatives: `~/.claude/operatives/<name>.md`
5. If not found, respond: "Operative '<name>' not found. Create one with `/run-create-operative`"

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
/run-consult-operative
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

Use: /run-consult-operative <name> "your question"
Create new: /run-create-operative
```

## Differences from Public Experts

| Aspect | `/run-consult-expert` | `/run-consult-operative` |
|--------|----------------------|--------------------------|
| Source | Public marketplace | Private (user/project) |
| Personas | Generic experts | Your specialists |
| Sharing | Anyone can use | Only you |
| Customization | Fixed | Fully customizable |

## Related Commands

- `/run-create-operative` - Create a new operative
- `/run-consult-expert` - Consult public personas
- `/run-get-started` - Overview of all commands
