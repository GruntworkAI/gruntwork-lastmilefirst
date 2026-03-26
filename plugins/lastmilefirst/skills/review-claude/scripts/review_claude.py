#!/usr/bin/env python3
"""
CLAUDE.md Review Tool

Reviews existing CLAUDE.md files against expected sections defined in templates.
Identifies gaps and optionally generates suggestions for missing content.

Uses the same config as organize-claude (shared workspace/orgs settings).
References organize-claude templates for expected section definitions.
Project-level reviews are archetype-aware: sections checked depend on the
project's declared archetype (Deployable, Usable, Referenceable, Experimental).
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

# Shared config with organize-claude
CONFIG_PATH = Path.home() / ".config" / "organize-claude" / "config.json"

# Template paths (from organize-claude)
ORGANIZE_CLAUDE_DIR = Path(__file__).parent.parent.parent / "organize-claude"
TEMPLATES_DIR = ORGANIZE_CLAUDE_DIR / "templates"
USER_TEMPLATE = TEMPLATES_DIR / "user-claude.md.template"
ORG_TEMPLATE = TEMPLATES_DIR / "org-claude.md.template"
PROJECT_TEMPLATE = TEMPLATES_DIR / "project-claude.md.template"

# Import archetypes from organize-claude
sys.path.insert(0, str(ORGANIZE_CLAUDE_DIR / "scripts"))
from archetypes import (
    VALID_ARCHETYPES,
    ARCHETYPE_DESCRIPTIONS,
    detect_archetype,
    get_sections_for_archetype,
    get_template_name_for_archetype,
    format_archetype_choices,
    infer_archetype,
    infer_archetype_from_content,
)


def load_config() -> Optional[dict]:
    """Load saved configuration (shared with organize-claude)."""
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text())
        except (json.JSONDecodeError, IOError):
            return None
    return None


def get_workspace_root(config: dict) -> Path:
    """Get the workspace root from config."""
    return Path(config["workspace"]).expanduser().resolve()


def get_orgs(config: dict) -> list[str]:
    """Get org list from config."""
    return config.get("orgs", [])


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


def get_expected_sections(level: str, archetype: Optional[str] = None) -> list[tuple[str, str]]:
    """
    Get expected sections for a given level from template frontmatter.
    For project level, uses archetype-specific sections if archetype is provided.
    """
    if level == "project" and archetype:
        return get_sections_for_archetype(archetype)

    template_map = {
        "user": USER_TEMPLATE,
        "org": ORG_TEMPLATE,
        "project": PROJECT_TEMPLATE,
    }
    template_path = template_map.get(level)
    if template_path:
        return parse_template_frontmatter(template_path)
    return []


def get_template_path(level: str, archetype: Optional[str] = None) -> Path:
    """Get template path for a given level, optionally archetype-specific."""
    if level == "project" and archetype:
        archetype_template = TEMPLATES_DIR / get_template_name_for_archetype(archetype)
        if archetype_template.exists():
            return archetype_template

    template_map = {
        "user": USER_TEMPLATE,
        "org": ORG_TEMPLATE,
        "project": PROJECT_TEMPLATE,
    }
    return template_map.get(level, PROJECT_TEMPLATE)


def review_claude_md(file_path: Path, expected_sections: list, level: str = "project") -> dict:
    """
    Review an existing CLAUDE.md against expected sections.
    Returns dict with 'present', 'missing', 'archetype', 'archetype_missing',
    'inferred_archetype', and 'content' keys.
    """
    result = {
        "path": file_path,
        "present": [],
        "missing": [],
        "archetype": None,
        "archetype_missing": False,
        "inferred_archetype": None,
        "content": "",
    }

    if not file_path.exists():
        result["missing"] = expected_sections
        return result

    content = file_path.read_text()
    result["content"] = content

    # Detect archetype for project-level files
    if level == "project":
        archetype = detect_archetype(content)
        result["archetype"] = archetype
        if archetype is None:
            result["archetype_missing"] = True
            # Try to infer from project directory structure, then from content
            project_dir = file_path.parent
            inferred, _scores = infer_archetype(project_dir)
            if inferred is None:
                inferred = infer_archetype_from_content(content)
            result["inferred_archetype"] = inferred
        else:
            expected_sections = get_sections_for_archetype(archetype)

    for section_header, description in expected_sections:
        if section_header in content:
            result["present"].append((section_header, description))
        else:
            result["missing"].append((section_header, description))

    return result


def show_review_report(reviews: list[dict], level: str) -> list[dict]:
    """Display review results and return files with gaps."""
    files_with_gaps = []

    print(f"\n{level.upper()}-LEVEL CLAUDE.MD REVIEW")
    print("-" * 60)

    for review in reviews:
        path = review["path"]
        present = review["present"]
        missing = review["missing"]
        archetype = review.get("archetype")
        archetype_missing = review.get("archetype_missing", False)

        if not review["content"]:
            print(f"\n  {path.name}: FILE MISSING")
            continue

        # Build label with archetype info for project-level
        label = f"{path.parent.name}/{path.name}"
        if level == "project":
            if archetype:
                label += f" [{archetype.capitalize()}]"
            else:
                label += " [No archetype]"

        if archetype_missing:
            files_with_gaps.append(review)
            inferred = review.get("inferred_archetype")
            print(f"\n  {label}:")
            if inferred:
                print(f"    No archetype declared — inferred: {inferred.capitalize()}")
                print(f"    Suggestion: add `## Archetype: {inferred.capitalize()}` to CLAUDE.md")
            else:
                print(f"    No archetype declared — could not infer")
                print(f"    Add: ## Archetype: Deployable|Usable|Referenceable|Experimental")
        elif missing:
            files_with_gaps.append(review)
            print(f"\n  {label}:")
            print(f"    Present: {len(present)} sections")
            print(f"    Missing: {len(missing)} sections")
            for header, desc in missing:
                print(f"      - {header} ({desc})")
        else:
            print(f"\n  {label}: All sections present ✓")

    return files_with_gaps


def generate_suggestions(review: dict, template_path: Path) -> str:
    """Generate suggested additions for missing sections."""
    suggestions = []
    missing = review["missing"]
    archetype_missing = review.get("archetype_missing", False)

    if archetype_missing:
        suggestions.append(f"# Archetype needed for {review['path'].parent.name}/CLAUDE.md")
        suggestions.append(f"# Add one of these lines near the top of your CLAUDE.md:\n")
        for name in VALID_ARCHETYPES:
            desc = ARCHETYPE_DESCRIPTIONS[name]
            suggestions.append(f"## Archetype: {name.capitalize()}")
            suggestions.append(f"# {desc}\n")
        return "\n".join(suggestions)

    if not missing:
        return ""

    suggestions.append(f"# Suggested additions for {review['path'].parent.name}/CLAUDE.md")
    suggestions.append(f"# Review and adapt these sections, then append to your file.\n")

    # Read template for section content
    if template_path.exists():
        template = template_path.read_text()
    else:
        template = ""

    for header, desc in missing:
        suggestions.append(f"\n{'=' * 60}")
        suggestions.append(f"# MISSING: {header}")
        suggestions.append(f"# Purpose: {desc}")
        suggestions.append(f"{'=' * 60}\n")

        # Try to extract section from template
        if template and header in template:
            # Find section in template (from header to next ## or end)
            start = template.find(header)
            next_section = template.find("\n## ", start + len(header))
            if next_section == -1:
                section_content = template[start:]
            else:
                section_content = template[start:next_section]
            suggestions.append(section_content.strip())
        else:
            # Generic placeholder
            suggestions.append(f"{header}\n\n(Add content here)\n")

    return "\n".join(suggestions)


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


def determine_level(file_path: Path, workspace: Path) -> str:
    """Determine if a file is user, org, or project level."""
    parent = file_path.parent
    grandparent = parent.parent

    if parent == workspace:
        return "user"
    elif grandparent == workspace:
        return "org"
    else:
        return "project"


def main():
    parser = argparse.ArgumentParser(description="Review CLAUDE.md files for missing sections")
    parser.add_argument("--file", type=Path, help="Review a specific CLAUDE.md file")
    parser.add_argument("--suggest", action="store_true", help="Generate suggestions for gaps")
    parser.add_argument("--yes", "-y", action="store_true", help="Auto-confirm suggestion generation")
    parser.add_argument("--fix", action="store_true", help="Add inferred archetype labels to CLAUDE.md files missing them")
    args = parser.parse_args()

    # Load config
    config = load_config()
    if not config:
        print("No configuration found. Run organize-claude first to set up workspace.")
        print("  python organize-claude/scripts/organize_claude.py --setup")
        return

    workspace = get_workspace_root(config)
    orgs = get_orgs(config)

    # Single file mode
    if args.file:
        file_path = args.file.expanduser().resolve()
        if not file_path.exists():
            print(f"Error: {file_path} does not exist")
            return

        level = determine_level(file_path, workspace)

        # For project-level, detect archetype first
        archetype = None
        if level == "project" and file_path.exists():
            content = file_path.read_text()
            archetype = detect_archetype(content)

        expected_sections = get_expected_sections(level, archetype)
        template_path = get_template_path(level, archetype)

        review = review_claude_md(file_path, expected_sections, level)

        if review.get("archetype_missing"):
            print(f"\n  No archetype declared in {file_path.name}")
            print(f"  Add one of these near the top of your CLAUDE.md:")
            print(format_archetype_choices())
            return

        if not review["missing"]:
            archetype_label = f" ({archetype.capitalize()})" if archetype else ""
            print(f"\n✓ {file_path.name}{archetype_label} has all expected {level}-level sections.")
            return

        archetype_label = f" [{archetype.capitalize()}]" if archetype else ""
        print(f"\nReviewing {file_path}{archetype_label}...")
        print(f"  Level: {level}")
        print(f"  Present: {len(review['present'])} sections")
        print(f"  Missing: {len(review['missing'])} sections")
        for header, desc in review["missing"]:
            print(f"    - {header} ({desc})")

        if args.suggest:
            suggestions = generate_suggestions(review, template_path)
            suggestions_file = file_path.parent / "CLAUDE.md.suggestions"
            suggestions_file.write_text(suggestions)
            print(f"\n✓ Suggestions written to {suggestions_file}")
        return

    # Full review mode
    print("\n" + "=" * 60)
    print("CLAUDE.MD REVIEW")
    print("=" * 60)
    print(f"\nWorkspace: {workspace}")

    # Gather all existing CLAUDE.md files
    org_info = find_org_directories(workspace, orgs)
    all_reviews = {"user": [], "org": [], "project": []}

    # Review user-level file
    user_claude_path = workspace / "CLAUDE.md"
    if user_claude_path.exists():
        review = review_claude_md(user_claude_path, get_expected_sections("user"), "user")
        all_reviews["user"].append(review)

    # Review org-level files
    for org_name, org_path, has_claude in org_info:
        if has_claude:
            claude_path = org_path / "CLAUDE.md"
            review = review_claude_md(claude_path, get_expected_sections("org"), "org")
            all_reviews["org"].append(review)

    # Review project-level files (archetype-aware)
    for org_name, org_path, _ in org_info:
        projects = find_projects(org_path)
        for proj_name, proj_path, has_claude in projects:
            if has_claude:
                claude_path = proj_path / "CLAUDE.md"
                # Pass default sections; review_claude_md will detect archetype and override
                review = review_claude_md(claude_path, get_expected_sections("project"), "project")
                all_reviews["project"].append(review)

    # Show reports
    user_gaps = []
    org_gaps = []
    project_gaps = []

    if all_reviews["user"]:
        user_gaps = show_review_report(all_reviews["user"], "user")

    if all_reviews["org"]:
        org_gaps = show_review_report(all_reviews["org"], "org")

    if all_reviews["project"]:
        project_gaps = show_review_report(all_reviews["project"], "project")

    # Summary
    total_reviewed = len(all_reviews["user"]) + len(all_reviews["org"]) + len(all_reviews["project"])
    total_with_gaps = len(user_gaps) + len(org_gaps) + len(project_gaps)

    # Count archetype stats
    archetype_counts = {"labeled": 0, "unlabeled": 0}
    for review in all_reviews["project"]:
        if review.get("archetype"):
            archetype_counts["labeled"] += 1
        elif review.get("archetype_missing"):
            archetype_counts["unlabeled"] += 1

    print("\n" + "=" * 60)
    print("REVIEW SUMMARY")
    print("=" * 60)
    print(f"  Files reviewed: {total_reviewed}")
    print(f"  Files with gaps: {total_with_gaps}")

    if all_reviews["project"]:
        total_projects = len(all_reviews["project"])
        print(f"\n  Project archetypes: {archetype_counts['labeled']}/{total_projects} labeled")
        if archetype_counts["unlabeled"] > 0:
            print(f"  {archetype_counts['unlabeled']} project(s) need an archetype declaration")

    if total_with_gaps == 0:
        print("\n✓ All reviewed files have expected sections.")
        return

    # Fix archetype labels if requested
    if args.fix:
        fixed = 0
        skipped = 0
        for review in all_reviews["project"]:
            if not review.get("archetype_missing"):
                continue
            inferred = review.get("inferred_archetype")
            if not inferred:
                skipped += 1
                continue
            file_path = review["path"]
            content = review["content"]
            # Insert archetype line after the first heading
            lines = content.split("\n")
            insert_idx = None
            for i, line in enumerate(lines):
                if line.startswith("# ") and not line.startswith("## "):
                    insert_idx = i + 1
                    # Skip blank lines after heading
                    while insert_idx < len(lines) and lines[insert_idx].strip() == "":
                        insert_idx += 1
                    # Skip description paragraph (next non-empty, non-heading line)
                    if insert_idx < len(lines) and not lines[insert_idx].startswith("#"):
                        insert_idx += 1
                        while insert_idx < len(lines) and lines[insert_idx].strip() == "":
                            insert_idx += 1
                    break

            if insert_idx is None:
                insert_idx = 0

            archetype_block = f"\n## Archetype: {inferred.capitalize()}\n"
            lines.insert(insert_idx, archetype_block)
            file_path.write_text("\n".join(lines))
            print(f"  ✓ {file_path.parent.name}: added ## Archetype: {inferred.capitalize()}")
            fixed += 1

        print(f"\n  Fixed: {fixed} file(s)")
        if skipped:
            print(f"  Skipped: {skipped} file(s) — could not infer archetype")
        return

    # Generate suggestions if requested via --suggest or --yes
    all_gaps = user_gaps + org_gaps + project_gaps

    if not (args.suggest or args.yes):
        hints = ["--suggest to generate suggestion templates for gaps"]
        if archetype_counts["unlabeled"] > 0:
            hints.append("--fix to add inferred archetype labels")
        print(f"\n  Run again with {' or '.join(hints)}.")
        return

    for review in all_gaps:
        file_path = review["path"]
        level = determine_level(file_path, workspace)
        archetype = review.get("archetype")
        template_path = get_template_path(level, archetype)

        suggestions = generate_suggestions(review, template_path)
        suggestions_file = file_path.parent / "CLAUDE.md.suggestions"
        suggestions_file.write_text(suggestions)
        print(f"  ✓ {suggestions_file}")

    print(f"\n✓ Generated {len(all_gaps)} suggestion files.")
    print("  Review each .suggestions file and copy relevant sections to your CLAUDE.md")


if __name__ == "__main__":
    main()
