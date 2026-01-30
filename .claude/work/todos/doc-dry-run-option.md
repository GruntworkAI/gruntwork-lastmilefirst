# Todo: Document --dry-run option in organize-project SKILL.md

**Status:** complete
**Priority:** medium
**Created:** 2026-01-29

## Summary

The `organize-project` script has an undocumented `--dry-run` option that should be added to the SKILL.md documentation.

## Current State

The script accepts `--dry-run`:
```python
parser.add_argument("--dry-run", action="store_true", help="Show what would happen without making changes")
```

But the SKILL.md doesn't mention it.

## Requested Change

Add to SKILL.md under "How to Run" section:

```markdown
## How to Run

```bash
python ${SKILL_ROOT}/scripts/organize.py
```

Preview changes without making them:

```bash
python ${SKILL_ROOT}/scripts/organize.py --dry-run
```

Or for a specific project:

```bash
python ${SKILL_ROOT}/scripts/organize.py /path/to/project
python ${SKILL_ROOT}/scripts/organize.py /path/to/project --dry-run
```
```

## Files Affected

- `plugins/lastmilefirst/skills/organize-project/SKILL.md`

## Notes

User asked about dry-run option during project review. The feature exists but wasn't discoverable.
