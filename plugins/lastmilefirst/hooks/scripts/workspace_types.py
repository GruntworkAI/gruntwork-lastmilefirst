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
- One level only. A container inside a container is yielded as a project.
- A container must not carry `.claude/org.json`, and should not be a git repo
  itself. It is still treated as a container either way.
- Layout problems are reported by `layout_issues(org_dir)`, from the container
  itself, so a container with no children still reports them. `iter_projects`
  yields projects only.
- The loader never filters. Callers keep their own filters (a `.git` for the
  scanner, a `todos/` for todos-summary).

The marker parser lives in organize-orgs/scripts/check_identity.py, because the
pre-commit hook must stay stdlib-only and self-contained. This module imports
it rather than copying it.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Iterable, Iterator, Mapping, NamedTuple, Optional, Tuple

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
    "ISSUE_SEVERITY",
    "UNGOVERNED_TYPES",
    "WORKSPACE_MARKER",
    "Context",
    "LayoutIssue",
    "Project",
    "ProjectLayout",
    "classify_org_entries",
    "container_layout_issues",
    "find_claude_md_projects",
    "find_projects",
    "is_container",
    "iter_containers",
    "iter_projects",
    "layout_issues",
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


class LayoutIssue(NamedTuple):
    """A layout problem found at a container, reported whether or not it has children."""

    path: Path      # the container directory the issue is about
    kind: str       # one of ISSUE_SEVERITY's keys
    message: str


class ProjectLayout(NamedTuple):
    """One-level hierarchy classification of already-read directory entries."""

    projects: Tuple[Project, ...]
    containers: Tuple[Path, ...]


# How a caller should label each kind of layout issue.
ISSUE_SEVERITY = {
    "container-org-json": "ACTION REQUIRED",
    "container-is-repo": "WARNING",
    "nested-container": "NOTE",
}


def classify_org_entries(
    org_dir: Path,
    entries: Iterable[Tuple[Path, Optional[str]]],
    container_children: Mapping[Path, Iterable[Path]],
) -> ProjectLayout:
    """Classify supplied entries, descending exactly one client tier, without I/O.

    Callers own enumeration, ordering, hidden/evidence filters, and marker
    parsing policy. Only direct org children can be containers. Their supplied
    children are projects even when marked as another client container.
    """
    projects, containers = [], []
    org = org_dir.name
    for child, kind in entries:
        if kind not in CONTAINER_TYPES:
            projects.append(Project(child, (org, child.name)))
            continue
        containers.append(child)
        for grandchild in container_children.get(child, ()):
            projects.append(Project(grandchild, (org, child.name, grandchild.name), client=child.name))
    return ProjectLayout(tuple(projects), tuple(containers))


def container_layout_issues(
    org_dir: Path,
    container: Path,
    *,
    has_org_config: bool,
    is_repo: bool,
    child_markers: Iterable[Tuple[Path, Optional[str]]] = (),
) -> list[LayoutIssue]:
    """Layout decisions for a known container, based only on supplied facts.

    Presence policy belongs to the reader: canonical callers check files and
    .git existence; bounded audits may flag any present/unsafe metadata entry.
    Diagnostics remain available even when the container has no projects.
    """
    issues = []
    label = f"{org_dir.name}/{container.name}"
    if has_org_config:
        issues.append(LayoutIssue(
            container, "container-org-json",
            f"{label} is a client directory but carries .claude/org.json. "
            f"The org's contract governs repos inside it; remove the file.",
        ))
    if is_repo:
        issues.append(LayoutIssue(
            container, "container-is-repo",
            f"{label} is a client directory and also a git repo. A container "
            f"should not be a repo: Overwatch, review-org, and the other "
            f"project walkers do not track its own contents as a project. "
            f"The secret scan and identity audit still cover it, keyed "
            f"{label}; move its files into a project inside it.",
        ))
    for grandchild, kind in child_markers:
        if kind in CONTAINER_TYPES:
            issues.append(LayoutIssue(
                grandchild, "nested-container",
                f"{label}/{grandchild.name} is marked as a client directory "
                f"inside another one. Only one level is supported, so it is "
                f"treated as a project.",
            ))
    return issues


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


def iter_containers(org_dir: Path) -> Iterator[Path]:
    """Every container directory directly inside an org."""
    for child in _children(org_dir):
        if is_container(child):
            yield child


def iter_projects(org_dir: Path) -> Iterator[Project]:
    """Every project directory under an org, descending one level through containers."""
    # Process one direct child at a time to preserve the loader's lazy reads.
    for child in _children(org_dir):
        kind = workspace_type(child) if child.is_dir() else None
        children = {child: _children(child)} if kind in CONTAINER_TYPES else {}
        yield from classify_org_entries(org_dir, [(child, kind)], children).projects


def find_projects(org_dir: Path) -> list:
    """Paths of every project under an org (`iter_projects` without the metadata)."""
    return [p.path for p in iter_projects(org_dir)]


def find_claude_md_projects(org_dir: Path) -> list:
    """(label, path, has_claude_md) for every project under an org.

    The shape organize-claude and review-claude both work from. `label` is
    `project`, or `client/project` inside a client directory; a client
    directory itself is never listed, so it is never scaffolded or reviewed
    as a project.
    """
    return [(p.label, p.path, (p.path / "CLAUDE.md").exists()) for p in iter_projects(org_dir)]


def layout_issues(org_dir: Path) -> list:
    """Layout problems at the containers of one org, as LayoutIssue tuples.

    Reported from the container itself, so a container with no children
    still reports them. Kinds:

    - `container-org-json`: the container carries `.claude/org.json`.
    - `container-is-repo`: the container is itself a git repo.
    - `nested-container`: a container inside a container (one level only).
    """
    issues = []
    for container in iter_containers(org_dir):
        issues.extend(container_layout_issues(
            org_dir, container,
            has_org_config=(container / ".claude" / "org.json").is_file(),
            is_repo=(container / ".git").exists(),
            child_markers=(
                (child, workspace_type(child) if child.is_dir() else None)
                for child in _children(container)
            ),
        ))
    return issues


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
