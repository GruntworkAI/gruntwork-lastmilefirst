#!/usr/bin/env python3
"""
CLAUDE Configuration Organization Tool

Audits, validates, and scaffolds CLAUDE.md files across the workspace hierarchy:
- Workspace level: {workspace}/CLAUDE.md (security boundary)
- Org level: {workspace}/{org}/CLAUDE.md (optional)
- Project level: {workspace}/{org}/{project}/CLAUDE.md, or
  {workspace}/{org}/{client}/{project}/CLAUDE.md inside a directory marked
  `type: client` (the client directory itself is never scaffolded)

Always shows what will happen and asks for confirmation before any changes.
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from archetypes import (
    VALID_ARCHETYPES,
    detect_archetype,
    get_template_name_for_archetype,
    format_archetype_choices,
)

# The workspace layout loader lives with the hook scripts (it decides which
# directories are projects, and which are client directories holding them).
_HOOKS_SCRIPTS = Path(__file__).resolve().parents[3] / "hooks" / "scripts"
if str(_HOOKS_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_HOOKS_SCRIPTS))
# find_projects: (label, path, has_claude_md) per project, shared with review-claude.
from workspace_types import find_claude_md_projects as find_projects  # noqa: E402

# Config file location
CONFIG_PATH = Path.home() / ".config" / "organize-claude" / "config.json"


def load_config() -> Optional[dict]:
    """Load saved configuration."""
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text())
        except (json.JSONDecodeError, IOError):
            return None
    return None


def save_config(config: dict) -> None:
    """Save configuration for future runs."""
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(config, indent=2))
    print(f"\n  Config saved to {CONFIG_PATH}")


def scan_orgs(workspace: Path) -> list[str]:
    """Auto-detect org directories by scanning workspace for non-hidden subdirectories."""
    orgs = []
    for item in sorted(workspace.iterdir()):
        if item.is_dir() and not item.name.startswith("."):
            orgs.append(item.name)
    return orgs


def setup_config(workspace_path: str, orgs_str: Optional[str] = None, auto_create: bool = False) -> dict:
    """Create config from CLI arguments (no interactive prompts)."""
    workspace = Path(workspace_path).expanduser().resolve()

    # Validate workspace
    if workspace == Path.home():
        print("ERROR: Home directory is too broad. Use a subdirectory like ~/Code")
        sys.exit(1)

    if not workspace.exists():
        if auto_create:
            workspace.mkdir(parents=True, exist_ok=True)
            print(f"  Created {workspace}")
        else:
            print(f"ERROR: {workspace} does not exist. Create it first or pass --yes to auto-create.")
            sys.exit(1)

    if not workspace.is_dir():
        print(f"ERROR: {workspace} is not a directory.")
        sys.exit(1)

    # Determine orgs
    if orgs_str:
        orgs = [o.strip() for o in orgs_str.split(",") if o.strip()]
    else:
        # Auto-detect by scanning workspace
        orgs = scan_orgs(workspace)
        if orgs:
            print(f"  Auto-detected orgs: {', '.join(orgs)}")
        else:
            print("  No org directories found in workspace.")

    config = {
        "workspace": str(workspace),
        "orgs": orgs,
        "created": datetime.now().isoformat(),
    }

    save_config(config)

    print("\n  CONFIGURATION SUMMARY")
    print(f"  Workspace: {workspace}")
    print(f"  Orgs: {', '.join(orgs) if orgs else '(none)'}")

    return config


def add_org_to_config(org_name: str) -> dict:
    """Add an org to existing config."""
    config = load_config()
    if not config:
        print("ERROR: No configuration found. Run --setup first.")
        sys.exit(1)

    orgs = config.get("orgs", [])
    if org_name in orgs:
        print(f"  Org '{org_name}' already in config.")
    else:
        orgs.append(org_name)
        config["orgs"] = orgs
        save_config(config)
        print(f"  Added org '{org_name}'. Orgs: {', '.join(orgs)}")

    return config


def remove_org_from_config(org_name: str) -> dict:
    """Remove an org from existing config."""
    config = load_config()
    if not config:
        print("ERROR: No configuration found. Run --setup first.")
        sys.exit(1)

    orgs = config.get("orgs", [])
    if org_name not in orgs:
        print(f"  Org '{org_name}' not in config. Current orgs: {', '.join(orgs)}")
    else:
        orgs.remove(org_name)
        config["orgs"] = orgs
        save_config(config)
        print(f"  Removed org '{org_name}'. Orgs: {', '.join(orgs)}")

    return config


def get_config_or_exit() -> dict:
    """Load config or exit with helpful error message."""
    config = load_config()
    if config:
        return config

    print("No configuration found.")
    print("\nTo set up, Claude should run:")
    print("  python organize_claude.py --setup --workspace ~/Code")
    print("  python organize_claude.py --setup --workspace ~/Code --orgs \"org1,org2\"")
    sys.exit(1)


def get_workspace_root(config: dict) -> Path:
    """Get the workspace root from config."""
    return Path(config["workspace"]).expanduser().resolve()


def get_orgs(config: dict) -> list[str]:
    """Get org list from config."""
    return config.get("orgs", [])


# Template paths for each level
TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
USER_TEMPLATE = TEMPLATES_DIR / "user-claude.md.template"
ORG_TEMPLATE = TEMPLATES_DIR / "org-claude.md.template"
PROJECT_TEMPLATE = TEMPLATES_DIR / "project-claude.md.template"


def parse_template_frontmatter(template_path: Path) -> list[tuple[str, str]]:
    """
    Parse YAML frontmatter from template to extract required sections.
    Returns list of (header, description) tuples.
    This is the single source of truth - no hardcoded section lists.
    """
    if not template_path.exists():
        return []

    content = template_path.read_text()

    # Check for frontmatter (starts and ends with ---)
    if not content.startswith("---"):
        return []

    # Find end of frontmatter
    end_marker = content.find("---", 3)
    if end_marker == -1:
        return []

    frontmatter = content[3:end_marker].strip()

    # Simple YAML parsing for required_sections
    sections = []
    in_sections = False
    current_header = None

    for line in frontmatter.split("\n"):
        line = line.strip()

        if line == "required_sections:":
            in_sections = True
            continue

        if in_sections:
            if line.startswith("- header:"):
                # Extract header value (remove quotes)
                current_header = line.replace("- header:", "").strip().strip('"\'')
            elif line.startswith("description:") and current_header:
                description = line.replace("description:", "").strip().strip('"\'')
                sections.append((current_header, description))
                current_header = None

    return sections


def get_expected_sections(level: str) -> list[tuple[str, str]]:
    """Get expected sections for a given level from template frontmatter."""
    template_map = {
        "user": USER_TEMPLATE,
        "org": ORG_TEMPLATE,
        "project": PROJECT_TEMPLATE,
    }
    template_path = template_map.get(level)
    if template_path:
        return parse_template_frontmatter(template_path)
    return []


def find_user_claude_md(workspace: Path) -> tuple[Path, bool, Optional[Path]]:
    """
    Find user-level CLAUDE.md.
    Returns: (path, exists, symlink_target)
    """
    user_claude = workspace / "CLAUDE.md"
    if user_claude.exists():
        if user_claude.is_symlink():
            return (user_claude, True, Path(os.readlink(user_claude)))
        return (user_claude, True, None)
    return (user_claude, False, None)


def find_org_directories(workspace: Path, orgs: list[str]) -> list[tuple[str, Path, bool]]:
    """
    Find org directories and their CLAUDE.md status.
    Returns: list of (org_name, path, has_claude_md)
    """
    results = []
    for org in orgs:
        org_path = workspace / org
        if org_path.exists() and org_path.is_dir():
            claude_md = org_path / "CLAUDE.md"
            results.append((org, org_path, claude_md.exists()))
    return results


def short_name(name: str, org_name: str) -> str:
    """Mapping-table name for a project: drop an `<org>-` prefix on flat repos.

    A project inside a client directory keeps its `client/project` name, with
    no prefix assumption.
    """
    if "/" in name:
        return name
    return name.removeprefix(f"{org_name}-")


def _org_of(path: Path, workspace: Path) -> str:
    """The org directory a project path sits in, or "" when outside the workspace."""
    rel = _relative(path, workspace.expanduser().resolve())
    return rel.split("/", 1)[0] if rel else ""


def parse_project_mapping(claude_md_path: Path) -> dict[str, str]:
    """
    Parse project directory mapping table from user-level CLAUDE.md.
    Returns: dict of directory_path -> project_name.

    Keyed by path, because names are not unique once client directories
    exist: two clients' `docs` rows would otherwise collapse into one.
    """
    mapping = {}
    if not claude_md_path.exists():
        return mapping

    content = claude_md_path.read_text()

    # Look for project mapping table
    # Format: | project_name | path |
    table_pattern = r"\|\s*(\w[\w-]*)\s*\|\s*(~/Code/[^\s|]+)\s*\|"
    for match in re.finditer(table_pattern, content):
        project_name = match.group(1).strip()
        project_path = match.group(2).strip()
        if project_name.lower() not in ("project", "name", "---"):
            mapping[project_path] = project_name

    return mapping


def _relative(path: Path, workspace: Path) -> Optional[str]:
    try:
        return path.expanduser().resolve().relative_to(workspace).as_posix()
    except (ValueError, OSError):
        return None


def validate_project_mapping(
    mapping: dict[str, str],
    actual_projects: list[tuple[str, Path, bool]],
    workspace: Optional[Path] = None,
) -> tuple[list[str], list[tuple[str, Path]]]:
    """
    Validate project mapping against actual directories.
    Returns: (in_mapping_not_disk, on_disk_not_mapping)

    `mapping` is the table as `name -> path`, or as a list of `(name, path)`
    rows (what `parse_project_mapping`'s path-keyed dict becomes, so rows
    sharing a name are all kept).

    With `workspace`, a row and a directory match when the row's path and the
    directory are the same path relative to the workspace, so two client
    directories each holding a `docs` repo stay distinct. A row whose path is
    not under the workspace, and every row when `workspace` is omitted, is
    matched by name as before.
    """
    rows = list(mapping.items()) if isinstance(mapping, dict) else list(mapping)
    if workspace is None:
        mapped_paths: dict[str, str] = {}
        by_name = dict(rows)
    else:
        workspace = workspace.expanduser().resolve()
        mapped_paths = {}
        by_name = {}
        for name, path in rows:
            rel = _relative(Path(path), workspace)
            if rel is None:
                by_name[name] = path
            else:
                mapped_paths[rel] = name

    actual_rels = set()
    actual_names = set()
    on_disk_not_mapping = []
    for name, path, _has_claude in actual_projects:
        rel = _relative(path, workspace) if workspace is not None else None
        actual_rels.add(rel)
        actual_names.add(name)
        if rel in mapped_paths or name in by_name:
            continue
        on_disk_not_mapping.append((name, path))

    in_mapping_not_disk = [name for rel, name in mapped_paths.items() if rel not in actual_rels]
    in_mapping_not_disk += [name for name in by_name if name not in actual_names]

    return in_mapping_not_disk, on_disk_not_mapping




def scaffold_org_claude_md(org_path: Path, org_name: str, projects: list) -> None:
    """Create a scaffold CLAUDE.md for an org."""
    template_path = Path(__file__).parent.parent / "templates" / "org-claude.md.template"

    # Build project table
    project_rows = []
    for proj_name, proj_path, has_claude in projects:
        status = "Active" if has_claude else "Needs CLAUDE.md"
        project_rows.append(f"| {proj_name} | | {status} | Internal |")

    project_table = "\n".join(project_rows) if project_rows else "| (no projects) | | | |"

    # Read template and substitute
    if template_path.exists():
        content = template_path.read_text()
        # Basic substitutions
        content = content.replace("{{ORG_NAME}}", org_name.title())
        content = content.replace("{{PROJECT_TABLE}}", project_table)
        # Leave other placeholders for manual completion
    else:
        # Fallback minimal template
        content = f"""# {org_name.title()} Development Context

