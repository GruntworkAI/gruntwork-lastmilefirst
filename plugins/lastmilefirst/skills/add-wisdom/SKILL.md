---
name: add-wisdom
description: Capture patterns, insights, and hard-won lessons to org stack-wisdom
---

# Add Wisdom

Capture patterns, insights, and hard-won lessons to your org's stack-wisdom repository.

## When to Add Wisdom

Add wisdom when you've learned something worth remembering:

| Good Candidates | Not Wisdom |
|----------------|------------|
| Debugging insight that took 30+ minutes | Simple typo fix |
| Pattern that applies across projects | Project-specific config |
| Gotcha that will bite others | One-time edge case |
| Best practice discovered through pain | Documentation of facts |
| Circuit breaker for critical failures | API reference |

**The test:** "Would this save future-me (or a teammate) significant time?"

## Usage

```
/run-add-wisdom                           # Interactive - guides you through it
/run-add-wisdom "terraform workspace"     # Start with a topic
```

## Wisdom Types

### 1. Pattern
A recurring problem with a known solution.

**Structure:**
- Problem statement
- Symptoms (how you know you have this problem)
- Solution (what to do)
- Prevention (how to avoid it)
- Wisdom (the insight)

### 2. Circuit Breaker
Detection for critical failures that should trigger immediate attention.

**Structure:**
- Failure mode description
- Trigger keywords/symptoms
- Immediate actions
- Escalation path

### 3. Trigger
Keywords that signal a specific issue (used by proactive systems).

**Structure:**
- Keywords list
- Associated pattern or action
- Confidence level

## Finding the Wisdom Repo

1. Discover org root (walk up to find CLAUDE.md in direct child of workspace)
2. Read `[org-root]/.claude/org.json` for `stack_wisdom.repo` setting
3. If no config, use convention: `[org-name]-stack-wisdom/`

## Creation Process

### Step 1: Gather Context

Ask the user:

```
Question 1: "What type of wisdom is this?"
- Header: "Type"
- Options:
  - "Pattern" - A recurring problem with a solution
  - "Circuit Breaker" - A critical failure to detect early
  - "Trigger" - Keywords that signal a known issue

Question 2: "Give it a short name (for the filename)"
- Header: "Name"
- Example: "terraform-workspace-check", "python-venv-corruption"

Question 3: "Describe the problem or situation"
- Header: "Problem"
- Freeform text

Question 4: "What are the symptoms? How do you know you have this issue?"
- Header: "Symptoms"
- Freeform text

Question 5: "What's the solution or insight?"
- Header: "Solution"
- Freeform text
```

### Step 2: Generate the Wisdom File

Use this template:

```markdown
# Pattern: [Title]

**Type:** [Pattern | Circuit Breaker | Trigger]
**Added:** [Date]

## Problem

[Problem description]

## Symptoms

[How you know you have this problem - bullet list]

## Solution

[What to do - step by step]

## Prevention

[How to avoid this in the future]

## Wisdom

> "[The key insight in one memorable sentence]"

## Trigger Keywords

[Keywords that indicate someone is experiencing this - for proactive detection]
- keyword1
- keyword2
- "phrase with spaces"
```

### Step 3: Write the File

1. Determine location based on type:
   - Pattern: `[wisdom-repo]/stack-wisdom/[name].md`
   - Circuit Breaker: `[wisdom-repo]/circuit-breakers/[name].md`
   - Trigger: `[wisdom-repo]/triggers/[name].md`

2. Ensure directory exists

3. Write the file

4. Offer to commit: "Should I commit this wisdom to the repo?"

## Proactive Wisdom Capture

Claude should offer to add wisdom when:

- A debugging session takes 30+ minutes
- User says "this keeps happening" or "I always forget"
- A pattern is used that doesn't exist in wisdom
- `/run-search-wisdom` returns no results for a common problem
- After successfully resolving a tricky issue

**Example prompt:**
> "That was a tricky one! This pattern (checking Terraform workspace before apply) could save time in the future. Want me to add it to stack-wisdom?"

## Sharing Wisdom Across Orgs

To share wisdom from one org to another:

```bash
# Copy a pattern
cp ~/Code/work/work-stack-wisdom/stack-wisdom/pattern.md \
   ~/Code/personal/personal-stack-wisdom/stack-wisdom/

# Or use the future /run-share-wisdom command
```

## Related Commands

- `/run-search-wisdom` - Search existing wisdom
- `/run-review-work` - Suggests wisdom extractions from completed work
- `/run-organize-project` - Sets up project structure including wisdom references
