# Last Mile First

> Build the delivery infrastructure before the product.

Claude Code plugin for setting up the "last mile" of Claude-assisted development: environment configuration, project structure, quality gates, and expert access via parallel AI agents.

## Philosophy

Most developers build features first and figure out deployment, configuration, and quality processes later. This plugin inverts that: set up the infrastructure for smooth delivery *first*, then build.

- Configure your Claude environment before coding
- Structure your project before filling it
- Establish quality gates before shipping
- Set up expert access before you're stuck

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

## Skills

| Skill | Purpose |
|-------|---------|
| `organize-claude` | Audit and scaffold CLAUDE.md hierarchy (user/org/project) |
| `organize-project` | Enforce consistent project structure (docs/, .claude/) |
| `review-claude` | Review CLAUDE.md for gaps, suggest additions |
| `review-project` | Combined docs + work artifact review |
| `review-docs` | Review docs/ for staleness, gaps, duplication |
| `review-work` | Review .claude/work/ for stale items, archive candidates |
| `consult-expert` | Consult AI expert personas for specialized guidance |

## Agents

Parallel AI expert agents for complex multi-domain problems.

### Founding Team
| Agent | Domain |
|-------|--------|
| `consult-charles` | Strategic leadership, cross-domain coordination |
| `consult-adam` | AWS infrastructure, Terraform, deployment |
| `consult-paloma` | Python/React development, code quality |
| `consult-andor` | AI systems, prompt engineering |
| `consult-dino` | Product strategy, UX design |
| `consult-max` | MCP protocol, IDE tooling |
| `consult-shannon` | Claude Code optimization |

### Key Hires
| Agent | Domain |
|-------|--------|
| `consult-maya` | Development methodology, project planning |
| `consult-archer` | System architecture, ADRs |
| `scout-coordinator` | Multi-agent orchestration |
| `consult-quinn` | QA strategy, TDD |
| `consult-reese` | Technology research |
| `consult-otto` | CI/CD, DevOps automation |

## Structure

```
lastmilefirst/
├── .claude-plugin/
│   └── plugin.json      # Plugin manifest
├── skills/              # Repeatable processes (on-demand)
│   ├── organize-claude/
│   ├── organize-project/
│   ├── review-*/
│   └── consult-expert/
├── agents/              # Parallel expert agents (via Task tool)
│   ├── scout-coordinator.md
│   └── consult-*.md
└── README.md
```

## Usage

### Skills (inline)
```
/organize-claude     # Audit CLAUDE.md hierarchy
/review-project      # Review project documentation
/consult-expert      # Interactive expert consultation
```

### Agents (parallel via Task tool)
```
# Single expert consultation
Task: consult-adam for AWS deployment help

# Multi-agent orchestration
Task: scout-coordinator to analyze cross-domain problem
```

## Related

- [gruntwork-stack-wisdom](https://github.com/GruntworkAI/gruntwork-stack-wisdom) - Patterns and circuit breakers
- [gruntwork-ai-team](https://github.com/GruntworkAI/gruntwork-ai-team) - AI expert personas
- [gruntwork-synthasaurus](https://github.com/GruntworkAI/gruntwork-synthasaurus) - MCP server for proactive assistance
