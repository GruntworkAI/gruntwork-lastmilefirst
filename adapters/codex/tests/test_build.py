"""Offline packaging and relocation checks; no plugin installation or agent calls."""
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("codex_adapter_build", HERE / "build.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class PackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.outputs = builder.build()

    def test_render_is_deterministic_and_clean(self):
        self.assertEqual(self.outputs, builder.build())
        self.assertEqual(builder.lint(self.outputs), [])

    def test_manifest_and_entry_points(self):
        manifest = json.loads(self.outputs["plugin.json"])
        self.assertEqual(manifest["$schema"], "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json")
        self.assertEqual(manifest["name"], "lastmilefirst-codex")
        self.assertNotIn("extensions", manifest)
        self.assertNotIn("hooks", manifest)
        actual = {Path(k).parts[1] for k in self.outputs if k.endswith("SKILL.md")}
        self.assertEqual(actual, {"lastmilefirst", "parc", "review-project", "review-org", "review-context"})
        self.assertFalse(any(k.startswith(("hooks/", ".mcp", "mcp.json", ".app")) for k in self.outputs))

    def test_canonical_dependency_bytes_and_hashes(self):
        hashes = json.loads(self.outputs["SOURCE_MANIFEST.json"])["sources_sha256"]
        for relative, digest in hashes.items():
            canonical = builder.SOURCE / relative
            self.assertEqual(hashlib.sha256(canonical.read_bytes()).hexdigest(), digest)
        for relative, data in self.outputs.items():
            prefix = builder.CORE + "vendor/plugins/lastmilefirst/"
            if relative.startswith(prefix):
                self.assertEqual(data, (builder.SOURCE / relative[len(prefix):]).read_bytes())
                if relative.endswith(".py"):
                    ast.parse(data)

    def test_all_persona_briefs_are_bundled(self):
        expected = {p.name for p in (builder.SOURCE / "personas").glob("*.md")}
        actual = {Path(k).name for k in self.outputs if "/references/personas/" in k}
        self.assertEqual(actual, expected)
        for name in expected:
            data = self.outputs[builder.CORE + "references/personas/" + name].decode()
            self.assertIn("## Expertise lenses", data)
            self.assertNotIn("plugins/lastmilefirst/personas", data)

    def test_missing_heading_fails_closed_and_fenced_heading_ignored(self):
        with self.assertRaisesRegex(ValueError, "exactly one"):
            builder.section("# Example\n```\n## Requested\n```\n", "Requested")
        with self.assertRaisesRegex(ValueError, "exactly one"):
            builder.section("## Duplicate\n## Duplicate\n", "Duplicate")
        self.assertEqual(builder.section("## Keep\nyes\n## Exclude\nno\n", "Keep"), "## Keep\nyes\n")

    def test_build_uses_strict_shared_fence_rules(self):
        content = "````markdown\n```\n## Example\n````\n## Keep\nyes\n"
        self.assertEqual(builder.headings(content), [(4, 2, "Keep")])
        content = "~~~\n```\n## Example\n~~~\n## Keep\n"
        self.assertEqual(builder.headings(content), [(4, 2, "Keep")])

    def test_every_shared_dependency_is_required_in_standalone_package(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            for name, data in self.outputs.items():
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
            for relative in builder.VENDOR_FILES:
                if not relative.endswith(".py"):
                    continue
                with self.subTest(dependency=relative):
                    dependency = root / builder.CORE / "vendor/plugins/lastmilefirst" / relative
                    data = dependency.read_bytes()
                    dependency.unlink()
                    try:
                        result = subprocess.run([sys.executable, str(root / builder.CORE / "scripts/audit.py"),
                                                 "--project", str(root)], capture_output=True, text=True)
                        self.assertEqual(result.returncode, 2, result.stderr)
                        self.assertEqual(json.loads(result.stdout)["findings"][0]["code"], "audit-unavailable")
                    finally:
                        dependency.write_bytes(data)

    def test_selected_review_judgments_exclude_mutating_procedures(self):
        docs = self.outputs[builder.CORE + "references/review-docs.md"].decode()
        project = self.outputs[builder.CORE + "references/review-project.md"].decode()
        self.assertNotIn("organize/SKILL.md", docs)
        self.assertNotIn("gh issue create", docs)
        self.assertNotIn("X/100", project)
        for name, data in self.outputs.items():
            if name.endswith(".md") and "/vendor/" not in name:
                self.assertNotIn("update_state.py", data.decode())

    def test_standalone_relocation_and_no_pycache(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            package = root / "relocated-package"
            project = root / "project"
            project.mkdir()
            (project / "AGENTS.md").write_text("## Archetype: Experimental\n## Quick Commands\nUse tests.\n")
            for name, data in self.outputs.items():
                target = package / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
            before = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}
            result = subprocess.run([sys.executable, str(package / builder.CORE / "scripts/audit.py"),
                                     "--project", str(project)], cwd=root, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report["mode"], "read-only")
            self.assertEqual(report["status"], "partial")
            self.assertEqual(report["projects"][0]["context"]["archetype"], "experimental")
            after = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}
            self.assertEqual(before, after)
            self.assertFalse(list(root.rglob("__pycache__")))

    def test_missing_dependency_returns_structured_error(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            script = root / "audit.py"
            script.write_bytes(self.outputs[builder.CORE + "scripts/audit.py"])
            result = subprocess.run([sys.executable, str(script), "--project", str(root)],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(json.loads(result.stdout)["status"], "error")

    def test_output_symlink_and_unexpected_files_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            target = root / "target"
            target.mkdir()
            link = root / "link"
            link.symlink_to(target, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "symlink"):
                builder.check_destination(link, self.outputs)
            (target / "unowned").write_text("preserve me")
            with self.assertRaisesRegex(ValueError, "unexpected"):
                builder.check_destination(target, self.outputs)
            self.assertEqual((target / "unowned").read_text(), "preserve me")

    def test_output_cannot_overwrite_repository_sources_or_unowned_manifest(self):
        for root in (builder.SOURCE, builder.SOURCE / ".claude-plugin", builder.HERE / "adapter",
                     builder.REPO / "adapters/muse", builder.REPO, builder.REPO.parent):
            with self.assertRaisesRegex(ValueError, "overlap repository inputs"):
                builder.check_destination(root, self.outputs)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            original = b'{"name": "unrelated-plugin"}'
            (root / "plugin.json").write_bytes(original)
            with self.assertRaisesRegex(ValueError, "not a managed"):
                builder.check_destination(root, self.outputs)
            self.assertEqual((root / "plugin.json").read_bytes(), original)

    def test_output_hardlinks_cannot_overwrite_other_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            source = root / "canonical.json"
            source.write_text('{"name": "canonical"}')
            package = root / "package"
            package.mkdir()
            (package / "plugin.json").hardlink_to(source)
            with self.assertRaisesRegex(ValueError, "hardlinked output"):
                builder.check_destination(package, self.outputs)
            self.assertEqual(source.read_text(), '{"name": "canonical"}')

    def test_check_detects_stale_and_unexpected_outputs(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve() / "package"
            build = [sys.executable, str(HERE / "build.py"), "--output", str(root)]
            self.assertEqual(subprocess.run(build, capture_output=True, text=True).returncode, 0)
            result = subprocess.run([*build, "--check"], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            vendored = root / builder.CORE / "vendor/plugins/lastmilefirst/hooks/scripts/markdown_content.py"
            original = vendored.read_bytes()
            vendored.write_bytes(original + b"\n")
            result = subprocess.run([*build, "--check"], capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertIn("stale or missing outputs", result.stderr)
            self.assertEqual(vendored.read_bytes(), original + b"\n", "check must not repair")
            vendored.write_bytes(original)
            (root / "skills/extra.md").write_text("planted\n")
            result = subprocess.run([*build, "--check"], capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertIn("unexpected output file", result.stderr)

    def test_output_under_a_symlinked_ancestor_is_accepted(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            target = root / "target"
            target.mkdir()
            link = root / "link"
            link.symlink_to(target, target_is_directory=True)
            builder.check_destination(link / "package", self.outputs)  # must not raise
            self.assertFalse((target / "package").exists())

    def test_check_and_lint_do_not_write(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve() / "never-written"
            result = subprocess.run([sys.executable, str(HERE / "build.py"), "--lint", "--output", str(root)],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(root.exists())
            result = subprocess.run([sys.executable, str(HERE / "build.py"), "--check", "--output", str(root)],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertFalse(root.exists())


if __name__ == "__main__":
    unittest.main()
