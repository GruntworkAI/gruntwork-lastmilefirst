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

### Cross-Platform Implementation

Overwatch hooks are implemented in Python for full cross-platform support:

| Feature | Mac/Linux/Windows |
|---------|-------------------|
| Session tracking | Full |
| Usage statistics | Full |
| Plugin update checks | Full |
| State file locking | Full (`fcntl`/`msvcrt`) |

The Python implementation automatically uses the appropriate file locking mechanism:
- Unix (macOS/Linux): `fcntl.flock()`
- Windows: `msvcrt.locking()`

## Commands

All commands use the `run-` prefix for discoverability via autocomplete.

| Command | Purpose |
|---------|---------|
| `/run-get-started` | Quick orientation and available commands |
| `/run-organize-claude` | Audit and scaffold CLAUDE.md hierarchy (user/org/project) |
| `/run-organize-project` | Enforce consistent project structure (docs/, .claude/) |
| `/run-review-claude` | Review CLAUDE.md for gaps, suggest additions |
| `/run-review-project` | Combined docs + work artifact review |
| `/run-review-docs` | Review docs/ for staleness, gaps, duplication |
| `/run-review-work` | Review .claude/work/ for stale items, archive candidates |
| `/run-consult-expert` | Consult public AI expert personas |
| `/run-consult-operative` | Consult your private operatives |
| `/run-create-operative` | Create a new private operative |
| `/run-overwatch` | Check status and manage proactive monitoring |

## Operatives

Operatives are **private AI personas** you create for specialized needs - competitive advantages, domain-specific expertise, or project-specific knowledge that you don't want public.

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

```
~/.claude/operatives/       # User-level (available in all projects)
.claude/operatives/         # Project-level (specific to one project)
```

### Inheritance

Operatives can inherit from public experts:

```markdown
---
name: razor
title: Security Penetration Specialist
base: paloma    # Inherits Python expertise from Paloma
---
```

## Public Expert Agents

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
│   └── plugin.json         # Plugin manifest
├── commands/               # Minimal slash commands (for autocomplete)
│   └── run-*.md            # All prefixed with run-
├── skills/                 # Full skill implementations
│   ├── organize-claude/
│   ├── organize-project/
│   ├── review-*/
│   ├── consult-expert/
│   ├── consult-operative/
│   ├── create-operative/
│   ├── overwatch/
│   └── get-started/
├── agents/                 # Parallel expert agents (via Task tool)
│   ├── scout-coordinator.md
│   └── consult-*.md
├── personas/               # Expert persona definitions
│   └── *.md
├── templates/              # Templates for creating new items
│   └── operative.md
└── README.md
```

## Usage Examples

### Commands (inline)
```bash
/run-get-started             # See what's available
/run-organize-claude         # Audit CLAUDE.md hierarchy
/run-review-project          # Review project documentation
/run-consult-expert          # Interactive expert consultation
/run-consult-operative razor # Use your private operative
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
