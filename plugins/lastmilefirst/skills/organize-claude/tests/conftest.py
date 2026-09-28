"""Pytest configuration for the organize-claude skill.

The skill ships as `scripts/*.py` (not a packaged module) and imports the
workspace layout loader from the hook scripts. The plugin repo has no
`pyproject.toml`, so these `sys.path` inserts make both importable.

Run with `pytest tests/` from the organize-claude directory. Tests build a fake
workspace under `tmp_path` and patch the config path, so the real
organize-claude config is never read or written.
"""

from __future__ import annotations

import sys
from pathlib import Path

_SKILLS = Path(__file__).resolve().parents[2]

for _path in (
    _SKILLS / "organize-claude" / "scripts",
    _SKILLS.parent / "hooks" / "scripts",
):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))
