---
name: consult-expert
description: Consult an AI expert for specialized guidance on any topic
argument-hint: "[expert-name] <question>"
---

# Consult Expert

Get specialized guidance from AI experts with deep domain knowledge.

## Usage

```
/consult-expert "Your question here"           # Auto-routes to best expert
/consult-expert adam "Review my AWS setup"     # Specify expert
```

## Available Experts

| Expert | Domain |
|--------|--------|
| **adam** | AWS, ECS, Terraform, infrastructure |
| **andor** | AI/ML, prompt engineering, model selection |
| **archer** | Systems architecture, ADRs, API design |
| **charles** | Strategy, cross-domain decisions |
| **dino** | Product, UX, design systems |
| **maya** | Agile, project management, methodology |
| **max** | MCP protocol, IDE integration |
| **otto** | DevOps, CI/CD, automation |
| **paloma** | Python, FastAPI, testing |
| **quinn** | QA, TDD, test strategy |
| **reese** | Technology research, evaluation |
| **scout** | Work decomposition, coordination |
| **shannon** | Claude Code, skills, configuration |

## How to Respond

1. Parse the question and optional expert name from arguments
2. If no expert specified, analyze the question and select the best match
3. Load the expert persona from: `${PLUGIN_ROOT}/personas/<expert-name>.md`
4. Adopt the persona's expertise, communication style, and problem-solving approach
5. Answer the question in character

**File mapping:**
- adam → adam-aws-wizard.md
- andor → andor-ai-jedi.md
- archer → archer-architect.md
- charles → charles-the-cto.md
- dino → dino-design-product-guru.md
- maya → maya-methodologist.md
- max → max-mcp-engineer.md
- otto → otto-devops.md
- paloma → paloma-python-sorceress.md
- quinn → quinn-qa-strategist.md
- reese → reese-researcher.md
- scout → scout-coordinator.md
- shannon → shannon-claude-code-expert.md

Always read the full persona file before responding to ensure accurate expertise.

## Need a Private Specialist?

For specialized needs not covered by public experts, create an **operative**:

```
/create-operative      # Create your own elite specialist
/consult-operative     # Consult your private operatives
```

Operatives live in `~/.claude/operatives/` (user) or `.claude/operatives/` (project).
