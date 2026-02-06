---
name: search-knowledge
description: Search org stack-knowledge for facts, documentation, and reference material
---

# Search Knowledge

Search your org's knowledge base for facts, documentation, and reference material.

## Knowledge vs Wisdom

This skill searches **knowledge**, not wisdom:

| Search Knowledge (this skill) | Search Wisdom (`/run-search-wisdom`) |
|------------------------------|-------------------------------------|
| "What is X?" | "How do we handle X?" |
| "How does client Y's API work?" | "What gotchas did we hit with Y's API?" |
| Facts and documentation | Patterns and lessons |
| Reference lookup | Solution lookup |

**Use knowledge for facts. Use wisdom for insights.**

## Usage

```bash
/run-search-knowledge "acme api auth"
/run-search-knowledge "payment processing"
/run-search-knowledge "project architecture"
```

## How It Works

### 1. Check Configured Backend

If `org.json` has a knowledge backend configured:

```json
{
  "stack_knowledge": {
    "type": "confluence",
    "url": "https://acme.atlassian.net/wiki",
    "space": "ENG"
  }
}
```

The skill uses the appropriate adapter to search the configured backend.

### 2. Search Local Knowledge

Always searches local knowledge store as well:

```
[org]/stack-knowledge/
├── clients/
├── projects/
├── domain/
└── reference/
```

### 3. Combine Results

Results from all sources are combined and ranked by relevance.

## Output Format

```markdown
## Knowledge Found: [query]

### From Confluence (ENG space)
- **Acme API Authentication** - OAuth2 flow with PKCE
  [View in Confluence](https://...)

### From Local Knowledge
- **clients/acme-api-reference.md** - API endpoints and auth
  Summary: Complete reference for Acme's REST API...

### No matches?
Consider asking the team or checking external documentation.
To add new knowledge: `/run-add-knowledge`
```

## Proactive Search

Claude should search knowledge proactively when:

- Starting work with a specific client
- Needing domain-specific information
- Looking for existing documentation
- Onboarding to a new project

**Example:**
> User: "I need to integrate with Acme's API"
> Claude: *searches knowledge for "acme api"*
> Found: acme-api-reference.md with auth flow and endpoints

## Supported Backends (Phase 1)

| Backend | Status | Search Support |
|---------|--------|----------------|
| Local markdown | ✅ Built-in | Full-text search |
| Confluence | 🔜 Planned | CQL search |
| Notion | 🔜 Planned | API search |
| Sharepoint | 🔜 Planned | Graph API search |

## When No Knowledge Exists

If search returns no results:

1. Suggest asking teammates or checking external sources
2. Offer to capture knowledge: "Should I add this to stack-knowledge with `/run-add-knowledge`?"

## Related Commands

- `/run-add-knowledge` - Capture new knowledge
- `/run-search-wisdom` - Search for patterns and lessons (not facts)
- `/run-consult-expert` - Get expert help when knowledge doesn't cover it
