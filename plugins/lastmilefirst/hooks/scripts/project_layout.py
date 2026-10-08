"""Canonical project work directories, without filesystem side effects."""

CLAUDE_SUBDIRS = ["work/todos", "work/plans", "work/sessions", "debt", "archive"]
PROJECT_LAYOUT = tuple(f".claude/{subdir}" for subdir in CLAUDE_SUBDIRS)
