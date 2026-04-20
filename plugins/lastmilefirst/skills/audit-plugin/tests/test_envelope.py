"""Tests for _envelope() — the single rendering-time defense for untrusted content.

The envelope wraps plugin-controlled strings in paired unicode brackets
(⟦…⟧) so Claude can recognize them as data, not instructions. This file
tests the wrapper's behavior on benign inputs and common edge cases.
Hostile-input scenarios live in test_adversarial.py.
"""

from __future__ import annotations

import audit_plugin


OPEN = "⟦"
CLOSE = "⟧"


class TestEnvelopeHappy:
    def test_plain_ascii(self):
        assert audit_plugin._envelope("hello") == f"{OPEN}hello{CLOSE}"

    def test_single_word_with_spaces(self):
        assert audit_plugin._envelope("hello world") == f"{OPEN}hello world{CLOSE}"

    def test_non_empty_string_is_always_wrapped(self):
        out = audit_plugin._envelope("x")
        assert out.startswith(OPEN)
        assert out.endswith(CLOSE)


class TestEnvelopeEmptyAndNone:
    def test_empty_string_marker(self):
        assert audit_plugin._envelope("") == f"{OPEN}(empty){CLOSE}"

    def test_none_marker(self):
        assert audit_plugin._envelope(None) == f"{OPEN}(empty){CLOSE}"

    def test_non_string_coerces(self):
        # Numbers, etc. should coerce to string before enveloping.
        assert audit_plugin._envelope(42) == f"{OPEN}42{CLOSE}"


class TestEnvelopeFlattensNewlines:
    def test_single_newline_becomes_space(self):
        assert audit_plugin._envelope("a\nb") == f"{OPEN}a b{CLOSE}"

    def test_crlf_flattened(self):
        out = audit_plugin._envelope("a\r\nb")
        assert "\n" not in out
        assert "\r" not in out

    def test_many_newlines_do_not_accumulate_blanks(self):
        out = audit_plugin._envelope("a\n\n\nb")
        # No newlines in output at all.
        assert "\n" not in out
        # Content preserved with whitespace collapsed.
        assert "a" in out and "b" in out


class TestEnvelopeLengthCap:
    def test_exactly_500_chars_untruncated(self):
        s = "x" * 500
        out = audit_plugin._envelope(s)
        # Content inside brackets is exactly 500 chars, no ellipsis.
        inner = out[len(OPEN) : -len(CLOSE)]
        assert len(inner) == 500
        assert "…" not in inner

    def test_over_500_chars_truncated_with_ellipsis(self):
        s = "x" * 600
        out = audit_plugin._envelope(s)
        inner = out[len(OPEN) : -len(CLOSE)]
        # Truncated content + "…" suffix; total inner is bounded.
        assert inner.endswith("…")
        assert len(inner) <= 501  # 500 chars + ellipsis

    def test_oversized_10mb_input_bounded(self):
        s = "x" * (10 * 1024 * 1024)
        out = audit_plugin._envelope(s)
        inner = out[len(OPEN) : -len(CLOSE)]
        assert len(inner) <= 501


class TestEnvelopeStripsControlChars:
    def test_c0_control_chars_stripped(self):
        # \x01 through \x08 are C0 controls; \x00 is NUL.
        out = audit_plugin._envelope("ab\x01cd\x07ef")
        assert "\x01" not in out
        assert "\x07" not in out
        # Content letters preserved.
        inner = out[len(OPEN) : -len(CLOSE)]
        assert "a" in inner and "b" in inner and "c" in inner

    def test_ansi_escape_stripped(self):
        out = audit_plugin._envelope("\x1b[31mred\x1b[0m")
        assert "\x1b" not in out
        # Content "red" preserved.
        inner = out[len(OPEN) : -len(CLOSE)]
        assert "red" in inner


class TestEnvelopeStripsUnicodeBidi:
    def test_rlo_bidi_override_stripped(self):
        # U+202E RIGHT-TO-LEFT OVERRIDE is a classic bidi attack char.
        out = audit_plugin._envelope("before\u202eafter")
        assert "\u202e" not in out

    def test_all_bidi_override_codepoints_stripped(self):
        bidi_chars = [
            "\u202a",  # LRE
            "\u202b",  # RLE
            "\u202c",  # PDF
            "\u202d",  # LRO
            "\u202e",  # RLO
            "\u2066",  # LRI
            "\u2067",  # RLI
            "\u2068",  # FSI
            "\u2069",  # PDI
        ]
        for ch in bidi_chars:
            out = audit_plugin._envelope(f"a{ch}b")
            assert ch not in out, f"{hex(ord(ch))} not stripped"

    def test_zero_width_chars_stripped(self):
        # U+200B zero-width space, U+200C ZWNJ, U+200D ZWJ, U+FEFF BOM
        for ch in ("\u200b", "\u200c", "\u200d", "\ufeff"):
            out = audit_plugin._envelope(f"a{ch}b")
            assert ch not in out, f"{hex(ord(ch))} not stripped"


class TestEnvelopeEscapesMarkerLiterals:
    def test_open_bracket_in_input_escaped(self):
        # Input contains the envelope's own opening bracket — must not be
        # allowed to break out.
        out = audit_plugin._envelope("foo⟦bar")
        # Output has exactly ONE opening marker (the outer envelope).
        assert out.count(OPEN) == 1
        # The input's ⟦ has been replaced with something non-bracket.
        assert "⟦bar" not in out[len(OPEN) :]

    def test_close_bracket_in_input_escaped(self):
        out = audit_plugin._envelope("foo⟧bar")
        # Output has exactly ONE closing marker (the outer envelope).
        assert out.count(CLOSE) == 1
        assert "foo⟧" not in out[: -len(CLOSE)]

    def test_both_markers_in_input_escaped(self):
        out = audit_plugin._envelope("⟦inner⟧")
        assert out.count(OPEN) == 1
        assert out.count(CLOSE) == 1


class TestEnvelopePipeEscape:
    def test_pipe_escaped_for_table_safety(self):
        # Pipes inside markdown table cells break the cell boundary.
        # Escape with backslash so the pipe renders as literal.
        out = audit_plugin._envelope("name | evil")
        inner = out[len(OPEN) : -len(CLOSE)]
        assert "\\|" in inner
        # Raw unescaped pipe must not appear in the inner content.
        assert " | " not in inner


class TestEnvelopeBackticksNotSpecial:
    def test_backticks_passed_through(self):
        # With the ⟦…⟧ marker choice we don't need to strip backticks.
        # They're just content.
        out = audit_plugin._envelope("he said `hi`")
        # Not asserting specific form; just that the envelope didn't
        # crash and content survives in some shape.
        assert "hi" in out

    def test_triple_backtick_does_not_break_envelope(self):
        out = audit_plugin._envelope("```injection```")
        # Still a single envelope with exactly one OPEN and one CLOSE.
        assert out.count(OPEN) == 1
        assert out.count(CLOSE) == 1
