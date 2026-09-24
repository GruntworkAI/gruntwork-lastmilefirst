# Bug: archetype detection misses the `**Archetype:** X` form

**Status:** OPEN
**Priority:** low
**Created:** 2026-09-24
**Found by:** the first live run of `review_org.py` against an org

## The problem

`detect_archetype()` in review-claude matches only a `## Archetype: X` heading. A project CLAUDE.md
that declares its archetype as a bold label (`**Archetype:** Deployable`) is reported as having
none, by both the review-org roll-up and the Overwatch session-start alert, which share the
detector.

## Shape of a fix

Either accept both forms in the detector, or have `organize-project` normalize to the heading
form. Decide which is canonical first; accepting both without saying so creates a second source of
truth for the same declaration.
