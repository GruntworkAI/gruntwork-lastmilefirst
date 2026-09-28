"""Pytest configuration for the todos-summary skill.

The skill ships as `scripts/*.py` (not a packaged module) and imports the
workspace layout loader from the hook scripts. The plugin repo has no
`pyproject.toml`, so these `sys.path` inserts make both importable.

Run with `pytest tests/` from the todos-summary directory. Tests build a fake
workspace under `tmp_path` and never read the real workspace config or cache.
"""

from __future__ import annotations

import sys
from pathlib import Path

_SKILLS = Path(__file__).resolve().parents[2]

for _path in (
    _SKILLS / "todos-summary" / "scripts",
    _SKILLS.parent / "hooks" / "scripts",
):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))
