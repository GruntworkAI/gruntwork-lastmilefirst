# Last Mile First

> Build the delivery infrastructure before the product.

Claude Code plugin for setting up the "last mile" of Claude-assisted development: environment configuration, project structure, quality gates, and expert access via parallel AI agents.

## Philosophy

Most developers build features first and figure out deployment, configuration, and quality processes later. This plugin inverts that: set up the infrastructure for smooth delivery *first*, then build.

- Configure your Claude environment before coding
- Structure your project before filling it
- Establish quality gates before shipping
- Set up expert access before you're stuck

## Concepts

### Tiered CLAUDE.md

Claude Code reads `CLAUDE.md` files for project context. This plugin structures them in three tiers:

```
~/Code/CLAUDE.md              # Workspace-level: your preferences, global patterns
~/Code/mycompany/CLAUDE.md    # Org-level: team standards, shared conventions
~/Code/mycompany/app/CLAUDE.md # Project-level: specific context, commands, gotchas
```

**Why "workspace"?** The top level isn't your home directory—that's too broad. Your workspace (e.g., `~/Code/`) is the broadest *safe* scope: everything you let Claude touch. Workspace preferences apply to all your development. Org standards apply to team projects. Project specifics stay local.

**Why tiers?** Lower levels inherit from higher levels. No duplication, clear override path. Your teammate's workspace preferences don't pollute your projects; your shared org standards do.

### Project Structure

The plugin enforces a standard structure that both humans and Claude can navigate:

```
project/
├── CLAUDE.md           # Project context (stays at root)
├── README.md           # Project overview (stays at root)
├── docs/               # Static reference documentation
│   ├── architecture.md
│   └── deployment.md
└── .claude/            # Working artifacts (ephemeral)
    ├── work/
    │   ├── todos/      # Active tasks
    │   ├── plans/      # Implementation plans
    │   └── sessions/   # Session notes, reviews
    ├── debt/           # Technical debt tracking
    └── archive/        # Auto-archived old items
```

**Why `docs/` vs `.claude/`?** Documentation is permanent reference—architecture decisions, deployment guides. Working artifacts are ephemeral—today's todos, this sprint's plan. Mixing them creates clutter and confusion. Separating them keeps both clean.

**Why `.claude/`?** It's Claude-optimized. Consistent structure means Claude finds context instantly. Session notes persist across conversations. Todos don't get lost in random markdown files.

**Why human-readable markdown?** Plans, session notes, and todos live in `.claude/work/` as markdown files—not databases, not proprietary formats. This matters when multiple team members work on the same project:

- Your teammate's Claude session can read your session notes
- You can review plans Claude drafted before approving them
- Handoffs between developers (or between Claude sessions) have context
- Everything is git-tracked and diffable

The structure is Claude-optimized for fast context retrieval *and* human-readable for collaboration and review.

### The Mental Model

| Component | What It Is | When to Use |
|-----------|------------|-------------|
| **CLAUDE.md** | Project context and instructions | Always—Claude reads this automatically |
| **Skills** | Reusable workflows with documentation | Complex multi-step tasks (`/organize-project`) |
| **Agents** | Expert personas via Task tool | Parallel consultation, specialized knowledge |
| **Operatives** | Your private expert personas | Proprietary knowledge, company-specific patterns |

**Why all four?** Different problems need different tools:
- CLAUDE.md gives Claude *passive* context it always has
- Skills give Claude *active* workflows it can execute
- Agents give Claude *specialized expertise* to consult
- Operatives give *you* a way to extend the system with private knowledge

They compound: CLAUDE.md tells Claude about your project, skills organize it, agents provide expertise, and operatives add your secret sauce.

### The PARC Workflow

Claude follows the PARC workflow by default, scaling ceremony to task complexity:

```
Plan → Allocate → Review → Compound
```

| Step | Purpose | Trivial Task | Complex Task |
|------|---------|--------------|--------------|
| **Plan** | Think before doing | Skip | Full planning, experts |
| **Allocate** | Delegate to agents | Direct execution | Orchestrate multiple agents |
| **Review** | Verify correctness | Quick check | Tests, reviewers, E2E |
| **Compound** | Capture learnings | Skip | Prompt for wisdom/operative |

