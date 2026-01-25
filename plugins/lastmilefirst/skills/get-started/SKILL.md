---
name: get-started
description: Interactive onboarding for the lastmilefirst plugin - assess your setup and recommend next steps
---

# Get Started with Last Mile First

Interactive onboarding that assesses your current setup and provides personalized recommendations.

## How This Skill Works

Unlike the `/run-get-started` command (quick reference), this skill:
1. **Assesses** your current project state
2. **Identifies** what's already set up vs missing
3. **Recommends** specific next steps in priority order
4. **Guides** you through initial setup if needed

## Onboarding Flow

### Step 1: Environment Assessment

Check the user's current setup:

```bash
# Check for CLAUDE.md hierarchy
ls -la ~/Code/CLAUDE.md 2>/dev/null
ls -la ./CLAUDE.md 2>/dev/null

# Check for standard project structure
ls -la docs/ plans/ .claude/work/ 2>/dev/null

# Check for existing configuration
cat ./CLAUDE.md 2>/dev/null | head -20
```

### Step 2: Report Current State

Present findings in a clear format:

```markdown
## Your Setup

| Component | Status | Notes |
|-----------|--------|-------|
| User CLAUDE.md | ✅/❌ | ~/Code/CLAUDE.md |
| Project CLAUDE.md | ✅/❌ | ./CLAUDE.md |
| Project structure | ✅/❌ | docs/, plans/, .claude/work/ |
| Documentation | ✅/❌ | README.md, docs/ |
```

### Step 3: Personalized Recommendations

Based on assessment, recommend in priority order:

**If no CLAUDE.md exists:**
> "Let's start with `/run-organize-claude scaffold` to create your Claude configuration."

**If no project structure:**
> "Run `/run-organize-project` to set up standard directories."

**If setup is complete:**
> "Your workspace looks good! Try `/run-consult-expert` to ask an AI expert about your current project."

### Step 4: Quick Wins

Suggest immediate value based on their situation:

**For new projects:**
1. `/run-organize-project` - Set up structure
2. `/run-organize-claude` - Configure Claude
3. `/run-consult-expert architect "Review my project plan"`

**For existing projects:**
1. `/run-review-project quick` - Get health snapshot
2. `/run-review-work` - Check todo hygiene
3. `/run-consult-expert` - Get expert guidance on current work

**For Claude Code optimization:**
1. `/run-review-claude` - Audit configuration
2. `/run-consult-expert shannon "Optimize my setup"`

## Available Commands Reference

### Organization
| Command | Use When |
|---------|----------|
| `/run-organize-project` | Starting a new project or cleaning up structure |
| `/run-organize-claude` | Setting up or auditing CLAUDE.md hierarchy |

### Review
| Command | Use When |
|---------|----------|
| `/run-review-project` | Want overall health check |
| `/run-review-work` | Todos/plans feeling messy |
| `/run-review-docs` | Documentation might be stale |
| `/run-review-claude` | Claude config might need improvement |

### Expert Consultation
| Expert | Best For |
|--------|----------|
| `/run-consult-expert adam` | AWS, infrastructure, deployment |
| `/run-consult-expert andor` | AI/ML, prompts, model selection |
| `/run-consult-expert archer` | Architecture, system design, ADRs |
| `/run-consult-expert charles` | Strategy, big decisions |
| `/run-consult-expert dino` | Product, UX, design |
| `/run-consult-expert maya` | Agile, project management |
| `/run-consult-expert max` | MCP, IDE integration |
| `/run-consult-expert otto` | DevOps, CI/CD |
| `/run-consult-expert paloma` | Python, FastAPI, testing |
| `/run-consult-expert quinn` | QA, TDD, test strategy |
| `/run-consult-expert reese` | Tech research, evaluation |
| `/run-consult-expert scout` | Work breakdown, coordination |
| `/run-consult-expert shannon` | Claude Code optimization |

## The Last Mile First Philosophy

This plugin embodies a methodology:

1. **Start with the end** - Define "done" before starting
2. **Consult experts early** - Get specialized guidance upfront
3. **Organize for velocity** - Structure enables speed
4. **Review regularly** - Catch drift before it compounds
5. **Compound knowledge** - Each project makes the next easier

## Getting Help

- `/run-consult-expert shannon` - Claude Code questions
- `/run-consult-expert charles` - Strategic decisions
- Check plugin README for detailed documentation

## Response Format

When invoked, provide:
1. Brief welcome
2. Assessment results table
3. Top 3 recommended actions (numbered)
4. Offer to run the first action

Example:
```
Welcome to Last Mile First! Let me check your setup...

## Your Setup
| Component | Status |
|-----------|--------|
| User CLAUDE.md | ✅ Found |
| Project CLAUDE.md | ❌ Missing |
| Project structure | ❌ Missing |

## Recommended Next Steps
1. `/run-organize-project` - Create standard structure
2. `/run-organize-claude scaffold` - Create project CLAUDE.md
3. `/run-review-project quick` - Get baseline health check

Want me to run `/run-organize-project` now?
```
