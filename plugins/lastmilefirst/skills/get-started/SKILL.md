---
name: get-started
description: Interactive onboarding for the lastmilefirst plugin - assess your setup and recommend next steps
---

# Get Started with Last Mile First

Interactive onboarding that assesses your current setup and provides personalized recommendations.

## How This Skill Works

Unlike the `/get-started` command (quick reference), this skill:
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
> "Let's start with `/organize-claude scaffold` to create your Claude configuration."

**If no project structure:**
> "Run `/organize-project` to set up standard directories."

**If setup is complete:**
> "Your workspace looks good! Try `/consult-expert` to ask an AI expert about your current project."

### Step 4: Quick Wins

Suggest immediate value based on their situation:

**For new projects:**
1. `/organize-project` - Set up structure
2. `/organize-claude` - Configure Claude
3. `/consult-expert architect "Review my project plan"`

**For existing projects:**
1. `/review-project quick` - Get health snapshot
2. `/review-work` - Check todo hygiene
3. `/consult-expert` - Get expert guidance on current work

**For Claude Code optimization:**
1. `/review-claude` - Audit configuration
2. `/consult-expert shannon "Optimize my setup"`

## Available Commands Reference

### Organization
| Command | Use When |
|---------|----------|
| `/organize-project` | Starting a new project or cleaning up structure |
| `/organize-claude` | Setting up or auditing CLAUDE.md hierarchy |

### Review
| Command | Use When |
|---------|----------|
| `/review-project` | Want overall health check |
| `/review-work` | Todos/plans feeling messy |
| `/review-docs` | Documentation might be stale |
| `/review-claude` | Claude config might need improvement |

### Expert Consultation
| Expert | Best For |
|--------|----------|
| `/consult-expert adam` | AWS, infrastructure, deployment |
| `/consult-expert andor` | AI/ML, prompts, model selection |
| `/consult-expert archer` | Architecture, system design, ADRs |
| `/consult-expert charles` | Strategy, big decisions |
| `/consult-expert dino` | Product, UX, design |
| `/consult-expert maya` | Agile, project management |
| `/consult-expert max` | MCP, IDE integration |
| `/consult-expert otto` | DevOps, CI/CD |
| `/consult-expert paloma` | Python, FastAPI, testing |
| `/consult-expert quinn` | QA, TDD, test strategy |
| `/consult-expert reese` | Tech research, evaluation |
| `/consult-expert scout` | Work breakdown, coordination |
| `/consult-expert shannon` | Claude Code optimization |

## The Last Mile First Philosophy

This plugin embodies a methodology:

1. **Start with the end** - Define "done" before starting
2. **Consult experts early** - Get specialized guidance upfront
3. **Organize for velocity** - Structure enables speed
4. **Review regularly** - Catch drift before it compounds
5. **Compound knowledge** - Each project makes the next easier

## Getting Help

- `/consult-expert shannon` - Claude Code questions
- `/consult-expert charles` - Strategic decisions
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
1. `/organize-project` - Create standard structure
2. `/organize-claude scaffold` - Create project CLAUDE.md
3. `/review-project quick` - Get baseline health check

Want me to run `/organize-project` now?
```
