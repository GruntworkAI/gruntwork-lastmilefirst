#!/usr/bin/env python3
"""
Output Formatters for Todo Aggregation.

Provides multiple output formats:
- TerminalFormatter: Human-readable with sections
- JsonFormatter: Machine-readable JSON
- CompactFormatter: One-line-per-project for Overwatch
"""

import json
from abc import ABC, abstractmethod
from typing import Dict, List

from aggregator import TodoItem


class BaseFormatter(ABC):
    """Base class for output formatters."""

    @abstractmethod
    def format(self, data: Dict[str, List[TodoItem]]) -> str:
        """Format aggregated todo data."""
        pass


class TerminalFormatter(BaseFormatter):
    """Human-readable terminal output with sections."""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose

    def format(self, data: Dict[str, List[TodoItem]]) -> str:
        lines = []

        for ws_name, todos in data.items():
            if not todos:
                continue

            # Header
            lines.append(f"CROSS-PROJECT TODO SUMMARY ({ws_name})")
            lines.append("=" * 50)
            lines.append("")

            # Group by state
            urgent = [t for t in todos if t.state == "urgent"]
            blocked = [t for t in todos if t.state == "blocked"]
            active = [t for t in todos if t.state == "active"]
            stale = [t for t in todos if t.state == "stale"]

            # Urgent section
            if urgent:
                lines.append(f"URGENT ({len(urgent)})")
                for todo in urgent:
                    age_str = f"({todo.age_days}d)" if todo.age_days > 0 else ""
                    lines.append(f"  [{todo.project}] {todo.title} {age_str}")
                lines.append("")

            # Blocked section
            if blocked:
                lines.append(f"BLOCKED ({len(blocked)})")
                for todo in blocked:
                    blocker = todo.blocked_by[0] if todo.blocked_by else "unknown"
                    lines.append(f"  [{todo.project}] {todo.title} (waiting: {blocker})")
                lines.append("")

            # Active section
            if active:
                if self.verbose:
                    lines.append(f"ACTIVE ({len(active)})")
                    for todo in active:
                        age_str = f"({todo.age_days}d)" if todo.age_days > 0 else ""
                        lines.append(f"  [{todo.project}] {todo.title} {age_str}")
                else:
                    # Summarize by project
                    by_project: Dict[str, int] = {}
                    for todo in active:
                        by_project[todo.project] = by_project.get(todo.project, 0) + 1

                    lines.append(f"ACTIVE ({len(active)})")
                    for project, count in sorted(by_project.items()):
                        lines.append(f"  [{project}] {count} pending")
                lines.append("")

            # Stale section
            if stale:
                if self.verbose:
                    lines.append(f"STALE ({len(stale)})")
                    for todo in stale:
                        lines.append(f"  [{todo.project}] {todo.title} ({todo.age_days}d)")
                else:
                    shown = stale[:2]
                    lines.append(f"STALE ({len(stale)} items, {len(shown)} shown)")
                    for todo in shown:
                        lines.append(f"  [{todo.project}] {todo.title} ({todo.age_days}d)")
                lines.append("")

            # Footer
            if not self.verbose and (len(active) > 5 or len(stale) > 2):
                lines.append("Run /run-todos-summary --verbose for full details")
                lines.append("")

        return "\n".join(lines)


class JsonFormatter(BaseFormatter):
    """Machine-readable JSON output."""

    def __init__(self, indent: int = 2):
        self.indent = indent

    def format(self, data: Dict[str, List[TodoItem]]) -> str:
        output = {}
        for ws_name, todos in data.items():
            output[ws_name] = {
                "total": len(todos),
                "by_state": {
                    "urgent": len([t for t in todos if t.state == "urgent"]),
                    "blocked": len([t for t in todos if t.state == "blocked"]),
                    "active": len([t for t in todos if t.state == "active"]),
                    "stale": len([t for t in todos if t.state == "stale"]),
                },
                "todos": [todo.to_dict() for todo in todos],
            }
        return json.dumps(output, indent=self.indent)


