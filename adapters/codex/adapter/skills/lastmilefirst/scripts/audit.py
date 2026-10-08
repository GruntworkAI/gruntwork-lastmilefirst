#!/usr/bin/env python3
"""Bounded, read-only LastMileFirst audit. Stdlib only; JSON on stdout.

Only named roots authorize reads. In particular, cwd does not authorize its
parents, and --workspace does not enable workspace-wide project discovery.
The installed vendor bundle is the source of section and identity semantics.
"""
import sys
sys.dont_write_bytecode = True  # Before importing the bundled loose scripts.

import argparse
import importlib
import json
import os
from pathlib import Path
import stat
import subprocess

MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_ENTRIES = 10000
CONTEXT_NAMES = ("AGENTS.md", "CLAUDE.md")
SIGNALS = (".git", "AGENTS.md", "CLAUDE.md", ".claude/work", ".claude/debt",
           "pyproject.toml", "package.json", "Cargo.toml", "go.mod", "Gemfile",
           "README.md", "README.rst", "README")


def canonical_helpers():
    """Import only the installed bundle, never a checkout or user's config."""
    bundle = Path(__file__).resolve().parents[1] / "vendor/plugins/lastmilefirst"
    modules = (
        ("review_claude", "skills/review-claude/scripts"),
        ("archetypes", "skills/organize-claude/scripts"),
        ("check_identity", "skills/organize-orgs/scripts"),
        ("workspace_types", "hooks/scripts"),
        ("markdown_content", "hooks/scripts"),
        ("aggregator", "skills/todos-summary/scripts"),
        ("project_layout", "hooks/scripts"),
        ("org_resources", "hooks/scripts"),
    )
    for module, relative in modules:
        if not (bundle / relative / (module + ".py")).is_file():
            raise RuntimeError("Bundled canonical helpers are missing; run the adapter build and use its output.")
    templates = bundle / "skills/organize-claude/templates"
    for filename in ("org-claude.md.template", "user-claude.md.template"):
        if not (templates / filename).is_file():
            raise RuntimeError(f"Bundled required template is missing: {filename}; rebuild the adapter.")
    for relative in dict.fromkeys(relative for _, relative in reversed(modules)):
        sys.path.insert(0, str(bundle / relative))
    review = importlib.import_module("review_claude")
    identity = importlib.import_module("check_identity")
    for tier in ("org", "user"):
        if not review.get_expected_sections(tier):
            raise RuntimeError(f"Bundled {tier} template has no readable required sections; rebuild the adapter.")
    return (review, identity, importlib.import_module("workspace_types"),
            importlib.import_module("markdown_content"), importlib.import_module("aggregator"),
            importlib.import_module("project_layout"), importlib.import_module("org_resources"))


