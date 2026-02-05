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

The command searches in order (first match wins):

1. **Project-level**: `.claude/operatives/` (project-specific operatives)
2. **Org-level**: `~/[workspace]/[org]/[operatives-repo]/` (shared team operatives)
3. **User-level**: `~/.claude/operatives/` (your personal operatives)

### Org-Level Discovery

To find org operatives:

1. Walk up from current directory to find the org root (contains `CLAUDE.md` and is direct child of workspace like `~/Code/`)
2. Check for `[org]/.claude/org.json` - if exists, read `operatives.repo` setting
3. If no config, use convention: `[org]-operatives/` directory
4. Look for operative files in that repo

**Example org.json:**
```json
{
  "name": "acme-corp",
  "operatives": {
    "repo": "acme-operatives"
  }
}
```

**Resolution example for `~/Code/acme-corp/webapp/`:**
- Org root: `~/Code/acme-corp/`
- Config: `~/Code/acme-corp/.claude/org.json`
- Operatives: `~/Code/acme-corp/acme-operatives/` (from config or convention)

### Recommended Org Structure

New users should create two default orgs:

```
~/Code/                    # Workspace
├── CLAUDE.md              # Workspace preferences
├── work/                  # Professional projects
│   ├── CLAUDE.md
│   ├── .claude/org.json
│   └── work-operatives/
└── personal/              # Side projects
    ├── CLAUDE.md
    ├── .claude/org.json
    └── personal-operatives/
```

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
4. If not found, discover org root and look in org operatives repo
5. If not found, look in user operatives: `~/.claude/operatives/<name>.md`
6. If not found, respond: "Operative '<name>' not found. Create one with `/run-create-operative`"

### Org Discovery Algorithm

```
1. Start from current working directory
2. Walk up until you find a directory that:
   a. Contains CLAUDE.md AND
   b. Is a direct child of a workspace (~/Code/, ~/Projects/, etc.)
3. This is the org root
4. Check [org-root]/.claude/org.json for operatives.repo
5. If no config, try convention: [org-root]/[org-name]-operatives/
6. Look for [name].md in that directory
```

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

If called without arguments, list available operatives from all three levels:

```
/run-consult-operative
```

Response:
```
## Your Operatives

### Project-level (.claude/operatives/)
- razor - Security penetration specialist

### Org-level (acme-operatives/)
- nexus - Data pipeline architect
- compliance-bot - Regulatory requirements checker

### User-level (~/.claude/operatives/)
- ghost - Stealth refactoring expert
- cipher - Cryptography consultant

Use: /run-consult-operative <name> "your question"
Create new: /run-create-operative
```

When listing, scan all three directories and parse each file's frontmatter to display name and title. Group by level for clarity.

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
