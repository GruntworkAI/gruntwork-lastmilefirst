#!/usr/bin/env python3
"""
CLAUDE.md Review Tool

Reviews existing CLAUDE.md files against expected sections defined in templates.
Identifies gaps and optionally generates suggestions for missing content.

Uses the same config as organize-claude (shared workspace/orgs settings).
References organize-claude templates for expected section definitions.
"""

import argparse
import json
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


def get_template_path(level: str) -> Path:
    """Get template path for a given level."""
    template_map = {
        "user": USER_TEMPLATE,
        "org": ORG_TEMPLATE,
        "project": PROJECT_TEMPLATE,
    }
    return template_map.get(level, PROJECT_TEMPLATE)


def review_claude_md(file_path: Path, expected_sections: list) -> dict:
    """
    Review an existing CLAUDE.md against expected sections.
    Returns dict with 'present', 'missing', and 'content' keys.
    """
    result = {
        "path": file_path,
        "present": [],
        "missing": [],
        "content": "",
    }

    if not file_path.exists():
        result["missing"] = expected_sections
        return result

    content = file_path.read_text()
    result["content"] = content

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

        if not review["content"]:
            print(f"\n  {path.name}: FILE MISSING")
            continue

        if missing:
            files_with_gaps.append(review)
            print(f"\n  {path.parent.name}/{path.name}:")
            print(f"    Present: {len(present)} sections")
            print(f"    Missing: {len(missing)} sections")
            for header, desc in missing:
                print(f"      - {header} ({desc})")
        else:
            print(f"\n  {path.parent.name}/{path.name}: All sections present ✓")

    return files_with_gaps


def generate_suggestions(review: dict, template_path: Path) -> str:
    """Generate suggested additions for missing sections."""
    suggestions = []
    missing = review["missing"]

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
        expected_sections = get_expected_sections(level)
        template_path = get_template_path(level)

        review = review_claude_md(file_path, expected_sections)

        if not review["missing"]:
            print(f"\n✓ {file_path.name} has all expected {level}-level sections.")
            return

        print(f"\nReviewing {file_path}...")
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
        review = review_claude_md(user_claude_path, get_expected_sections("user"))
        all_reviews["user"].append(review)

    # Review org-level files
    for org_name, org_path, has_claude in org_info:
        if has_claude:
            claude_path = org_path / "CLAUDE.md"
            review = review_claude_md(claude_path, get_expected_sections("org"))
            all_reviews["org"].append(review)

    # Review project-level files
    for org_name, org_path, _ in org_info:
        projects = find_projects(org_path)
        for proj_name, proj_path, has_claude in projects:
            if has_claude:
                claude_path = proj_path / "CLAUDE.md"
                review = review_claude_md(claude_path, get_expected_sections("project"))
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

    print("\n" + "=" * 60)
    print("REVIEW SUMMARY")
    print("=" * 60)
    print(f"  Files reviewed: {total_reviewed}")
    print(f"  Files with gaps: {total_with_gaps}")

    if total_with_gaps == 0:
        print("\n✓ All reviewed files have expected sections.")
        return

    # Offer to generate suggestions
    all_gaps = user_gaps + org_gaps + project_gaps

    if args.suggest or args.yes:
        choice = "Y"
    else:
        print("\n" + "-" * 60)
        choice = input("\nGenerate suggestions for files with gaps? [y/N]: ").strip().upper()

    if choice == "Y":
        for review in all_gaps:
            file_path = review["path"]
            level = determine_level(file_path, workspace)
            template_path = get_template_path(level)

            suggestions = generate_suggestions(review, template_path)
            suggestions_file = file_path.parent / "CLAUDE.md.suggestions"
            suggestions_file.write_text(suggestions)
            print(f"  ✓ {suggestions_file}")

        print(f"\n✓ Generated {len(all_gaps)} suggestion files.")
        print("  Review each .suggestions file and copy relevant sections to your CLAUDE.md")


if __name__ == "__main__":
    main()
