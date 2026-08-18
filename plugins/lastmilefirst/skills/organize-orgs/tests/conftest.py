"""Pytest configuration for the organize-orgs scripts.

The skill ships as `scripts/*.py` (not a packaged module) and the plugin repo
has no `pyproject.toml`, so this makes `import check_identity` resolve when
running `pytest tests/` from the skill directory.
"""

from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))
