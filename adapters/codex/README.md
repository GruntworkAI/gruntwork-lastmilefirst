# LastMileFirst Codex adapter pilot

A local, **skills-only** package for PARC and organization-first project/context reviews.
Canonical LastMileFirst sources remain in `plugins/lastmilefirst`. The shared-rule refactor
updates their Python callers to use the same pure helpers as this adapter; existing Claude
behavior is regression-tested and Muse-generated outputs remain byte-identical. Marketplace
release metadata is unchanged. This is a bounded pilot, not a full port.

## Build and verify

Python 3.11+ and Git are the only runtime tools. No third-party Python modules are required.

```sh
python3 adapters/codex/build.py
python3 adapters/codex/build.py --check
python3 adapters/codex/build.py --lint
python3 -B -m unittest discover -s adapters/codex/tests -v
```

The installable package is `adapters/codex/dist/` (gitignored). Build does **not** install,
activate, register, publish, or alter user configuration. Copying or installing it is a separate
authorized action. `--output PATH` builds into a new package directory; a destination that is itself a
symlink, hardlinked output files, or unexpected files are refused rather than followed/deleted
(symlinks in the destination's ancestors, such as macOS's `/tmp`, are resolved). Inside this repository only the
default dist/ is an allowed destination; elsewhere a nonempty destination must already carry
this adapter's manifest and source-provenance marker. Canonical/Muse/source directories cannot
be build destinations. `--check` checks exact contents
and `--lint` renders and validates without writing; it refuses Claude command paths and Claude
subagent names in generated prose. Do not hand-edit generated files.

```text
adapters/codex/
  build.py                    deterministic stdlib generator
  mapping.toml                selected canonical sections and mechanism adaptations
  adapter/skills/             native Codex operating instructions and audit wrapper
  tests/                      offline package and audit tests
  dist/                       generated portable plugin root
    plugin.json
    SOURCE_MANIFEST.json      SHA-256 provenance, no installed-checkout dependency
    skills/
      lastmilefirst/          shared boundaries, references, persona briefs, audit helper
        vendor/plugins/lastmilefirst/  exact canonical dependency copies
      parc/
      review-project/
      review-org/
      review-context/
```

## What is shared, what is adapted

- PARC entry points, discovery, five-element briefs, YAGNI/YAGWYDI, and review/Compound judgment
  are extracted from the canonical skill. The native entry point scales ceremony and preserves
  the quick-question/no-PARC escape hatch. Compound writes remain separate from read-only review
- Project/docs/work review criteria are extracted without stale organization commands,
  executable issue-creation procedures, or the undefined project health score
- Context, marker, hierarchy, identity, todo, overlap, resource-default, and layout rules are
  imported from bundled byte-identical canonical Python dependencies and templates. Both the
  original callers and the adapter use those shared implementations. The adapter supplies
  bounded inputs and never invokes canonical auto-discovery, suggestion, organization,
  aggregation/cache, or update-state command-line interfaces
- All 16 persona briefs are generated from canonical expertise headings. They are compact
  lenses, not copies of Claude tool assumptions or evidence that named agents are installed
- The source manifest records canonical and adapter hashes. Missing/renamed excerpt headings
  fail the build; canonical changes require regeneration and review of affected behavior

### Shared rules and explicit adapter policy

| Canonical helper | Original caller | Adapter policy |
| --- | --- | --- |
| `check_identity.py`: marker parsing, contract inspection, claim registry, field/remote comparisons, supplied-tier selection | Identity hook and its filesystem wrappers | Strict marker/config validation; explicit approved tiers; stop at malformed nearer config; repository-local Git evidence only |
| `workspace_types.py`: project classification and container issue decisions | Workspace walkers and layout diagnostics | Bounded safe enumeration; one client tier; evidence filter and excluded-directory reporting |
| `aggregator.py`: content-only todo metadata/title parsing | `TodoAggregator.parse_todo_file` | Strict frontmatter/headings; fenced examples excluded; no discovery, timestamps, caches, or aggregation writes |
| `review_claude.py`: heading/section matching, inventory, topic carriers | Existing context review | Explicit context filename/tier; topic overlap is not a contradiction claim |
| `markdown_content.py`: fence handling | Context review and todo content parsing | Strict matching character/length rules; legacy canonical defaults remain explicit |
| `org_resources.py`: defaults, opt-outs, local/external backend selection | Session-start infrastructure check | Strict config shapes; adapter separately validates and safely reads relative paths |
| `project_layout.py`: storage paths | Project organizer | Read-only layout presence, never scaffolding |

