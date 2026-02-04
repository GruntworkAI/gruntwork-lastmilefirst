#!/usr/bin/env python3
"""
Todo Aggregator - Core logic for cross-project todo aggregation.

Discovers projects across orgs in a workspace, parses todo files, and aggregates
them with metadata for filtering and display.

Terminology (consistent with organize-claude):
- Workspace: The root directory (e.g., ~/Code) - security boundary
- Org: A subdirectory grouping related projects (e.g., personal, client-work)
- Project: A single project directory within an org
"""

import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


# Configuration paths
WORKSPACE_CONFIG = Path.home() / ".claude" / "workspace-config.json"
CACHE_DIR = Path.home() / ".claude" / "cache"
CACHE_FILE = CACHE_DIR / "todo-aggregator.json"
CACHE_TTL_SECONDS = 300  # 5 minutes


@dataclass
class OrgConfig:
    """Configuration for an org within the workspace."""

    name: str
    path: Path
    default: bool = False
    sensitive: bool = False

    @classmethod
    def from_dict(cls, data: Dict[str, Any], workspace_path: Path) -> "OrgConfig":
        return cls(
            name=data["name"],
            path=workspace_path / data["name"],
            default=data.get("default", False),
            sensitive=data.get("sensitive", False),
        )


@dataclass
class TodoItem:
    """A parsed todo item with metadata."""

    project: str
    file_path: Path
    title: str
    status: str = "pending"
    priority: str = "normal"
    age_days: int = 0
    blocks: List[str] = field(default_factory=list)
    blocked_by: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)

    @property
    def is_urgent(self) -> bool:
        return self.priority in ("urgent", "p1", "high") or "[URGENT]" in self.title

    @property
    def is_blocked(self) -> bool:
        return bool(self.blocked_by) or "[BLOCKED" in self.title

    @property
    def is_stale(self) -> bool:
        return self.age_days > 7

    @property
    def state(self) -> str:
        """Computed state: urgent, blocked, active, stale."""
        if self.is_urgent:
            return "urgent"
        if self.is_blocked:
            return "blocked"
        if self.is_stale:
            return "stale"
        return "active"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "project": self.project,
            "file_path": str(self.file_path),
            "title": self.title,
            "status": self.status,
            "priority": self.priority,
            "age_days": self.age_days,
            "blocks": self.blocks,
            "blocked_by": self.blocked_by,
            "tags": self.tags,
            "state": self.state,
        }


