#!/usr/bin/env python3
"""
CLAUDE Configuration Organization Tool

Audits, validates, and scaffolds CLAUDE.md files across the workspace hierarchy:
- User level: {workspace}/CLAUDE.md (security boundary)
- Org level: {workspace}/{org}/CLAUDE.md (optional)
- Project level: {workspace}/{org}/{project}/CLAUDE.md

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


def prompt_for_config() -> dict:
    """Interactive setup for first run or reconfiguration."""
    print("\n" + "=" * 60)
    print("ORGANIZE-CLAUDE SETUP")
    print("=" * 60)
    print("\nThis skill manages CLAUDE.md files across your workspace.")
    print("Let's configure your environment.\n")

    # Workspace path
    print("WORKSPACE PATH")
    print("-" * 40)
    print("The workspace is your security boundary - the root directory")
    print("where Claude operates. Your user-level CLAUDE.md lives here.")
    print("\nChoose a location that is:")
    print("  - Broad enough to include everything Claude needs to work on")
    print("  - Narrow enough to keep Claude isolated from sensitive areas")
    print("  - NOT your home directory (~) - that's too broad!")
    print("\nExamples: ~/Code, ~/Projects, ~/dev")

    while True:
        workspace_input = input("\nWorkspace path: ").strip()
        if not workspace_input:
            print("  Please enter a path.")
            continue

        # Warn if they try to use home directory
        if workspace_input in ("~", "~/", "$HOME", "$HOME/"):
            print("  WARNING: Using your home directory as workspace is a security risk.")
            print("  Claude would have access to everything. Choose a subdirectory instead.")
            continue

        workspace = Path(workspace_input).expanduser().resolve()

        # Also check if resolved path is home directory
        if workspace == Path.home():
            print("  WARNING: This resolves to your home directory - too broad!")
            print("  Choose a subdirectory like ~/Code or ~/Projects.")
            continue
        if not workspace.exists():
            create = input(f"  {workspace} doesn't exist. Create it? [y/N]: ").strip().lower()
            if create == 'y':
                workspace.mkdir(parents=True, exist_ok=True)
                print(f"  Created {workspace}")
            else:
                continue
        if not workspace.is_dir():
            print(f"  {workspace} is not a directory.")
            continue
        break

    # Org directories
    print("\n\nORG DIRECTORIES")
    print("-" * 40)
    print("Orgs are subdirectories that group related projects.")
    print("Examples: 'personal', 'work', 'client-acme', 'opensource'")
    print("\nEnter org names (comma-separated), or leave blank to scan for directories:")

    orgs_input = input("\nOrg names: ").strip()

    if orgs_input:
        orgs = [o.strip() for o in orgs_input.split(",") if o.strip()]
    else:
        # Scan for directories
        print(f"\n  Scanning {workspace} for directories...")
        orgs = []
        for item in sorted(workspace.iterdir()):
            if item.is_dir() and not item.name.startswith("."):
                orgs.append(item.name)
        if orgs:
            print(f"  Found: {', '.join(orgs)}")
            confirm = input("  Use these? [Y/n]: ").strip().lower()
            if confirm == 'n':
                orgs_input = input("  Enter org names (comma-separated): ").strip()
                orgs = [o.strip() for o in orgs_input.split(",") if o.strip()]
        else:
            print("  No directories found. Enter org names manually.")
            orgs_input = input("  Org names (comma-separated): ").strip()
            orgs = [o.strip() for o in orgs_input.split(",") if o.strip()]

    config = {
        "workspace": str(workspace),
        "orgs": orgs,
        "created": datetime.now().isoformat(),
    }

    # Confirm
    print("\n\nCONFIGURATION SUMMARY")
    print("-" * 40)
    print(f"  Workspace: {workspace}")
    print(f"  Orgs: {', '.join(orgs) if orgs else '(none)'}")

    save = input("\nSave this configuration? [Y/n]: ").strip().lower()
    if save != 'n':
        save_config(config)

    return config


def get_config(force_setup: bool = False) -> dict:
    """Get configuration, prompting for setup if needed."""
    if force_setup:
        return prompt_for_config()

    config = load_config()
    if config:
        return config

    print("\nNo configuration found. Let's set up organize-claude.")
    return prompt_for_config()


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


def find_projects(org_path: Path) -> list[tuple[str, Path, bool]]:
    """
    Find all projects in an org directory.
    Returns: list of (project_name, path, has_claude_md)
    """
    results = []
    for item in sorted(org_path.iterdir()):
        if item.is_dir() and not item.name.startswith("."):
            claude_md = item / "CLAUDE.md"
            results.append((item.name, item, claude_md.exists()))
    return results


def parse_project_mapping(claude_md_path: Path) -> dict[str, str]:
    """
    Parse project directory mapping table from user-level CLAUDE.md.
    Returns: dict of project_name -> directory_path
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
            mapping[project_name] = project_path

    return mapping


