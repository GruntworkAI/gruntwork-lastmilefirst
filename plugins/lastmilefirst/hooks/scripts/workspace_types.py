#!/usr/bin/env python3
"""
Workspace layout: which directories under an org are projects.

The workspace is `<workspace>/<org>/<project>`, with one optional tier in
between. A directory directly inside an org that carries a `.claude-workspace`
marker with `type: client` is a container for one counterparty: its non-hidden
children are projects, and it is not one itself. So a project lives at either

    <workspace>/<org>/<project>             key "org/project"
    <workspace>/<org>/<client>/<project>    key "org/client/project"

The key is the path relative to the workspace. Three-part keys cannot collide
with two-part keys, so adding a container never re-keys a flat project.

Rules (plan 2026-09-28-001, D1 to D6):

- `type: client` is only recognized one level inside an org. A marker at the
  top level does nothing; a client that is a whole org is an ordinary org.
- One level only. A container inside a container is yielded as a project,
  with a note the caller prints.
- A container must not carry `.claude/org.json`. It is still treated as a
  container, and its first child carries a defect string the caller surfaces
  as an error.
- The loader never filters. Callers keep their own filters (a `.git` for the
  scanner, a `todos/` for todos-summary).

The marker parser lives in organize-orgs/scripts/check_identity.py, because the
pre-commit hook must stay stdlib-only and self-contained. This module imports
it rather than copying it.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Iterable, Iterator, NamedTuple, Optional, Tuple

_ORGANIZE_ORGS_DIR = Path(__file__).resolve().parent.parent.parent / "skills" / "organize-orgs" / "scripts"
if str(_ORGANIZE_ORGS_DIR) not in sys.path:
    sys.path.insert(0, str(_ORGANIZE_ORGS_DIR))

from check_identity import (  # noqa: E402
    UNGOVERNED_TYPES,
    WORKSPACE_MARKER,
    workspace_type,
)

__all__ = [
    "CONTAINER_TYPES",
    "UNGOVERNED_TYPES",
    "WORKSPACE_MARKER",
    "Context",
    "Project",
    "is_container",
    "iter_projects",
    "project_key",
    "resolve",
    "workspace_type",
]

CONTAINER_TYPES = {"client"}


class Project(NamedTuple):
    """One project directory found under an org."""

    path: Path
    key_parts: Tuple[str, ...]      # ("org", "project") or ("org", "client", "project")
    client: Optional[str] = None    # container directory name when nested
    note: Optional[str] = None      # something the caller should print, not an error
    defect: Optional[str] = None    # a misconfiguration the caller surfaces as an error

    @property
    def key(self) -> str:
        """State key: the path relative to the workspace."""
        return "/".join(self.key_parts)

    @property
    def label(self) -> str:
        """Name within the org: `project`, or `client/project` when nested."""
        return "/".join(self.key_parts[1:])


class Context(NamedTuple):
    """Where a path sits in the workspace."""

    org: Optional[str] = None
    client: Optional[str] = None
    project: Optional[str] = None   # project directory name
    key: Optional[str] = None       # state key, e.g. "org/client/project"


def is_container(directory: Path) -> bool:
    """True when the directory carries a marker of a container type.

    Depth is the caller's business: this answers only what the marker says.
    """
    return directory.is_dir() and workspace_type(directory) in CONTAINER_TYPES


def _children(directory: Path) -> list:
    try:
        return sorted(
            c for c in directory.iterdir()
            if c.is_dir() and not c.name.startswith(".")
        )
    except OSError:
        return []


def iter_projects(org_dir: Path) -> Iterator[Project]:
    """Every project directory under an org, descending one level through containers."""
    org = org_dir.name
    for child in _children(org_dir):
        if not is_container(child):
            yield Project(child, (org, child.name))
            continue

        defect = None
        if (child / ".claude" / "org.json").is_file():
            defect = (
                f"{org}/{child.name} is a client directory but carries .claude/org.json. "
                f"The org's contract governs repos inside it; remove the file."
            )
        for grandchild in _children(child):
            note = None
            if is_container(grandchild):
                note = (
                    f"{org}/{child.name}/{grandchild.name} is marked as a client directory "
                    f"inside another one. Only one level is supported, so it is treated as a project."
                )
            yield Project(grandchild, (org, child.name, grandchild.name),
                          client=child.name, note=note, defect=defect)
            defect = None  # reported once, on the first child


def _relative_parts(path: Path, workspace: Path) -> Optional[Tuple[str, ...]]:
    try:
        return path.relative_to(workspace).parts
    except ValueError:
        pass
    try:
        return path.resolve().relative_to(workspace.resolve()).parts
    except (ValueError, OSError):
        return None


def _locate(parts: Tuple[str, ...], workspace: Path) -> Context:
    """Context from workspace-relative parts, without checking the org list."""
    if not parts:
        return Context()
    org = parts[0]
    if len(parts) == 1:
        return Context(org=org)
    second = workspace / org / parts[1]
    if is_container(second):
        client = parts[1]
        if len(parts) == 2:
            return Context(org=org, client=client)
        project = parts[2]
        return Context(org, client, project, f"{org}/{client}/{project}")
    project = parts[1]
    return Context(org=org, project=project, key=f"{org}/{project}")


def project_key(path: Path, workspace: Path) -> Optional[str]:
    """State key of the project containing `path`, or None.

    None for the workspace itself, an org directory, a container directory, and
    anything outside the workspace.
    """
    parts = _relative_parts(path, workspace)
    if parts is None:
        return None
    return _locate(parts, workspace).key


def resolve(path: Path, workspace: Path, orgs: Optional[Iterable[str]] = None) -> Context:
    """Org, client, project, and key for a path.

    When `orgs` is given, a path under a directory not in it resolves to an
    empty Context, matching how Overwatch treats unconfigured directories.
    From inside a container the result has the org and client and no project.
    """
    parts = _relative_parts(path, workspace)
    if not parts:
        return Context()
    if orgs is not None and parts[0] not in set(orgs):
        return Context()
    return _locate(parts, workspace)
