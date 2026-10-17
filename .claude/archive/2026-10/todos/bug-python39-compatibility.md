# Bug: organize-project script requires Python 3.10+

**Status:** complete
**Priority:** high
**Created:** 2026-01-29

## Summary

The `organize-project` skill's Python script fails on Python 3.9 due to use of modern type hint syntax.

## Error

```
File ".../organize-project/scripts/organize.py", line 171, in <module>
    def classify_file(filename: str) -> tuple[str, str] | None:
TypeError: unsupported operand type(s) for |: 'types.GenericAlias' and 'NoneType'
```

## Root Cause

The script uses `tuple[str, str] | None` union type syntax which requires Python 3.10+. System Python on macOS is 3.9.6.

## Fix Options

1. **Add future import** (recommended):
   ```python
   from __future__ import annotations
   ```
   Add at top of file - enables PEP 604 syntax on Python 3.7+

2. **Use Optional syntax**:
   ```python
   from typing import Optional, Tuple
   def classify_file(filename: str) -> Optional[Tuple[str, str]]:
   ```

## Files Affected

- `plugins/lastmilefirst/skills/organize-project/scripts/organize.py`

## Notes

Discovered during `/run-organize-project --dry-run` on gruntwork-marketplace project.
