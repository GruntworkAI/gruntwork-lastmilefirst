#!/usr/bin/env python3
"""
Project Archetypes

Defines the four project archetypes and their required CLAUDE.md sections.
Shared by organize-claude and review-claude as the single source of truth.
"""

import re
from pathlib import Path
from typing import Optional

# Canonical archetype list
VALID_ARCHETYPES = ["deployable", "usable", "referenceable", "experimental"]

# Human-readable descriptions for each archetype
ARCHETYPE_DESCRIPTIONS = {
    "deployable": "You deploy it somewhere (AWS, Vercel, etc.)",
    "usable": "You install, run, or invoke it (gems, CLIs, plugins, SDKs)",
    "referenceable": "You read and consult it (knowledge archives, docs, wisdom repos)",
    "experimental": "New project, shape TBD",
}

# Required sections per archetype: list of (header, description) tuples
# This is the single source of truth — templates echo these for self-documentation.
ARCHETYPE_SECTIONS: dict[str, list[tuple[str, str]]] = {
    "deployable": [
        ("## Development Environment", "Runtime setup, start commands"),
        ("## Infrastructure", "Cloud provider, region, account details"),
        ("### Cloud Details", "AWS/GCP region and account table"),
        ("### Terraform Workspaces", "Workspace to environment mapping"),
        ("## Deployment", "Deploy commands and verification"),
        ("## Gotchas", "Learned-the-hard-way issues table"),
        ("## Testing", "Test commands"),
    ],
    "usable": [
        ("## Development Environment", "Runtime setup, start commands"),
        ("## Installation", "How to install or add as dependency"),
        ("## Configuration", "Settings, env vars, config files"),
        ("## Testing", "Test commands"),
        ("## Publishing", "How to release or publish new versions"),
        ("## Gotchas", "Learned-the-hard-way issues table"),
    ],
    "referenceable": [
        ("## Content Structure", "How content is organized"),
        ("## How to Update", "Process for adding or modifying content"),
        ("## Gotchas", "Learned-the-hard-way issues table"),
    ],
    "experimental": [
        ("## Quick Commands", "Essential commands to get started"),
    ],
}

# Regex to detect archetype from CLAUDE.md content
_ARCHETYPE_PATTERN = re.compile(
    r"^##\s+Archetype:\s*(\w+)", re.MULTILINE | re.IGNORECASE
)


def detect_archetype(content: str) -> Optional[str]:
    """
    Detect archetype from CLAUDE.md content.
    Returns lowercase archetype name or None if not found/invalid.
    """
    match = _ARCHETYPE_PATTERN.search(content)
    if not match:
        return None
    value = match.group(1).lower()
    if value in VALID_ARCHETYPES:
        return value
    return None


def get_sections_for_archetype(archetype: str) -> list[tuple[str, str]]:
    """Get required sections for an archetype. Returns empty list for unknown archetypes."""
    return ARCHETYPE_SECTIONS.get(archetype.lower(), [])


def get_template_name_for_archetype(archetype: str) -> str:
    """Get template filename for an archetype."""
    return f"project-{archetype.lower()}.md.template"


def format_archetype_choices() -> str:
    """Format archetype choices for CLI help or user-facing output."""
    lines = []
    for name in VALID_ARCHETYPES:
        desc = ARCHETYPE_DESCRIPTIONS[name]
        lines.append(f"  {name.capitalize():15s} {desc}")
    return "\n".join(lines)


# --- Archetype inference from project directory ---

# File/directory signals that suggest a specific archetype.
# Each entry: (glob_pattern, archetype, weight)
# Higher total weight wins. Ties go to the first in VALID_ARCHETYPES order.
_INFERENCE_SIGNALS = [
    # Deployable signals
    ("**/terraform*", "deployable", 3),
    ("**/Dockerfile", "deployable", 2),
    ("**/docker-compose*", "deployable", 2),
    ("**/.terraform*", "deployable", 3),
    ("**/serverless.yml", "deployable", 3),
    ("**/cdk.json", "deployable", 3),
    ("**/vercel.json", "deployable", 2),
    ("**/fly.toml", "deployable", 2),
    ("**/Procfile", "deployable", 2),
    ("**/ecs-params.yml", "deployable", 3),
    # Usable signals
    ("**/setup.py", "usable", 3),
    ("**/setup.cfg", "usable", 2),
    ("**/pyproject.toml", "usable", 1),  # low weight — also used by deployable apps
    ("**/*.gemspec", "usable", 3),
    ("**/package.json", "usable", 1),  # low weight — universal
    ("**/.claude-plugin/plugin.json", "usable", 4),
    ("**/Cargo.toml", "usable", 1),
    ("**/go.mod", "usable", 1),
    # Referenceable signals
    ("**/wisdom/**/*.md", "referenceable", 3),
    ("**/knowledge/**/*.md", "referenceable", 3),
    ("**/docs/**/*.md", "referenceable", 1),
]


def infer_archetype(project_path: Path) -> tuple[Optional[str], dict[str, int]]:
    """
    Infer the most likely archetype from a project's file structure.

    Returns (inferred_archetype, scores_dict).
    scores_dict maps archetype -> total weight from matched signals.
    Returns (None, {}) if no signals found.
    """
    if not project_path.is_dir():
        return None, {}

    scores: dict[str, int] = {}

    for pattern, archetype, weight in _INFERENCE_SIGNALS:
        # Use a bounded glob — only check top 2 levels for speed, except ** patterns
        matches = list(project_path.glob(pattern))
        if matches:
            scores[archetype] = scores.get(archetype, 0) + weight

    if not scores:
        return None, {}

    # Pick the highest score; on tie, follow VALID_ARCHETYPES order
    max_score = max(scores.values())
    for archetype in VALID_ARCHETYPES:
        if scores.get(archetype, 0) == max_score:
            return archetype, scores

    return None, scores


def infer_archetype_from_content(content: str) -> Optional[str]:
    """
    Infer archetype from CLAUDE.md content when no archetype line is declared.
    Looks for keywords that suggest the project type.
    """
    lower = content.lower()

    # Strong deployment signals in content
    deploy_keywords = ["terraform", "aws", "deploy", "infrastructure", "ecs", "lambda", "vercel"]
    deploy_score = sum(1 for kw in deploy_keywords if kw in lower)

    # Strong usable signals
    usable_keywords = ["install", "plugin", "sdk", "gem ", "package", "publish", "cli"]
    usable_score = sum(1 for kw in usable_keywords if kw in lower)

    # Referenceable signals
    ref_keywords = ["knowledge", "archive", "reference", "documentation", "wisdom"]
    ref_score = sum(1 for kw in ref_keywords if kw in lower)

    scores = {
        "deployable": deploy_score,
        "usable": usable_score,
        "referenceable": ref_score,
    }

    max_score = max(scores.values())
    if max_score == 0:
        return None

    for archetype in VALID_ARCHETYPES:
        if scores.get(archetype, 0) == max_score:
            return archetype

    return None
