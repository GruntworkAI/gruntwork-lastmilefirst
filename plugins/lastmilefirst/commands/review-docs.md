---
name: review-docs
description: Audit documentation quality, freshness, and completeness
argument-hint: "[path]"
---

# Review Docs

Analyzes documentation for quality, freshness, and gaps.

## Usage

```
/review-docs              # Review docs/ directory
/review-docs ./guides     # Review specific path
```

## What Gets Checked

### Freshness
- Last modified date vs code changes
- References to deprecated features
- Outdated version numbers or links

### Completeness
- Missing README files
- Undocumented public APIs
- Missing architecture docs for complex systems

### Quality
- Broken internal links
- Missing code examples
- Unclear or ambiguous sections

### Structure
- Consistent formatting
- Proper heading hierarchy
- Table of contents accuracy

## Output

Produces a documentation health report:
- **Critical** - Broken links, severely outdated
- **Warning** - Stale content, missing sections
- **Suggestion** - Improvements, additions

## Related Commands

- `/organize-project` - Set up docs structure
- `/review-project` - Overall project health
