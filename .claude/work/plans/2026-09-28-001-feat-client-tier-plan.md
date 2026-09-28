---
title: Client tier — a counterparty directory between org and project
version: 1.1
date: 2026-09-28
status: draft
type: feat
component: hooks/scripts/workspace_types.py (new), hooks/scripts/overwatch.py, hooks/scripts/session_start.py, hooks/scripts/update_state.py, skills/scan-secrets/scripts/scanner.py, skills/todos-summary/scripts/aggregator.py, skills/review-org/scripts/review_org.py, skills/review-claude/scripts/review_claude.py, skills/organize-claude/scripts/organize_claude.py, skills/organize-orgs/scripts/audit_identity.py
target_version: 0.36.0
refs:
  - .claude/work/plans/2026-05-02-workspace-types.md (draft spec that already defines `type: client`; amended by D1)
  - .claude/work/plans/2026-08-17-001-feat-per-org-identity-contract-plan.md (the marker mechanism and the four-type list, line 52)
  - plugins/lastmilefirst/skills/organize-orgs/scripts/check_identity.py (the marker parser, `workspace_type`, 153-174; the loader imports it)
---

# Client tier — a counterparty directory between org and project (v1.1)

> **v1.1 (2026-09-28).** After review. `client` is now nested-only (D1); the loader imports the existing parser instead of duplicating it (D4); a client directory has no state scope and its CLAUDE.md is chained but not tracked (D6); the adoption unit is generic, with the concrete steps kept in the adopting org's private repo (U6); two walkers added to the inventory (organize-claude's mapping validation, review-claude's inventory check); test injection points named.
>
> **v1.0 (2026-09-28).** First draft, written the day the practice's first client engagement was set up and the two-tier layout turned out to have no place for the counterparty.

## Problem

### P1. An advisory org has a unit the workspace model lacks

The workspace model is org, then project: `~/Code/<org>/<project>`. That fits a product org, where a project is the unit of work. In an advisory org the unit is the counterparty. One client brings several repos at once (an engagement workspace, a read-only clone of their code, a deliverable that becomes code), and nothing in the layout says they belong together. Today they sit flat beside practice-level repos, connected only by naming and by memory.

### P2. The tooling assumes exactly two tiers, in eleven places

Every walker enumerates an org's immediate children as projects and stops: Overwatch's workspace summary, the `--all` secret scan, todos-summary, review-org, review-claude (discovery and the inventory check), organize-claude (discovery and the mapping validation), and the identity audit. Project state is keyed `org/project` by four separate f-strings. A counterparty directory added by hand today is reported as one project with a missing CLAUDE.md, and the repos inside it drop out of every sweep silently. Silent is the problem: the scan would say "clean" about repos it never opened.

### P3. The marker vocabulary already has the right word, with a different meaning

A draft spec (2026-05-02, never built) defines four org-level types for the `.claude-workspace` marker: studio, client, external, scratch. There `client` marks a top-level directory that belongs to a client. No such marker exists in any workspace today. This plan needs the word one level down, and two meanings for one word in one marker is not acceptable, so the plan settles it.

### P4. Renames orphan project state

Moving a project under a counterparty directory changes its state key, and nothing migrates keys. The cost is modest (a "never scanned" line that one `--all` run clears, and a dead entry in `status --all`), but it is the same gap any directory rename hits today, and adopting the tier is the moment it becomes visible.

## Decisions

