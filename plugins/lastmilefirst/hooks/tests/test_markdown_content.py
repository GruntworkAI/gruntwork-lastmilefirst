"""Characterize legacy fences and stricter, shared bounded-audit fences."""

import pytest

from markdown_content import without_fenced_blocks


@pytest.mark.parametrize("fence", ["```", "~~~"])
def test_regular_fences_are_blank_in_both_modes(fence):
    content = f"# Before\n{fence}md\n# Example\n{fence}\n# After"
    expected = "# Before\n\n\n\n# After"
    assert without_fenced_blocks(content, strict=True) == expected
    assert without_fenced_blocks(content, strict=False) == expected


def test_strict_fences_require_same_character_and_sufficient_length():
    content = "````md\n# Hidden\n```\n# Hidden too\n~~~\n# Hidden still\n````\n# Visible"
    assert without_fenced_blocks(content, strict=True).splitlines() == [""] * 7 + ["# Visible"]
    # Canonical callers retain their original toggle-on-any-fence semantics.
    assert without_fenced_blocks(content, strict=False).splitlines() == [
        "", "", "", "# Hidden too", "", "", "", "# Visible"]


def test_strict_fence_closer_cannot_have_info_string():
    content = "```md\n```md\n# Hidden\n```\n# Visible"
    assert without_fenced_blocks(content, strict=True) == "\n\n\n\n# Visible"


def test_strict_backtick_info_string_cannot_contain_backticks():
    content = "```bad`info\n# Visible"
    assert without_fenced_blocks(content, strict=True) == content
    assert without_fenced_blocks(content, strict=False) == "\n"


def test_unclosed_fence_hides_remainder():
    assert without_fenced_blocks("# Visible\n~~~\n# Hidden", strict=True) == "# Visible\n\n"
