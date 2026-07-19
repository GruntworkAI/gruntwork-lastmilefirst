---
title: "feat: Network-based plugin-update check for Overwatch"
date: 2026-07-18
type: feat
status: draft
artifact_contract: ce-unified-plan/v1
artifact_readiness: implementation-ready
execution: code
product_contract_source: ce-plan-bootstrap
revised: 2026-07-18
---

# feat: Network-based plugin-update check for Overwatch

**Target repo:** gruntwork-lastmilefirst · **Plugin:** `plugins/lastmilefirst/` · all paths repo-relative.

> **Revision note (post ce-doc-review):** v1 of this plan compared installed versions against the upstream **release tag** (`git ls-remote --tags`). A four-reviewer pass empirically disproved that signal against the user's real installs — release tags track *plugin* version only for single-plugin marketplaces we tag ourselves (1 of 5 installed), and produced a false un-clearable alert for `travel-skills`. This revision switches the signal to the upstream **marketplace manifest on the default branch** — the exact version `/plugin update` resolves — fetched over plain HTTPS. See "Rejected approach" and Sources.

---

## Summary

Overwatch's plugin-update check (`session_start.py::check_plugin_updates`) is a **local-only** diff of installed version vs the *locally-cached marketplace manifest*. That cache is refreshed by Claude Code's own background sync, which is [widely reported broken](https://github.com/anthropics/claude-code/issues/17361) — so a genuinely-published update rarely surfaces.

This plan adds an **independent network check** that reads the **upstream marketplace manifest** (`.claude-plugin/marketplace.json` on the repo's default branch, falling back to the plugin's own `plugin.json`) via stdlib HTTPS, and compares its version to what's installed. This is the same version `/plugin update` would resolve, so a positive is always a *consumable* update (no false or un-clearable nags), and it is correct per-plugin for monorepo marketplaces and for marketplaces that cut no tags. It runs **throttled** (once/24h), **non-blocking** (a hard wall-clock deadline well inside the SessionStart 10s budget), and **offline-safe** (silent degrade). The existing local manifest diff is retained as an additional signal.

---

## Problem Frame

- **Who:** every user of any plugin they have installed — acutely the maintainer, who publishes releases and needs to know they landed.
- **Today:** `check_plugin_updates()` (`plugins/lastmilefirst/hooks/scripts/session_start.py`, L98–151) alerts only when the *cached* manifest version exceeds installed — a condition that requires Claude Code's unreliable cache refresh to have already run.
- **Gap:** a freshly published version produces no alert until that refresh happens. Verified live: `lastmilefirst` is installed at 0.16.0 while the upstream manifest is at 0.16.1; `gruntwork-travel-skills` is installed at 0.3.1 while upstream is at 0.4.1 — neither surfaces today.
- **Why now:** Claude Code's cache bugs make the local signal unreliable, and the upstream manifest is a cheap, auth-free, per-plugin-correct signal we can read directly.

---

## Requirements

- **R1** — Detect when an installed plugin's upstream **marketplace-manifest version** (default branch) exceeds the installed version, independent of the local marketplace cache.
- **R2** — Network work MUST NOT stall session start; the SessionStart hook has a 10s timeout (`plugins/lastmilefirst/hooks/hooks.json`). Enforce a hard total wall-clock budget (≤5s) with per-request timeouts; cold/slow/offline never delays or breaks the session.
- **R3** — Throttle network checks to at most once per 24h, reusing the existing-but-vestigial `last_plugin_check` state field. The throttle MUST advance even if a refresh is interrupted (write the timestamp before fetching).
- **R4** — Offline / proxy-blocked / HTTP-failure / malformed-response degrades silently: no error output, no spurious alert, session unaffected.
- **R5** — Resolve each plugin's repo from trusted local config; only fetch from `raw.githubusercontent.com` for `github`-sourced marketplaces; validate all URL components; skip anything unresolvable or non-github. No arbitrary-host egress.
- **R6** — A positive alert must reflect a **consumable** update, match existing Overwatch style, and tell the user the reliable update path given Claude Code's stale-cache bugs.
- **R7** — The network call is isolated behind one small stubbable function; ship unit tests. (No hook-script test harness exists yet — this establishes one.)
- **R8** — Keep the existing local manifest diff as an additional signal; never regress current behavior. Drive alerts from the current installed set (prune stale cache entries).

---

## Key Technical Decisions

**KTD1 — Signal = upstream marketplace manifest, not release tag.** Fetch `.claude-plugin/marketplace.json` from the repo's default branch and read the installed plugin's `plugins[].version`. This is exactly what `/plugin update` resolves, so it is per-plugin correct and consumable by definition. Empirically validated (2026-07-18): the monorepo case that killed the tag approach produces **no false nag** — `compound-engineering` resolves via its in-repo `plugin.json` to 3.19.0 == installed → silent; and the false-nag case tags got wrong is a real update — `travel-skills` upstream is genuinely 0.4.1 vs installed 0.3.1. **Coverage is not universal** (see KTD2): a marketplace is covered only when the plugin's version is discoverable in-repo. Rejected: `git ls-remote --tags` (see "Rejected Approach").

**KTD2 — Two-level version resolution, in-repo only.** Read `marketplace.json`; if the plugin's entry has an inline `version`, use it (ours: `lastmilefirst: 0.16.1`; also `travel-skills: 0.4.1`). Else, **only if `plugins[].source` is a string path within the repo**, fetch `<source>/.claude-plugin/plugin.json` and read `version` there (`compound-engineering`'s `source: "./"` → repo-root `plugin.json` → 3.19.0). Empirically, `source` is frequently a **dict** (`{"source":"git-subdir","url":…,"path":…}` or `{"source":"url",…}`) pointing to an **external** repo — those are **out of reach of the host-pinned in-repo fetch and are silently skipped** (verified: `claude-plugins-official` has 205/257 external-dict sources and null in-repo versions → not covered). Worst-case GETs per plugin: branch-resolve (up to 2, KTD3) + `marketplace.json` + optional `plugin.json`; the wall-clock deadline (KTD4), not this count, is what bounds cost.