The adapter still owns approval-root validation, safe file/Git reads, discovery evidence,
report wording, and partial-coverage status. Those are platform/scope adaptations, not a
second implementation of the shared domain rules. Generated vendored copies are packaging
output, not hand-maintained forks. This refactor intentionally adds canonical helper APIs;
copying only `adapters/codex/` into an older checkout is insufficient to rebuild it.

`CLAUDE.md` remains valid legacy context when selected explicitly. The review defaults to
`AGENTS.md`; `.claude/org.json`, `.claude-workspace`, `.claude/work`, `.claude/debt`, and
`.claude/archive` remain shared storage. No global search-and-replace or filesystem migration
is performed. The context-name parameter is independent of storage paths.

## Bounded audit examples

```sh
CORE=adapters/codex/dist/skills/lastmilefirst
python3 -B "$CORE/scripts/audit.py" --project /approved/project
python3 -B "$CORE/scripts/audit.py" --project /approved/org --org /approved/org
python3 -B "$CORE/scripts/audit.py" --project /approved/org/client/project \
  --org /approved/org --workspace /approved
python3 -B "$CORE/scripts/audit.py" --project /approved/project --context-name CLAUDE.md
```

Paths are examples, not authorization. Use only approved readable roots. Default project is
cwd. Project-only mode never searches parents and explicitly reports partial org coverage.
Org mode inspects direct projects and one `.claude-workspace` client tier. Optional workspace
scope adds its context and direct-org ownership claims, not all-workspace project discovery.
Context above a nested Git root is **not automatically inherited by Codex**. Identify manually
loaded sources and effective `AGENTS.override.md`/fallback behavior separately. Never copy
private org/client material into a public repository.

The CLI returns JSON. Exit 0 means a report was produced, not that every check passed; 2 is an
invalid scope or dependency error. Report status and coverage alongside findings. Review mode
has no repair/record switch: writes are a separate task with specific authorization.

## Known pilot limits

- Offline, read-only structural evidence; no network/account liveness, GitHub issue sync,
  secret scanning, remote protections, automatic Overwatch hooks, or review-state freshness
- Local Git config evidence only; inherited/global/system/include/environment identity is
  unverified. Support-repo cleanliness and synchronization are also unverified. The pilot is
  not pre-commit identity enforcement
- Symlinks and linked-worktree/submodule Git pointers are deliberately skipped and disclosed.
  A named root must not itself be a symlink; symlinks in its ancestors (macOS `/var`, a home
  directory on another volume) are resolved once, and the report shows the resolved path
- Only directories with project evidence are auto-discovered; excluded directories are listed
  as unreviewed and make coverage partial, never falsely reported as absent
- Heading checks do not assess section bodies. Overlapping topics are not proof of contradiction.
  Docs/work content judgment is done by the skill, not claimed by the structural runner
- Missing structure is reported, not silently scaffolded. No cache, bytecode, state, suggestions,
  archive, or last_applied updates occur during audits
- A built package and deterministic tests do not prove live plugin loading or model behavior.
  No live Codex installation or paid agent/service test is part of this pilot

## Platform contract checked 2026-10-06

The portable root `plugin.json` plus fixed `skills/` layout follows current official
[plugin packaging guidance](https://developers.openai.com/plugins/build/plugins).
`.codex-plugin/plugin.json` remains supported, but is unnecessary for this skills-only pilot.
No MCP registration, permissions, or hook manifest is shipped.

Context behavior follows [AGENTS.md discovery](https://learn.chatgpt.com/docs/agent-configuration/agents-md).
The separation from Claude hooks follows the [Claude plugin migration guidance](https://developers.openai.com/plugins/guides/submit-claude-plugin).
Current runtime support must be verified in an explicitly authorized live pilot before rollout.

## Validation scope

Offline tests cover deterministic generation, source hashes, standalone package relocation,
missing dependencies, path/symlink refusals, no-write snapshots, org/client discovery, all four
archetypes, identity registry semantics, inventory and malformed/partial inputs.

Independent instruction walkthroughs cover these routing cases: explicit no-PARC → direct
answer; exploratory org reorganization → discovery/options; whole-org review with one approved
repo → partial bounded review; supplied plan → Review without implementation. These are
manual forward checks, not proof of live automatic skill activation.

The eight existing canonical pytest suites can be run separately as documented in repository
CLAUDE.md. Run each independently because their test package names collide. New characterization
tests preserve the intentional default-versus-strict policies and check pure helper behavior.
Apply the shared canonical source changes together with this adapter; no Muse source or
release-metadata changes are required for this local prerelease.
