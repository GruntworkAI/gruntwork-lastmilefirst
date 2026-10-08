"""Project organization and adapters share one required work-layout constant."""

import importlib.util
from pathlib import Path

from project_layout import CLAUDE_SUBDIRS, PROJECT_LAYOUT


def test_project_layout_matches_existing_canonical_structure(tmp_path):
    path = Path(__file__).resolve().parents[2] / "skills/organize-project/scripts/organize_project.py"
    spec = importlib.util.spec_from_file_location("organize_project_layout_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.CLAUDE_SUBDIRS is CLAUDE_SUBDIRS
    assert PROJECT_LAYOUT == (".claude/work/todos", ".claude/work/plans", ".claude/work/sessions",
                              ".claude/debt", ".claude/archive")
    assert module.check_structure(tmp_path)["missing_dirs"] == ["docs", ".claude", *PROJECT_LAYOUT]