**KTD3 — Plain HTTPS via stdlib, no git subprocess.** Fetch with a **dedicated `urllib` opener** (not bare `urlopen`) from `https://raw.githubusercontent.com/<owner>/<repo>/<branch>/<path>`. Eliminates the git/shell command surface entirely (executes nothing; parses JSON only). Default branch resolved by trying `main` then `master`, cached per marketplace (a repo whose default is neither — e.g. `develop` — is an unsupported **silent miss**, never a false alert; optionally resolve the true default from the already-cloned marketplace at `known_marketplaces[mp].installLocation` via local git, no network). Rename handling: `raw.githubusercontent.com` **serves renamed repos transparently** — verified the maintainer's stale `gruntwork-marketplace` path returns HTTP 200 (0 redirects) with `lastmilefirst 0.16.1`; no HTTP redirect actually occurs, so the redirect guard (U2) is a safety net, not a happy-path dependency.

**KTD4 — Non-blocking via throttled bounded-inline refresh.** Session start **surfaces from cached results instantly** (zero network on the hot path). At most once/24h it runs an **inline** refresh guarded by a hard wall-clock deadline: check elapsed before each plugin, `per-request timeout = min(remaining_budget, 2s)`, abort the remainder on breach; total budget ≤5s (within the 10s hook budget with margin). Rejected detached-background: no process-spawn precedent exists in `hooks/scripts/` (the POSIX/Windows code there is file-locking only), cross-platform detachment is error-prone, and a reaped child would never advance the throttle. **Write `last_plugin_check = now` in the parent before fetching** (R3) so the throttle advances regardless of how the refresh ends.

**KTD5 — Consumable + self-clearing, driven by the installed set.** Alert when upstream manifest version > installed. Because the manifest is the consumable version, the alert clears the moment the user updates. On every session, re-verify cached `available` against the *freshly-read current installed* version (self-clear), and **drive alerts from the current installed set** — cache keys for uninstalled plugins are pruned and never alert (R8).