class CompactFormatter(BaseFormatter):
    """
    Compact one-line-per-workspace format for Overwatch.

    Only shows urgent and blocked items.
    """

    def format(self, data: Dict[str, List[TodoItem]]) -> str:
        lines = []

        for ws_name, todos in data.items():
            urgent = [t for t in todos if t.state == "urgent"]
            blocked = [t for t in todos if t.state == "blocked"]

            if not urgent and not blocked:
                continue

            parts = []
            if urgent:
                parts.append(f"{len(urgent)} urgent")
            if blocked:
                parts.append(f"{len(blocked)} blocked")

            total_active = len([t for t in todos if t.status != "complete"])
            lines.append(f"[{ws_name}] {', '.join(parts)} ({total_active} total)")

            # Show first urgent item if any
            if urgent:
                first = urgent[0]
                lines.append(f"   ! [{first.project}] {first.title}")

        return "\n".join(lines) if lines else ""


class OverwatchFormatter(BaseFormatter):
    """
    Minimal format for session start.

    Shows only if there are urgent/blocked items worth mentioning.
    """

    def format(self, data: Dict[str, List[TodoItem]]) -> str:
        all_urgent = []
        all_blocked = []

        for org_name, todos in data.items():
            for todo in todos:
                if todo.state == "urgent":
                    all_urgent.append((org_name, todo))
                elif todo.state == "blocked":
                    all_blocked.append((org_name, todo))

        if not all_urgent and not all_blocked:
            return ""

        lines = []

        if all_urgent:
            lines.append(f"{len(all_urgent)} urgent todo(s) across projects")
            # Show top 2
            for org_name, todo in all_urgent[:2]:
                lines.append(f"   [{todo.project}] {todo.title}")

        if all_blocked:
            lines.append(f"{len(all_blocked)} blocked todo(s) need attention")

        if all_urgent or all_blocked:
            lines.append("   Run /run-todos-summary for details")

        return "\n".join(lines)


