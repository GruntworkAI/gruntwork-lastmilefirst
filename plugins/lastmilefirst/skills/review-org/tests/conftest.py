"""Pytest configuration for the review-org skill.

Why this file exists: the skill ships as `scripts/review_org.py` (not a
packaged module), and it imports `overwatch` from the hook scripts and
`archetypes` from the sibling organize-claude skill. The plugin repo has no
`pyproject.toml`, so without these `sys.path` inserts tests cannot import
any of them.

Mirrors `skills/review-claude/tests/conftest.py`. Run with `pytest tests/`
from the review-org directory. Tests build a fake org and a fake state file
under `tmp_path` and never read or write the real Overwatch state.
"""

from __future__ import annotations

import sys
from pathlib import Path

_SKILLS = Path(__file__).resolve().parents[2]

for _path in (
    _SKILLS / "review-org" / "scripts",
    _SKILLS / "organize-claude" / "scripts",
    _SKILLS.parent / "hooks" / "scripts",
):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))