**D1. `type: client` is a nested container, and only that.** A directory carrying the marker inside an org is a container of projects for one counterparty: its non-hidden children are projects, it is not one. It is not recognized at the top level. A client that is a whole org (the draft spec's case) is an ordinary org with its own `org.json` and needs no marker. The 2026-05-02 spec is amended to say so; its `status: active|paused|archived` field carries over unchanged, and its hygiene-default table is not built here. The reason for nested-only rather than "either depth": a top-level directory needs `org.json`, is discovered through the config's `orgs` list, and reviews as tier `org`; a nested one must not have `org.json`, is discovered by marker, and reviews as tier `client`. That is two behaviors, and one word claiming they are the same would be a trap.

**D2. One level only.** A container inside a container is yielded as an ordinary project with a one-line `note` the caller prints. No org has needed a second level.

**D3. The project key is the path relative to the workspace.** `org/client/project` for nested projects, `org/project` as today for flat ones. Three-part keys cannot collide with existing two-part keys, so nothing is silently re-keyed. Labels in output show `client/project` when nested, so two clients holding a `docs` repo each stay distinct.

**D4. One loader, in `hooks/scripts/workspace_types.py`, importing the parser that already exists.** `check_identity.workspace_type`, `WORKSPACE_MARKER`, and `UNGOVERNED_TYPES` are already on the import path of `session_start` (through `audit_identity`, which puts `organize-orgs/scripts` on `sys.path` at module load). The loader imports those three and adds only `is_container`, `iter_projects`, `project_key`, `resolve`. The pre-commit hook stays stdlib-only because it is the source, not a consumer. Nothing is duplicated and there is no parity test. `hooks/scripts` is the home by the `github_protections` precedent: its latency-sensitive consumer is `session_start`.

**D5. The client directory must not carry `.claude/org.json`.** The org's contract governs; `find_governing_org` walks up through the client to the org, so commit identity and remote checks are unchanged. A client-level `org.json` is half-honored today (nearest-wins in the hook, invisible to the claims registry, the audit, `discover_accounts`, and `classify_tier`), and the hook keeps obeying it between "flagged" and "fixed," so the flag is an ERROR line at session start, not a warning. If an engagement ever requires committing under a client-issued GitHub account, the shape is an identity-only override that all four depth-1 readers learn about in the same change, never a second `org.json`. Not built here.

**D6. A client directory has no Overwatch state scope, and its CLAUDE.md is chained but not tracked.** State has three scopes (global, orgs, projects) and review-claude's tiers map onto them one-to-one. This release does not add a fourth. `resolve` from inside a client directory returns the org and no project; `update_state.py` says "container directory, not tracked" instead of "not in a recognized project." review-claude classifies a CLAUDE.md in a container as tier `client`, chains a nested project as project, then client, then org, and runs the overlap report over the chain. No expected-section list and no template until a second client exists to compare against.

**D7. Pseudonyms are the adopting org's convention, not a plugin rule.** The plugin does not care what a client directory is called. An org that wants pseudonyms for counterparties writes the rule in its own CLAUDE.md.

**D8. State keys get a rename tool, not an automatic migration.** `update_state.py rename --from <key> --to <key>`, refusing when the target exists. Explicit and reversible, about forty lines, and it closes P4 for ordinary renames too. Drop it if it grows past that.

## Design

### The loader

```python
# hooks/scripts/workspace_types.py
from check_identity import workspace_type, WORKSPACE_MARKER, UNGOVERNED_TYPES  # organize-orgs/scripts on sys.path
CONTAINER_TYPES = {"client"}

def is_container(directory: Path) -> bool
def iter_projects(org_dir: Path) -> Iterator[Project]      # Project(path, key_parts, client: str | None, note: str | None, defect: str | None)
def project_key(path: Path, workspace: Path) -> str | None
def resolve(path: Path, workspace: Path, orgs) -> Context   # org, client, project, key
```

`iter_projects` yields every non-hidden child of the org. A child that is a container is not yielded; its non-hidden children are, with `client` set and three `key_parts`. A container inside a container is yielded as a project with a `note`. A container carrying `.claude/org.json` is still treated as a container (its children are yielded) and the first child carries a `defect` string the caller surfaces as an ERROR line. Filters stay where they are: the scanner still requires `.git`, todos-summary still requires `todos/`, the summary and review-org take every directory. The loader never filters.

### Where the key is made

Today four f-strings build `org/dirname` (`overwatch.py:410`, `session_start.py:685`, `scanner.py:597`, `review_org.py:141`). After: `resolve_context` calls `resolve`, and the other three take `key_parts` from `iter_projects`. `update_state.py --key` accepts three-part keys; `status --all` prints keys as stored.

### Walkers

| Walker | Today | After |
|---|---|---|
| `session_start.check_workspace_summary` | `org_dir.iterdir()` | `iter_projects`; label `client/project` when nested; `note` and `defect` become Overwatch lines; gains `state=` and `commit_ts=` parameters for tests, in the style of `review_org.build_rollup` |
| `scanner.scan_workspace` | depth 2, all of `~/Code` | depth 2, plus depth 3 under a container; `.git` still required; SKILL.md sentence updated |
| `aggregator.discover_projects` | one level, needs `todos/` | `iter_projects`, same filter; item `project` becomes `client/project` |
| `review_org.project_dirs` + key | one level | `iter_projects`; roll-up groups nested rows under the client |
| `review_claude.find_projects`, `classify_tier`, `tier_files`, `disk_projects` | one level; position-based tiers; inventory by `find_projects` | descend; container marker means tier `client`; `tier_files` walks up to the org instead of fixed depth; the org Projects table lists nested repos by full path (the container may have a row, but it does not stand in for its children); `TIER_CHOICES` gains `client` |
| `review_claude.py:268` review label | `parent.name/CLAUDE.md` | `client/project/CLAUDE.md` when nested |
| `organize_claude.find_projects`, `validate_project_mapping`, `short_name` (615) | one level; compares by directory name; assumes an `<org>-` prefix | descend; compare by workspace-relative path; no prefix assumption for nested repos; never scaffold into a container; audit report indents `client/` rows under the org |
| `audit_identity.iter_repos` | one level, "repos don't nest" | descend one level through containers; messages `org/client/repo` |
| `github_protections.discover_accounts` | `org.json` at depth 1 | unchanged (D5) |
| `check_identity` (pre-commit) | walks up | unchanged; one test added for a repo under a container |

### Import plumbing

Runtime `sys.path` inserts to `hooks/scripts`, one each in `review_claude.py`, `organize_claude.py`, `aggregator.py`, and `audit_identity.py` (the last also needs `organize-orgs/scripts` for the parser, which it has). `aggregator` is imported lazily by `session_start` with its directory pushed and popped, so its import of the loader lives inside the function that needs it. Test conftests that gain a `hooks/scripts` entry: review-claude and organize-orgs; review-org and scan-secrets already have one; todos-summary and organize-claude get new `tests/` directories with the standard conftest.

### The workspace CLAUDE.md path convention

The user-tier CLAUDE.md lists path conventions per org. An org adopting the tier adds `~/Code/<org>/{client}/{project}` beside its flat convention. `organize_claude.parse_project_mapping` already accepts any `~/Code/...` path.

## Units

Build order is the dependency order. A minimal 0.36.0 is U1, U2, and the `audit_identity` row of U3, which closes the two silent gaps (the scan and the identity audit); the other U3 walkers fail visibly and can follow in a point release.

### U1. Loader and tests

`hooks/scripts/workspace_types.py` per the Design. `hooks/tests/test_workspace_types.py` builds a `tmp_path/Code` workspace with a flat org, an org holding one container with two repos, a container inside a container, and a container carrying `org.json`.

*Accept:* `iter_projects` yields the flat and nested cases with the right keys and labels, notes the inner container, flags the `org.json`, and never filters.

### U2. Keys and state

`overwatch.resolve_context` uses `resolve`; from a container it returns the org and no project. `update_state.py` accepts three-part `--key`, says "container directory, not tracked" for a container, and gains `rename`. `scanner.scan_workspace` descends through containers and keys by `key_parts`. `session_start.check_workspace_summary` and `main()` use the loader for iteration and labels, with the injection parameters above. New file `hooks/tests/test_resolve_and_summary.py` (there are no tests for either function today): `resolve_context` for flat, nested, the container itself, and a path outside any org; `rename`; the summary listing nested projects under their client with a fake state and a fake `commit_ts`. A scan-secrets test for `scan_workspace` finding a depth-3 repo and skipping a container without `.git`.

*Accept:* a nested repo gets key `org/client/project` from every producer, the scan opens it, Overwatch lists it, a renamed key keeps its timestamps, and a container directory produces no project state.

### U3. Skill walkers

Per the Walkers table and the import plumbing. Tests: nested todos aggregate under the client label; the review-org roll-up shows the nested row; a container CLAUDE.md classifies as `client`; a nested project's tier chain is project, client, org; the org inventory check matches a nested repo listed by full path and reports one listed only by its container's name; organize-claude does not scaffold into a container and `validate_project_mapping` distinguishes two clients' `docs`; `audit_identity` finds an unregistered-account repo under a container.

*Accept:* every walker finds the nested fixtures, and none reports the container as a project.

### U4. Docs and the draft spec

scan-secrets SKILL.md ("two levels deep" becomes the container rule), review-org SKILL.md, organize-claude SKILL.md path table, organize-orgs SKILL.md marker paragraph (now the one place the vocabulary is documented: what each type does, and that only the identity checks honor `external` and `scratch`), overwatch SKILL.md org-finding sentence, README workspace-layout section. The 2026-05-02 draft spec gets a note at the top: `client` is nested-only per this plan, `status` retained, the hygiene-defaults table still unbuilt.

*Accept:* the marker has one documented vocabulary, in one place, and the other SKILL.md files link to it.

### U5. Release 0.36.0

Version in plugin.json, marketplace.json, and the README table. CHANGELOG entry under `### Added`, plus a one-line note that 0.32 to 0.35 are recorded in GitHub releases. Branch, PR, merge, `gh release create v0.36.0 --target main --latest`, `claude plugin update`, `/reload-plugins`.

*Accept:* Overwatch at session start reports the new version, and the three version declarations match.

### U6. Adopt it in one org (not plugin work, not recorded here)

The adopting org creates `<org>/<client>/` with a marker `type: client`, moves its counterparty repos under it, renames state keys with `update_state.py rename`, and updates its own project table and the user-tier path convention. The concrete steps, names, and remotes belong in that org's private repos, not in this one.

*Accept:* `scan_secrets.py --all` lists `<org>/<client>/<repo>` for each moved repo, Overwatch raises no missing-CLAUDE.md alert for the container, and a commit inside a moved repo passes the identity hook.

## Verification

Each suite runs separately from `plugins/lastmilefirst/` with `../../.venv/bin/pytest <suite>/tests/` (issue #12, the `tests` package names collide). New: `hooks/tests/test_workspace_types.py`, `hooks/tests/test_resolve_and_summary.py`, `skills/todos-summary/tests/`, `skills/organize-claude/tests/`. Additions to review-claude, review-org, organize-orgs, and scan-secrets suites. Then U6's acceptance run in the adopting org is the live check.

## Risks

- **A walker missed.** The inventory found eleven. The SKILL.md-only walks (overwatch, consult-operative, add-wisdom, search-wisdom, create-operative) resolve the org by "direct child of workspace," which passes through a container correctly; U4 re-reads them, no change expected.
- **`check_overwatch_guidance` is position-based** (`session_start.py:496-521`, assumes `cwd.parent` is the org). For a nested project the parent is the container. It passes today only because the user-tier CLAUDE.md carries the keyword. Noted, not changed.
- **Old plugin versions on other machines.** A container written here is invisible to an older plugin elsewhere: its repos drop out of sweeps there. Not a data risk. Update before use.
- **Third-party directories.** `scan_workspace` walks all of `~/Code`, not the config orgs, so a container marker in a third-party directory would be honored. Harmless and consistent.
- **A stray top-level `client` marker.** Recognized nowhere after D1, so it does nothing. The organize-orgs SKILL.md says so.

## Open questions

1. Should `iter_projects` honor the draft spec's `status: archived` by muting the container's projects in Overwatch alerts? Cheap once `status` is in use. Leaning yes, in a later release.
2. Should the review-org roll-up gain a counterparty summary line (n projects, last activity)? Deferred until a second client exists to compare against.

## Deferred

- The 2026-05-02 spec's hygiene-defaults table (`claude_md`, `secret_scan`, `review` overrides per type).
- A client-tier expected-section list, template, and scaffold in organize-claude and review-claude (D6).
- A client-level identity override (D5).
- Automatic state-key migration on rename (D8 chose the explicit tool).
