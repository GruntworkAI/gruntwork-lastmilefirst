---
title: scan-secrets — Modernize gitleaks Invocation and Extract a Scanner Seam
version: 1.1
date: 2026-07-28
status: proposed
type: refactor
component: plugins/lastmilefirst/skills/scan-secrets
target_version: 0.19.0
---

# scan-secrets: Modernize gitleaks Invocation and Extract a Scanner Seam (v1.1)

> **v1.1 correction (2026-07-28):** Ground-truthed against the actual `scanner.py` before
> building. The v1.0 premise that the code "does not currently pass `--redact`" is **false** —
> `_run_gitleaks` already appends `--redact` (`scanner.py:111`) for both call sites. The redact
> item is therefore a *verification*, not a code change, and adding `--redact` to the args per the
> translation table would double the flag. All redact-related scope below is corrected. Everything
> else in v1.0 verified accurate.

> **v1.2 build log (2026-07-28):** Executed on branch `feature/scan-secrets-gitleaks-modernization`.
> **Scope decisions with Fish:** ship **Phase 1 + Phase 3 as 0.19.0**; **Phase 2 (seam) deferred** as
> an optional testability/clarity refactor (NOT a portability play — verified no cheap second backend
> exists: only Betterleaks keeps the gitleaks TOML, and it barely tests the seam; TruffleHog/Titus/
> detect-secrets all require re-authoring the custom rules); **Phase 4 → GitHub issue** (TruffleHog +
> rule-translation, community-contributable).
> **Coverage fix folded in (was out of scope in v1.0/v1.1):** verification revealed the merged config
> loaded **only** the custom `lmf-*` rules — no `[extend]`, so gitleaks defaults (AWS/GitHub/Stripe/…)
> were **never scanned**. Fish chose to fix it now: `format_loader.write_merged_config` now emits
> `[extend]\nuseDefault = true`, so scans run defaults **+** custom formats.
> **Verified (real gitleaks 8.30.1, scratch repos):** `detect`≡`git` (identical findings, regression-
> clean); staged scan blocks + redacts; malformed config fails closed; version gate parses/compares;
> **post-fix**: a default-rule secret (github-pat) AND a custom-rule secret (lmf-postgres) both fire in
> one scan, redacted; clean repo passes (proves the extended config parses). Version gate lives in
> `_check_gitleaks` (fail-closed, consistent with existing missing-gitleaks handling — the v1.0
> hard-fail-vs-warn open question resolved by reading the code: missing gitleaks already blocks).

## Decision

Three options were considered: leave the plugin as-is, update to the current gitleaks
invocations, or migrate to Betterleaks.

**Chosen: update the invocations now, extract a scanner seam in the same pass, and defer
the Betterleaks decision behind an explicit gate.**

The deprecated commands are not going to break (gitleaks is in security-patches-only mode,
so removal is close to impossible). The real cost of leaving them is credibility: this is a
distributed plugin whose entire premise is discipline, and clients are being pointed at the
source. Migrating to Betterleaks now is premature. It is roughly six months old, its
drop-in-replacement claim is the vendor's, and the two-tier custom TOML merge in this skill
is exactly the surface where such claims break.

The tension between those two (gitleaks is frozen, Betterleaks is unproven) is resolved by
the plugin's own architecture. The design premise is that the scanner is a commodity and the
value lives in the layer above it. If that premise holds, swapping scanners should be cheap.
It currently isn't, because the invocations are inline. Phase 2 makes it cheap and tests the
premise.

## Scope

**In scope**

- Replace deprecated `detect` / `protect` invocations with current `git` subcommand forms
- Extract scanner invocation behind a single seam so the backend is a config choice
- Update SKILL.md so documentation matches behavior
- Stand up a shadow-evaluation harness for Betterleaks (no switch)

**Out of scope**

- Switching the default scanner to Betterleaks
- Changing detection rules in `common_secret_formats.toml`
- Changing severity logic, public-repo handling, or the hook installation model
- Any change to `repo_auditor.py` beyond what the seam requires
- ~~Adding `--redact`~~ — already present (`scanner.py:111`); see correction above

## Verified facts this plan relies on

### gitleaks upstream (confirmed against the repo 2026-07-27)

