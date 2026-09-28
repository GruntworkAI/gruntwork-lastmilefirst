"""Pytest configuration for the review-claude skill.

Why this file exists: the skill ships as `scripts/review_claude.py` (not a
packaged module) and imports `archetypes` from the sibling organize-claude
skill and `workspace_types` from the hook scripts, and the plugin repo has no
`pyproject.toml`. Without these `sys.path` inserts, tests cannot import them.

Mirrors `skills/audit-plugin/tests/conftest.py` — path setup lives here so
test files stay clean imports.

Run with `pytest tests/` from the review-claude directory.
"""

from __future__ import annotations

import sys
from pathlib import Path

_SKILLS = Path(__file__).resolve().parents[2]

for _path in (
    _SKILLS / "review-claude" / "scripts",
    _SKILLS / "organize-claude" / "scripts",
    _SKILLS.parent / "hooks" / "scripts",
):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))
