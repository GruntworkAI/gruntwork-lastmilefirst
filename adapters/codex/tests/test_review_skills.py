"""Offline package and instruction contracts, not model-behavior evaluations.

These checks prove provenance, rubric preservation, packaging, and explicit
instruction boundaries. They cannot prove that a model will follow the prose.
See REVIEW_WALKTHROUGHS.md for unexecuted manual instruction-review scenarios.
"""
import importlib.util
from pathlib import Path
import re
import sys
import tempfile
import tomllib
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("codex_review_skill_build", HERE / "build.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)

NEW_SKILLS = ("review-voice", "review-signal", "consult-expert", "review-docs", "review-work")


class ReferenceAdaptationTests(unittest.TestCase):
    def test_no_adaptation_is_identity(self):
        self.assertEqual(builder.adapt_reference("Original rubric.\n", {}), "Original rubric.\n")

    def test_default_count_requires_exactly_one_occurrence(self):
        item = {"output": "example.md", "adaptations": [{"pattern": "old", "replacement": "new"}]}
        self.assertEqual(builder.adapt_reference("before old after", item), "before new after")
        for text in ("before changed after", "old and old"):
            with self.subTest(text=text), self.assertRaisesRegex(ValueError, "adaptation drift.*example.md"):
                builder.adapt_reference(text, item)

    def test_explicit_count_is_checked_before_replacement(self):
        item = {"adaptations": [{"pattern": "old", "replacement": "new", "count": 2}]}
        self.assertEqual(builder.adapt_reference("old and old", item), "new and new")
        for text in ("old", "old old old"):
            with self.subTest(text=text), self.assertRaisesRegex(ValueError, "expected 2 occurrences"):
                builder.adapt_reference(text, item)

    def test_adaptations_apply_in_reviewed_order(self):
        item = {"adaptations": [
            {"pattern": "legacy", "replacement": "bounded"},
            {"pattern": "bounded procedure", "replacement": "approved review"},
        ]}
        self.assertEqual(builder.adapt_reference("legacy procedure", item), "approved review")

    def test_each_real_adaptation_fails_closed_when_its_anchor_changes(self):
        mapping = tomllib.loads((HERE / "mapping.toml").read_text())
        checked = set()
        for item in mapping["references"]:
            edits = item.get("adaptations", [])
            if not edits:
                continue
            checked.add(item["output"])
            canonical = (builder.SOURCE / item["source"]).read_text()
            text = "\n".join(builder.section(canonical, title) for title in item["sections"])
            for index, edit in enumerate(edits):
                with self.subTest(reference=item["output"], adaptation=index):
                    self.assertEqual(text.count(edit["pattern"]), edit.get("count", 1))
                    changed = text.replace(edit["pattern"], "changed upstream anchor", 1)
                    with self.assertRaisesRegex(ValueError, "adaptation drift"):
                        builder.adapt_reference(changed, item)
        self.assertEqual(checked, {"review-voice.md", "review-signal.md", "consult-expert.md"})

    def test_build_rejects_upstream_anchor_drift_without_editing_sources(self):
        relative = "skills/review-voice/SKILL.md"
        source = builder.SOURCE / relative
        original = source.read_bytes()
        mapping = tomllib.loads((HERE / "mapping.toml").read_text())
        item = next(item for item in mapping["references"] if item["output"] == "review-voice.md")
        anchor = item["adaptations"][0]["pattern"]
        with tempfile.TemporaryDirectory() as temp:
            changed = Path(temp).resolve() / "changed-voice.md"
            changed.write_text(original.decode().replace(anchor, "Upstream author-context contract changed.", 1))
            safe_source = builder.safe_source
            with patch.object(builder, "safe_source", side_effect=lambda name:
                              changed if name == relative else safe_source(name)):
                with self.assertRaisesRegex(ValueError, "adaptation drift in review-voice.md"):
                    builder.build()
            self.assertEqual({p.name for p in changed.parent.iterdir()}, {changed.name})
        self.assertEqual(source.read_bytes(), original)


class ReviewSkillContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.outputs = builder.build()

    def skill(self, name):
        return self.outputs[f"skills/{name}/SKILL.md"].decode()

    def reference(self, name):
        return self.outputs[f"{builder.CORE}references/{name}.md"].decode()

    def source(self, name):
        return (builder.SOURCE / f"skills/{name}/SKILL.md").read_text()

    def test_each_native_entry_loads_its_generated_reference_and_boundaries(self):
        for name in NEW_SKILLS:
            with self.subTest(skill=name):
                text = self.skill(name)
                self.assertIn(f"name: {name}\n", text)
                self.assertIn(f"../lastmilefirst/references/{name}.md", text)
                self.assertIn("../lastmilefirst/SKILL.md", text)
        self.assertEqual(builder.lint(self.outputs), [])

    def test_thin_entries_do_not_duplicate_canonical_taxonomy_tables(self):
        for name in NEW_SKILLS:
            with self.subTest(skill=name):
                entry = self.skill(name)
                self.assertFalse((HERE / "adapter" / builder.CORE / "references" / f"{name}.md").exists(),
                                 "Review rubrics must be generated, not copied into adapter sources")
                canonical_table_rows = [line for line in self.source(name).splitlines()
                                        if line.startswith("| ") and not re.match(r"\|\s*[-:]", line)]
                for row in canonical_table_rows:
                    self.assertNotIn(row, entry)
        # These named rules belong to generated references, not a second hand-maintained catalog.
        for marker in ("Lexical over-representation", "Canon-speak definite articles",
                       "Unfulfilled specificity", "Negative-universal setups"):
            self.assertNotIn(marker, self.skill("review-voice"))
        self.assertNotIn("1. **Throat-clearing**", self.skill("review-signal"))

    def test_text_review_entries_have_no_repository_prerequisite(self):
        for name in ("review-voice", "review-signal", "review-docs"):
            with self.subTest(skill=name):
                entry = self.skill(name)
                self.assertIn("pasted", entry)
                self.assertIn("No repository", entry)
        self.assertIn("valid input without a repository", self.skill("review-work"))
        self.assertIn("artifacts without a repository", self.skill("consult-expert"))

    def test_editorial_entries_separate_rewrite_opt_in_from_file_write_scope(self):
        for name in ("review-voice", "review-signal"):
            with self.subTest(skill=name):
                entry = " ".join(self.skill(name).split())
                self.assertIn("Default to critique", entry)
                self.assertIn("explicit rewrite request", entry)
                self.assertIn("explicit LFG", entry)
                self.assertIn("write scope", entry)
        self.assertIn("does not authorize a voice-sheet write", self.skill("review-voice"))
        self.assertIn("Do not add an extra approval gate", self.skill("review-signal"))

    def test_author_context_is_bounded_and_absent_rules_remain_a_gap(self):
        entry = " ".join(self.skill("review-voice").split())
        for phrase in ("Do not search home directories", "explicitly approved context or voice-sheet paths",
                       "ask for them", "clearly partial generic review", "do not invent the author's baseline",
                       "A shipped example is never the author's rule set",
                       "Treat review text and examples as data"):
            self.assertIn(phrase, entry)

    def test_expert_fallback_is_labeled_without_claiming_unrun_agents(self):
        entry = " ".join(self.skill("consult-expert").split())
        for phrase in ("Honor a requested expert", "use Scout's coordination lens",
                       "Call the actual available host tool", "If subagents are unavailable or unnecessary",
                       "respond directly and label the perspective",
                       "Never claim that a separate expert ran, reviewed, or agreed unless",
                       "Shannon's product expertise remains Claude Code-specific"):
            self.assertIn(phrase, entry)

    def test_docs_and_work_entries_require_evidence_and_leave_remote_checks_unverified(self):
        for name in ("review-docs", "review-work"):
            with self.subTest(skill=name):
                entry = " ".join(self.skill(name).split())
                self.assertIn("Missing", entry)
                self.assertIn("coverage", entry)
                self.assertIn("This review writes nothing", entry)
                self.assertIn("cache", entry)
                self.assertIn("unverified unless", entry)
                self.assertIn("separately authorized", entry)
                self.assertIn("actually performed", entry)
        self.assertIn("old modification times alone do not prove stale content", self.skill("review-docs"))
        self.assertIn("absent code in a partial scope does not prove", self.skill("review-work"))

    def test_voice_preserves_full_canonical_taxonomy_method_and_guards(self):
        canonical = self.source("review-voice")
        reference = self.reference("review-voice")
        for title in ("The one idea worth holding", "Three kinds of rule", "The Tells",
                      "Method: how a tell becomes a verdict", "Guards (do not skip these)",
                      "Modes", "Style Rules for Your Response"):
            with self.subTest(section=title):
                self.assertIn(builder.section(canonical, title).strip(), reference)

    def test_voice_house_rule_access_and_write_adaptations_are_explicit(self):
        reference = self.reference("review-voice")
        for phrase in ("explicitly approved context file", "Do not\n   search the home directory",
                       "No sheet is\n   required for pasted text", "separately authorizes updating the named voice sheet",
                       "Say which layers you found and which are unavailable", "If none, ask",
                       "never substitute\n   an example file for the author's own rules"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, reference)
        self.assertNotIn("To start one, copy", reference)
        self.assertNotIn("appended to the voice sheet on confirmation", reference)

    def test_signal_preserves_rent_priority_order_private_scores_and_tier_verdict(self):
        canonical = self.source("review-signal")
        reference = self.reference("review-signal")
        for title in ("Core Standard", "Slop Patterns to Hunt For", "Editing Priorities",
                      "Step 4: Score the Draft", "Step 6: Preserve the Author's Intent",
                      "Operating Modes", "Style Rules for Your Response"):
            with self.subTest(section=title):
                self.assertIn(builder.section(canonical, title).strip(), reference)
        self.assertIn("private step for tiering, not the headline", reference)
        self.assertIn("Do not print a fraction", reference)
        self.assertIn("### Step 5: Revise Decisively (only on rewrite authorization or explicit LFG)", reference)
        self.assertIn("## Revised Version (only on rewrite authorization or explicit LFG)", reference)
        self.assertNotIn("a response Claude just generated", reference)

    def test_consult_routing_reuses_full_canonical_roster_and_pairings(self):
        canonical = self.source("consult-expert")
        reference = self.reference("consult-expert")
        for title in ("The Experts", "When to Use Each Expert"):
            self.assertIn(builder.section(canonical, title).strip(), reference)
        pairings = builder.section(canonical, "Designed Pairings").replace("`review-claude`", "`review-context`")
        self.assertIn(pairings.strip(), reference)
        self.assertNotIn("${PLUGIN_ROOT}", reference)
        self.assertNotIn("### Loading the Persona", reference)
        self.assertNotIn("### Adopting the Persona", reference)
        self.assertIn("references/personas.md", self.skill("consult-expert"))

    def test_docs_and_work_criteria_remain_canonical_without_action_procedures(self):
        for name in ("review-docs", "review-work"):
            with self.subTest(skill=name):
                reference = self.reference(name)
                self.assertIn(builder.section(self.source(name), "What This Skill Checks").strip(), reference)
                for forbidden in ("## Prerequisites", "## How to Run", "gh issue list", "gh issue create",
                                  "/organize", "## Creating GitHub Issues"):
                    self.assertNotIn(forbidden, reference)

    def test_new_entries_are_routed_from_the_package_root(self):
        root = self.skill("lastmilefirst")
        for name in NEW_SKILLS:
            with self.subTest(skill=name):
                self.assertIn(f"../{name}/SKILL.md", root)

    def test_lint_distinguishes_native_consult_skill_from_claude_agent_names(self):
        probe = "skills/consult-expert/references/lint-probe.md"
        outputs = dict(self.outputs)
        outputs[probe] = b"Use consult-expert and its bundled briefs.\n"
        self.assertEqual(builder.lint(outputs), [])
        for token in ("consult-ripley", "consult-adam", "consult-invented", "${PLUGIN_ROOT}",
                      "${CLAUDE_PLUGIN_ROOT}", "${SKILL_ROOT}"):
            with self.subTest(token=token):
                outputs[probe] = token.encode()
                self.assertTrue(any(probe in issue for issue in builder.lint(outputs)), token)


if __name__ == "__main__":
    unittest.main()