## Overview

(Add org description)

## Projects

| Project | Description | Status | Data Classification |
|---------|-------------|--------|---------------------|
{project_table}

---

*Inherits from ~/Code/CLAUDE.md*
"""

    output_path = org_path / "CLAUDE.md"
    output_path.write_text(content)
    print(f"  ✓ Created {output_path}")


def scaffold_project_claude_md(
    project_path: Path, project_name: str, org_name: str, archetype: Optional[str] = None
) -> None:
    """Create a scaffold CLAUDE.md for a project, optionally archetype-specific."""
    templates_dir = Path(__file__).parent.parent / "templates"

    # Select archetype-specific template if provided
    if archetype:
        template_path = templates_dir / get_template_name_for_archetype(archetype)
        if not template_path.exists():
            template_path = templates_dir / "project-claude.md.template"
    else:
        template_path = templates_dir / "project-claude.md.template"

    if template_path.exists():
        content = template_path.read_text()
        # Basic substitutions
        content = content.replace("{{PROJECT_NAME}}", project_name)
        content = content.replace("{{ORG}}", org_name)
        content = content.replace("{{PROJECT_DESCRIPTION}}", "(Add project description)")
        # Leave other placeholders for manual completion
    else:
        # Fallback minimal template
        content = f"""# {project_name}

