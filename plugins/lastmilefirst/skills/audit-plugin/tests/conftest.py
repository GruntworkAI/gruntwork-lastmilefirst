"""Pytest configuration for the audit-plugin skill.

Why this file exists: the skill ships as `scripts/audit_plugin.py` (not a
packaged module), and the plugin repo has no `pyproject.toml`. Without
this `sys.path.insert`, tests cannot `import audit_plugin`.

This is the first thing a contributor running `pytest tests/` from the
audit-plugin directory hits. Keeping the path insertion here — rather
than requiring every test file to do it — means test files stay clean
imports.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make `scripts/audit_plugin.py` importable as `audit_plugin`.
_SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))