- v8.19.0 deprecated `detect` and `protect`. They still work and are hidden from `--help`.
- Three scanning modes exist: `git`, `dir`, `stdin`.
- `--staged` and `--pre-commit` are flags on the `git` subcommand, not global flags.
  From `cmd/git.go`: `--staged` is "scan staged commits (good for pre-commit)" and
  `--pre-commit` is "scan using git diff". Either flag routes to `NewGitDiffCmdContext`.
- The project's own `.pre-commit-hooks.yaml` entry is:
  `gitleaks git --pre-commit --redact --staged --verbose`
- `--redact` is a global flag accepting an optional percentage (`--redact=20`), defaulting to 100.
- gitleaks is MIT licensed. The README states it is feature complete, security patches only.

### plugin code (confirmed against `scanner.py` 2026-07-28)

- **All** gitleaks invocations route through `_run_gitleaks` (`scanner.py:97`). Two call sites:
  `scan_repo` full-history (`:201-205`, uses `detect`) and staged (`:251-256`, uses `protect --staged`).
  Nothing shells out from `hook_installer.py` or `repo_auditor.py`. → Phase 1 has no hidden call sites.
- `_run_gitleaks` assembles `["gitleaks"] + ["--config", <path>] + args + ["--redact"]` (`:107-111`).
  **`--redact` is already applied to both call sites, including the `--report-path` JSON file.**
- Fail-closed logic is present exactly as v1.0 described: gitleaks exit code is ignored as ambiguous;
  the scan is trusted only if the `--report-path` file materialized (`:207-217`, `:262-269`).

## Command translation

`--redact` is **already appended centrally** by `_run_gitleaks:111` — it is NOT part of the args and
must NOT be added to the translation, or it will be passed twice.

| Current (deprecated) args | Replacement args |
|---|---|
| `["detect", "--report-format", "json", "--report-path", <p>]` | `["git", "--report-format", "json", "--report-path", <p>]` |
| `["protect", "--staged", "--report-format", "json", "--report-path", <p>]` | `["git", "--pre-commit", "--staged", "--report-format", "json", "--report-path", <p>]` |

`gitleaks git` scans the current working directory as a git repo when no positional target is
supplied (the code passes `cwd=cwd` to subprocess), which matches the existing `detect` behavior.
`--config` stays before the subcommand — it is a global/persistent flag and already works there.

---

## Phase 1 — Invocation update (deprecation swap)

Single pass, single commit. Only the two `args` lists in `scanner.py` change.

1. In `scan_repo` (`scanner.py:201-205`), change the args list `detect` → `git`.
2. In the staged scan (`scanner.py:251-256`), change `protect --staged` → `git --pre-commit --staged`.
3. **Do NOT touch `--redact`.** It is centrally applied at `:111`; adding it to the args doubles it.
   Item 3 in v1.0 was based on a false premise — this is now a *verification* step (see below), not
   an edit.
4. Preserve the existing fail-closed logic exactly. The scanner must continue to ignore
   gitleaks' ambiguous exit code and instead assert that the file at `--report-path`
   materialized. Do not "simplify" this into an exit-code check.
5. Add a minimum-version assertion. The `git` subcommand requires v8.19.0 or later, so a
   user on an older binary will now fail in a confusing way. `_check_gitleaks` already parses
   `gitleaks version` (`:32-50`) — extend it to compare against the required version and fail with
   an actionable message. (See open question on hard-fail vs warn.)

**Verification for Phase 1**

- Create a scratch repo, commit a fake AWS key, run a full scan. Confirm the finding is
  detected **and that the secret appears redacted in both stdout and the JSON report file**
  (this empirically closes the v1.0 concern — confirming existing behavior, not a new fix).
- Stage a fake key without committing, run the pre-commit path. Confirm the commit is blocked
  and the finding is redacted.
- Point `--config` at a deliberately malformed TOML. Confirm the scan fails closed (blocks)
  rather than reporting clean.
- Run against a repo with no findings. Confirm clean exit and no false block.
- Confirm the version assertion fires on a stubbed older version string.

---

## Phase 2 — Extract the scanner seam

The goal is that changing scanner backends becomes a config value rather than a code change.
Keep this small. It is an interface extraction, not a rewrite.

1. Define a single abstraction with the minimum surface the skill actually uses. Based on
   current behavior that is roughly: run a full-history scan, run a staged scan, report the
   backend version. Resist adding capabilities nothing calls.
