#!/usr/bin/env python3
"""
Project Organization Tool

Establishes consistent project structure:
- docs/ for static reference documentation
- .claude/work/ for working artifacts (todos, plans, sessions)
- .claude/debt/ for technical debt tracking
- .claude/archive/ for old files

Always shows what will happen and asks for confirmation before any changes.
"""

import argparse
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# Configuration
ARCHIVE_AGE_DAYS = 30
PROTECTION_AGE_DAYS = 7

# Required directory structure
CLAUDE_SUBDIRS = ["work/todos", "work/plans", "work/sessions", "debt", "archive"]

# Legacy directories that should be migrated with symlinks
LEGACY_DIRS = {
    "todos": ".claude/work/todos",
    "plans": ".claude/work/plans",
    "sessions": ".claude/work/sessions",
}

# Documentation patterns (root → docs/)
DOC_PATTERNS = [
    (r".*DEPLOYMENT.*\.md$", "docs"),
    (r".*DEPLOY.*\.md$", "docs"),
    (r".*INFRASTRUCTURE.*\.md$", "docs"),
    (r".*INFRA.*\.md$", "docs"),
    (r".*API.*\.md$", "docs"),
    (r".*TESTING.*\.md$", "docs"),
    (r".*TEST_GUIDE.*\.md$", "docs"),
    (r".*SECURITY.*\.md$", "docs"),
    (r".*ARCHITECTURE.*\.md$", "docs"),
    (r".*_GUIDE\.md$", "docs"),
]

# Working artifact patterns (root → .claude/work/)
WORK_PATTERNS = [
    # Sessions
    (r"^SESSION_.*\.md$", ".claude/work/sessions"),
    (r".*_SESSION\.md$", ".claude/work/sessions"),
    (r"^SYNTHASAURUS_.*\.md$", ".claude/work/sessions"),
    (r".*_ANALYSIS.*\.md$", ".claude/work/sessions"),
    (r".*_REVIEW.*\.md$", ".claude/work/sessions"),
    (r"^CODE_REVIEW_SUMMARY\.md$", ".claude/work/sessions"),
    (r".*_PROGRESS\.md$", ".claude/work/sessions"),
    (r".*_STATUS\.md$", ".claude/work/sessions"),
    (r"^screenshot.*\.png$", ".claude/work/sessions"),
    # Todos
    (r"^TODO\.md$", ".claude/work/todos"),
    (r".*TODO.*\.md$", ".claude/work/todos"),
    (r"^ISSUE.*\.md$", ".claude/work/todos"),
    (r".*_ISSUE\.md$", ".claude/work/todos"),
    # Plans
    (r"^PLAN.*\.md$", ".claude/work/plans"),
    (r".*_PLAN\.md$", ".claude/work/plans"),
    (r"^PRD.*\.md$", ".claude/work/plans"),
    (r"^FEATURE.*\.md$", ".claude/work/plans"),
]

# Technical debt patterns (root → .claude/debt/)
DEBT_PATTERNS = [
    (r".*TECH_DEBT.*\.md$", ".claude/debt"),
    (r".*TECHNICAL_DEBT.*\.md$", ".claude/debt"),
    (r"^DEBT.*\.md$", ".claude/debt"),
]

# Files that should stay at root
ROOT_STAY = ["README.md", "CHANGELOG.md", "LICENSE", "LICENSE.md", "CONTRIBUTING.md"]


def get_file_age_days(path: Path) -> int:
    """Get file age in days based on modification time."""
    mtime = datetime.fromtimestamp(path.stat().st_mtime)
    return (datetime.now() - mtime).days


def get_todo_status(path: Path) -> Optional[str]:
    """Extract status from YAML frontmatter in TODO file."""
    try:
        content = path.read_text()
        if content.startswith("---"):
            end = content.find("---", 3)
            if end > 0:
                frontmatter = content[3:end]
                for line in frontmatter.split("\n"):
                    if line.startswith("status:"):
                        return line.split(":", 1)[1].strip()
    except Exception:
        pass
    return None


