"""Read-only adapter contract tests; run with stdlib unittest, no installation.

Each invocation uses a standalone skill copy in a temporary directory. Fake
orgs, clients, git configs, and home directories contain no user information.
"""
import sys
sys.dont_write_bytecode = True

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import unittest
from unittest.mock import patch


REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "adapters/codex/adapter/skills/lastmilefirst/scripts/audit.py"
CANONICAL = REPO / "plugins/lastmilefirst"
VENDOR_FILES = (
    "skills/review-claude/scripts/review_claude.py",
    "skills/organize-claude/scripts/archetypes.py",
    "hooks/scripts/workspace_types.py",
    "hooks/scripts/markdown_content.py",
    "hooks/scripts/project_layout.py",
    "hooks/scripts/org_resources.py",
    "skills/todos-summary/scripts/aggregator.py",
    "skills/organize-orgs/scripts/check_identity.py",
    "templates/org.json",
)


def write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def snapshot(root):
    result = {}
    for path in sorted(root.rglob("*")):
        info = path.lstat()
        if stat.S_ISLNK(info.st_mode):
            value = ("link", os.readlink(path))
        elif path.is_file():
            value = ("file", hashlib.sha256(path.read_bytes()).hexdigest(), info.st_mtime_ns)
        elif path.is_dir():
            value = ("directory", info.st_mtime_ns)
        else:
            value = ("special", info.st_mode)
        result[str(path.relative_to(root))] = value
    return result


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="lmf-audit-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.skill = self.root / "installed/skills/lastmilefirst"
        self.script = self.skill / "scripts/audit.py"
        self.script.parent.mkdir(parents=True)
        shutil.copyfile(SCRIPT, self.script)
        bundle = self.skill / "vendor/plugins/lastmilefirst"
        for relative in VENDOR_FILES:
            target = bundle / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(CANONICAL / relative, target)
        shutil.copytree(CANONICAL / "skills/organize-claude/templates",
                        bundle / "skills/organize-claude/templates")
        self.home = self.root / "home"
        self.home.mkdir()
        self.workspace = self.root / "workspace"
        self.org = self.workspace / "studio"
        self.project = self.org / "alpha"
        self.project.mkdir(parents=True)
        self.env = dict(os.environ, HOME=str(self.home))
        self.env.pop("PYTHONDONTWRITEBYTECODE", None)

    def run_audit(self, *arguments, expected_code=0, cwd=None, env=None):
        completed = subprocess.run([sys.executable, str(self.script), *map(str, arguments)],
                                   cwd=cwd or self.project, env=env or self.env,
                                   capture_output=True, text=True, timeout=20)
        self.assertEqual(completed.returncode, expected_code, completed.stderr + completed.stdout)
        self.assertEqual(completed.stderr, "", completed.stderr)
        return json.loads(completed.stdout)

    def context(self, project=None, archetype="experimental", extra="", name="AGENTS.md"):
        return write((project or self.project) / name,
                     f"# Example\n\n## Archetype: {archetype}\n\n## Quick Commands\n\n{extra}")

    def org_config(self, org=None, account="team", **kwargs):
        data = {"name": "Example", "operatives": {"enabled": False},
                "stack_wisdom": {"enabled": False}, "stack_knowledge": {"enabled": False},
                "identity": {"github_account": account, "git_user_name": "Example Author",
                             "git_email": "author@example.invalid", "owns_remotes": [account],
                             "enforcement": "block"}}
        data.update(kwargs)
        return write((org or self.org) / ".claude/org.json", json.dumps(data))

    def git(self, project=None, name="Example Author", email="author@example.invalid", remote="team"):
        value = "[core]\n\trepositoryformatversion = 0\n\tbare = false\n"
        if name or email:
            value += "[user]\n"
            if name:
                value += f"\tname = {name}\n"
            if email:
                value += f"\temail = {email}\n"
        value += f'[remote "origin"]\n\turl = git@github.com:{remote}/example.git\n'
        return write((project or self.project) / ".git/config", value)

    def codes(self, report):
        return {item["code"] for item in report["findings"]}

    def test_standalone_default_cwd_is_partial_and_never_reads_parents(self):
        self.context()
        write(self.org / ".claude/org.json", "not JSON: must never be read")
        write(self.org / "AGENTS.md", "## Secret Parent Heading")
        report = self.run_audit()
        self.assertEqual(report["schema_version"], 1)
        self.assertEqual(report["mode"], "read-only")
        self.assertEqual(report["status"], "partial")
        self.assertEqual(report["coverage"]["organization"], "partial-project-only")
        self.assertEqual([c["tier"] for c in report["hierarchy"]], ["project"])
        self.assertNotIn("malformed-org-config", self.codes(report))
        self.assertEqual(report["projects"][0]["identity"]["status"], "no-contract-in-approved-scope")

    def test_org_discovers_direct_and_one_client_tier_only(self):
        self.context()
        self.org_config()
        client = self.org / "counterparty"
        write(client / ".claude-workspace", "type: client\nstatus: active\n")
        self.context(client / "beta", extra="## Tools\n")
        self.context(client / ".hidden")
        self.context(self.org / ".hidden")
        (self.org / "assets").mkdir()
        (client / "not-a-project").mkdir()
        write(self.org / "AGENTS.md", "## Projects\n\n| Name | Purpose |\n| --- | --- |\n| alpha | example |\n| counterparty/beta | example |\n")
        report = self.run_audit("--org", self.org)
        self.assertEqual([p["label"] for p in report["projects"]], ["alpha", "counterparty/beta"])
        self.assertEqual(report["organization"]["inventory"]["unlisted"], ["assets", "counterparty/not-a-project"])
        self.assertEqual(report["organization"]["inventory"]["not_on_disk"], [])
        self.assertEqual(len(report["organization"]["skipped_directories"]), 2)
        self.assertEqual(report["status"], "partial")

    def test_referenceable_readme_and_excluded_directory_are_never_reported_absent(self):
        self.context()
        write(self.org / "handbook/README.md", "# Reference handbook\n")
        write(self.org / "misc/example.txt", "An arbitrary file\n")
        write(self.org / "AGENTS.md", "## Projects\n\n| Name | Purpose |\n| --- | --- |\n| alpha | example |\n| handbook | reference |\n| misc | other |\n")
        report = self.run_audit("--org", self.org)
        self.assertEqual([p["label"] for p in report["projects"]], ["alpha", "handbook"])
        inventory = report["organization"]["inventory"]
        self.assertEqual(inventory["not_on_disk"], [])
        self.assertEqual(inventory["unreviewed_on_disk"], ["misc"])
        self.assertEqual(inventory["coverage"], "partial")
        self.assertEqual(report["status"], "partial")

    def test_org_root_can_be_selected_without_becoming_a_project(self):
        self.context()
        report = self.run_audit("--project", self.org, "--org", self.org)
        self.assertEqual([p["label"] for p in report["projects"]], ["alpha"])

    def test_all_four_archetypes_reuse_bundled_rubrics(self):
        expected = {"experimental": "## Quick Commands", "referenceable": "## Content Structure",
                    "usable": "## Installation", "deployable": "## Deployment"}
        for archetype, required in expected.items():
            with self.subTest(archetype=archetype):
                self.context(archetype=archetype)
                report = self.run_audit()
                context = report["projects"][0]["context"]
                self.assertEqual(context["archetype"], archetype)
                self.assertIn(required, [item["header"] for item in context["sections"]])

    def test_fenced_archetype_is_not_a_declaration_and_aliases_work(self):
        write(self.project / "AGENTS.md", "```md\n## Archetype: Deployable\n```\n## Archetype: Experimental\n## Commands\n")
        context = self.run_audit()["projects"][0]["context"]
        self.assertEqual(context["archetype"], "experimental")
        self.assertEqual(context["sections"][0]["status"], "present_via_alias")
        write(self.project / "AGENTS.md", "```md\n## Archetype: Experimental\n## Quick Commands\n```\n")
        self.assertIsNone(self.run_audit()["projects"][0]["context"]["archetype"])

    def test_fences_require_matching_character_and_sufficient_length(self):
        for opening, embedded, closing in (("````md", "```", "````"), ("~~~~", "~~~", "~~~~"),
                                          ("```md", "~~~", "```")):
            with self.subTest(opening=opening, embedded=embedded):
                write(self.project / "AGENTS.md", f"## Archetype: Experimental\n{opening}\n{embedded}\n## Quick Commands\n{closing}\n")
                context = self.run_audit()["projects"][0]["context"]
                self.assertEqual(context["sections"][0]["status"], "missing")
                write(self.project / ".claude/work/todos/example.md",
                      f"# Actual task\n{opening}\n{embedded}\n- [ ] Example only\n{closing}\n- [ ] Actual\n")
                self.assertEqual(self.run_audit()["projects"][0]["todos"]["open_checkboxes"], 1)

    def test_empty_org_still_validates_marker_and_identity_contract(self):
        self.project.rmdir()
        write(self.org / ".claude-workspace", "type: unknown\n")
        self.org_config(identity={})
        report = self.run_audit("--project", self.org, "--org", self.org, cwd=self.org)
        self.assertEqual(report["projects"], [])
        self.assertTrue({"malformed-marker", "org-identity-contract"}.issubset(self.codes(report)))
        self.assertEqual(report["organization"]["identity_contract"]["status"], "missing")
        self.assertEqual(report["status"], "partial")

    def test_missing_or_malformed_required_templates_fail_as_json(self):
        templates = self.skill / "vendor/plugins/lastmilefirst/skills/organize-claude/templates"
        for filename in ("org-claude.md.template", "user-claude.md.template"):
            path = templates / filename
            original = path.read_text()
            path.unlink()
            report = self.run_audit(expected_code=2)
            self.assertEqual(report["status"], "error")
            self.assertIn("template is missing", report["findings"][0]["message"])
            write(path, "# Template without required section definitions\n")
            self.assertIn("no readable required sections", self.run_audit(expected_code=2)["findings"][0]["message"])
            write(path, original)

    def test_argument_errors_return_json(self):
        for arguments in (("--context-name", "README.md"), ("--unknown-option",), ("--org",)):
            report = self.run_audit(*arguments, expected_code=2)
            self.assertEqual(report["status"], "error")

    def test_explicit_context_filename_and_unknown_archetype(self):
        self.context(name="CLAUDE.md", archetype="imaginary")
        report = self.run_audit("--context-name", "CLAUDE.md")
        self.assertEqual(report["projects"][0]["context"]["status"], "read")
        self.assertIn("archetype-missing-or-invalid", self.codes(report))

    def test_overlap_reports_evidence_not_contradictions(self):
        self.context(extra="## Tools\nUse tool A.\n")
        write(self.org / "AGENTS.md", "## Approved Tools\nUse tool B.\n")
        write(self.workspace / "AGENTS.md", "## Development Tools\nUse tool C.\n")
        report = self.run_audit("--org", self.org, "--workspace", self.workspace)
        overlap = report["projects"][0]["overlaps"][0]
        self.assertEqual(overlap["topic"], "tools")
        self.assertEqual([c["tier"] for c in overlap["carriers"]], ["workspace", "org", "project"])
        self.assertIn("not compared", overlap["interpretation"])

    def test_todos_and_preserved_layout_are_read_only(self):
        self.context()
        write(self.project / ".claude/work/todos/task.md",
              "---\nstatus: pending\npriority: high\n---\n# Example task\n- [ ] Open\n- [x] Done\n```\n- [ ] Example\n```\n")
        for relative in (".claude/work/plans", ".claude/work/sessions", ".claude/debt", ".claude/archive"):
            (self.project / relative).mkdir(parents=True)
        todos = self.run_audit()["projects"][0]["todos"]
        self.assertEqual((todos["open_checkboxes"], todos["done_checkboxes"]), (1, 1))
        self.assertEqual(todos["files"][0]["priority"], "high")
        self.assertEqual(todos["files"][0]["title"], "Example task")

    def test_crlf_todo_frontmatter_preserves_status_and_priority(self):
        self.context()
        todo = self.project / ".claude/work/todos/example.md"
        todo.parent.mkdir(parents=True)
        todo.write_bytes(b"---\r\nstatus: complete\r\npriority: high\r\n---\r\n# Finished task\r\n- [x] Done\r\n")
        original = todo.read_bytes()
        result = self.run_audit()["projects"][0]["todos"]["files"][0]
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["priority"], "high")
        self.assertEqual(result["title"], "Finished task")
        self.assertEqual(result["done_checkboxes"], 1)
        self.assertEqual(todo.read_bytes(), original)

    def test_optouts_local_resources_and_unsafe_paths(self):
        self.context()
        self.org_config(stack_knowledge={"type": "local", "path": "../outside"})
        report = self.run_audit("--org", self.org)
        resources = {r["name"]: r for r in report["organization"]["resources"]}
        self.assertEqual(resources["operatives"]["status"], "opted-out")
        self.assertEqual(resources["stack_wisdom"]["status"], "opted-out")
        self.assertEqual(resources["stack_knowledge"]["status"], "unsafe")
        self.assertIn("unsafe-resource-path", self.codes(report))
        self.org_config(stack_knowledge={"type": "confluence", "url": "https://example.invalid"})
        self.assertEqual(self.run_audit("--org", self.org)["organization"]["resources"][-1]["status"], "external-not-queried")

    def test_missing_and_inconsistent_roots_return_json_error(self):
        for args in (("--project", self.root / "missing"), ("--org", self.root / "missing"),
                     ("--workspace", self.home), ("--project", self.home, "--org", self.org),
                     ("--project", "/")):
            with self.subTest(args=args):
                before = snapshot(self.root)
                report = self.run_audit(*args, expected_code=2)
                self.assertEqual(snapshot(self.root), before)
                self.assertEqual(report["status"], "error")
                self.assertTrue(report["findings"])

    def test_symlink_roots_contexts_resources_and_projects_are_not_followed(self):
        self.context()
        self.org_config(stack_knowledge={"type": "local", "path": "knowledge"})
        outside = self.root / "outside"
        outside.mkdir()
        write(outside / "AGENTS.md", "## Secret Outside Heading")
        (self.org / "linked").symlink_to(outside, target_is_directory=True)
        (self.org / "knowledge").symlink_to(outside, target_is_directory=True)
        (self.project / "AGENTS.md").unlink()
        (self.project / "AGENTS.md").symlink_to(outside / "AGENTS.md")
        before = snapshot(self.root)
        report = self.run_audit("--org", self.org)
        self.assertEqual(snapshot(self.root), before)
        self.assertEqual(report["status"], "partial")
        self.assertIn("symlink-skipped", self.codes(report))
        self.assertNotIn("secret outside", json.dumps(report).lower())
        self.assertNotIn("linked", [p["label"] for p in report["projects"]])
        self.run_audit("--project", self.org / "linked", expected_code=2)
        self.assertEqual(snapshot(self.root), before)

    def test_malformed_marker_config_and_invalid_utf8_are_findings(self):
        self.context()
        write(self.org / ".claude/org.json", "{oops")
        write(self.org / "broken/.claude-workspace", "type: client\ntype: external\n")
        self.context(self.org / "broken/hidden-child")
        (self.project / "AGENTS.md").write_bytes(b"\xff\xfe")
        before = snapshot(self.root)
        report = self.run_audit("--org", self.org)
        self.assertEqual(snapshot(self.root), before)
        self.assertTrue({"malformed-marker", "malformed-org-config", "unreadable-file"}.issubset(self.codes(report)))
        self.assertEqual([p["label"] for p in report["projects"]], ["alpha"])
        for content in ("[]", '{"name":"a","name":"b"}', '{"value":NaN}'):
            write(self.org / ".claude/org.json", content)
            before = snapshot(self.root)
            self.assertIn("malformed-org-config", self.codes(self.run_audit("--org", self.org)))
            self.assertEqual(snapshot(self.root), before)

    def test_client_conflicts_and_nested_client_are_reported(self):
        self.context()
        client = self.org / "client"
        write(client / ".claude-workspace", "type: client\n")
        write(client / ".claude/org.json", "{}")
        write(client / ".git/config", "[core]\n bare=false\n")
        write(client / "inner/.claude-workspace", "type: client\n")
        self.context(client / "inner/deeper")
        report = self.run_audit("--org", self.org)
        self.assertTrue({"container-org-json", "container-is-repo", "nested-container"}.issubset(self.codes(report)))
        self.assertIn("client/inner", [p["label"] for p in report["projects"]])
        self.assertNotIn("client/inner/deeper", [p["label"] for p in report["projects"]])

    @unittest.skipUnless(shutil.which("git"), "Git is optional for the CLI; this test requires it")
    def test_identity_local_match_mismatch_and_shared_account_claims(self):
        self.context()
        self.org_config()
        self.git()
        self.org_config(self.workspace / "second", account="team")
        report = self.run_audit("--org", self.org, "--workspace", self.workspace)
        self.assertEqual(report["projects"][0]["identity"]["status"], "matches-local-config")
        self.git(email="wrong@example.invalid")
        report = self.run_audit("--org", self.org)
        self.assertEqual(report["projects"][0]["identity"]["status"], "mismatch")

    @unittest.skipUnless(shutil.which("git"), "Git is optional for the CLI; this test requires it")
    def test_remote_claims_are_cross_account_registry_not_allowlist(self):
        self.context()
        self.org_config()
        self.org_config(self.workspace / "second", account="other")
        self.git(remote="unclaimed")
        self.assertEqual(self.run_audit("--org", self.org, "--workspace", self.workspace)["projects"][0]["identity"]["status"], "matches-local-config")
        self.git(remote="other")
        self.assertEqual(self.run_audit("--org", self.org, "--workspace", self.workspace)["projects"][0]["identity"]["status"], "mismatch")
        self.assertEqual(self.run_audit("--org", self.org)["projects"][0]["identity"]["status"], "matches-local-config")

    @unittest.skipUnless(shutil.which("git"), "Git is optional for the CLI; this test requires it")
    def test_ambiguous_claims_are_advisory_without_changing_canonical_semantics(self):
        self.context()
        self.org_config()
        self.org_config(self.workspace / "second", identity={"github_account": "other", "owns_remotes": ["team"]})
        self.git()
        report = self.run_audit("--org", self.org, "--workspace", self.workspace)
        self.assertEqual(report["projects"][0]["identity"]["status"], "matches-local-config")
        self.assertIn("ambiguous-owner-claims", self.codes(report))

    @unittest.skipUnless(shutil.which("git"), "Git is optional for the CLI; this test requires it")
    def test_git_home_includes_and_environment_overrides_are_not_read(self):
        self.context()
        self.org_config()
        config = self.git(name=None, email=None)
        write(self.home / ".gitconfig", "[user]\n name=Example Author\n email=author@example.invalid\n")
        config.write_text(config.read_text() + f'[include]\n path={self.home}/.gitconfig\n')
        env = dict(self.env, GIT_CONFIG_COUNT="2", GIT_CONFIG_KEY_0="user.name", GIT_CONFIG_VALUE_0="Example Author",
                   GIT_CONFIG_KEY_1="user.email", GIT_CONFIG_VALUE_1="author@example.invalid",
                   GIT_TRACE=str(self.root / "must-not-write-trace"))
        identity = self.run_audit("--org", self.org, env=env)["projects"][0]["identity"]
        self.assertEqual(identity["status"], "unverified-inherited-identity")
        self.assertEqual(identity["unresolved_fields"], ["user.name", "user.email"])
        self.assertFalse((self.root / "must-not-write-trace").exists())

    def test_ungoverned_markers_and_identity_optout(self):
        self.context()
        self.org_config(identity={"enforcement": "off"})
        identity = self.run_audit("--org", self.org)["projects"][0]["identity"]
        self.assertEqual(identity["reason"], "enforcement-off")
        write(self.project / ".claude-workspace", "type: external\n")
        identity = self.run_audit("--org", self.org)["projects"][0]["identity"]
        self.assertEqual(identity["reason"], "external-or-scratch-marker")

    def test_no_mutation_including_home_cache_bytecode_and_git(self):
        self.context()
        self.org_config()
        self.git()
        write(self.project / ".claude/work/todos/example.md", "# Example\n- [ ] Task\n")
        before = snapshot(self.root)
        self.run_audit("--org", self.org, "--workspace", self.workspace)
        self.assertEqual(snapshot(self.root), before)
        self.assertFalse(list(self.root.rglob("__pycache__")))
        self.assertFalse(list(self.root.rglob(".identity-cache*")))

    def test_git_pointer_is_not_followed(self):
        self.context()
        self.org_config()
        write(self.project / ".git", "gitdir: ../../outside-git\n")
        report = self.run_audit("--org", self.org)
        self.assertEqual(report["projects"][0]["identity"]["status"], "unsupported-git-metadata")
        self.assertIn("git-metadata-skipped", self.codes(report))

    def test_fifo_and_oversized_context_do_not_hang(self):
        if hasattr(os, "mkfifo"):
            os.mkfifo(self.project / "AGENTS.md")
            self.assertIn("special-file-skipped", self.codes(self.run_audit()))
            (self.project / "AGENTS.md").unlink()
        write(self.project / "AGENTS.md", "x" * (2 * 1024 * 1024 + 1))
        self.assertIn("unreadable-file", self.codes(self.run_audit()))

    def test_inaccessible_read_is_reported_without_mutation(self):
        spec = importlib.util.spec_from_file_location("codex_audit_test", self.script)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        audit = module.Audit(argparse.Namespace(context_name="AGENTS.md"), *([None] * 7))
        self.context()
        with patch.object(module.os, "open", side_effect=PermissionError("Access denied")):
            content, state = audit.read(self.project / "AGENTS.md", self.project)
        self.assertIsNone(content)
        self.assertEqual(state, "unreadable")
        self.assertEqual(audit.findings[0]["code"], "unreadable-file")

    def test_todo_unicode_separator_matches_original_pilot(self):
        self.context()
        write(self.project / ".claude/work/todos/task.md", "---\nstatus: done\u2028priority: high\n---\n# Task")
        todo = self.run_audit()["projects"][0]["todos"]["files"][0]
        self.assertEqual((todo["status"], todo["priority"]), ("done", "high"))


if __name__ == "__main__":
    unittest.main()