def validate_project_mapping(
    mapping: dict[str, str], actual_projects: list[tuple[str, Path, bool]]
) -> tuple[list[str], list[tuple[str, Path]]]:
    """
    Validate project mapping against actual directories.
    Returns: (in_mapping_not_disk, on_disk_not_mapping)
    """
    actual_names = {p[0] for p in actual_projects}
    mapped_names = set(mapping.keys())

    # In mapping but not on disk
    in_mapping_not_disk = [name for name in mapped_names if name not in actual_names]

    # On disk but not in mapping
    on_disk_not_mapping = [
        (p[0], p[1]) for p in actual_projects if p[0] not in mapped_names
    ]

    return in_mapping_not_disk, on_disk_not_mapping


def prompt_choice(message: str, choices: list[tuple[str, str]]) -> str:
    """Show choices and get user input."""
    print(f"\n{message}")
    for key, desc in choices:
        print(f"  [{key}] {desc}")
    print()
    while True:
        choice = input("> ").strip().upper()
        valid = [c[0].upper() for c in choices]
        if choice in valid:
            return choice
        print(f"Please enter one of: {', '.join(valid)}")


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


def scaffold_project_claude_md(project_path: Path, project_name: str, org_name: str) -> None:
    """Create a scaffold CLAUDE.md for a project."""
    template_path = Path(__file__).parent.parent / "templates" / "project-claude.md.template"

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

## Gotchas (Learned the Hard Way)

| Issue | Cause | Solution |
|-------|-------|----------|
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

    # User level
    print(f"\nWorkspace: {workspace}")
    user_path, user_exists, symlink_target = user_claude
    if user_exists:
        if symlink_target:
            print(f"User Level: {user_path}")
            print(f"  → symlink to {symlink_target} ✓")
        else:
            print(f"User Level: {user_path} ✓")
    else:
        print(f"User Level: {user_path} ✗ MISSING")

    # Org level
    print("\nORG COVERAGE")
    print("-" * 60)
    for org_name, org_path, has_claude in org_info:
        projects = all_projects.get(org_name, [])
        project_count = len(projects)
        status = "✓" if has_claude else "✗ MISSING"
        print(f"  {status} {org_name}/CLAUDE.md ({project_count} projects below)")

    # Project level per org
    for org_name, org_path, _ in org_info:
        projects = all_projects.get(org_name, [])
        if not projects:
            continue

        has_claude_count = sum(1 for p in projects if p[2])
        total = len(projects)
        pct = (has_claude_count / total * 100) if total > 0 else 0

        print(f"\nPROJECT COVERAGE: {org_name}/ ({total} projects)")
        print("-" * 60)

        for proj_name, proj_path, has_claude in projects:
            if has_claude:
                # Check for nested CLAUDE.md files
                nested = list(proj_path.rglob("CLAUDE.md"))
                if len(nested) > 1:
                    print(f"  ✓ {proj_name} ({len(nested)} files)")
                else:
                    print(f"  ✓ {proj_name}")
            else:
                print(f"  ✗ {proj_name} MISSING")

        print(f"\nCoverage: {has_claude_count}/{total} ({pct:.0f}%)")

    # Mapping validation
    if mapping_validation:
        in_mapping_not_disk, on_disk_not_mapping = mapping_validation
        print("\nPROJECT MAPPING VALIDATION (user-level)")
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
                short_name = name.replace("gruntwork-", "")
                print(f"  ✗ {short_name} → add: | {short_name} | {path} |")
        else:
            print("\nProjects on disk but missing from mapping: (none)")