def resolve_conflict(target: Path) -> Path:
    """Add timestamp suffix if target exists."""
    if not target.exists():
        return target
    timestamp = int(datetime.now().timestamp())
    stem = target.stem
    suffix = target.suffix
    return target.parent / f"{stem}_{timestamp}{suffix}"


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


def check_structure(project_root: Path) -> dict:
    """Check project directory structure."""
    result = {
        "docs_exists": (project_root / "docs").exists(),
        "claude_exists": (project_root / ".claude").exists(),
        "missing_dirs": [],
        "present_dirs": [],
        "legacy_dirs": [],
    }

    # Check docs/
    if result["docs_exists"]:
        result["present_dirs"].append("docs")
    else:
        result["missing_dirs"].append("docs")

    # Check .claude/ structure
    claude_dir = project_root / ".claude"
    if claude_dir.exists():
        result["present_dirs"].append(".claude")
        for subpath in CLAUDE_SUBDIRS:
            full_path = claude_dir / subpath
            if full_path.exists() or full_path.is_symlink():
                result["present_dirs"].append(f".claude/{subpath}")
            else:
                result["missing_dirs"].append(f".claude/{subpath}")
    else:
        result["missing_dirs"].append(".claude")
        for subpath in CLAUDE_SUBDIRS:
            result["missing_dirs"].append(f".claude/{subpath}")

    # Check for legacy directories at project root
    for legacy_name, target in LEGACY_DIRS.items():
        legacy_path = project_root / legacy_name
        if legacy_path.exists() and legacy_path.is_dir() and not legacy_path.is_symlink():
            result["legacy_dirs"].append((legacy_name, legacy_path, target))

    return result


def classify_file(filename: str) -> tuple[str, str] | None:
    """Classify a file and return (category, destination) or None."""
    # Skip files that should stay at root
    if filename in ROOT_STAY:
        return None

    # Check documentation patterns
    for pattern, dest in DOC_PATTERNS:
        if re.match(pattern, filename, re.IGNORECASE):
            return ("docs", dest)

    # Check work patterns
    for pattern, dest in WORK_PATTERNS:
        if re.match(pattern, filename, re.IGNORECASE):
            return ("work", dest)

    # Check debt patterns
    for pattern, dest in DEBT_PATTERNS:
        if re.match(pattern, filename, re.IGNORECASE):
            return ("debt", dest)

    return None


def find_scattered_files(project_root: Path) -> dict:
    """Find files in project root that should be migrated."""
    scattered = {"docs": [], "work": [], "debt": []}

    for item in project_root.iterdir():
        if item.is_file():
            result = classify_file(item.name)
            if result:
                category, dest = result
                scattered[category].append((item, dest))

    return scattered


def find_archive_candidates(project_root: Path) -> tuple[list, list]:
    """Find files to archive and protected files."""
    claude_dir = project_root / ".claude"
    candidates = []
    protected = []

    work_dir = claude_dir / "work"
    if not work_dir.exists():
        return candidates, protected

    # Check sessions
    sessions_dir = work_dir / "sessions"
    if sessions_dir.exists():
        for item in sessions_dir.iterdir():
            if item.is_file():
                age = get_file_age_days(item)
                if age <= PROTECTION_AGE_DAYS:
                    protected.append((item, f"modified {age} days ago"))
                elif age > ARCHIVE_AGE_DAYS:
                    candidates.append((item, age, "sessions"))

    # Check plans
    plans_dir = work_dir / "plans"
    if plans_dir.exists():
        actual_dir = plans_dir.resolve() if plans_dir.is_symlink() else plans_dir
        for item in actual_dir.iterdir():
            if item.is_file() and item.suffix == ".md":
                age = get_file_age_days(item)
                if age <= PROTECTION_AGE_DAYS:
                    protected.append((item, f"modified {age} days ago"))
                elif age > ARCHIVE_AGE_DAYS:
                    candidates.append((item, age, "plans"))

    # Check todos - only archive completed
    todos_dir = work_dir / "todos"
    if todos_dir.exists():
        actual_dir = todos_dir.resolve() if todos_dir.is_symlink() else todos_dir
        for item in actual_dir.iterdir():
            if item.is_file() and item.suffix == ".md":
                age = get_file_age_days(item)
                status = get_todo_status(item)

                if age <= PROTECTION_AGE_DAYS:
                    protected.append((item, f"modified {age} days ago"))
                elif status in ("in_progress", "pending"):
                    protected.append((item, f"status: {status}"))
                elif status == "complete" and age > ARCHIVE_AGE_DAYS:
                    candidates.append((item, age, "todos"))

    return candidates, protected


