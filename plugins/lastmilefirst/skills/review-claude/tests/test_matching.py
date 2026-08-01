"""
Heading-scoped section matching for review-claude.

The behaviour under test replaced a whole-file substring check
(`if section_header in content`) that counted prose, fenced code samples, and
scaffolded files' YAML frontmatter as real sections. The fix narrows the same
leniency to real ATX headings — so the false positives go away without breaking
any file that passed before.
"""

import pytest

from review_claude import extract_headings, match_section
from archetypes import ARCHETYPE_SECTIONS, SECTION_ALIASES


def state(section, content):
    return match_section(section, extract_headings(content))[0]


# --- false positives the old whole-file check accepted -----------------------

def test_fenced_code_block_is_not_a_section():
    content = "# Project\n\n```markdown\n## Testing\nrun pytest\n```\n"
    assert state("## Testing", content) == "missing"


def test_tilde_fenced_code_block_is_not_a_section():
    content = "# Project\n\n~~~\n## Testing\n~~~\n"
    assert state("## Testing", content) == "missing"


def test_frontmatter_required_sections_list_is_not_a_section():
    """The worst case: a scaffolded file listing every header in its frontmatter."""
    content = (
        "---\n"
        "required_sections:\n"
        '  - header: "## Testing"\n'
        '    description: "Test commands"\n'
        "---\n\n"
        "# Project\n"
    )
    assert state("## Testing", content) == "missing"


def test_prose_mention_is_not_a_section():
    content = "# Project\n\nWe should add a ## Installation section one day.\n"
    assert state("## Installation", content) == "missing"


# --- leniency that must be preserved (these all passed before) ---------------

@pytest.mark.parametrize(
    "heading,section",
    [
        ("### Deployment", "## Deployment"),                       # deeper level
        ("## Deployment Instructions", "## Deployment"),           # trailing words
        ("## Testing Strategy", "## Testing"),                     # trailing words
        ("## Core Philosophy: Compound Engineering", "## Core Philosophy"),  # colon suffix
        ("## Gotchas (Learned the Hard Way)", "## Gotchas"),       # parenthetical
        ("#### Testing", "## Testing"),                            # much deeper
    ],
)
def test_lenient_heading_forms_still_match(heading, section):
    assert state(section, f"# Project\n\n{heading}\n\nbody\n") == "present"


# --- aliases: genuine renames the canonical word cannot reach ----------------

def test_alias_resolves_a_renamed_section():
    content = "# Project\n\n## Common Pitfalls to Avoid\n\nbody\n"
    assert state("## Gotchas", content) == "present_via_alias"


def test_alias_reports_the_matched_heading():
    headings = extract_headings("# P\n\n## Common Commands\n")
    result, matched = match_section("## Quick Commands", headings)
    assert result == "present_via_alias"
    assert matched == "common commands"


@pytest.mark.parametrize(
    "heading",
    ["## CRITICAL: Version Bumping", "## Releases & packaging", "### Cutting a release"],
)
def test_publishing_resolves_through_release_vocabulary(heading):
    """Real headings in this repo and travel-skills; both document how to release."""
    content = f"# Project\n\n{heading}\n\nbody\n"
    assert state("## Publishing", content) == "present_via_alias"


def test_direct_match_wins_over_alias():
    content = "# Project\n\n## Gotchas\n\n## Troubleshooting\n"
    assert state("## Gotchas", content) == "present"


# --- the Gotchas split -------------------------------------------------------

def test_undivided_gotchas_satisfies_both_split_sections():
    """Migration guarantee: projects predating the split are not newly flagged."""
    content = "# Project\n\n## Gotchas\n\n| Issue | Symptom | Cause / fix |\n"
    assert state("## Dev Gotchas", content) == "present_via_alias"
    assert state("## Deployment Gotchas", content) == "present_via_alias"
    assert state("## Usage Gotchas", content) == "present_via_alias"


def test_divided_gotchas_match_directly_not_via_alias():
    content = "# Project\n\n## Dev Gotchas\n\nbody\n\n## Deployment Gotchas\n\nbody\n"
    assert state("## Dev Gotchas", content) == "present"
    assert state("## Deployment Gotchas", content) == "present"


def test_split_sections_are_required_by_the_right_archetypes():
    deployable = [h for h, _ in ARCHETYPE_SECTIONS["deployable"]]
    usable = [h for h, _ in ARCHETYPE_SECTIONS["usable"]]
    referenceable = [h for h, _ in ARCHETYPE_SECTIONS["referenceable"]]

    assert "## Dev Gotchas" in deployable and "## Deployment Gotchas" in deployable
    assert "## Dev Gotchas" in usable and "## Usage Gotchas" in usable
    # A knowledge archive is neither deployed nor invoked — it keeps one section.
    assert referenceable.count("## Gotchas") == 1
    assert "## Dev Gotchas" not in referenceable


# --- guards ------------------------------------------------------------------

def test_architecture_is_not_an_infrastructure_alias():
    """
    Rejected during review: Infrastructure means cloud provider/region/account,
    not code structure. Keeping it would have marked a genuine gap documented.
    """
    assert "Architecture" not in SECTION_ALIASES.get("## Infrastructure", [])
    content = "# Project\n\n## Architecture\n\nbody\n"
    assert state("## Infrastructure", content) == "missing"


def test_archetype_marker_collides_with_no_required_section():
    """`## Archetype: <X>` is in every project file; it must match nothing."""
    required = {h.lstrip("#").strip().casefold()
                for sections in ARCHETYPE_SECTIONS.values() for h, _ in sections}
    aliases = {a.casefold() for values in SECTION_ALIASES.values() for a in values}
    for value in ("Deployable", "Usable", "Referenceable", "Experimental"):
        heading = f"archetype: {value}".casefold()
        assert not any(name in heading for name in required | aliases)


def test_headings_are_extracted_in_document_order():
    content = "# Title\n\n## First\n\n### Second\n\n## Third\n"
    assert extract_headings(content) == ["title", "first", "second", "third"]


def test_no_headings_means_everything_missing():
    assert state("## Testing", "just prose, no headings at all\n") == "missing"
