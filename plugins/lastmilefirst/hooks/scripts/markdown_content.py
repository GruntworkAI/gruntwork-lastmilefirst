"""Pure Markdown content helpers shared by canonical tools and adapters."""

import re

_FENCE = re.compile(r"^\s*(`{3,}|~{3,})(.*)$")
_LEGACY_FENCE = re.compile(r"^\s*(```|~~~)")


def without_fenced_blocks(content: str, *, strict: bool = True) -> str:
    """Blank fenced examples while retaining original line positions.

    Strict fences close only with the opening character, at least the opening
    length, and no trailing non-whitespace text. Backtick info strings cannot
    contain backticks. ``strict=False`` retains review-claude's historical
    behavior: every line beginning with three backticks or tildes toggles the
    fence, regardless of its opening character or length.

    This helper only processes the supplied string; it performs no I/O.
    """
    result = []
    fence_char, fence_length = None, 0
    for line in content.splitlines():
        if not strict:
            if _LEGACY_FENCE.match(line):
                fence_char = None if fence_char else "legacy"
                result.append("")
            else:
                result.append("" if fence_char else line)
            continue

        match = _FENCE.match(line)
        if fence_char:
            if (match and match.group(1)[0] == fence_char
                    and len(match.group(1)) >= fence_length
                    and not match.group(2).strip()):
                fence_char, fence_length = None, 0
            result.append("")
        elif match and not (match.group(1)[0] == "`" and "`" in match.group(2)):
            fence_char, fence_length = match.group(1)[0], len(match.group(1))
            result.append("")
        else:
            result.append(line)
    return "\n".join(result)