def show_structure_report(structure: dict, scattered: dict) -> None:
    """Display structure validation results."""
    print("\n" + "=" * 60)
    print("PROJECT STRUCTURE")
    print("=" * 60)

    print("\nDocumentation:")
    if structure["docs_exists"]:
        print("  ✓ docs/")
    else:
        print("  ✗ docs/ (missing)")

    print("\nWorking artifacts:")
    claude_dirs = [".claude"] + [f".claude/{s}" for s in CLAUDE_SUBDIRS]
    for d in claude_dirs:
        if d in structure["present_dirs"]:
            print(f"  ✓ {d}/")
        else:
            print(f"  ✗ {d}/ (missing)")

    if structure["legacy_dirs"]:
        print(f"\nLegacy directories to migrate:")
        for name, path, target in structure["legacy_dirs"]:
            count = len(list(path.iterdir()))
            print(f"  - {name}/ ({count} files) → {target}/ + symlink")

    has_scattered = any(scattered.values())
    if has_scattered:
        print("\nScattered files in root:")
        if scattered["docs"]:
            print("  Documentation:")
            for path, dest in scattered["docs"]:
                print(f"    - {path.name} → {dest}/")
        if scattered["work"]:
            print("  Work artifacts:")
            for path, dest in scattered["work"]:
                print(f"    - {path.name} → {dest}/")
        if scattered["debt"]:
            print("  Technical debt:")
            for path, dest in scattered["debt"]:
                print(f"    - {path.name} → {dest}/")


def show_archive_report(candidates: list, protected: list) -> None:
    """Display archive candidates and protected files."""
    print("\n" + "=" * 60)
    print("ARCHIVE CANDIDATES")
    print("=" * 60)

    if candidates:
        print(f"\nFiles to archive (>{ARCHIVE_AGE_DAYS} days old):")
        for path, age, category in candidates:
            print(f"  - {path.name} ({age} days old)")
    else:
        print("\nNo files eligible for archiving.")

    if protected:
        print(f"\nProtected ({len(protected)} files will NOT be archived):")
        for path, reason in protected[:10]:
            print(f"  - {path.name} ({reason})")
        if len(protected) > 10:
            print(f"  ... and {len(protected) - 10} more")


def create_structure(project_root: Path, missing_dirs: list) -> None:
    """Create missing directories."""
    print("\nCreating structure...")

    for dir_path in missing_dirs:
        full_path = project_root / dir_path
        full_path.mkdir(parents=True, exist_ok=True)
        print(f"  ✓ {dir_path}/")


def migrate_legacy_directory(project_root: Path, name: str, src: Path, target: str) -> int:
    """Move legacy directory contents to target and create symlink."""
    target_path = project_root / target
    target_path.mkdir(parents=True, exist_ok=True)

    files = list(src.iterdir())
    count = len(files)

    print(f"\nMigrating {name}/ ({count} files)...")

    for item in files:
        dest = target_path / item.name
        if dest.exists():
            dest = resolve_conflict(dest)
        shutil.move(str(item), str(dest))
        print(f"  → {item.name}")

    # Remove empty directory and create symlink
    src.rmdir()
    src.symlink_to(target_path)
    print(f"  [symlink] {name}/ → {target}/")

    return count


def migrate_files(project_root: Path, scattered: dict) -> int:
    """Migrate scattered files to their destinations."""
    count = 0

    all_files = scattered["docs"] + scattered["work"] + scattered["debt"]
    if not all_files:
        return 0

    print("\nMigrating files...")

    for src_path, dest in all_files:
        dest_dir = project_root / dest
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_path = resolve_conflict(dest_dir / src_path.name)

        shutil.move(str(src_path), str(dest_path))
        print(f"  → {src_path.name} → {dest}/{dest_path.name}")
        count += 1

    return count


