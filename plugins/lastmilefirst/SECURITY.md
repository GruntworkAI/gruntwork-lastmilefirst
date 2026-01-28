# Security Policy

## Reporting Vulnerabilities

If you discover a security vulnerability in lastmilefirst, please report it by emailing the maintainers directly rather than opening a public issue.

## Security Advisories

### LMFA-2025-001: Path Traversal in Operative Loading

**Severity:** Medium
**Fixed in:** v0.7.1
**Published:** 2025-01-28

#### Summary

The `consult-operative` skill accepted user-provided operative names without validation, potentially allowing path traversal attacks to read arbitrary files.

#### Details

When invoking `/run-consult-operative <name>`, the operative name was used directly to construct file paths like `.claude/operatives/<name>.md`. A malicious name containing `../` sequences could escape the intended directory.

**Example attack vector:**
```
/run-consult-operative ../../../etc/passwd "read this"
```

#### Impact

Low-Medium. Requires user to attack themselves (Claude reads files the user already has access to). The file must also parse as valid markdown with frontmatter to function as an operative.

#### Mitigation

Added validation to reject:
- Names containing `..` (path traversal)
- Names starting with `/` or `~` (absolute paths)
- Names containing `\` (Windows path separator)

Subdirectories remain allowed (e.g., `security/razor`).

---

### LMFA-2025-002: Predictable Temp File Location

**Severity:** Low
**Fixed in:** v0.7.1
**Published:** 2025-01-28

#### Summary

Session tracking used `/tmp/claude-session-changes.log`, a world-readable location on shared systems.

#### Details

The plugin tracked file edits during a session by appending to `/tmp/claude-session-changes.log`. On multi-user systems, this file could be read by other users to observe Claude session activity, or pre-created as a symlink to redirect writes.

#### Impact

Low. Information disclosure on shared systems. Most Claude Code users run on single-user machines.

#### Mitigation

Changed to user-specific directory: `~/.claude/tmp/session-changes.log`

---

### LMFA-2025-003: State File Race Condition

**Severity:** Medium
**Fixed in:** v0.7.1
**Published:** 2025-01-28

#### Summary

Multiple concurrent Claude sessions could corrupt the overwatch state file due to unsynchronized read-modify-write operations.

#### Details

The state file (`~/.claude/lastmilefirst/overwatch-state.json`) was updated using a non-atomic pattern:

```bash
cat "$FILE" | sed "s/.../" > "$FILE.tmp"
mv "$FILE.tmp" "$FILE"
```

Two sessions reading simultaneously could overwrite each other's changes, resulting in corrupted JSON like `{"last_plugin_check":1769232869 0}`.

#### Impact

Medium. State corruption causes "JSON validation failed" errors in stop hooks. Requires multiple simultaneous Claude sessions.

#### Mitigation

Added `flock`-based file locking with graceful degradation for platforms where `flock` is unavailable (Windows/Git Bash).

---

## Security Best Practices for Plugin Authors

Based on this audit, we recommend:

1. **Validate user-provided paths** - reject `..`, absolute paths, and backslashes
2. **Use user-specific directories** - prefer `~/.claude/` over `/tmp/`
3. **Add file locking** for shared state accessed by multiple processes
4. **Test cross-platform** - check if Unix utilities exist before using them
5. **Run security audits** - use tools like `security-sentinel` before release

## References

- [OWASP Path Traversal](https://owasp.org/www-community/attacks/Path_Traversal)
- [Anthropic Claude Code Security](https://github.com/anthropics/claude-code/security)
