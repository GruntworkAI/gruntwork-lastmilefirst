---
name: add-knowledge
description: Capture facts, documentation, and reference material to org stack-knowledge
---

# Add Knowledge

Capture facts, documentation, and reference material to your org's knowledge base.

## Knowledge vs Wisdom

This skill captures **knowledge**, not wisdom. Know the difference:

| Knowledge (this skill) | Wisdom (`/run-add-wisdom`) |
|------------------------|---------------------------|
| Facts and data | Patterns and practices |
| Documentation | Lessons learned |
| Reference material | Gotchas and pitfalls |
| "What exists" | "What we learned" |
| API specs, configs | Debugging insights |
| Client requirements | Prevention strategies |

**The test:**
- "This is specific to how this project/client works" → **Knowledge**
- "This will probably be helpful in a different project someday" → **Wisdom**

## When to Add Knowledge

Add knowledge when you encounter or create:

| Candidate | Example |
|-----------|---------|
| Client documentation | API specs, requirements, conventions |
| Project architecture | System design, component relationships |
| Product specs | Features, requirements, constraints |
| Configuration reference | Environment setup, deployment configs |
| Domain facts | Business rules, terminology, processes |
| Team conventions | Coding standards, review processes |

**The test:** "Would someone new to this project/client/domain need this information?"

## Usage

```bash
/run-add-knowledge                    # Interactive - guides through capture
/run-add-knowledge "Client API auth"  # Start with a topic
```

## Knowledge Storage

### Configured Backend (Preferred)

If your org has a knowledge backend configured in `org.json`:

```json
{
  "stack_knowledge": {
    "type": "confluence",
    "url": "https://acme.atlassian.net/wiki",
    "space": "ENG"
  }
}
```

The skill will attempt to use the configured adapter to store knowledge directly.

### Local Fallback

If no backend is configured (or adapter unavailable), knowledge is written locally:

```
[org]/stack-knowledge/           # Local knowledge store
├── clients/
│   └── acme-api-reference.md
├── projects/
│   └── webapp-architecture.md
└── domain/
    └── payment-processing-rules.md
```

**After local write, the skill recommends:**
> "Knowledge saved locally. Consider adding to your team's knowledge base (Confluence, Notion, etc.) for better discoverability."

## Creation Process

### Step 1: Identify Knowledge Type

Ask the user:

```
Question: "What type of knowledge is this?"
- Header: "Type"
- Options:
  - "Client" - Client-specific information (API, requirements)
  - "Project" - Project architecture, design decisions
  - "Product" - Product specs, features, requirements
  - "Domain" - Business rules, terminology, processes
  - "Reference" - Configuration, setup, technical reference
```

### Step 2: Gather Details

```
Question: "Give it a descriptive title"
- Header: "Title"
- Example: "Acme API Authentication Flow"

Question: "Summarize the knowledge (1-2 sentences)"
- Header: "Summary"

Question: "Full content or reference?"
- Header: "Content"
- Options:
  - "Full content" - Capture the complete documentation
  - "Reference" - Just link to existing documentation
```

### Step 3: Write the Knowledge

**For full content:**

```markdown
# [Title]

**Type:** [Client | Project | Product | Domain | Reference]
**Added:** [Date]
**Source:** [Where this came from, if applicable]

## Summary

[1-2 sentence summary]

## Content

[Full knowledge content]

## Related

- [Links to related knowledge or wisdom]
```

**For references:**

```markdown
# [Title]

**Type:** Reference
**Added:** [Date]

## Summary

[1-2 sentence summary]

## Location

[URL or path to the actual documentation]

## Notes

[Any context about how to use this reference]
```

### Step 4: Store and Recommend

1. Check `org.json` for `stack_knowledge` config
2. If adapter available, store in configured backend
3. If not, write to `[org]/stack-knowledge/[type]/[slug].md`
4. Recommend proper storage if written locally

## Supported Backends (Phase 1)

| Backend | Status | Config |
|---------|--------|--------|
| Local markdown | ✅ Built-in | Default fallback |
| Confluence | 🔜 Planned | `type: "confluence"` |
| Notion | 🔜 Planned | `type: "notion"` |
| Sharepoint | 🔜 Planned | `type: "sharepoint"` |

### Contributing Adapters

We welcome community adapters for knowledge backends. See `templates/knowledge-adapter.md` for the adapter interface.

```bash
# Future: Install community adapter
/plugin install confluence-adapter@community
```

## Proactive Knowledge Capture

Claude should offer to add knowledge when:

- Documenting client-specific APIs or processes
- Writing architecture or design docs
- Capturing requirements or specifications
- Explaining domain concepts
- Creating configuration references

**Example prompt:**
> "This API documentation looks like knowledge worth preserving. Want me to add it to stack-knowledge?"

## Differences from Wisdom

| Aspect | Knowledge | Wisdom |
|--------|-----------|--------|
| **Trigger** | "Document this fact" | "Remember this lesson" |
| **Storage** | Org's knowledge base | Git repo (stack-wisdom) |
| **Format** | Documentation | Pattern with triggers |
| **Lookup** | Search for facts | Search for solutions |
| **Example** | "Client uses OAuth2 with PKCE" | "OAuth gotcha: always check token expiry" |

## Related Commands

- `/run-search-knowledge` - Find existing knowledge
- `/run-add-wisdom` - Capture patterns and lessons (not facts)
- `/run-organize-orgs` - Set up org infrastructure