**KTD6 — Alert text reflects the stale-cache reality (R6).** Beyond `name@marketplace: installed -> available`, include the reliable update path: `/plugin update` / `/plugin marketplace update` often report success while leaving the cache stale ([#61954](https://github.com/anthropics/claude-code/issues/61954), [#72616](https://github.com/anthropics/claude-code/issues/72616)); the dependable path is uninstall+reinstall or `rm -rf ~/.claude/plugins/cache` then re-add.

**KTD7 — Version compare must reject pre-releases.** `overwatch.py::version_compare` drops fused non-numeric components: verified `version_compare("0.17.1-rc1","0.17.0") == 0` (mis-ranked) and its docstring is wrong. Filter out any version string containing a non-numeric-suffixed component (e.g. `-rc1`, `-beta`) before comparing; fix the docstring. Do not silently trust `normalize`.

**KTD8 — Version bump = MINOR (0.17.0).** New user-visible behavior. Follow the repo checklist (`plugin.json`, `marketplace.json` ×2, `README.md`); cut `v0.17.0` after merge.

---

## Rejected Approach: release-tag signal (v1)

`git ls-remote --tags <marketplace-repo>` then max-semver vs installed. Rejected because "tag == plugin version" holds only for single-plugin marketplaces we tag ourselves. Empirically, of 5 installed marketplaces: `every-marketplace` returns marketplace-level `v2.x` tags while `compound-engineering` is at 3.19.0 (wrong axis); `claude-plugins-official` cuts no tags (silent no-op); `travel-skills` has tags ahead of an installed version with no matching tag → a **permanent un-clearable false ACTION REQUIRED**. Only `lastmilefirst` worked. The manifest signal (KTD1) fixes the monorepo and false-nag cases and needs no tag discipline; tag-less/external-source marketplaces (`claude-plugins-official`) are silently skipped by both approaches, but the manifest approach at least never *misfires* on them.

---

## High-Level Technical Design

```mermaid
flowchart TD
    A[SessionStart hook] --> B[check_plugin_updates]
    B --> C[Read installed set + cached results from state]
    C --> D{For each cached entry:<br/>available &gt; CURRENT installed?<br/>KTD5 re-verify + prune}
    D -- yes --> E[Emit consumable ACTION REQUIRED<br/>KTD6 text]
    D -- no --> F[No network-sourced alert]
    E --> G{now - last_plugin_check &gt; 24h?}
    F --> G
    G -- no --> H[Return - zero network on hot path]
    G -- yes --> I[Write last_plugin_check=now in PARENT - KTD4/R3]
    I --> J[Bounded-inline refresh<br/>wall-clock deadline &le;5s]
    J --> H
    subgraph refresh [Inline refresh - deadline-bounded]
        K[For each installed github-sourced plugin] --> L[Resolve owner/repo + default branch - KTD3, validate - R5]
        L --> M[GET marketplace.json]
        M --> N{plugins[].version present?}
        N -- yes --> P[use it - KTD2]
        N -- no --> O[GET plugin.json at source path] --> P
        P --> Q[Filter pre-release - KTD7, compare vs installed]
        Q --> R[Write results to cache, prune uninstalled - KTD5]
    end
```

The existing local manifest diff (R8) contributes to the same alert list, deduped.

---

## Implementation Units

### U1. Repo + default-branch + plugin-entry resolver

**Goal:** From an installed plugin id, produce a validated `raw.githubusercontent.com` base and locate its `plugins[]` entry.
**Requirements:** R5. **Dependencies:** none.
**Files:** `plugins/lastmilefirst/hooks/scripts/overwatch.py` (helpers), test in `plugins/lastmilefirst/hooks/tests/test_plugin_update_check.py`.
**Approach:** Read `known_marketplaces.json` via `get_plugins_dir()`; map `<name>@<marketplace>` → `source`. Require `source.source == "github"` and `source.repo` matching `^[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*$` — else `None` (R5, blocks path/host injection). Resolve default branch by trying `main` then `master` (cache per marketplace). Match the installed `<name>` to a `plugins[].name` entry; no match → `None` (skip). **`plugins[].source` may be a string or a dict** — require `isinstance(source, str)` (dict/external sources → `None`, an explicit skip, not exception-driven), then validate it with an **allowlist** `^[A-Za-z0-9][A-Za-z0-9._/-]*$`, reject any `..` path segment and any `%` (defeats encoded traversal like `%2e%2e`), before use.
**Patterns to follow:** tolerant loaders in `overwatch.py` (`_load_organize_config`, `get_plugins_dir`).
**Test scenarios:**
  - github source, valid repo → correct owner/repo.
  - non-github / malformed `repo` (`../x`, `a/b/c`, leading `-`, whitespace, `ext::…`) → `None`.
  - marketplace absent / malformed JSON → `None`, no exception.
  - `<name>` not present in `plugins[]` → `None` (skip).
  - `plugins[].source` is a dict → `None` (skip, no exception).
  - string `plugins[].source` with `..`, leading `/`, scheme, or `%2e%2e` encoded traversal → rejected.
**Verification:** returns validated components or `None` across cases; no network.

### U2. Upstream version fetcher (stubbable HTTP boundary)

**Goal:** Given resolver output, return the upstream version string or `None`.
**Requirements:** R1, R2, R4, R5, R7. **Dependencies:** U1.
**Files:** `plugins/lastmilefirst/hooks/scripts/overwatch.py` (`fetch_upstream_version` wrapping the sole network primitive `_http_get_json`), test file above.
**Approach:** `_http_get_json(url, timeout)` is the **only** function that hits the network, and the only thing tests stub. Build a **dedicated `OpenerDirector`** with a custom `HTTPRedirectHandler.redirect_request` that **rejects any redirect whose host is not exactly `raw.githubusercontent.com`** (`urllib`'s default follows redirects without host validation — the pin must be enforced in the opener, not assumed); **no `ProxyHandler`** (ignore `*_proxy` env — deterministic egress; note in Risks); send no credentials/cookies and no `Accept-Encoding` (avoid decompression bombs). Enforce the size cap by reading `resp.read(MAX_BYTES + 1)` and rejecting if it exceeds `MAX_BYTES` (~1 MB) — do **not** trust `Content-Length`. Verify the initial URL's scheme+host before the request. Return parsed JSON or `None` on any error/timeout/non-200/oversize/non-JSON. `fetch_upstream_version` does KTD2 two-level resolution: marketplace.json entry version, else (string in-repo source only) plugin.json at the validated source path. Any failure → `None` (R4).
**Patterns to follow:** stdlib `urllib.request` `OpenerDirector`/`HTTPRedirectHandler`; `json.loads`.
**Test scenarios:**
  - inline-version manifest → returns that version.
  - null version + in-repo string source → falls back to plugin.json → returns its version.
  - 404 / non-200 / URLError (offline) / timeout → `None`, no exception.
  - oversize (body > cap, incl. a lying `Content-Length`) / non-JSON body → `None`.
  - stubbed redirect to a non-`raw.githubusercontent.com` host (incl. `evilraw.githubusercontent.com` and `raw.githubusercontent.com.attacker.com`) → refused → `None`.
  - URL construction pins host to `raw.githubusercontent.com` (assert the URL passed to the stub).
**Verification:** correct version from stubbed fixtures; real network never hit in tests.

### U3. Version selection + pre-release guard

**Goal:** Decide "upstream newer than installed," rejecting pre-releases.
**Requirements:** R1 (approach realizes KTD7). **Dependencies:** none (pure), used by U5.
**Files:** `plugins/lastmilefirst/hooks/scripts/overwatch.py` (`is_pre_release` guard + a thin `is_newer(installed, upstream)`; fix `version_compare` docstring), test file above.
**Approach:** Treat any version containing a non-numeric-suffixed component as pre-release and exclude it from "newer" (return False). Keep `version_compare` for the numeric compare (its lexical-trap behavior is correct — verified `0.9.0 < 0.16.1`).
**Test scenarios:**
  - `is_newer("0.16.0","0.16.1")` → True; `("0.16.1","0.16.1")` → False; `("0.17.0","0.16.1")` → False.
  - lexical trap: `("0.9.0","0.16.1")` → True.
  - pre-release upstream `0.17.1-rc1` vs installed `0.17.0` → not newer (guard).
**Verification:** boundary + pre-release cases correct.

### U4. Throttle + result cache in state

**Goal:** Persist last-check timestamp (written before refresh) and per-plugin results, pruned to installed.
**Requirements:** R3, R4, R8. **Dependencies:** none (schema), consumed by U5.
**Files:** `plugins/lastmilefirst/hooks/scripts/overwatch.py` (extend v2 state `global`, helpers, `_ensure_v2`), test file above.
**Approach:** Reuse `global.last_plugin_check` as the 24h gate. Add `global.plugin_update_cache`: `{ "<name>@<marketplace>": {"available": "0.16.1", "checked_at": ts} }`. Add `is_plugin_check_due(state, now)`, and a `record_check_started(now)` that writes `last_plugin_check` **before** fetching (R3). Prune cache keys absent from the current installed set on write. Update `_ensure_v2` + the schema docstring so existing state files gain the field.
**Patterns to follow:** `_ensure_v2`, `update_scoped_state`, `file_lock`, state docstring at `overwatch.py` top.
**Test scenarios:**
  - due at `last_plugin_check=0`; not due within 24h; due after.
  - `record_check_started` advances the timestamp even if no results follow.
  - cache round-trips; malformed cache → treated empty.
  - prune drops an uninstalled key; `_ensure_v2` adds missing field without dropping others.
**Verification:** throttle advances on interruption; migration idempotent; prune works.

### U5. Wire into `check_plugin_updates`

**Goal:** Instant surface-from-cache + throttled bounded-inline refresh; keep local diff; consumable/self-clearing alerts.
**Requirements:** R1, R2, R4, R6, R8. **Dependencies:** U1–U4.
**Files:** `plugins/lastmilefirst/hooks/scripts/session_start.py` (`check_plugin_updates` L98–151, alert block L695–701), test file above.
**Approach:** (1) Read installed set + cache; for each cache entry whose plugin is still installed and `is_newer(installed, available)`, emit a line (KTD5). (2) Keep the existing manifest diff, merged/deduped (R8). (3) If `is_plugin_check_due`: `record_check_started`, then refresh under the wall-clock deadline (KTD4) — resolve (U1), fetch (U2), select (U3), write+prune cache (U4). (4) Alert copy per KTD6. Hot path performs **zero** network.
**Execution note:** build the cache-surface + re-verify + prune path first and prove it with stubbed state (no network); add the deadline-bounded refresh last so the non-blocking guarantee is unit-testable in isolation (assert refresh is skipped when not due, and that it never exceeds the budget with a slow stub).
**Patterns to follow:** existing `check_plugin_updates` join; alert conventions in `main()` (`ACTION REQUIRED:` + indented detail).
**Test scenarios:**
  - cached available > installed, still installed → alert with KTD6 guidance.
  - available == installed (user updated) → no alert (self-clear).
  - cached key for uninstalled plugin → no alert (prune).
  - not due + empty cache → refresh not invoked; no alert.
  - due → `record_check_started` called before any fetch; refresh respects deadline with a slow stub (asserts total elapsed ≤ budget).
  - local diff still contributes; duplicate from both sources collapses to one line.
**Verification:** on a machine behind (e.g. travel-skills 0.3.1→0.4.1), the alert surfaces from cache within one refresh cycle (the first behind-session runs the refresh; emission is instant thereafter); offline session silent and unaffected.

### U6. Test harness for hooks scripts

**Goal:** Stand up the first pytest suite under `hooks/`, covering U1–U5.
**Requirements:** R7. **Dependencies:** U1–U5.
**Files:** `plugins/lastmilefirst/hooks/tests/test_plugin_update_check.py` (+ `conftest.py`/`__init__.py`/`fixtures/` as the audit-plugin suite uses).
**Approach:** Mirror `plugins/lastmilefirst/skills/audit-plugin/tests/`. Inject a temp plugins dir (`installed_plugins.json`, `known_marketplaces.json`, state) and stub `_http_get_json`. Fixtures for the real-world shapes: inline-version (lastmilefirst 0.16.1 > 0.16.0 → alert); null-version + in-repo string source → plugin.json 3.19.0 == installed → no alert (the ex-monorepo case, proving no misfire without any tag involvement); dict/external `source` → skip; `<name>` not in `plugins[]` → skip; no manifest / 404 (private) → skip; pre-release upstream → not newer; default branch neither main/master → skip. No real network.
**Patterns to follow:** `skills/audit-plugin/tests/test_*.py` + `conftest.py` + `fixtures/`.
**Test scenarios:** aggregate of U1–U5 plus one end-to-end: fixture "installed 0.16.0, upstream manifest 0.16.1" → refresh populates cache → next `check_plugin_updates` emits exactly one alert.
**Verification:** `pytest plugins/lastmilefirst/hooks/tests/` green, offline, deterministic.

### U7. Docs + version bump

**Goal:** Document behavior + coverage honestly; ship the version.
**Requirements:** R6 (ships KTD8). **Dependencies:** U1–U6.
**Files:** `plugins/lastmilefirst/skills/overwatch/SKILL.md`, `plugins/lastmilefirst/commands/run-overwatch.md`, `plugins/lastmilefirst/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `README.md`.
**Approach:** Document the network check: what it reads (upstream manifest, default branch), the 24h throttle, offline-safe, surface-next-refresh latency, and the KTD6 update path. **State coverage honestly** — covered only when the plugin's version is discoverable in-repo (inline `plugins[].version`, or a string in-repo `source` whose `plugin.json` carries a version). Silently skipped (local diff still applies): non-github marketplace sources; dict/external `plugins[].source`; plugins with null versions in both manifest and in-repo `plugin.json` (e.g. much of `claude-plugins-official`); private/unreachable repos; default branch neither `main` nor `master`. Bump all four version sites to **0.17.0**; cut `v0.17.0` post-merge (release is out of this plan's code scope).
**Test expectation:** none — docs + version strings. Verify all four sites read 0.17.0.
**Verification:** docs accurate; version grep consistent.

---

## Definition of Done

- All installed **github-sourced** plugins one release behind (per upstream manifest) surface a consumable `ACTION REQUIRED` within one refresh cycle; the alert clears after the user updates.
- Hot path issues zero network calls; refresh runs ≤ once/24h, bounded ≤5s wall-clock, and never delays or breaks session start; offline is silent.
- No false or un-clearable alerts for monorepo, tag-less, external-source, or non-github marketplaces (they compare the correct per-plugin in-repo version, or skip silently — never misfire).
- `pytest plugins/lastmilefirst/hooks/tests/` green offline; all four version sites at 0.17.0.

---

## Trust Boundary & Security

- **Boundary:** `known_marketplaces.json` is user-owned but attacker-influenceable (a marketplace the user added, or a direct edit). For the *content* (version strings shown in an alert), adding a marketplace already implies trusting it — **not a new trust class**. But the rewrite does add a genuinely new *capability*: local config now drives **outbound HTTPS with a path derived from that config** — an SSRF-pivot surface that did not exist for a local-only diff. The controls below exist precisely to contain that; they are load-bearing, not merely cosmetic defense-in-depth.
- **Controls (stated requirements, not incidental):** github-source-only + anchored `owner/repo` regex (U1) — excludes `@`/userinfo, extra slashes, `%`-encoding, CRLF, `..`; string-source-only + allowlist source-path regex rejecting `..` segments and `%` (U1); initial scheme+host pinned to `https://raw.githubusercontent.com` **and** redirects refused unless the target host is exactly `raw.githubusercontent.com`, enforced by a custom opener (U2); bounded read before consuming body, no `Content-Length` trust, no `Accept-Encoding`, no proxy env, no credentials/cookies (U2); JSON parse only, execute nothing.
- **Egress:** limited to `raw.githubusercontent.com` (initial request and any redirect); a hostile `source.repo`/`source` can only alter the URL *path*, not the host.

---

## Scope Boundaries

**In scope:** manifest network check (two-level), throttle+cache, non-blocking wiring, repo/URL resolution+validation, consumable/self-clearing alerts, tests, docs, 0.17.0 bump.

### Deferred to Follow-Up Work
- **Non-github marketplace sources** (GitLab, generic git, local path) — skipped for now; if added, re-apply the host-pinning/validation analysis before shipping.
- **Per-plugin throttle** — a newly installed plugin waits for the global 24h window (acceptable v1); optionally refresh only entries older than 24h via the per-entry `checked_at`.
- **Snooze/ack for genuinely un-landable updates** — not needed with the consumable-manifest signal, but revisit if Claude Code's cache bugs make a real update repeatedly un-applyable.
- **Pre-push secret-scan hook** — unrelated tracked idea (`project_lmf_prepush_scan`).

**Out of scope:** fixing Claude Code's own cache-refresh bugs (upstream); the secret-scan hook (shipped 0.16.1).

---

## Open Questions

- **Q1:** Default-branch resolution is main-then-master (2 GETs on the rare master repo; a `develop`/`trunk` default is a silent miss). Acceptable, or resolve the true default locally from `known_marketplaces[mp].installLocation` (the already-cloned marketplace, no network)? Lean main-then-master + per-session cache for v1; local resolution is a cheap follow-up.
- **Q2:** Total refresh budget (proposed ≤5s) and per-request timeout (`min(remaining, 2s)`) — confirm against the 10s hook budget with the user's 4–5 marketplaces (worst case: several 2s timeouts must stay under budget via the wall-clock abort).
- **Q3:** Should the 24h throttle be configurable (organize-config key)? Lean hard-coded for v1.

---

## Risks & Dependencies

- **Proxy env ignored (decision):** the U2 opener is built **without `ProxyHandler`**, so `*_proxy` env never routes these requests — deterministic, security-scoped egress. Consequence: corporate users who reach GitHub *only* via an env proxy get a silent skip (local diff still runs). Acceptable for v1; revisit if a real user needs proxied reachability.
- **`raw.githubusercontent.com` unreachable** (proxy block, offline, DNS) → fetch fails → silent skip (R4). Local diff still runs.
- **Default branch neither `main` nor `master`** → both probes 404 → silent miss (never a false alert). Q1 notes local `installLocation` resolution as the fix if this bites.
- **Rename-redirect dependency** — the maintainer's `gruntwork-marketplace` path is served transparently by raw (verified 200, 0 redirects). If the old repo name were deleted/recreated, resolution 404s → silent skip; add a test for graceful 404. Longer-term: re-add the marketplace under `gruntwork-lastmilefirst` so `known_marketplaces.json` points directly.
- **Private repos** → raw 404/401 → silent skip.
- **`version_compare` pre-release bug** — guarded in U3; do not rely on `normalize`.

---

## Sources & Research

- Empirical validation (2026-07-18, live installs): tag signal fails, manifest signal succeeds — every-marketplace (compound `source:"./"`, version in repo-root plugin.json = 3.19.0 == installed → no nag), travel-skills (manifest 0.4.1 inline vs installed 0.3.1 → real update), claude-plugins-official (257 plugins, 205 external-dict sources + null versions → **not covered**, silent skip), gruntwork rename served transparently by raw (200, 0 redirects). Second review round (2026-07-18) drove: honest coverage (no universal claim), `isinstance(str)` source guard, allowlist source-path vs `%2e%2e`, custom redirect opener with exact host pin, bounded read, no-proxy decision.
- Claude Code cache-refresh bugs: [#17361](https://github.com/anthropics/claude-code/issues/17361), [#46081](https://github.com/anthropics/claude-code/issues/46081), [#61954](https://github.com/anthropics/claude-code/issues/61954), [#72616](https://github.com/anthropics/claude-code/issues/72616), [#36938](https://github.com/anthropics/claude-code/issues/36938).
- Local grounding: `session_start.py::check_plugin_updates`/`main`, `overwatch.py` state schema + `version_compare` + `get_plugins_dir`, `~/.claude/plugins/{installed_plugins,known_marketplaces}.json`, test pattern `skills/audit-plugin/tests/`.
- Review: ce-doc-review 4-reviewer pass (coherence, feasibility, adversarial, security) 2026-07-18 — drove the tag→manifest pivot, throttle-in-parent, cache pruning, pre-release guard, timeout-math, and security controls.

**Product Contract preservation:** n/a (bootstrap plan).
