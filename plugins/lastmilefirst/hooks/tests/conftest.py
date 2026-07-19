"""Pytest configuration for the Overwatch hook scripts.

The hooks ship as `scripts/*.py` (not a packaged module) and the plugin repo
has no `pyproject.toml`, so this makes `import overwatch` / `import session_start`
resolve when running `pytest tests/` from the hooks directory.
"""

from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))