class TodoAggregator:
    """Aggregates todos across projects in workspace orgs."""

    def __init__(self, exclude_patterns: Optional[List[str]] = None):
        self.exclude_patterns = exclude_patterns or [
            "node_modules", ".git", "venv", "__pycache__", ".venv"
        ]
        self._workspace_path: Optional[Path] = None
        self._orgs: List[OrgConfig] = []
        self._load_config()

    def _load_config(self) -> None:
        """Load workspace and org configuration from file."""
        if not WORKSPACE_CONFIG.exists():
            # Auto-detect from ~/Code
            self._workspace_path = Path.home() / "Code"
            if self._workspace_path.exists():
                for item in sorted(self._workspace_path.iterdir()):
                    if item.is_dir() and not item.name.startswith("."):
                        self._orgs.append(OrgConfig(
                            name=item.name,
                            path=item,
                            default=(item.name.lower() == "gruntwork"),
                        ))
            return

        try:
            with open(WORKSPACE_CONFIG, encoding="utf-8") as f:
                data = json.load(f)

            # Load workspace path
            workspace_str = data.get("workspace", "~/Code")
            self._workspace_path = Path(workspace_str).expanduser()

            # Load orgs
            for org_data in data.get("orgs", []):
                self._orgs.append(OrgConfig.from_dict(org_data, self._workspace_path))

            # Override exclude patterns if specified
            if "exclude_patterns" in data:
                self.exclude_patterns = data["exclude_patterns"]

        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Failed to load workspace config: {e}")
            self._workspace_path = Path.home() / "Code"

    def get_workspace_path(self) -> Optional[Path]:
        """Get the workspace root path."""
        return self._workspace_path

    def get_orgs(self) -> List[OrgConfig]:
        """Get all configured orgs."""
        return self._orgs

    def get_default_org(self) -> Optional[OrgConfig]:
        """Get the default org."""
        for org in self._orgs:
            if org.default:
                return org
        return self._orgs[0] if self._orgs else None

    def get_org_by_name(self, name: str) -> Optional[OrgConfig]:
        """Get an org by name."""
        for org in self._orgs:
            if org.name.lower() == name.lower():
                return org
        return None

    def discover_projects(self, org: OrgConfig) -> List[Path]:
        """Discover all projects in an org that have .claude/work/todos."""
        projects = []

        if not org.path.exists():
            return projects

        for item in sorted(org.path.iterdir()):
            if not item.is_dir():
                continue
            if item.name.startswith("."):
                continue
            if item.name in self.exclude_patterns:
                continue

            todos_dir = item / ".claude" / "work" / "todos"
            if todos_dir.exists() and todos_dir.is_dir():
                projects.append(item)

        return projects

    def parse_todo_file(self, file_path: Path, project_name: str) -> Optional[TodoItem]:
        """Parse a single todo file and extract metadata."""
        try:
            content = file_path.read_text(encoding="utf-8")
        except IOError:
            return None

        # Calculate age
        try:
            mtime = file_path.stat().st_mtime
            age_days = int((time.time() - mtime) / 86400)
        except OSError:
            age_days = 0

        # Extract YAML frontmatter
        frontmatter = self._parse_frontmatter(content)

        # Extract title (first markdown heading or filename)
        title = self._extract_title(content, file_path)

        # Parse inline tags
        inline_blocks, inline_blocked_by = self._parse_inline_tags(content)

        return TodoItem(
            project=project_name,
            file_path=file_path,
            title=title,
            status=frontmatter.get("status", "pending"),
            priority=frontmatter.get("priority", "normal"),
            age_days=age_days,
            blocks=frontmatter.get("blocks", []) + inline_blocks,
            blocked_by=frontmatter.get("blocked_by", []) + inline_blocked_by,
            tags=frontmatter.get("tags", []),
        )

    def _parse_frontmatter(self, content: str) -> Dict[str, Any]:
        """Parse YAML frontmatter from content."""
        if not content.startswith("---"):
            return {}

        end_marker = content.find("---", 3)
        if end_marker == -1:
            return {}

        frontmatter_text = content[3:end_marker].strip()
        result: Dict[str, Any] = {}

        for line in frontmatter_text.split("\n"):
            line = line.strip()
            if ":" not in line:
                continue

            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()

            # Handle list values
            if value.startswith("[") and value.endswith("]"):
                # Simple list parsing
                items = value[1:-1].split(",")
                result[key] = [item.strip().strip("\"'") for item in items if item.strip()]
            else:
                result[key] = value.strip("\"'")

        return result

    def _extract_title(self, content: str, file_path: Path) -> str:
        """Extract title from content or filename."""
        # Skip frontmatter
        if content.startswith("---"):
            end_marker = content.find("---", 3)
            if end_marker != -1:
                content = content[end_marker + 3:].strip()

        # Look for first heading
        for line in content.split("\n"):
            line = line.strip()
            if line.startswith("#"):
                return line.lstrip("#").strip()

        # Fall back to filename
        return file_path.stem.replace("-", " ").replace("_", " ").title()

    def _parse_inline_tags(self, content: str) -> tuple[List[str], List[str]]:
        """Parse inline [BLOCKS:...] and [BLOCKED-BY:...] tags."""
        blocks = []
        blocked_by = []

        # Find [BLOCKS:project]
        for match in re.finditer(r"\[BLOCKS:([^\]]+)\]", content):
            blocks.append(match.group(1).strip())

        # Find [BLOCKED-BY:project#id] or [BLOCKED-BY:project]
        for match in re.finditer(r"\[BLOCKED-BY:([^\]]+)\]", content):
            blocked_by.append(match.group(1).strip())

        return blocks, blocked_by

    def aggregate_todos(
        self,
        org: Optional[OrgConfig] = None,
        all_orgs: bool = False,
        use_cache: bool = True,
    ) -> Dict[str, List[TodoItem]]:
        """
        Aggregate todos from projects.

        Returns dict mapping org name to list of TodoItems.
        """
        # Check cache
        if use_cache:
            cached = self._load_cache()
            if cached is not None:
                return cached

        result: Dict[str, List[TodoItem]] = {}

        if all_orgs:
            orgs_to_scan = self._orgs
        elif org:
            orgs_to_scan = [org]
        else:
            default = self.get_default_org()
            orgs_to_scan = [default] if default else []

        for org_config in orgs_to_scan:
            todos = []
            projects = self.discover_projects(org_config)

            for project_path in projects:
                project_name = project_path.name
                todos_dir = project_path / ".claude" / "work" / "todos"

                for todo_file in todos_dir.glob("*.md"):
                    todo = self.parse_todo_file(todo_file, project_name)
                    if todo and todo.status != "complete":
                        todos.append(todo)

            result[org_config.name] = todos

        # Save to cache
        if use_cache:
            self._save_cache(result)

        return result

    def _load_cache(self) -> Optional[Dict[str, List[TodoItem]]]:
        """Load from cache if valid."""
        if not CACHE_FILE.exists():
            return None

        try:
            mtime = CACHE_FILE.stat().st_mtime
            if time.time() - mtime > CACHE_TTL_SECONDS:
                return None

            with open(CACHE_FILE, encoding="utf-8") as f:
                data = json.load(f)

            result: Dict[str, List[TodoItem]] = {}
            for org_name, todos_data in data.items():
                todos = []
                for td in todos_data:
                    todos.append(TodoItem(
                        project=td["project"],
                        file_path=Path(td["file_path"]),
                        title=td["title"],
                        status=td["status"],
                        priority=td["priority"],
                        age_days=td["age_days"],
                        blocks=td.get("blocks", []),
                        blocked_by=td.get("blocked_by", []),
                        tags=td.get("tags", []),
                    ))
                result[org_name] = todos

            return result

        except (json.JSONDecodeError, IOError, KeyError):
            return None

    def _save_cache(self, data: Dict[str, List[TodoItem]]) -> None:
        """Save aggregated data to cache."""
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

        cache_data = {}
        for org_name, todos in data.items():
            cache_data[org_name] = [todo.to_dict() for todo in todos]

        try:
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(cache_data, f)
        except IOError:
            pass  # Cache write failure is non-fatal