class Audit:
    def __init__(self, args, review, identity, workspace, markdown, todos, layout, resources):
        self.args, self.review, self.identity_helper = args, review, identity
        self.workspace_helper, self.markdown_helper = workspace, markdown
        self.todo_helper, self.layout_helper, self.resource_helper = todos, layout, resources
        self.findings = []
        self.seen_findings = set()
        self.incomplete = False
        self.marker_cache = {}
        self.config_cache = {}
        self.context_cache = {}
        self.contents = {}
        self.roots = {}

    def finding(self, code, path, message, severity="warning", incomplete=False):
        key = (code, str(path), message)
        if key not in self.seen_findings:
            self.seen_findings.add(key)
            self.findings.append({"severity": severity, "code": code,
                                  "path": str(path), "message": message})
        self.incomplete |= incomplete

    def status(self, path, root):
        """lstat every component; reject all symlinks, including in-root links.

        This intentionally conservative policy also excludes linked worktrees.
        It is a best-effort filesystem audit, not a hostile concurrent-writer
        sandbox; callers must not mutate the audited tree while it runs.
        """
        try:
            path.relative_to(root)
        except ValueError:
            self.finding("unsafe-path", path, "Path leaves the explicitly approved root.", "error", True)
            return "unsafe"
        current = root
        try:
            for component in (None, *path.relative_to(root).parts):
                if component is not None:
                    current = current / component
                info = current.lstat()
                if stat.S_ISLNK(info.st_mode):
                    self.finding("symlink-skipped", current, "Symlinks are not followed, even within an approved root.", "warning", True)
                    return "unsafe"
                if current != path and not stat.S_ISDIR(info.st_mode):
                    return "missing"
            if stat.S_ISDIR(info.st_mode):
                return "directory"
            if stat.S_ISREG(info.st_mode):
                return "file"
            self.finding("special-file-skipped", path, "Only regular files and directories are read.", "warning", True)
            return "unsafe"
        except FileNotFoundError:
            return "missing"
        except (OSError, ValueError) as error:
            self.finding("inaccessible-path", path, str(error), "warning", True)
            return "unreadable"

    def read(self, path, root):
        state = self.status(path, root)
        if state != "file":
            if state == "directory":
                self.finding("expected-file", path, "Expected a regular file, found a directory.", "warning", True)
            return None, state
        try:
            # Opening with O_NOFOLLOW also closes the last-component link race.
            descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
            with os.fdopen(descriptor, "rb") as handle:
                info = os.fstat(handle.fileno())
                if not stat.S_ISREG(info.st_mode):
                    raise ValueError("File changed to a non-regular file during the audit.")
                if info.st_size > MAX_FILE_BYTES:
                    raise ValueError("File exceeds the 2 MiB audit limit.")
                data = handle.read(MAX_FILE_BYTES + 1)
                if len(data) > MAX_FILE_BYTES:
                    raise ValueError("File exceeds the 2 MiB audit limit.")
            return data.decode("utf-8"), "read"
        except (OSError, UnicodeError, ValueError) as error:
            self.finding("unreadable-file", path, str(error), "warning", True)
            return None, "unreadable"

    def children(self, directory, root, files=False):
        if self.status(directory, root) != "directory":
            return []
        try:
            entries = []
            with os.scandir(directory) as scan:
                for entry in scan:
                    if len(entries) >= MAX_ENTRIES:
                        self.finding("directory-limit", directory, "Directory exceeds the 10,000-entry audit limit.", "warning", True)
                        break
                    entries.append(Path(entry.path))
            result = []
            for child in sorted(entries):
                if child.name.startswith("."):
                    continue
                state = self.status(child, root)
                if state == "directory" or (files and state == "file"):
                    result.append(child)
            return result
        except OSError as error:
            self.finding("inaccessible-directory", directory, str(error), "warning", True)
            return []

    def root(self, name, value):
        path = Path(os.path.abspath(os.path.expanduser(str(value))))
        # The named directory itself must not be a link: that indirection is
        # disclosed, not followed. Links in its ancestors are operating-system
        # layout (macOS keeps /tmp and /var behind symlinks; a home directory
        # can live on another volume) and are resolved once, here. Everything
        # inside the resolved root is still held to the no-symlink rule.
        try:
            if path.is_symlink():
                self.finding("invalid-root", path, f"The {name} root must be an accessible, non-symlink directory.", "error")
                return None
        except OSError:
            pass
        path = Path(os.path.realpath(path))
        if path == Path(path.anchor):
            self.finding("unsafe-root", path, "A filesystem root is too broad; name a project, org, or workspace.", "error")
            return None
        # Check ancestor metadata only; never enumerate or read ancestor files.
        if self.status(path, Path(path.anchor)) != "directory":
            self.finding("invalid-root", path, f"The {name} root must be an accessible, non-symlink directory.", "error")
            return None
        self.roots[name] = path
        return path

    def marker(self, directory, root):
        if directory in self.marker_cache:
            return self.marker_cache[directory]
        content, state = self.read(directory / self.identity_helper.WORKSPACE_MARKER, root)
        result = {"path": str(directory / self.identity_helper.WORKSPACE_MARKER), "status": state, "type": None}
        if content is not None:
            result["type"] = self.identity_helper.parse_workspace_type(content, strict=True)
            if result["type"] is None:
                result["status"] = "malformed"
                self.finding("malformed-marker", directory / self.identity_helper.WORKSPACE_MARKER,
                             "Expected exactly one unquoted top-level type: studio, client, external, or scratch.", "warning", True)
        self.marker_cache[directory] = result
        return result

    def config(self, directory, root):
        if directory in self.config_cache:
            return self.config_cache[directory]
        path = directory / ".claude/org.json"
        content, state = self.read(path, root)
        data = None
        if content is not None:
            try:
                def unique_pairs(pairs):
                    obj = {}
                    for key, value in pairs:
                        if key in obj:
                            raise ValueError(f"Duplicate JSON key: {key}")
                        obj[key] = value
                    return obj
                data = json.loads(content, object_pairs_hook=unique_pairs,
                                  parse_constant=lambda value: (_ for _ in ()).throw(ValueError(f"Invalid JSON constant: {value}")))
                if not isinstance(data, dict):
                    raise ValueError("org.json must contain a JSON object.")
                state = "read"
            except (ValueError, RecursionError) as error:
                data, state = None, "malformed"
                self.finding("malformed-org-config", path, str(error), "error", True)
        result = ({"path": str(path), "status": state}, data)
        self.config_cache[directory] = result
        return result

    def context(self, directory, tier, root):
        key = (directory, tier)
        if key in self.context_cache:
            return self.context_cache[key]
        path = directory / self.args.context_name
        content, state = self.read(path, root)
        visible = self.markdown_helper.without_fenced_blocks(content or "", strict=True)
        headings = self.review.extract_headings(visible)
        archetype = None
        if tier == "project":
            # Canonical detect_archetype alone also matches inside code fences.
            declarations = [h for h in headings if h.startswith("archetype:")]
            if len(declarations) == 1:
                archetype = self.review.detect_archetype("## " + declarations[0])
            if archetype is None:
                self.finding("archetype-missing-or-invalid", path,
                             "Declare exactly one of Deployable, Usable, Referenceable, Experimental in an Archetype heading.")
        expected = []
        if tier == "project" and archetype:
            expected = self.review.get_sections_for_archetype(archetype)
        elif tier in ("org", "workspace"):
            expected = self.review.get_expected_sections("user" if tier == "workspace" else "org")
        sections = []
        for header, description in expected:
            match, heading = self.review.match_section(header, headings)
            sections.append({"header": header, "description": description, "status": match,
                             "matched_heading": heading})
        missing = [item["header"] for item in sections if item["status"] == "missing"]
        if state == "missing" and tier != "client":
            self.finding("context-missing", path, f"No {self.args.context_name} at the explicit {tier} tier.")
        if missing:
            self.finding("context-section-gaps", path, "Missing required sections: " + ", ".join(missing))
        result = {"tier": tier, "path": str(path), "status": state, "archetype": archetype,
                  "headings": headings, "sections": sections,
                  "section_coverage": "unclassified" if tier == "project" and not archetype else "checked"}
        self.context_cache[key] = result
        self.contents[str(path)] = visible
        return result

    def discover(self, org):
        entries, children, skipped = [], {}, []

        def report_layout(issues):
            # Canonical kinds/decisions; audit wording never suggests a repair
            # was authorized, and excluded repository scope stays explicit.
            messages = {
                "container-org-json": ("A client container must not carry .claude/org.json.", "error", False),
                "container-is-repo": ("A client container is also a repository; its own repository is outside project discovery.", "warning", True),
                "nested-container": ("Only one client tier is supported; this directory is treated as a project.", "warning", True),
            }
            for issue in issues:
                self.finding(issue.kind, issue.path, *messages[issue.kind])

        for child in self.children(org, org):
            marker = self.marker(child, org)
            if marker["status"] == "malformed":
                skipped.append({"path": str(child), "reason": "malformed-marker"})
                continue
            if marker["type"] in self.workspace_helper.CONTAINER_TYPES:
                entries.append((child, marker["type"]))
                children[child] = []
                config, _ = self.config(child, org)
                report_layout(self.workspace_helper.container_layout_issues(
                    org, child, has_org_config=config["status"] != "missing", is_repo=False))
                report_layout(self.workspace_helper.container_layout_issues(
                    org, child, has_org_config=False, is_repo=self.status(child / ".git", org) != "missing"))
                for project in self.children(child, org):
                    nested = self.marker(project, org)
                    report_layout(self.workspace_helper.container_layout_issues(
                        org, child, has_org_config=False, is_repo=False,
                        child_markers=[(project, nested["type"])]))
                    if nested["status"] == "malformed":
                        skipped.append({"path": str(project), "reason": "malformed-marker"})
                    elif self.is_project(project, org) or nested["type"] in self.workspace_helper.CONTAINER_TYPES:
                        children[child].append(project)
                    else:
                        skipped.append({"path": str(project), "reason": "no-project-evidence"})
            elif self.is_project(child, org):
                entries.append((child, marker["type"]))
            else:
                skipped.append({"path": str(child), "reason": "no-project-evidence"})
        layout = self.workspace_helper.classify_org_entries(org, entries, children)
        return ([(item.path, item.path.parent if item.client else None) for item in layout.projects],
                list(layout.containers), skipped)

    def is_project(self, directory, root):
        return any(self.status(directory / signal, root) in {"file", "directory"} for signal in SIGNALS)

    def resources(self, org, config):
        results = []
        for name in self.resource_helper.RESOURCE_NAMES:
            settings = self.resource_helper.resource_settings(org.name, name, config, strict=True)
            item = {"name": name, "status": "unconfigured", "path": None,
                    "cleanliness": "unverified", "synchronization": "unverified"}
            if settings["status"] == "malformed":
                item["status"] = "malformed"
                self.finding("malformed-resource", org / ".claude/org.json", settings["problem"])
            elif settings["status"] == "opted-out":
                item["status"] = "opted-out"
            elif settings["status"] == "external":
                item.update(status="external-not-queried", backend=settings["backend"])
            else:
                relative = settings["relative"]
                if (not isinstance(relative, str) or not relative or "\\" in relative
                        or Path(relative).is_absolute()
                        or any(p.startswith(".") or p == "" for p in relative.split("/"))):
                    item["status"] = "unsafe"
                    self.finding("unsafe-resource-path", org / ".claude/org.json",
                                 f"{name} must reference a non-hidden relative path inside the org.", "error", True)
                else:
                    path = org / relative
                    item["path"] = str(path)
                    item["status"] = self.status(path, org)
                    if item["status"] == "directory" and name != "stack_knowledge":
                        item["git_metadata"] = self.status(path / ".git", org)
                    if item["status"] == "missing":
                        self.finding("resource-missing", path, f"The configured/default {name} location is missing.")
            results.append(item)
        return results

    def contract_summary(self, config):
        """Report shared validation using the audit's explicitly strict policy."""
        summary = self.identity_helper.inspect_identity_contract(config, strict=True)
        result = {"status": summary.status, "enforcement": summary.enforcement, "problems": []}
        if summary.status == "missing":
            result["problems"].append("The governing config has no valid identity block.")
        if summary.missing_fields:
            result["problems"].append("Missing, placeholder, or malformed identity fields: " + ", ".join(summary.missing_fields))
        if summary.invalid_enforcement:
            result["problems"].append("identity.enforcement must be block, warn, or off.")
        if summary.invalid_owners:
            result["problems"].append("identity.owns_remotes must be a list of nonempty owner strings.")
        return result

    def todos(self, project, root):
        directory = project / ".claude/work/todos"
        result = {"path": str(directory), "status": self.status(directory, root), "files": [],
                  "open_checkboxes": 0, "done_checkboxes": 0}
        for path in self.children(directory, root, files=True):
            if path.suffix.lower() != ".md" or self.status(path, root) != "file":
                continue
            content, state = self.read(path, root)
            if content is None:
                continue
            parsed = self.todo_helper.parse_todo_content(
                content, path.name, ignore_fenced=True, strict_frontmatter=True, strict_headings=True)
            if parsed["frontmatter_status"] == "malformed":
                self.finding("malformed-todo-frontmatter", path, "Opening frontmatter delimiter has no closing delimiter.", "warning", True)
            frontmatter = parsed["frontmatter"]
            opened, done = parsed["open_checkboxes"], parsed["done_checkboxes"]
            result["files"].append({"path": str(path), "title": parsed["title"],
                                    "status": frontmatter.get("status", "pending"),
                                    "priority": frontmatter.get("priority", "normal"),
                                    "open_checkboxes": opened, "done_checkboxes": done})
            result["open_checkboxes"] += opened
            result["done_checkboxes"] += done
        return result

    def claims(self, workspace, org):
        directories = self.children(workspace, workspace) if workspace else ([org] if org else [])
        registry = self.identity_helper.collect_claims(
            ((directory, self.config(directory, workspace or org)[1]) for directory in directories), strict=True)
        for directory in registry.invalid_sources:
            self.finding("invalid-claim-contract", directory / ".claude/org.json",
                         "Cannot read remote claims: expected an account string and list of nonempty owner strings.", "warning", True)
        return registry.claims

    def git_config(self, project, root):
        """Read one validated repository-local file; no global/includes/hooks."""
        metadata = project / ".git"
        state = self.status(metadata, root)
        if state == "missing":
            return None, "not-a-repository"
        if state != "directory":
            self.finding("git-metadata-skipped", metadata,
                         "Linked worktree/submodule pointers and unsafe .git entries are not followed.", "warning", True)
            return None, "unsupported-git-metadata"
        path = metadata / "config"
        _, state = self.read(path, root)
        if state != "read":
            return None, "unreadable-git-config"
        environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
        environment.update({"GIT_OPTIONAL_LOCKS": "0", "GIT_CONFIG_NOSYSTEM": "1",
                            "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull,
                            "GIT_TERMINAL_PROMPT": "0"})
        command = ["git", "--no-pager", "-c", "core.fsmonitor=false", "-c", "core.untrackedCache=false",
                   "config", "--file", str(path), "--no-includes", "--null", "--list"]
        try:
            completed = subprocess.run(command, cwd=project, env=environment, capture_output=True,
                                       text=True, timeout=5, check=False)
        except (OSError, subprocess.TimeoutExpired, UnicodeError) as error:
            self.finding("git-read-failed", path, str(error), "warning", True)
            return None, "unavailable"
        if completed.returncode:
            self.finding("git-read-failed", path, "Git could not parse the repository-local config.", "warning", True)
            return None, "unreadable-git-config"
        values = {}
        for record in completed.stdout.split("\0"):
            key, separator, value = record.partition("\n")
            if separator:
                values[key] = value
        return values, "read"

    def identity(self, project, client, org, workspace, claims):
        root = org or project
        result = {"status": "unverified", "contract_path": None, "enforcement": None,
                  "identity_source": "repository-local-config-only", "problems": [], "remotes": [],
                  "limitations": ["Global, system, include/includeIf and environment identities are not evaluated.",
                                  "GitHub authentication and remote connectivity are not checked."]}
        tiers = [p for p in (workspace, org, client, project) if p is not None]
        if self.identity_helper.select_ungoverned_ancestor(
                (tier, self.marker(tier, workspace or root)["type"]) for tier in tiers):
            result.update(status="skipped", reason="external-or-scratch-marker")
            return result

        def candidates():
            # Explicit tiers only. A client config is flagged, not trusted.
            for tier in (project, org, workspace):
                if tier is not None:
                    meta, config = self.config(tier, workspace or root)
                    yield tier, meta["status"] != "missing", config

        governing, contract = self.identity_helper.select_governing_org(candidates(), stop_on_malformed=True)
        if governing is None:
            result["status"] = "no-contract-in-approved-scope"
            return result
        result["contract_path"] = str(governing / ".claude/org.json")
        summary = self.contract_summary(contract)
        result["enforcement"] = summary["enforcement"]
        if summary["status"] in {"missing", "invalid"}:
            result["status"] = "invalid-contract"
            result["problems"] = summary["problems"]
            return result
        if summary["status"] == "disabled":
            result["status"] = "skipped"
            result["reason"] = "enforcement-off"
            return result
        identity = contract["identity"]
        enforcement = summary["enforcement"]
        values, state = self.git_config(project, root)
        if values is None:
            result["status"] = state
            return result
        comparison = self.identity_helper.compare_identity_fields(identity, values)
        for key in comparison.mismatches:
            result["problems"].append(f"Repository-local {key} does not match the governing contract.")
        for key, url in sorted(values.items()):
            if key.startswith("remote.") and key.endswith(".url"):
                claim = self.identity_helper.inspect_remote_claim(url, identity["github_account"], claims)
                result["remotes"].append({"name": key[7:-4], "owner": claim.owner, "claimed_by": list(claim.claimed_by)})
                if len(claim.claimed_by) > 1:
                    self.finding("ambiguous-owner-claims", project,
                                 f"Remote {key[7:-4]} has an owner claimed by multiple accounts; review the org contracts.")
                if claim.conflict:
                    result["problems"].append(f"Remote {key[7:-4]} belongs to an owner claimed by a different account.")
        result["unresolved_fields"] = list(comparison.unresolved_fields)
        if result["problems"]:
            result["status"] = "mismatch" if enforcement == "block" else "warned"
        elif comparison.unresolved_fields:
            result["status"] = "unverified-inherited-identity"
        else:
            result["status"] = "matches-local-config"
        return result

    def overlaps(self, contexts):
        return [dict(item, interpretation="Shared topic only; content was not compared for contradictions.")
                for item in self.review.topic_overlaps(
                    (context["tier"], context["path"], context["headings"]) for context in contexts)
                if len(item["carriers"]) > 1]

    def run(self):
        report = {"schema_version": 1, "mode": "read-only", "status": "error", "scope": {},
                  "coverage": {}, "hierarchy": [], "organization": None, "projects": [], "findings": self.findings}
        project = self.root("project", self.args.project)
        org = self.root("org", self.args.org) if self.args.org else None
        workspace = self.root("workspace", self.args.workspace) if self.args.workspace else None
        report["scope"] = {name: str(path) for name, path in self.roots.items()}
        report["scope"].update({"context_name": self.args.context_name})
        if not project or (self.args.org and not org) or (self.args.workspace and not workspace):
            return report, 2
        if org and not project.is_relative_to(org):
            self.finding("inconsistent-scope", project, "--project must be inside --org.", "error")
            return report, 2
        if workspace and not (org or project).is_relative_to(workspace):
            self.finding("inconsistent-scope", org or project, "The named org/project must be inside --workspace.", "error")
            return report, 2
        if org and workspace and org.parent != workspace:
            self.finding("inconsistent-scope", org, "--org must be directly inside --workspace; no tiers are guessed.", "error")
            return report, 2
        limitations = ["No network, hooks, state/cache writes, parent search, or home/config discovery.",
                       "Discovery recognizes non-hidden directories with project evidence; arbitrary directories are excluded.",
                       "Symlinks and linked worktree/submodule git pointers are excluded.",
                       "Section presence and topic overlap are evidence, not semantic correctness or contradiction checks."]
        if not org:
            limitations.append("Organization coverage is partial: supply --org to authorize org context, sibling projects, and shared resources.")
        if not workspace:
            limitations.append("Cross-org remote claims are partial: supply --workspace to authorize direct org contract reads.")
        report["coverage"] = {"organization": "explicit-org" if org else "partial-project-only",
                              "project_discovery": "direct-and-one-client-tier" if org else "explicit-project-only",
                              "identity_claims": "explicit-workspace" if workspace else "explicit-org-only" if org else "not-checked",
                              "limitations": limitations}
        contexts = []
        if workspace:
            self.marker(workspace, workspace)
            contexts.append(self.context(workspace, "workspace", workspace))
        clients, skipped = [], []
        if org:
            self.marker(org, org)
            contexts.append(self.context(org, "org", org))
            projects, clients, skipped = self.discover(org)
            if project != org and project not in [p for p, _ in projects]:
                relative = project.relative_to(org).parts
                if len(relative) == 1 and project not in clients and not project.name.startswith("."):
                    projects.append((project, None))
                elif len(relative) == 2 and project.parent in clients and not project.name.startswith("."):
                    projects.append((project, project.parent))
                else:
                    self.finding("unsupported-project-tier", project,
                                 "Explicit project must be direct or inside one marked client tier, and cannot be a hidden directory or client container.", "error")
                    return report, 2
                # Naming the project is the evidence discovery lacked: it is
                # reviewed, so it is no longer an excluded directory.
                skipped = [item for item in skipped if Path(item["path"]) != project]
            config_meta, config = self.config(org, org)
            org_context = contexts[-1]
            # A filtered directory still exists. Include known excluded paths
            # in the inventory comparison rather than calling their rows stale.
            unreviewed = sorted(str(Path(item["path"]).relative_to(org)) for item in skipped)
            inventory_names = sorted(set(str(p.relative_to(org)) for p, _ in projects) | set(unreviewed))
            inventory = self.review.check_inventory(self.contents[org_context["path"]], "org",
                                                   inventory_names,
                                                   tuple(org.name + "/" + p.name for p in clients))
            inventory["unreviewed_on_disk"] = unreviewed
            inventory["coverage"] = "partial" if self.incomplete or skipped else "complete"
            if self.incomplete:
                # Inaccessible or unsafe directories can hide a matching path.
                # These are candidates to review, not proved-absent projects.
                inventory["unverified_rows"] = inventory["not_on_disk"]
                inventory["not_on_disk"] = []
            if skipped:
                self.finding("project-discovery-incomplete", org,
                             "Some existing directories were excluded from project review; see unreviewed_on_disk and skipped_directories.",
                             "warning", True)
            contract_summary = self.contract_summary(config)
            report["organization"] = {"path": str(org), "config": config_meta,
                                      "identity_contract": contract_summary,
                                      "inventory": inventory, "resources": self.resources(org, config or {}),
                                      "clients": [str(p) for p in clients], "skipped_directories": skipped}
            if config_meta["status"] == "missing":
                self.finding("org-config-missing", org / ".claude/org.json", "No org contract or shared-resource configuration exists.")
            elif contract_summary["status"] in {"missing", "invalid"}:
                self.finding("org-identity-contract", org / ".claude/org.json",
                             "; ".join(contract_summary["problems"]), "error")
            if inventory["unlisted"] or inventory["not_on_disk"]:
                self.finding("inventory-drift", org_context["path"], "The Projects table and discovered project evidence differ.")
        else:
            projects = [(project, None)]
        claims = self.claims(workspace, org)
        report["hierarchy"].extend(contexts)
        for client in clients:
            report["hierarchy"].append(self.context(client, "client", org))
        for path, client in sorted(projects):
            root = org or path
            own = self.context(path, "project", root)
            chain = contexts + ([self.context(client, "client", root)] if client else []) + [own]
            report["hierarchy"].append(own)
            layout = [{"path": str(path / item), "status": self.status(path / item, root)} for item in self.layout_helper.PROJECT_LAYOUT]
            identity = self.identity(path, client, org, workspace, claims)
            if identity["status"] in {"mismatch", "warned", "invalid-contract"}:
                self.finding("identity-" + identity["status"], path, "; ".join(identity["problems"]),
                             "error" if identity["status"] != "warned" else "warning")
            report["projects"].append({"path": str(path), "label": str(path.relative_to(org)) if org else path.name,
                                       "client": client.name if client else None, "context": own, "layout": layout,
                                       "todos": self.todos(path, root), "identity": identity, "overlaps": self.overlaps(chain)})
        report["status"] = "partial" if self.incomplete or not org else "complete"
        return report, 0


def main(argv=None):
    class JsonArgumentParser(argparse.ArgumentParser):
        def error(self, message):
            raise ValueError(message)

    parser = JsonArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=Path.cwd(), help="Explicit project root (default: cwd).")
    parser.add_argument("--org", type=Path, help="Explicitly approved org root; enables bounded project discovery.")
    parser.add_argument("--workspace", type=Path, help="Approved workspace context and direct org identity contracts only.")
    parser.add_argument("--context-name", choices=CONTEXT_NAMES, default="AGENTS.md")
    try:
        args = parser.parse_args(argv)
        helpers = canonical_helpers()
        report, code = Audit(args, *helpers).run()
    except (ImportError, RuntimeError, OSError, ValueError) as error:
        report, code = {"schema_version": 1, "mode": "read-only", "status": "error",
                        "findings": [{"severity": "error", "code": "audit-unavailable", "path": str(Path(__file__)),
                                      "message": str(error)}]}, 2
    print(json.dumps(report, indent=2, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