def archive_files(project_root: Path, candidates: list) -> int:
    """Move old files to archive."""
    archive_month = datetime.now().strftime("%Y-%m")
    archive_base = project_root / ".claude" / "archive" / archive_month
    count = 0

    print(f"\nArchiving to .claude/archive/{archive_month}/...")

    for path, age, category in candidates:
        archive_dir = archive_base / category
        archive_dir.mkdir(parents=True, exist_ok=True)

        dest_path = resolve_conflict(archive_dir / path.name)
        shutil.move(str(path), str(dest_path))
        print(f"  → {path.name}")
        count += 1

    return count


def main():
    parser = argparse.ArgumentParser(description="Organize project structure")
    parser.add_argument("path", nargs="?", default=".", help="Project root path")
    parser.add_argument("--dry-run", action="store_true", help="Show what would happen without making changes")
    parser.add_argument("--yes", "-y", action="store_true", help="Auto-confirm all actions")
    args = parser.parse_args()

    project_root = Path(args.path).resolve()
    dry_run = args.dry_run
    auto_yes = args.yes

    if dry_run:
        print("=" * 60)
        print("DRY RUN - No changes will be made")
        print("=" * 60)

    print(f"\nOrganizing: {project_root}")

    # Phase 1: Structure and migration
    structure = check_structure(project_root)
    scattered = find_scattered_files(project_root)

    has_missing = bool(structure["missing_dirs"])
    has_legacy = bool(structure["legacy_dirs"])
    has_scattered = any(scattered.values())
    has_work = has_missing or has_legacy or has_scattered

    if has_work:
        show_structure_report(structure, scattered)

        if dry_run:
            print("\n" + "-" * 60)
            print("WOULD EXECUTE:")
            if structure["missing_dirs"]:
                print(f"  • Create {len(structure['missing_dirs'])} directories")
            if structure["legacy_dirs"]:
                print(f"  • Migrate {len(structure['legacy_dirs'])} legacy directories")
            total_scattered = sum(len(v) for v in scattered.values())
            if total_scattered:
                print(f"  • Move {total_scattered} scattered files")
        elif auto_yes:
            choice = "O"
        else:
            choice = prompt_choice(
                "What would you like to do?",
                [
                    ("O", "Organize (create structure and migrate)"),
                    ("S", "Skip to archive phase"),
                    ("Q", "Quit"),
                ]
            )

            if choice == "Q":
                print("Exiting.")
                return

        if choice == "O":
            # Create missing directories
            if structure["missing_dirs"]:
                create_structure(project_root, structure["missing_dirs"])

            # Migrate legacy directories
            for name, src, target in structure["legacy_dirs"]:
                migrate_legacy_directory(project_root, name, src, target)

            # Migrate scattered files
            if has_scattered:
                migrated = migrate_files(project_root, scattered)
                print(f"\n✓ Migrated {migrated} files.")
    else:
        print("\n✓ Structure is valid, no scattered files found.")

    # Phase 2: Archive old files
    candidates, protected = find_archive_candidates(project_root)

    if not candidates:
        print("\n✓ No files need archiving.")
        if dry_run:
            print("\n" + "=" * 60)
            print("DRY RUN COMPLETE")
            print("=" * 60)
        else:
            print("\nOrganization complete.")
        return

    show_archive_report(candidates, protected)

    archive_month = datetime.now().strftime("%Y-%m")

    if dry_run:
        print("\n" + "-" * 60)
        print("WOULD EXECUTE:")
        print(f"  • Archive {len(candidates)} files to .claude/archive/{archive_month}/")
        print("\n" + "=" * 60)
        print("DRY RUN COMPLETE")
        print("=" * 60)
        return

    if auto_yes:
        choice = "A"
    else:
        choice = prompt_choice(
            "What would you like to do?",
            [
                ("A", f"Archive {len(candidates)} files to .claude/archive/{archive_month}/"),
                ("S", "Skip archiving"),
                ("Q", "Quit"),
            ]
        )

        if choice in ("Q", "S"):
            print("Exiting.")
            return

    if choice == "A":
        archived = archive_files(project_root, candidates)
        print(f"\n✓ Archived {archived} files.")

    print("\nOrganization complete.")


if __name__ == "__main__":
    main()