(Add project description)

## Infrastructure

### Cloud Details

| Setting | Value |
|---------|-------|
| **Provider** | (AWS/GCP/etc) |
| **Region** | (region) |
| **Account/Project** | (account ID) |

### CRITICAL: Check Terraform Workspace First

```bash
terraform workspace show  # Must match your target environment!
```

## Quick Commands

```bash
# Development
(add commands)

# Testing
(add commands)

# Deployment
(add commands)
```

## Dev Gotchas

Traps for someone changing this repo. Lead with the symptom — it's what you'll be searching by when you hit this again.

| Issue | Symptom | Cause / fix |
|-------|---------|-------------|
| | | |

## Deployment Gotchas

Traps for someone deploying or running it. Lead with the symptom — it's what you'll be searching by when you hit this again.

| Issue | Symptom | Cause / fix |
|-------|---------|-------------|
| | | |

---

*Inherits from ~/Code/CLAUDE.md and ~/Code/{org_name}/CLAUDE.md*
"""

    output_path = project_path / "CLAUDE.md"
    output_path.write_text(content)
    print(f"  ✓ Created {output_path}")


def show_audit_report(
    workspace: Path,
    user_claude: tuple[Path, bool, Optional[Path]],
    orgs: list[tuple[str, Path, bool]],
    all_projects: dict[str, list[tuple[str, Path, bool]]],
    mapping_validation: Optional[tuple[list, list]] = None,
) -> None:
    """Display comprehensive audit report."""
    print("\n" + "=" * 60)
    print("CLAUDE CONFIGURATION AUDIT")
    print("=" * 60)

    # Workspace level
    print(f"\nWorkspace: {workspace}")
    user_path, user_exists, symlink_target = user_claude
    if user_exists:
        if symlink_target:
            print(f"Workspace Level: {user_path}")
            print(f"  → symlink to {symlink_target} ✓")
        else:
            print(f"Workspace Level: {user_path} ✓")
    else:
        print(f"Workspace Level: {user_path} ✗ MISSING")

    # Org level
    print("\nORG COVERAGE")
    print("-" * 60)
    for org_name, org_path, has_claude in orgs:
        projects = all_projects.get(org_name, [])
        project_count = len(projects)
        status = "✓" if has_claude else "✗ MISSING"
        print(f"  {status} {org_name}/CLAUDE.md ({project_count} projects below)")

    # Project level per org
    for org_name, org_path, _ in orgs:
        projects = all_projects.get(org_name, [])
        if not projects:
            continue

        has_claude_count = sum(1 for p in projects if p[2])
        total = len(projects)
        pct = (has_claude_count / total * 100) if total > 0 else 0

        print(f"\nPROJECT COVERAGE: {org_name}/ ({total} projects)")
        print("-" * 60)

        current_client = None
        for proj_name, proj_path, has_claude in projects:
            # A project inside a client directory prints indented under a
            # `client/` line, which is shown once per client.
            client, _, leaf = proj_name.rpartition("/")
            if client != current_client:
                current_client = client
                if client:
                    print(f"  {client}/")
            indent = "    " if client else "  "
            if has_claude:
                # Check for nested CLAUDE.md files
                nested = list(proj_path.rglob("CLAUDE.md"))
                if len(nested) > 1:
                    print(f"{indent}✓ {leaf} ({len(nested)} files)")
                else:
                    print(f"{indent}✓ {leaf}")
            else:
                print(f"{indent}✗ {leaf} MISSING")

        print(f"\nCoverage: {has_claude_count}/{total} ({pct:.0f}%)")

    # Mapping validation
    if mapping_validation:
        in_mapping_not_disk, on_disk_not_mapping = mapping_validation
        print("\nPROJECT MAPPING VALIDATION (workspace-level)")
        print("-" * 60)

        if in_mapping_not_disk:
            print("Projects in ~/Code/CLAUDE.md but not on disk:")
            for name in in_mapping_not_disk:
                print(f"  ✗ {name}")
        else:
            print("Projects in ~/Code/CLAUDE.md but not on disk: (none)")

        if on_disk_not_mapping:
            print("\nProjects on disk but missing from mapping:")
            for name, path in on_disk_not_mapping:
                label = short_name(name, _org_of(path, workspace))
                print(f"  ✗ {label} → add: | {label} | {path} |")
        else:
            print("\nProjects on disk but missing from mapping: (none)")


def find_scaffold_target(all_projects: dict[str, list], wanted: str):
    """The project `--scaffold-project` names, or a message saying why not.

    `wanted` matches a project's label (`project`, or `client/project` in a
    client directory) or its leaf directory name. An exact label match wins;
    a leaf name shared by projects in two client directories is ambiguous.
    Returns (org_name, label, path, has_claude_md), or a message string.
    """
    by_label = []
    by_leaf = []
    for org_name, projects in all_projects.items():
        for proj_name, proj_path, has_claude in projects:
            entry = (org_name, proj_name, proj_path, has_claude)
            if proj_name == wanted:
                by_label.append(entry)
            elif proj_path.name == wanted:
                by_leaf.append(entry)
    matches = by_label or by_leaf
    if len(matches) == 1:
        return matches[0]
    if matches:
        labels = ", ".join(sorted(f"{org}/{label}" for org, label, _p, _h in matches))
        return f"Project '{wanted}' matches more than one directory ({labels}). Pass the client/project form."
    return (f"Project '{wanted}' not found. Name it as the audit lists it: `project`, "
            f"or `client/project` for a project inside a client directory.")


def main():
    parser = argparse.ArgumentParser(description="Organize CLAUDE.md configuration files")

    # Config management
    parser.add_argument("--setup", action="store_true", help="Create or reconfigure workspace config")
    parser.add_argument("--workspace", type=str, help="Workspace root path (required with --setup)")
    parser.add_argument("--orgs", type=str, help="Comma-separated org names (with --setup; auto-detects if omitted)")
    parser.add_argument("--add-org", type=str, help="Add an org to existing config")
    parser.add_argument("--remove-org", type=str, help="Remove an org from existing config")
    parser.add_argument("--show-config", action="store_true", help="Show current configuration")

    # Actions
    parser.add_argument("--scaffold-org", type=str, help="Scaffold CLAUDE.md for specific org")
    parser.add_argument("--scaffold-project", type=str, help="Scaffold CLAUDE.md for specific project")
    parser.add_argument(
        "--archetype",
        type=str,
        choices=VALID_ARCHETYPES,
        help="Project archetype (deployable, usable, referenceable, experimental). Used with --scaffold-project.",
    )
    parser.add_argument("--scaffold-all-orgs", action="store_true", help="Scaffold all missing org-level CLAUDE.md files")
    parser.add_argument("--scaffold-all-projects", action="store_true", help="Scaffold all missing project-level CLAUDE.md files")
    parser.add_argument("--update-mappings", action="store_true", help="Show missing project mappings for the workspace-level CLAUDE.md")
    parser.add_argument("--full-sync", action="store_true", help="Scaffold all missing files and show mapping updates")

    # Modifiers
    parser.add_argument("--dry-run", action="store_true", help="Show what would happen without making changes")
    parser.add_argument("--yes", "-y", action="store_true", help="Auto-confirm all actions")
    args = parser.parse_args()

    # Handle --show-config
    if args.show_config:
        config = load_config()
        if config:
            print("\nCurrent configuration:")
            print(f"  Config file: {CONFIG_PATH}")
            print(f"  Workspace: {config.get('workspace')}")
            print(f"  Orgs: {', '.join(config.get('orgs', []))}")
            print(f"  Created: {config.get('created', 'unknown')}")
        else:
            print(f"\nNo configuration found at {CONFIG_PATH}")
            print("Run with --setup --workspace ~/Code to configure.")
        return

    # Handle --setup
    if args.setup:
        if not args.workspace:
            print("ERROR: --setup requires --workspace PATH")
            print("  Example: --setup --workspace ~/Code")
            print("  Example: --setup --workspace ~/Code --orgs \"gruntwork,work\"")
            sys.exit(1)
        setup_config(args.workspace, args.orgs, auto_create=args.yes)
        return

    # Handle --add-org / --remove-org
    if args.add_org:
        add_org_to_config(args.add_org)
        return

    if args.remove_org:
        remove_org_from_config(args.remove_org)
        return

    # All other actions require existing config
    config = get_config_or_exit()
    workspace = get_workspace_root(config)
    orgs = get_orgs(config)

    dry_run = args.dry_run

    if dry_run:
        print("=" * 60)
        print("DRY RUN - No changes will be made")
        print("=" * 60)

    # Gather information
    user_claude = find_user_claude_md(workspace)
    org_info = find_org_directories(workspace, orgs)

    all_projects: dict[str, list] = {}
    for org_name, org_path, _ in org_info:
        all_projects[org_name] = find_projects(org_path)

    # Parse and validate mapping
    mapping = parse_project_mapping(user_claude[0]) if user_claude[1] else {}

    # Combine all projects for validation
    all_project_list = []
    for org_name, projects in all_projects.items():
        for proj_name, proj_path, has_claude in projects:
            all_project_list.append((short_name(proj_name, org_name), proj_path, has_claude))

    mapping_rows = [(name, path) for path, name in mapping.items()]
    mapping_validation = (
        validate_project_mapping(mapping_rows, all_project_list, workspace) if mapping else None
    )

    # Show audit report (always)
    show_audit_report(workspace, user_claude, org_info, all_projects, mapping_validation)

    if dry_run:
        print("\n" + "=" * 60)
        print("DRY RUN COMPLETE")
        print("=" * 60)
        return

    # Determine what's missing
    missing_orgs = [o for o in org_info if not o[2]]
    missing_projects = []
    for org_name, projects in all_projects.items():
        for proj_name, proj_path, has_claude in projects:
            if not has_claude:
                missing_projects.append((org_name, proj_name, proj_path))

    has_mapping_gaps = mapping_validation and mapping_validation[1]

    # Determine which actions to take based on flags
    do_orgs = args.scaffold_all_orgs or args.full_sync or args.yes
    do_projects = args.scaffold_all_projects or args.full_sync or args.yes
    do_mappings = args.update_mappings or args.full_sync or args.yes

    # Handle specific scaffold requests
    if args.scaffold_org:
        for org_name, org_path, has_claude in orgs:
            if org_name == args.scaffold_org:
                if has_claude:
                    print(f"\n  {org_name}/CLAUDE.md already exists.")
                else:
                    projects = all_projects.get(org_name, [])
                    scaffold_org_claude_md(org_path, org_name, projects)
                return
        print(f"\n  Org '{args.scaffold_org}' not found in config.")
        return

    if args.scaffold_project:
        match = find_scaffold_target(all_projects, args.scaffold_project)
        if isinstance(match, str):
            print(f"\n  {match}")
            return
        org_name, proj_name, proj_path, has_claude = match
        if has_claude:
            print(f"\n  {proj_name}/CLAUDE.md already exists.")
        else:
            scaffold_project_claude_md(proj_path, proj_path.name, org_name, args.archetype)
        return

    # Execute bulk actions if flags were given
    acted = False

    if do_orgs and missing_orgs:
        print("\nScaffolding org-level CLAUDE.md files...")
        for org_name, org_path, _ in missing_orgs:
            projects = all_projects.get(org_name, [])
            scaffold_org_claude_md(org_path, org_name, projects)
        acted = True

    if do_projects and missing_projects:
        print("\nScaffolding project-level CLAUDE.md files...")
        for org_name, proj_name, proj_path in missing_projects:
            scaffold_project_claude_md(proj_path, proj_path.name, org_name)
        acted = True

    if do_mappings and has_mapping_gaps:
        print("\nMissing project mappings (add to ~/Code/CLAUDE.md):")
        for name, path in mapping_validation[1]:
            label = short_name(name, _org_of(path, workspace))
            print(f"  | {label} | {path} |")
        acted = True

    if acted:
        print("\n✓ Organization complete.")
    elif not missing_orgs and not missing_projects and not has_mapping_gaps:
        print("\n✓ All CLAUDE.md files present, mappings valid.")
    else:
        # Report what could be done
        print("\nAvailable actions:")
        if missing_orgs:
            print(f"  --scaffold-all-orgs    Scaffold {len(missing_orgs)} missing org-level files")
        if missing_projects:
            print(f"  --scaffold-all-projects  Scaffold {len(missing_projects)} missing project-level files")
        if has_mapping_gaps:
            print(f"  --update-mappings      Show {len(mapping_validation[1])} missing project mappings")
        print(f"  --full-sync            Do all of the above")


if __name__ == "__main__":
    main()
