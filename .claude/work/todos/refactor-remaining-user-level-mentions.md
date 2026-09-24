# Refactor: remaining "user-level" mentions that may mean the workspace tier

**Status:** OPEN
**Priority:** low
**Created:** 2026-09-24
**Source:** the 0.34.0 rename (plan 2026-09-21-001, U2), which changed only review-claude, organize-claude, and the user-facing lines that were unambiguous

## The problem

"User-level" now means two different things in the plugin. For the top CLAUDE.md tier the word is
"workspace" as of 0.34.0. For the `~/.claude/` directory (operatives, the personal CLAUDE.md that
Claude Code itself calls user-level) the word stays "user-level" and is right. These mentions were
left alone because they could mean either:

- `skills/overwatch/SKILL.md` lines 31, 157, 174, 193: "user CLAUDE.md"
- `skills/review-voice/SKILL.md` and `voice-sheet-example.md`: "user-level CLAUDE.md" as the home of house rules. For a plugin user this is probably `~/.claude/CLAUDE.md`, which is the right word; for the author it is the workspace file
- `agents/consult-ripley.md` line 61: same as review-voice
- `agents/consult-shannon.md` and `personas/shannon-claude-code-expert.md`: hierarchy talk in Claude Code's own vocabulary, where user-level is a real tier name

## Shape of a fix

Decide per file whether the sentence means the Claude Code tier (leave it) or the plugin's
workspace tier (rename). For review-voice, the honest answer is "wherever the author keeps
standing rules," which is what the skill's House Rules section already says; the phrase "user-level
CLAUDE.md" there could become "the author's own CLAUDE.md" and be right on every surface.
