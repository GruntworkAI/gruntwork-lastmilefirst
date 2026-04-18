# Follow-up: LMF hook subprocess hardening — minor improvements

**Surfaced during Griffith Unit 4 scan of lastmilefirst 0.14.0 (2026-04-17).**

Griffith's scanner flagged 8 `subprocess-in-hooks` findings on LMF. On
investigation, all 8 are legitimate and well-implemented — list args, timeouts,
specific exception handlers, no `shell=True`. This followup captures the two
small improvements worth making anyway.

## Context

LMF's hooks shell out for:
- Git status checks (`git rev-parse`, `git status`, `git remote get-url`)
- GitHub visibility check (`gh repo view --json`)
- Python script launching from `run.py`
- Python interpreter probing from `find_python()`

All are idiomatic Python and already follow best practices. The scanner is
correctly identifying "this plugin uses subprocess in hooks" as a capability
fact, not a defect.

## Improvement 1: Drop dead Python-probing branch in `run.py`

Current `find_python()` has two branches:

```python
def find_python() -> str:
    # Branch A (happy path): return sys.executable if already Python 3
    if sys.version_info[0] >= 3:
        return sys.executable

    # Branch B (never reached in practice): probe python3 / python / py -3
    candidates = ["python3", "python", "py -3"]
    for cmd in candidates:
        try:
            result = subprocess.run(
                cmd.split() + ["--version"],
                capture_output=True, text=True, timeout=5,
            )
            ...
```

Branch B is only reachable if LMF's hook is invoked from Python 2. That's
extinct. The `hooks/hooks.json` already invokes scripts via `python` / `python3`
with a `||` fallback, so the launcher will always run under Python 3.

**Proposed:** delete Branch B. `find_python()` becomes `return sys.executable`.
Removes 1 subprocess call site (the version probe) and the code it depends on.

**Impact:** zero behavior change on current systems. Eliminates an entire
subprocess-finding category in Griffith scans.

## Improvement 2: Document subprocess best practices in CLAUDE.md

LMF's CLAUDE.md doesn't explicitly state the subprocess rules the current code
follows. Writing them down protects against regression as new hooks get added.

**Proposed additions to `hooks/README.md` or `CLAUDE.md` hook section:**

```markdown
## Subprocess rules for hook scripts

All subprocess calls MUST:
- Use list arguments (never `shell=True`)
- Set `timeout=` (typically 5-30s depending on expected duration)
- Capture output with `capture_output=True` when output is parsed
- Handle `subprocess.TimeoutExpired`, `FileNotFoundError`, and `OSError`
  explicitly — never a bare `except`
- Take inputs only from constants or already-validated paths

Run `python -c "import ast; ..."` audits (or griffith analyze) before merging
new hook code that shells out.
```

## What NOT to do

- **Don't use full binary paths** (`/usr/bin/git` instead of `git`) — resists
  PATH hijacking but that's a broader system-compromise threat; adding full
  paths breaks on systems where git lives elsewhere (homebrew, nix, etc.).
  Not worth the portability cost.
- **Don't replace git subprocess with GitPython** — big dep; 4 calls doesn't
  justify it.
- **Don't replace gh with raw REST API** — requires managing auth tokens in
  the plugin, strictly worse from a security perspective.

## Priority

Low. LMF's hook code is already correct; these are polish items.

## Testing

After Improvement 1, re-scan LMF with Griffith:
```
griffith analyze ~/.claude/plugins/cache/gruntwork-marketplace/lastmilefirst/<version>/
```
Expected: subprocess-in-hooks count drops from 8 to 7 (one removed call site).
