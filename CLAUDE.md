# Gruntwork LastMileFirst

Purpose-driven Claude Code marketplace for the `lastmilefirst` plugin (PARC workflow, AI expert agents, workspace organization, Claude configuration management).


## Archetype: Usable

## CRITICAL: Version Bumping

**When bumping a plugin version, you MUST update ALL of these files:**

1. `plugins/<plugin-name>/.claude-plugin/plugin.json` - The plugin's own version
2. `.claude-plugin/marketplace.json` - BOTH `metadata.version` AND `plugins[].version` (what Claude Code reads!)
3. `README.md` - The version table

**Why this matters:** Claude Code reads the marketplace.json to determine available versions. If you only update plugin.json, users will see stale versions when running `/plugin update`. Keep all three marketplace `version` fields (metadata + every plugin entry) equal to the plugin version — a drifted `metadata.version` is a bug (was found at `1.0.0` while the plugin was `0.16.0`, 2026-07-14).

**CRITICAL: cut a GitHub release/tag for the CONSUMER surface (learned 2026-07-14).** Merging to `main` makes the new version available in **Claude Code** (it resolves the marketplace from the default branch). But the **claude.ai / Claude Desktop** consumer app resolves a plugin via its GitHub **release/tag**, NOT the default branch — with no release/tag, a Desktop install **404s / "release not found."** So the version bump is not fully released until you cut the tag. Do it every bump.

### Version Bump Checklist

```bash
# 0. Run the adapter checks (Testing, below). A canonical skill edit can break an adapter build.
# After updating plugin.json version to X.Y.Z:
# 1. Update marketplace.json (sets BOTH metadata.version and plugins[].version)
sed -i '' 's/"version": "[^"]*"/"version": "X.Y.Z"/' .claude-plugin/marketplace.json

# 2. Update README.md table
# Find the plugin row and update the version number

# 3. Commit all three files together, open a PR, merge to main
git add plugins/<name>/.claude-plugin/plugin.json .claude-plugin/marketplace.json README.md
git commit -m "chore(<plugin-name>): Bump version to X.Y.Z"

# 4. AFTER the merge to main: cut the GitHub release/tag (required for Desktop/consumer installs)
gh release create vX.Y.Z --target main --latest --title "vX.Y.Z" --notes "..."
```

## Repository Structure

```
gruntwork-lastmilefirst/
├── .claude-plugin/
│   └── marketplace.json    # INDEX FILE - lists all plugins with versions
├── plugins/
│   └── lastmilefirst/      # Plugin source
│       ├── .claude-plugin/
│       │   └── plugin.json # Plugin metadata & version
│       ├── commands/
│       ├── skills/
│       ├── agents/
│       └── ...
├── adapters/
│   ├── muse/               # Muse skill package built from the plugin (build.py + mapping.toml)
│   └── codex/              # Codex skills-only pilot, same pattern; dist/ is gitignored in both
└── README.md               # Also contains version table
```

The adapters are generated from the plugin, never hand-copied. Shared domain rules live in the
plugin's Python (`hooks/scripts/markdown_content.py`, `org_resources.py`, `project_layout.py`,
and helpers in `check_identity.py`, `workspace_types.py`, `aggregator.py`, `review_claude.py`);
an adapter opts into stricter policies by flag, and the canonical callers keep their defaults.

## Adding a New Plugin

1. Create directory under `plugins/<plugin-name>/`
2. Add `.claude-plugin/plugin.json` with name, version, description
3. Add entry to `.claude-plugin/marketplace.json` plugins array
4. Add row to README.md version table

## Public-Repo Content Rule

