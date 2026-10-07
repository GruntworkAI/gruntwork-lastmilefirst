#!/usr/bin/env python3
"""Build a self-contained skills-only Codex pilot; no installation or activation."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import sys
import tomllib
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
SOURCE = REPO / "plugins" / "lastmilefirst"
DIST = HERE / "dist"
CORE = "skills/lastmilefirst/"
sys.path.insert(0, str(SOURCE / "hooks/scripts"))
from markdown_content import without_fenced_blocks  # shared content-only parser
VENDOR_FILES = [
    "skills/review-claude/scripts/review_claude.py",
    "skills/organize-claude/scripts/archetypes.py",
    "hooks/scripts/workspace_types.py",
    "hooks/scripts/markdown_content.py",
    "hooks/scripts/project_layout.py",
    "hooks/scripts/org_resources.py",
    "skills/todos-summary/scripts/aggregator.py",
    "skills/organize-orgs/scripts/check_identity.py",
    "templates/org.json",
]


def headings(text: str) -> list[tuple[int, int, str]]:
    """ATX headings outside fences (upstream examples contain real-looking headings)."""
    result = []
    for index, line in enumerate(without_fenced_blocks(text).splitlines()):
        match = re.match(r"^(#{1,6})\s+(.+?)\s*#*\s*$", line)
        if match:
            result.append((index, len(match.group(1)), match.group(2)))
    return result


def section(text: str, title: str) -> str:
    entries = headings(text)
    matches = [(i, level) for i, level, name in entries if name == title]
    if len(matches) != 1:
        raise ValueError(f"expected exactly one section {title!r}, found {len(matches)}")
    start, level = matches[0]
    end = next((i for i, depth, _ in entries if i > start and depth <= level), len(text.splitlines()))
    return "\n".join(text.splitlines()[start:end]).rstrip() + "\n"


def safe_source(relative: str) -> Path:
    path = SOURCE / relative
    if path.is_symlink() or not path.resolve().is_relative_to(SOURCE.resolve()) or not path.is_file():
        raise ValueError(f"missing or unsafe canonical source: {relative}")
    return path


def build() -> dict[str, bytes]:
    """Pure rendering; source hashes document provenance without runtime checkout links."""
    mapping = tomllib.loads((HERE / "mapping.toml").read_text())
    outputs: dict[str, bytes] = {}
    sources: dict[str, str] = {}

    def read(relative: str) -> bytes:
        data = safe_source(relative).read_bytes()
        sources[relative] = hashlib.sha256(data).hexdigest()
        return data

    def prose(text: str) -> str:
        for item in sorted(mapping["replacements"], key=lambda x: len(x["pattern"]), reverse=True):
            text = text.replace(item["pattern"], item["replacement"])
        return text

    for item in mapping["references"]:
        text = read(item["source"]).decode()
        extracted = "\n".join(section(text, title) for title in item["sections"])
        for title in item.get("exclude", []):
            extracted = extracted.replace(section(extracted, title), "")
        header = (f"> Generated judgment excerpt from canonical {item['source']}.\n"
                  "> Use with the adapter SKILL.md: these are review criteria, not permission to act.\n"
                  "> Existing CLAUDE.md paths describe legacy storage, not Codex automatic inheritance.\n\n")
        outputs[CORE + "references/" + item["output"]] = (header + prose(extracted)).encode()

    # Generate a readable archetype index from the same constants used by audits.
    tree = ast.parse(read("skills/organize-claude/scripts/archetypes.py"))
    constants = {}
    for node in tree.body:
        names = ([target.id for target in node.targets if isinstance(target, ast.Name)]
                 if isinstance(node, ast.Assign) else
                 [node.target.id] if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) else [])
        for name in names:
            if name in {"ARCHETYPE_DESCRIPTIONS", "ARCHETYPE_SECTIONS"}:
                constants[name] = ast.literal_eval(node.value)
    archetypes = ["# Project archetypes", "", "Generated from canonical archetype constants; declarations are not inferred.", ""]
    for name, description in constants["ARCHETYPE_DESCRIPTIONS"].items():
        sections = constants["ARCHETYPE_SECTIONS"][name]
        archetypes += [f"## {name.capitalize()}", description, "",
                       "Expected headings: " + ", ".join(header.lstrip("# ") for header, _ in sections), ""]
    outputs[CORE + "references/archetypes.md"] = ("\n".join(archetypes) + "\n").encode()

    roster = ["# Bundled persona briefs", "", "Use as a review lens, not as a tool identity or permission grant.",
              "These compact briefs retain canonical expertise topics. They do not port Claude tools, hooks, or runtime claims.", ""]
    for path in sorted((SOURCE / "personas").glob("*.md")):
        text = read(str(path.relative_to(SOURCE))).decode()
        title = next(name for _, depth, name in headings(text) if depth == 1)
        expertise = section(text, "Your Expertise")
        topics = [name.strip("*") for _, depth, name in headings(expertise) if depth == 3]
        brief = (f"# {title}\n\nCanonical domain brief; not an installed agent or platform tool.\n"
                 "Apply only the expertise relevant to this task. Never infer Codex capabilities from a persona.\n\n"
                 "## Expertise lenses\n" + "\n".join(f"- {topic}" for topic in topics) + "\n")
        if "shannon" in path.name:
            brief += ("\nShannon's canonical product expertise is Claude Code. For Codex mechanics use current official Codex documentation; "
                      "use this brief only for context placement and progressive disclosure.\n")
        outputs[CORE + "references/personas/" + path.name] = brief.encode()
        roster.append(f"- [{title}](personas/{path.name})")
    outputs[CORE + "references/personas.md"] = ("\n".join(roster) + "\n").encode()

    vendor = VENDOR_FILES + [str(p.relative_to(SOURCE)) for p in sorted(
        (SOURCE / "skills/organize-claude/templates").glob("*.template"))]
    for relative in vendor:
        outputs[CORE + "vendor/plugins/lastmilefirst/" + relative] = read(relative)

    source_manifest = json.loads(read(".claude-plugin/plugin.json"))
    manifest = {
        "$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
        "name": "lastmilefirst-codex",
        "version": source_manifest["version"] + "-codex.0",
        "description": "Bounded LastMileFirst pilot: PARC and read-only project, organization, and context reviews.",
        "author": source_manifest["author"],
        "repository": source_manifest["repository"],
        "license": source_manifest["license"],
        "keywords": ["parc", "organization", "context-review", "codex"],
    }
    outputs["plugin.json"] = (json.dumps(manifest, indent=2) + "\n").encode()
    for path in sorted((HERE / "adapter").rglob("*")):
        if path.is_symlink():
            raise ValueError(f"adapter symlinks are forbidden: {path}")
        if path.is_file() and "__pycache__" not in path.parts:
            relative = str(path.relative_to(HERE / "adapter"))
            if relative in outputs:
                raise ValueError(f"adapter would shadow generated source: {relative}")
            outputs[relative] = path.read_bytes()
    outputs["SOURCE_MANIFEST.json"] = (json.dumps({
        "upstream_version": source_manifest["version"], "sources_sha256": sources,
        "adapter_sha256": {str(p.relative_to(HERE)): hashlib.sha256(p.read_bytes()).hexdigest()
                           for p in sorted(HERE.rglob("*")) if p.is_file() and
                           (p == HERE / "build.py" or p == HERE / "mapping.toml" or
                            p.is_relative_to(HERE / "adapter")) and "__pycache__" not in p.parts},
    }, indent=2, sort_keys=True) + "\n").encode()
    return outputs


def lint(outputs: dict[str, bytes]) -> list[str]:
    issues = []
    manifest = json.loads(outputs["plugin.json"])
    if any(key in manifest for key in ("mcpServers", "apps", "hooks", "extensions")):
        issues.append("pilot manifest must remain skills-only")
    for relative, data in outputs.items():
        if Path(relative).is_absolute() or ".." in Path(relative).parts:
            issues.append(f"unsafe output path: {relative}")
        if relative.endswith(".py"):
            try:
                ast.parse(data, filename=relative)
            except SyntaxError as error:
                issues.append(str(error))
        if "/vendor/" in relative or not relative.endswith(".md"):
            continue
        text = data.decode()
        if re.search(r"/(?:run-|reload-|compound-engineering:)|\$\{(?:CLAUDE_PLUGIN_ROOT|SKILL_ROOT)\}", text):
            issues.append(f"unadapted command mechanism: {relative}")
        for link in re.findall(r"\[[^\]]+\]\(([^)]+)\)", text):
            if "://" in link or link.startswith("#"):
                continue
            target = Path(relative).parent / link.split("#")[0]
            # Normalize package-internal links without touching disk.
            import posixpath
            target = posixpath.normpath(str(target))
            if target not in outputs:
                issues.append(f"missing bundled reference: {relative} -> {link}")
        if relative.endswith("SKILL.md"):
            for key in ("name", "description"):
                if not re.search(rf"^{key}: .+", text, re.MULTILINE):
                    issues.append(f"missing {key}: {relative}")
    return issues


def check_destination(root: Path, outputs: dict[str, bytes]) -> None:
    # Never follow a pre-existing output symlink, including any ancestor.
    for path in [root, *root.parents]:
        if path.is_symlink():
            raise ValueError(f"output ancestor is a symlink: {path}")
    resolved = root.resolve()
    repo = REPO.resolve()
    if (resolved == repo or repo.is_relative_to(resolved) or
            (resolved.is_relative_to(repo) and resolved != DIST.resolve())):
        raise ValueError("output would overlap repository inputs; use the default dist/ or a directory outside the repository")
    if root.exists() and not root.is_dir():
        raise ValueError(f"output must be a directory: {root}")
    for path in root.rglob("*") if root.exists() else []:
        if path.is_symlink():
            raise ValueError(f"output symlink refused: {path}")
        if path.is_file() and path.stat().st_nlink > 1:
            raise ValueError(f"hardlinked output file refused: {path}")
        if path.is_file() and str(path.relative_to(root)) not in outputs:
            raise ValueError(f"unexpected output file (use a new empty --output): {path}")
    existing_files = [p for p in root.rglob("*") if p.is_file()] if root.exists() else []
    if existing_files:
        try:
            manifest = json.loads((root / "plugin.json").read_bytes())
            provenance = json.loads((root / "SOURCE_MANIFEST.json").read_bytes())
        except (OSError, ValueError) as error:
            raise ValueError("nonempty output is not a managed adapter package; use a new empty --output") from error
        if (not isinstance(manifest, dict) or not isinstance(provenance, dict) or
                manifest.get("name") != "lastmilefirst-codex" or
                not isinstance(provenance.get("sources_sha256"), dict) or
                not isinstance(provenance.get("adapter_sha256"), dict)):
            raise ValueError("nonempty output is not a managed adapter package; use a new empty --output")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify exact generated output without writing")
    parser.add_argument("--lint", action="store_true", help="validate rendered package without writing")
    parser.add_argument("--output", type=Path, default=DIST, help="package directory; never installs the plugin")
    args = parser.parse_args(argv)
    try:
        outputs = build()
        issues = lint(outputs)
        if issues:
            raise ValueError("\n".join(issues))
        if args.lint and not args.check:
            print(f"lint clean: {len(outputs)} package files")
            return 0
        root = args.output.absolute()
        check_destination(root, outputs)
        stale = [name for name, value in outputs.items()
                 if not (root / name).is_file() or (root / name).read_bytes() != value]
        if args.check:
            if stale:
                raise ValueError("stale or missing outputs: " + ", ".join(stale))
            print(f"package fresh: {len(outputs)} files")
            return 0
        for name in stale:
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(outputs[name])
        print(f"built {len(outputs)} files at {root}; not installed or activated")
        return 0
    except (ValueError, OSError, KeyError) as error:
        print(f"build failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
