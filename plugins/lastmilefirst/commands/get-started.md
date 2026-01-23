---
name: get-started
description: Learn how to use the lastmilefirst plugin - quick orientation and available commands
argument-hint: "[optional: topic]"
---

# Get Started with Last Mile First

Welcome! This plugin provides AI expert agents, project organization tools, and review workflows.

## Quick Start

**Most common commands:**

| Command | What it does |
|---------|-------------|
| `/consult-expert` | Ask an AI expert for specialized guidance |
| `/organize-project` | Set up standard project structure |
| `/organize-claude` | Audit and scaffold CLAUDE.md files |
| `/review-work` | Review todos, plans, sessions for hygiene |

## The AI Expert Team

Consult specialists with deep domain knowledge:

```
/consult-expert "How should I structure my ECS deployment?"
/consult-expert adam "Review my Terraform module"
/consult-expert shannon "Help me optimize my CLAUDE.md"
```

**Available experts:**
- **adam** - AWS infrastructure, ECS, Terraform, deployment
- **andor** - AI/ML architecture, prompt engineering
- **archer** - Systems architecture, ADRs, API design
- **charles** - Strategic decisions, cross-domain coordination
- **dino** - Product strategy, UX design
- **maya** - Agile methodology, project management
- **max** - MCP protocol, IDE integration
- **otto** - DevOps, CI/CD, automation
- **paloma** - Python development, FastAPI, testing
- **quinn** - QA strategy, TDD, test automation
- **reese** - Technology research, evaluation
- **scout** - Work decomposition, coordination
- **shannon** - Claude Code optimization, skills, configuration

## Organization Commands

**Set up your workspace:**

```
/organize-project          # Create standard project structure
/organize-claude           # Audit CLAUDE.md hierarchy
```

## Review Commands

**Keep your project healthy:**

```
/review-work              # Check todos, plans, sessions
/review-docs              # Audit documentation quality
/review-project           # Overall project health check
/review-claude            # Validate Claude configuration
```

## Operatives - Your Private Elite Team

Create private specialists for competitive advantage:

```
/create-operative              # Create a new operative
/consult-operative razor       # Consult your operative
```

**Operatives vs Experts:**
| Aspect | Experts | Operatives |
|--------|---------|------------|
| Source | Public (marketplace) | Private (yours) |
| Scope | Generic domain expertise | Your specialized needs |
| Location | Plugin | `~/.claude/operatives/` or `.claude/operatives/` |

Create operatives for:
- Competitive advantages you don't want public
- Project-specific specialists
- Domain experts for your industry
- Experimental persona designs

## Philosophy: Last Mile First

This plugin embodies the "Last Mile First" methodology:

1. **Start with the end** - Define what "done" looks like before starting
2. **Expert consultation** - Get specialized guidance early
3. **Organized workspace** - Structure enables velocity
4. **Regular reviews** - Catch drift before it compounds
5. **Elite operatives** - Build your private advantage

## Overwatch - Proactive Monitoring

The plugin includes an overwatch system that automatically:
- Alerts you to uncommitted changes at session start
- Reminds you when it's been a while since `/review-project`
- Suggests committing when you've made changes
- Checks for plugin updates weekly

Check status anytime: `/overwatch`

## Need Help?

- `/consult-expert shannon "How do I..."` - Claude Code questions
- `/consult-expert charles "Should I..."` - Strategic decisions
- `/overwatch` - Check what needs attention
- Check the README: `~/.claude/plugins/cache/gruntwork-marketplace/lastmilefirst/*/README.md`

**Now try:** `/consult-expert "What should I work on first?"`