This repo is public. Nothing committed here names a client, an engagement, or a private person.
Skill text, example files, fixtures, tests, commit messages, PRs, and release notes reconstruct
their examples. Provenance is a date and a generic context ("a README review," "an engagement's
first round"), never a name or a quote. Our own project names are allowed where the reader needs
them and dropped where they do not. The same holds for security specifics: describe the class of
problem, not the incident.

## Development Environment

This repo ships Python scripts but has **no `pyproject.toml` and no Poetry env** — unlike griffith
and the other Python projects here. It uses a plain venv:

```bash
python3 -m venv .venv && .venv/bin/pip install pytest
```

`.venv/` is gitignored. There is no CI, so running the suites locally is the only check.

## Testing

Eight suites, each run on its own from `plugins/lastmilefirst/`:

```bash
../../.venv/bin/pytest -q hooks/tests/                   # Overwatch, session start, workspace layout loader
../../.venv/bin/pytest -q skills/organize-orgs/tests/    # identity contract hook and audit
../../.venv/bin/pytest -q skills/review-org/tests/       # project roll-up from Overwatch state
../../.venv/bin/pytest -q skills/review-claude/tests/    # section matching, tier detection, cross-tier
../../.venv/bin/pytest -q skills/scan-secrets/tests/     # scanner, formats, hook installer
../../.venv/bin/pytest -q skills/todos-summary/tests/    # todo aggregation
../../.venv/bin/pytest -q skills/organize-claude/tests/  # CLAUDE.md audit and scaffolding
../../.venv/bin/pytest -q skills/audit-plugin/tests/     # plugin analyzer
```

`skills/review-voice/tests/` holds hand-run test cases, not pytest.

The adapters have their own checks, run from the repository root. Run them on macOS, not only
in a Linux sandbox (see the gotchas table):

```bash
python3 -B adapters/codex/build.py --check && python3 -B adapters/codex/build.py --lint
python3 -B -m unittest discover -s adapters/codex/tests
python3 -B adapters/muse/build.py --check
```

Each suite carries its own `conftest.py` doing the `sys.path` inserts, because the skills ship as
loose scripts rather than packaged modules.

## Dev Gotchas

Traps for someone changing this repo. Lead with the symptom — it's what you'll be searching by when
you hit this again.

| Issue | Symptom | Cause / fix |
|-------|---------|-------------|
| **No repo-level venv exists by default** | `pytest` not found; you conclude the repo has no tests. It has over 700 across eight suites. | Every other Python project here has a `.venv` or Poetry env; this one has neither checked in. Create it per Development Environment above. Found 2026-07-30 while adding the first review-claude tests. |
| **The suites can't be run in one command** | `ImportPathMismatchError` / "Plugin already registered under a different name" when you point pytest at more than one suite. | All eight pytest `tests/` dirs carry an `__init__.py`, so each is a package literally named `tests` and they collide on import. Run them separately (see Testing above). Tracked as issue #12; `--import-mode=importlib` does not fix it. |
| **Editing the cache instead of source** | Changes vanish on the next `/plugin update`. | Source is `~/Code/gruntwork/gruntwork-lastmilefirst/plugins/lastmilefirst/`. `~/.claude/plugins/cache/…` is install output — correct to *run* from, never to edit. Always `git pull` before starting. |
| **Adding a persona requires four files, not one** | New expert works via one entry point, missing from another. | README, the `run-consult-expert` command, `skills/consult-expert/SKILL.md`, and the persona file must be touched **together**. Drift found 2026-05-21: SKILL.md was missing 6 Key Hires and pointed at the wrong persona path (fixed in `ca4ee22`). |

## Usage Gotchas

Traps for someone installing or invoking the plugin. The common shape: **the failure is silent — you
get a plausible-looking success, not an error.**

| Issue | Symptom | Cause / fix |
|-------|---------|-------------|
| **`claude plugin update` leaves the OLD version loaded** | Update reports success, then a skill behaves like the previous version. | The CLI prints "Restart to apply changes" — the running session keeps the old code. Run `/reload-plugins` (user-typed; Claude can't invoke it) before using the skill; it reloads in place and preserves session context, unlike a full restart. Learned 2026-07-28 updating 0.18.0 → 0.20.0: scanning before the reload would have run 0.18.0's pre-modernization `gitleaks detect` path and produced a wrong scan that still looked clean. |
| **scan-secrets reads INSTALLED formats, not the shipped copy** | Ship a rule fix, re-scan, see no change. | Scans load `~/.claude/lastmilefirst/secret-formats/common_secret_formats.toml`, not `plugins/lastmilefirst/skills/scan-secrets/data/`. After any rule change, run `/run-scan-secrets --update-formats`. This preserves org rules; it only refreshes the common tier. |
| **Version check passes while cached files are stale** | Reported version is current, behavior is not. | Verify the cached *file contents*, not just the version number. If they're stale: `claude plugin uninstall <plugin>@<marketplace> && claude plugin install <plugin>@<marketplace>`. |
| **scan-secrets pre-push hook needs a reinstall** | A `--no-verify` commit still reaches the remote unchecked after upgrading to 0.37.0. | Pre-push coverage shipped in 0.37.0, but only `--install-hooks` writes the new hook, so run it again after upgrading. The hook scans the commits being pushed; a ref's first push audits its whole history plus gitignore gaps, dangerous files, and the declared visibility against GitHub's. `git push --no-verify` skips it, and only GitHub's push protection cannot be skipped. |
| **Editing the cache instead of source** | Changes vanish on the next `/plugin update`. | Source is `~/Code/gruntwork/gruntwork-lastmilefirst/plugins/lastmilefirst/`. `~/.claude/plugins/cache/…` is install output — correct to *run* from, never to edit. Always `git pull` before starting. |
| **Editing a canonical skill can break an adapter build** | `adapters/codex/build.py --check` fails with `adaptation drift` or a missing heading after an edit to `review-voice`, `review-signal`, `consult-expert`, or `parc`. | The adapters extract canonical sections by heading and rewrite a few paragraphs by exact anchor with an occurrence count (`mapping.toml`). Both fail closed on purpose, and no canonical pytest suite runs the adapter build, so the break only shows when the adapter checks run. Run them after any canonical skill edit and before every release (step 0 of the version bump checklist). Update the anchor in `mapping.toml` rather than loosening the match. Added 2026-10-08 when the review skills landed in the Codex adapter. |
| **Adapter suites must pass on macOS, not just in a Linux sandbox** | `unittest` reports 20 failures here while a PR says 43 passed. | macOS keeps `/tmp` and `/var` behind symlinks, so any path policy that refuses symlinked *ancestors* fails every `tempfile`-based test and refuses real workspaces on linked volumes. Refuse the named directory being a link, resolve its ancestors once, and have tests `.resolve()` their temp dirs. Found 2026-10-08 reviewing the Codex adapter pilot; the self-reported pass came from a Linux sandbox. Run the adapter suite locally before trusting a count. |
| **Not every component runs on every surface** | A skill silently does nothing in Chat, or Overwatch alerts in a folder that is not a project. | Per the [platform matrix](https://claude.com/docs/plugins/platform-support): skills load everywhere; hooks and agents load in Claude Code and Cowork and are ignored in Chat. So Overwatch runs in Cowork too, not only in Claude Code. Its project checks (CLAUDE.md, archetype) are evaluated at the resolved project root and only inside a configured project; outside one they are silent (0.36.2). The filesystem skills need a filesystem. Whether Skills auto-trigger on Desktop Chat is still untested.