**The key tension:** YAGNI vs YAGWYDI
- **YAGNI** (You Aren't Gonna Need It) - Don't overbuild features
- **YAGWYDI** (You're Gonna Wish You Did It) - Do invest in infrastructure

PARC applies YAGNI to features and YAGWYDI to scaffolding. Don't add speculative functionality, but do capture patterns and build operatives that compound future value.

For critical work, use `/run-strict-parc` to enforce explicit gates between phases.

## Installation

Run these commands inside a Claude Code session:

```bash
# 1. Add the Gruntwork marketplace (one time, interactive)
/plugin marketplace add
# When prompted, enter: GruntworkAI/gruntwork-marketplace

# 2. Install the plugin
/plugin install lastmilefirst@gruntwork-marketplace

# 3. Verify installation
/plugin list
```

### Updating

```bash
# Refresh marketplace first (fetches latest versions)
/plugin marketplace update gruntwork-marketplace

# Then update the plugin
/plugin update lastmilefirst@gruntwork-marketplace
```

### Local Development

```bash
claude --plugin-dir /path/to/gruntwork-marketplace/plugins/lastmilefirst
```

## Platform Requirements

| Platform | Support | Notes |
|----------|---------|-------|
| **macOS** | Full | Primary development platform |
| **Linux** | Full | All features supported |
| **WSL/WSL2** | Full | All features supported |
| **Windows (native)** | Full | Python 3.9+ required |

### Prerequisites

- **Python 3.9+** - Required for Overwatch hooks
- **Git** - For repository status checks

## Commands

All commands use the `run-` prefix for discoverability via autocomplete.

| Command | Purpose |
|---------|---------|
| `/run-get-started` | Quick orientation and available commands |
| `/run-organize-orgs` | Set up org infrastructure (org.json, operatives, wisdom repos) |
| `/run-organize-claude` | Audit and scaffold CLAUDE.md hierarchy (user/org/project) |
| `/run-organize-project` | Enforce consistent project structure (docs/, .claude/) |
| `/run-review-claude` | Review CLAUDE.md for gaps, suggest additions |
| `/run-review-project` | Combined docs + work artifact review |
| `/run-review-docs` | Review docs/ for staleness, gaps, duplication |
| `/run-review-work` | Review .claude/work/ for stale items, archive candidates |
| `/run-consult-expert` | Consult public AI expert personas |
| `/run-consult-operative` | Consult your private operatives |
| `/run-create-operative` | Create a new private operative |
| `/run-search-wisdom` | Search org stack-wisdom for patterns and insights |
| `/run-add-wisdom` | Capture hard-won lessons to stack-wisdom |
| `/run-strict-parc` | Enforce strict PARC workflow with explicit gates |
| `/run-overwatch` | Check status and manage proactive monitoring |
| `/run-plugin-inventory` | Show installed plugins with versions and usage stats |
| `/run-todos-summary` | Aggregate todos across all projects in an org |

## Public Expert Agents

The plugin includes 13 AI expert personas you can consult when you need specialized knowledge. These are **public experts** - built into the plugin and available to everyone.

### When to Use Experts

- Claude becomes tunnel-visioned on one stack → call a specialist
- You need domain knowledge outside your expertise → consult an expert
- Complex decisions need strategic input → coordinate with Charles
- Not sure who to ask → start with Scout, who routes to the right expert

### Founding Team

The core team with deep expertise in their domains:

| Expert | Role | Personality |
|--------|------|-------------|
| **Charles** | CTO / Strategic Coordinator | Systems thinker, orchestrates multi-domain problems. Start here when unsure. "Each piece of work should make the next piece easier." |
| **Adam** | AWS Infrastructure Wizard | Terraform, ECS/Fargate, deployment pipelines. Cost-conscious, security-aware. |
| **Paloma** | Full-Stack Sorceress | Python/FastAPI + React/TypeScript. Known for elegant, type-safe solutions. Also handles state management issues. |
| **Andor** | AI Systems Architect | Model selection, prompt engineering, AI integration patterns. "The AI Jedi." |
| **Dino** | Product & Design Guru | UX strategy, user validation, design systems. Bridges tech and user needs. |
| **Max** | MCP Protocol Engineer | Model Context Protocol, IDE integration, tooling automation. |
| **Shannon** | Claude Code Expert | CLAUDE.md optimization, skills system, context management. |

### Key Hires

Specialists who extend the team's capabilities:

| Expert | Role | Personality |
|--------|------|-------------|
| **Scout** | Multi-Agent Coordinator | Routes problems to the right expert. Start here when you're not sure who to ask. |
| **Maya** | Development Methodologist | Agile, project planning, process design. Keeps projects on track. |
| **Archer** | System Architect | ADRs, API design, database schema. Big-picture technical decisions. |
| **Quinn** | QA Strategist | Test strategy, TDD, acceptance criteria. Quality advocate. |
| **Reese** | Technology Researcher | Evaluation, comparison, feasibility studies. Evidence-based recommendations. |
| **Otto** | DevOps Engineer | CI/CD, GitHub Actions, deployment automation. Pipeline specialist. |

### Using Experts

```bash
# Interactive - shows available experts
/run-consult-expert

# Direct consultation
/run-consult-expert paloma "Why is my React Query cache stale after mutation?"
/run-consult-expert adam "Review my Terraform module for ECS"
/run-consult-expert charles "Should we use Lambda or ECS for this service?"
```

### Experts via Task Tool (Parallel Agents)

For complex problems, invoke experts as parallel agents:

```
Task: consult-paloma to review the authentication flow
Task: consult-adam to check the infrastructure cost implications
Task: scout-coordinator to analyze this cross-domain problem
```

## Private Operatives

Operatives are **private AI personas** you create for specialized needs. They're the extension point that makes this plugin *yours*.

### Why Private?

The public experts handle general domain knowledge—Python best practices, AWS patterns, architecture principles. But your real competitive advantage isn't general knowledge. It's:

- **Your company's coding standards** that took years to develop
- **Your client's domain** that you've learned through hard-won experience
- **Your proprietary methods** that differentiate your work
- **Confidential knowledge** that can't be shared publicly

Operatives keep this knowledge private while making it accessible through the same interface as public experts. Your secret sauce stays secret.

### Extending the Plugin

Operatives are how you extend lastmilefirst for your specific needs without forking the plugin:

- **Company operatives** - Shared standards across your team (`~/.claude/operatives/`)
- **Project operatives** - Client-specific knowledge (`.claude/operatives/`)
- **Personal operatives** - Your own accumulated expertise

When the public experts don't cover your domain, create an operative. When your company has specific patterns, encode them in an operative. When you're working with a client's proprietary system, build an operative that knows it.

### Experts vs Operatives

| Aspect | Public Experts | Private Operatives |
|--------|----------------|-------------------|
| **Source** | Built into plugin | You create them |
| **Visibility** | Same for all users | Only visible to you |
| **Knowledge** | General domain expertise | Your proprietary knowledge |
| **Updates** | Plugin maintainers | You control them |
| **Examples** | Paloma (Python), Adam (AWS) | Your company's standards, your client's domain, your methods |

### Creating Operatives

```bash
/run-create-operative           # Interactive creation wizard
/run-create-operative razor     # Create operative named "razor"
```

### Using Operatives

```bash
/run-consult-operative                    # List your operatives
/run-consult-operative razor "question"   # Consult a specific operative
```

### Operative Storage

Operatives are markdown files stored at three levels:

```
.claude/operatives/              # Project-level (specific to one project)
[org]/[org]-operatives/          # Org-level (shared with team, git-tracked)
~/.claude/operatives/            # User-level (your personal operatives)
```

**Lookup precedence:** Project → Org → User (first match wins)

### Recommended Structure

```
~/Code/                          # Workspace
├── CLAUDE.md                    # Workspace preferences
├── personal/                    # Personal projects and experiments
│   ├── CLAUDE.md                # Personal standards
│   ├── .claude/org.json         # Org config
│   ├── personal-operatives/     # Your personal specialists
│   └── [projects]/
├── work/                        # Primary professional org
│   ├── CLAUDE.md                # Team standards
│   ├── .claude/org.json
│   ├── work-operatives/         # Team operatives (git repo)
│   │   ├── compliance-bot.md
│   │   └── deploy-master.md
│   └── [projects]/
└── work-2/                      # Second work org (e.g., different client)
    ├── CLAUDE.md                # Client-specific standards
    ├── .claude/org.json
    └── work-2-operatives/       # Client-specific operatives
```

You can have multiple work orgs for different clients, companies, or contexts.

### Org Configuration

Each org can have a `.claude/org.json` for custom settings:

```json
{
  "name": "work",
  "operatives": {
    "repo": "work-operatives"
  },
  "stack_wisdom": {
    "repo": "work-stack-wisdom"
  }
}
```

If no config exists, the plugin uses conventions: `[org]-operatives/` and `[org]-stack-wisdom/`.

## Stack-Wisdom

Stack-wisdom is your org's institutional insight - patterns that took time to learn, captured so future sessions (and teammates) benefit immediately.

### Wisdom vs. Knowledge

| Wisdom | Knowledge |
|--------|-----------|
| Patterns and practices | Facts and data |
| Lessons learned | Reference documentation |
| Gotchas and pitfalls | API specifications |
| Insights from experience | Datasets and configs |

### Three Types of Wisdom

| Type | Location | Purpose |
|------|----------|---------|
| **Patterns** | `stack-wisdom/` | Solutions to recurring problems |
| **Circuit Breakers** | `circuit-breakers/` | Detection for critical failures |
| **Triggers** | `triggers/` | Keywords that signal specific issues |

### Using Stack-Wisdom

```bash
# Search for relevant wisdom
/run-search-wisdom terraform workspace
/run-search-wisdom "resource already exists"

# Add new wisdom after solving a hard problem
/run-add-wisdom
```

### The Compound Loop

1. **Encounter a problem** - Something takes 30+ minutes to debug
2. **Solve it** - With or without expert help
3. **Capture the insight** - `/run-add-wisdom` to add the pattern
4. **Future benefit** - Next time, `/run-search-wisdom` finds it instantly

This is the "compound" in compound engineering - every hard-won insight becomes future leverage.

### Stack-Wisdom Structure

```
[org]-stack-wisdom/
├── stack-wisdom/           # Patterns and solutions
│   ├── terraform-workspace-check.md
│   └── python-venv-corruption.md
├── circuit-breakers/       # Critical failure detection
│   └── production-deploy-guard.md
└── triggers/               # Proactive detection keywords
    └── debugging-loop-signals.md
```

### Operative Template

See `templates/operative.md` for the template. Operatives can inherit from public experts:

```markdown
---
name: razor
title: Security Penetration Specialist
base: paloma    # Inherits Python expertise from Paloma
---

# Razor - Security Specialist

Your custom persona definition here...
```

## Structure

```
lastmilefirst/
├── .claude-plugin/
│   └── plugin.json         # Plugin manifest
├── commands/               # Slash commands (for autocomplete)
│   └── run-*.md            # All prefixed with run-
├── skills/                 # Full skill implementations
│   ├── organize-orgs/
│   ├── organize-claude/
│   ├── organize-project/
│   ├── review-*/
│   ├── consult-expert/
│   ├── consult-operative/
│   ├── create-operative/
│   ├── search-wisdom/
│   ├── add-wisdom/
│   ├── parc/
│   ├── strict-parc/
│   ├── overwatch/
│   ├── plugin-inventory/
│   ├── todos-summary/
│   └── get-started/
├── agents/                 # Parallel expert agents (via Task tool)
│   ├── scout-coordinator.md
│   └── consult-*.md
├── personas/               # Expert persona definitions
│   └── *.md
├── templates/              # Templates for creating new items
│   ├── operative.md
│   ├── org.json
│   ├── wisdom-pattern.md
│   ├── operatives-readme.md
│   └── stack-wisdom-readme.md
├── hooks/                  # Overwatch automation
│   └── scripts/
└── README.md
```

## Usage Examples

### Commands (inline)
```bash
/run-get-started              # See what's available
/run-organize-claude          # Audit CLAUDE.md hierarchy
/run-review-project           # Review project documentation
/run-consult-expert           # Interactive expert consultation
/run-consult-operative razor  # Use your private operative
/run-plugin-inventory         # Check installed plugins and usage
/run-todos-summary            # See todos across all projects
```

### Agents (parallel via Task tool)
```
# Single expert consultation
Task: consult-adam for AWS deployment help

# Multi-agent orchestration
Task: scout-coordinator to analyze cross-domain problem
```

## Philosophy

For a deeper exploration of the ideas behind this plugin, see [Last Mile First: Fast Alone, Far Together](https://outsideshot.substack.com/p/last-mile-first-fast-alone-far-together).

## Related

- [gruntwork-stack-wisdom](https://github.com/GruntworkAI/gruntwork-stack-wisdom) - Patterns and circuit breakers
- [gruntwork-ai-team](https://github.com/GruntworkAI/gruntwork-ai-team) - AI expert personas
- [gruntwork-synthasaurus](https://github.com/GruntworkAI/gruntwork-synthasaurus) - MCP server for proactive assistance
