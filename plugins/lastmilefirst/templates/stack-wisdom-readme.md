# {{ORG_NAME}} Stack Wisdom

Patterns, insights, and hard-won lessons for {{ORG_NAME}} projects.

## Wisdom vs. Knowledge

This repo contains **wisdom**, not knowledge:

| Wisdom (here) | Knowledge (elsewhere) |
|---------------|----------------------|
| Patterns and practices | Facts and data |
| Lessons learned | API documentation |
| Gotchas and pitfalls | Configuration reference |
| Insights from experience | Datasets |

If it took pain to learn, it belongs here.

## Structure

```
{{ORG_NAME}}-stack-wisdom/
├── stack-wisdom/        # Patterns and solutions
├── circuit-breakers/    # Critical failure detection
└── triggers/            # Keywords that signal issues
```

## Adding Wisdom

After solving a hard problem:

```bash
/run-add-wisdom
```

Or create a markdown file directly following the template.

## Searching Wisdom

When stuck or starting work:

```bash
/run-search-wisdom terraform workspace
/run-search-wisdom "resource already exists"
```

## The Compound Loop

1. **Encounter a problem** - Something takes 30+ minutes
2. **Solve it** - With or without help
3. **Capture the insight** - Add it here
4. **Future benefit** - Next time, it takes 30 seconds

Every entry here is time saved for future-you and your teammates.

## Pattern Template

```markdown
# Pattern: Title

**Type:** Pattern
**Added:** {{DATE}}

## Problem

What goes wrong and why it matters.

## Symptoms

How you know you have this problem:
- Symptom 1
- Symptom 2

## Solution

What to do, step by step.

## Prevention

How to avoid this in the future.

## Wisdom

> "The key insight in one memorable sentence."

## Trigger Keywords

- keyword1
- "phrase with spaces"
```

## This Repo

This repository is shared across all {{ORG_NAME}} projects. Wisdom here benefits everyone in the org.

Managed by the [lastmilefirst](https://github.com/GruntworkAI/gruntwork-marketplace) plugin.