def get_aggregated_summary(
    org_name: Optional[str] = None,
    all_orgs: bool = False,
    use_cache: bool = True,
) -> Dict[str, List[TodoItem]]:
    """
    Convenience function to get aggregated todos.

    Args:
        org_name: Specific org to scan (default: default org)
        all_orgs: Scan all orgs in workspace
        use_cache: Use cached results if available

    Returns:
        Dict mapping org name to list of TodoItems
    """
    aggregator = TodoAggregator()

    org = None
    if org_name:
        org = aggregator.get_org_by_name(org_name)
        if not org:
            raise ValueError(f"Unknown org: {org_name}")

    return aggregator.aggregate_todos(
        org=org,
        all_orgs=all_orgs,
        use_cache=use_cache,
    )


if __name__ == "__main__":
    # Quick test
    aggregator = TodoAggregator()
    print(f"Workspace: {aggregator.get_workspace_path()}")
    print(f"Orgs: {[org.name for org in aggregator.get_orgs()]}")
    print(f"Default org: {aggregator.get_default_org()}")

    result = aggregator.aggregate_todos(use_cache=False)
    for org_name, todos in result.items():
        print(f"\n{org_name}: {len(todos)} todos")
        for todo in todos[:3]:
            print(f"  - [{todo.state}] {todo.project}: {todo.title}")