def main():
    parser = argparse.ArgumentParser(description="Organize CLAUDE.md configuration files")
    parser.add_argument("--workspace", type=Path, help="Override workspace root path")
    parser.add_argument("--setup", action="store_true", help="Run interactive setup (reconfigure)")
    parser.add_argument("--show-config", action="store_true", help="Show current configuration")
    parser.add_argument("--dry-run", action="store_true", help="Show what would happen")
    parser.add_argument("--scaffold-org", type=str, help="Scaffold CLAUDE.md for specific org")
    parser.add_argument("--scaffold-project", type=str, help="Scaffold CLAUDE.md for specific project")
    parser.add_argument("--update-mappings", action="store_true", help="Update user-level project mappings")
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
            print("Run with --setup to configure.")
        return

    # Get or create config
    config = get_config(force_setup=args.setup)

    # Allow command-line override of workspace
    if args.workspace:
        workspace = args.workspace.expanduser().resolve()
        orgs = get_orgs(config)
    else:
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
            # Use short name for mapping comparison
            short_name = proj_name.replace(f"{org_name}-", "")
            all_project_list.append((short_name, proj_path, has_claude))

    mapping_validation = validate_project_mapping(mapping, all_project_list) if mapping else None

    # Show audit report
    show_audit_report(workspace, user_claude, org_info, all_projects, mapping_validation)

    if dry_run:
        print("\n" + "=" * 60)
        print("DRY RUN COMPLETE")
        print("=" * 60)
        return

    # Determine what actions are available
    missing_orgs = [o for o in org_info if not o[2]]
    missing_projects = []
    for org_name, projects in all_projects.items():
        for proj_name, proj_path, has_claude in projects:
            if not has_claude:
                missing_projects.append((org_name, proj_name, proj_path))

    if not missing_orgs and not missing_projects and not (mapping_validation and mapping_validation[1]):
        print("\n✓ All CLAUDE.md files present, mappings valid.")
        return

    # Build choices
    choices = [("A", "Audit only (no changes)")]

    if missing_orgs:
        choices.append(("O", f"Scaffold {len(missing_orgs)} missing org-level files"))

    if missing_projects:
        choices.append(("P", f"Scaffold {len(missing_projects)} missing project-level files"))

    if mapping_validation and mapping_validation[1]:
        choices.append(("U", "Update user-level project mappings"))

    if len(choices) > 2:  # More than just Audit and Quit
        choices.append(("F", "Full sync (all of the above)"))

    choices.append(("Q", "Quit"))

    if args.yes:
        choice = "F" if "F" in [c[0] for c in choices] else "A"
    else:
        choice = prompt_choice("What would you like to do?", choices)

    if choice == "Q" or choice == "A":
        print("Exiting.")
        return

    # Execute chosen actions
    if choice in ("O", "F") and missing_orgs:
        print("\nScaffolding org-level CLAUDE.md files...")
        for org_name, org_path, _ in missing_orgs:
            projects = all_projects.get(org_name, [])
            scaffold_org_claude_md(org_path, org_name, projects)

    if choice in ("P", "F") and missing_projects:
        print("\nScaffolding project-level CLAUDE.md files...")
        for org_name, proj_name, proj_path in missing_projects:
            scaffold_project_claude_md(proj_path, proj_name, org_name)

    if choice in ("U", "F") and mapping_validation and mapping_validation[1]:
        print("\nUpdating project mappings...")
        print("  (Manual step: Add missing projects to ~/Code/CLAUDE.md Project Directory Mapping table)")
        for name, path in mapping_validation[1]:
            short_name = name.replace("gruntwork-", "")
            print(f"  | {short_name} | {path} |")

    print("\n✓ Organization complete.")


if __name__ == "__main__":
    main()
