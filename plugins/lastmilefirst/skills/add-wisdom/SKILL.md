---
name: add-wisdom
description: Capture patterns, insights, and hard-won lessons to org stack-wisdom
---

# Add Wisdom

Capture patterns, insights, and hard-won lessons to your org's stack-wisdom repository.

## Wisdom vs Knowledge

This skill captures **wisdom**, not knowledge. Know the difference:

| Wisdom (this skill) | Knowledge (`/run-add-knowledge`) |
|---------------------|----------------------------------|
| Patterns and practices | Facts and data |
| Lessons learned | Documentation |
| Gotchas that generalize across projects | Reference material |
| "What we learned" | "What exists" |
| Debugging insights | API specs, configs |
| Prevention strategies | Client requirements |

**The test:**
- "This will probably be helpful in a different project someday" → **Wisdom**
- "This is specific to how this project/client works" → **Knowledge**

**Gotchas are the exception. There are three destinations, not two.** A trap that only bites in
one repo belongs in that project's CLAUDE.md (`## Dev Gotchas` / `## Deployment Gotchas` /
`## Usage Gotchas`), not here and not in knowledge. Wisdom takes the gotchas that generalize. See
the placement rule in the `organize-claude` skill.

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

### Step 0: Rhyme check first

Before writing anything, search for a prior lesson this one rhymes with: the same problem,
mechanism, or trap under a different name. Run `/run-search-wisdom` with the problem statement
and the symptoms as the query, and act on the outcome:

| Outcome | Action |
|---|---|
| No rhyme | Continue to Step 1. First occurrence. |
| One rhyme | Stop. Do not write a second entry. A lesson that recurs is a procedure or a rule that never got written down, so route it through the skill-or-context fork in the `parc` skill. On the original entry, set `Rhymes with` to this occurrence (date and a few words), and set `Promoted to` once the skill or rule exists. |
| Rhyme with an entry already promoted | The promotion did not hold. Fix the skill or the rule it points at. Do not add a third copy. |

The Compound close in `parc` runs this same search earlier in the cycle. This step is the guard
for when `/run-add-wisdom` is invoked directly.

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
**Last applied:** never
**Rhymes with:** none
**Promoted to:** none

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

### The three ledger lines

Every entry carries three lines under `Added`, and they are what make wisdom compound instead
of accumulate:

- **Last applied.** The date the entry was last confirmed as used, written by the Compound
  close (`/run-search-wisdom --applied <file>`). An entry applied last week needs nothing. An
  entry never applied in six months is forgotten or dead, and the weekly review decides which.
- **Rhymes with.** A later occurrence of the same lesson. Set instead of writing a second
  entry.
- **Promoted to.** The skill, CLAUDE.md rule, or operative the lesson became once it recurred.
  A rhyme against a promoted entry means the promotion did not hold.

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