2. Move the existing gitleaks calls into a `GitleaksBackend` implementation. Behavior must be
   byte-identical to Phase 1 output; this phase changes structure only. `--redact`, `--config`
   merge, and the fail-closed report-file check all move intact into the backend.
3. Add a backend selector reading from config with `gitleaks` as the default. Do not add a
   Betterleaks implementation yet. An unknown backend name should fail loudly at startup, not
   silently fall back.
4. Keep report parsing and severity logic (including the public-repo bump, `_parse_findings:128`
   / `_bump_severity`) on the far side of the seam. Those are the plugin's value and must not be
   duplicated per backend. If a backend emits a different report shape, normalization belongs
   inside that backend.

**Verification for Phase 2**

- All Phase 1 verification steps pass unchanged.
- Diff the JSON report from a Phase 1 build and a Phase 2 build against the same fixture repo.
  They should be identical.
- Confirm an invalid backend name in config produces a clear startup error.

---

## Phase 3 — Documentation alignment

1. Update SKILL.md to reflect the current commands. Remove or correct any reference to
   `detect` / `protect`.
2. Confirm the `--redact` claim in SKILL.md matches behavior (it already does; keep it honest).
3. Document the gitleaks minimum version requirement in the prerequisites.
4. Note the backend config option, marked as gitleaks-only for now.

---

## Phase 4 — Betterleaks shadow evaluation

No switch. This phase produces evidence for a later decision.

1. Add a Betterleaks backend behind the seam, opt-in only, never the default.
2. Run both backends across the org's own repositories and record findings from each.
3. Compare on three axes: findings gitleaks caught that Betterleaks missed, findings
   Betterleaks caught that gitleaks missed, and false-positive volume on real code.
4. Verify explicitly that the two-tier TOML merge in `format_loader.py` loads unmodified.
   This is the most likely place the drop-in claim breaks and the single most important
   thing this evaluation needs to answer.

**Decision gate — switch the default only if all of the following hold**

- Betterleaks is still actively maintained at the twelve-month mark (roughly February 2027)
- The license has not changed from MIT and the open-source posture has not narrowed
- The custom rule config loads without modification
- The shadow run shows a real recall gain on the org's own corpus, not just on a public benchmark
- False-positive volume has not materially increased

If any condition fails, stay on gitleaks and re-evaluate in another two quarters. Staying is a
legitimate outcome, not a failure of the evaluation.

---

## Acceptance criteria

- No deprecated gitleaks commands remain anywhere in the skill
- Secrets are redacted in every artifact the scan produces, including intermediate report files
  (already true via `:111`; Phase 1 verification confirms it empirically and a test locks it in)
- Fail-closed behavior on config load failure is preserved and covered by a test
- The deliberate fail-open in the hook (missing tooling warns rather than blocking every commit)
  is preserved and its rationale is documented in a comment
- Swapping scanner backends requires editing config, not code
- SKILL.md matches actual behavior

## Rollback

Phases 1 and 2 are independently revertable. Phase 1 carries the only real behavioral risk
(a blocked commit path that fails incorrectly), so verify the staged-scan path on a real
repository before merging.

## Assumptions and open questions

- **Verified (was assumed):** all gitleaks invocations live in `scanner.py` via `_run_gitleaks`.
  Confirmed 2026-07-28 — no hidden call sites in the hook or auditor.
- **Assumed:** no downstream consumer parses the current report format in a way that the `git`
  subcommand's output would break. `git` and `detect` emit the same finding schema, so `_parse_findings`
  should be unaffected — confirm in Phase 1 verification.
- **Open:** whether `--redact` at 100% removes enough context to make findings hard to triage.
  If so, `--redact=20` (partial value preserved for identification) is available — but note this is a
  *new* decision to widen the redact surface, separate from the migration. Decide during Phase 1
  verification rather than in advance. Default: leave at 100%.
- **Open:** whether the version assertion should hard-fail or warn-and-continue. Hard-fail is
  recommended, consistent with the fail-closed posture, but it will break any user on an old
  binary at the moment of upgrade.
- **Unverified:** the precise Betterleaks CLI surface. Phase 4 must confirm it rather than
  assume flag parity, despite the drop-in claim.