class ProjectFormatter(BaseFormatter):
    """
    Project-centric view showing what each project needs.

    Groups todos by project rather than by state.
    """

    def __init__(self, verbose: bool = False):
        self.verbose = verbose

    def format(self, data: Dict[str, List[TodoItem]]) -> str:
        lines = []

        for org_name, todos in data.items():
            if not todos:
                continue

            # Header
            lines.append(f"PROJECT STATUS ({org_name})")
            lines.append("=" * 50)
            lines.append("")

            # Group by project
            by_project: Dict[str, List[TodoItem]] = {}
            for todo in todos:
                if todo.project not in by_project:
                    by_project[todo.project] = []
                by_project[todo.project].append(todo)

            # Sort projects: those with urgent items first, then by todo count
            def project_sort_key(item):
                project_name, project_todos = item
                has_urgent = any(t.state == "urgent" for t in project_todos)
                has_blocked = any(t.state == "blocked" for t in project_todos)
                return (not has_urgent, not has_blocked, -len(project_todos))

            sorted_projects = sorted(by_project.items(), key=project_sort_key)

            for project_name, project_todos in sorted_projects:
                # Count by state
                urgent_count = len([t for t in project_todos if t.state == "urgent"])
                blocked_count = len([t for t in project_todos if t.state == "blocked"])
                stale_count = len([t for t in project_todos if t.state == "stale"])

                # Project header with summary
                status_parts = []
                if urgent_count:
                    status_parts.append(f"{urgent_count} urgent")
                if blocked_count:
                    status_parts.append(f"{blocked_count} blocked")
                if stale_count:
                    status_parts.append(f"{stale_count} stale")

                status_str = f" - {', '.join(status_parts)}" if status_parts else ""
                lines.append(f"{project_name} ({len(project_todos)} todos){status_str}")

                # Sort todos: urgent first, then blocked, then active, then stale
                state_order = {"urgent": 0, "blocked": 1, "active": 2, "stale": 3}
                sorted_todos = sorted(project_todos, key=lambda t: state_order.get(t.state, 4))

                # Show todos
                if self.verbose:
                    for todo in sorted_todos:
                        age_str = f" ({todo.age_days}d)" if todo.age_days > 0 else ""
                        if todo.state == "blocked" and todo.blocked_by:
                            blocker = todo.blocked_by[0]
                            lines.append(f"  - [{todo.state}] {todo.title} (waiting: {blocker})")
                        else:
                            lines.append(f"  - [{todo.state}] {todo.title}{age_str}")
                else:
                    # Show up to 3 most important todos
                    for todo in sorted_todos[:3]:
                        age_str = f" ({todo.age_days}d)" if todo.age_days > 0 else ""
                        if todo.state == "blocked" and todo.blocked_by:
                            blocker = todo.blocked_by[0]
                            lines.append(f"  - [{todo.state}] {todo.title} (waiting: {blocker})")
                        else:
                            lines.append(f"  - [{todo.state}] {todo.title}{age_str}")
                    if len(sorted_todos) > 3:
                        lines.append(f"  ... and {len(sorted_todos) - 3} more")

                lines.append("")

            # Summary
            total = len(todos)
            urgent_total = len([t for t in todos if t.state == "urgent"])
            blocked_total = len([t for t in todos if t.state == "blocked"])

            if urgent_total or blocked_total:
                summary_parts = []
                if urgent_total:
                    summary_parts.append(f"{urgent_total} urgent")
                if blocked_total:
                    summary_parts.append(f"{blocked_total} blocked")
                lines.append(f"Summary: {total} todos across {len(by_project)} projects ({', '.join(summary_parts)})")
            else:
                lines.append(f"Summary: {total} todos across {len(by_project)} projects")

            if not self.verbose:
                lines.append("Run with --verbose for full details")
            lines.append("")

        return "\n".join(lines)


def get_formatter(format_name: str, verbose: bool = False) -> BaseFormatter:
    """
    Factory function to get formatter by name.

    Args:
        format_name: One of "terminal", "json", "compact", "overwatch", "project"
        verbose: Enable verbose output (for terminal/project format)

    Returns:
        Formatter instance
    """
    formatters = {
        "terminal": lambda: TerminalFormatter(verbose=verbose),
        "json": lambda: JsonFormatter(),
        "compact": lambda: CompactFormatter(),
        "overwatch": lambda: OverwatchFormatter(),
        "project": lambda: ProjectFormatter(verbose=verbose),
    }

    if format_name not in formatters:
        raise ValueError(f"Unknown format: {format_name}. Choose from: {list(formatters.keys())}")

    return formatters[format_name]()


if __name__ == "__main__":
    # Test with sample data
    from aggregator import TodoItem

    sample_todos = [
        TodoItem(
            project="remail",
            file_path="/test/todo1.md",
            title="Fix rate limiting false positives",
            priority="urgent",
            age_days=3,
        ),
        TodoItem(
            project="calvin",
            file_path="/test/todo2.md",
            title="Voice auth token expiring",
            priority="p1",
            age_days=1,
        ),
        TodoItem(
            project="remail",
            file_path="/test/todo3.md",
            title="Prod deploy",
            blocked_by=["infrastructure#vpc"],
            age_days=2,
        ),
        TodoItem(
            project="promptasaurus",
            file_path="/test/todo4.md",
            title="Add streaming support",
            age_days=5,
        ),
    ]

    data = {"gruntwork": sample_todos}

    print("=== Terminal Format ===")
    print(TerminalFormatter().format(data))

    print("\n=== Compact Format ===")
    print(CompactFormatter().format(data))

    print("\n=== Overwatch Format ===")
    print(OverwatchFormatter().format(data))
