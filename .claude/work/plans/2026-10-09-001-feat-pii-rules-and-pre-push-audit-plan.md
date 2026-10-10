---
title: PII rules that fire in private repos, and a pre-push audit on first push
version: 1.0
date: 2026-10-09
status: planned
type: feat
component: skills/scan-secrets/scripts/{scanner.py,scan_secrets.py,hook_installer.py}, skills/scan-secrets/data/common_secret_formats.toml, skills/scan-secrets/tests/, hooks/scripts/session_start.py, hooks/tests/, skills/scan-secrets/SKILL.md, CHANGELOG.md, README.md
target_version: 0.37.0
refs:
  - .claude/work/todos/feature-pii-rules-and-pre-push-audit.md (the spec this plan details; decisions confirmed 2026-10-09)
  - .claude/work/todos/bug-scan-secrets-low-severity-rule-noise.md (the noise discipline the new rules must respect)
  - .claude/work/todos/feature-scan-secrets-repo-local-config.md (a later third tier; not touched here)
  - skills/scan-secrets/tests/test_public_only.py (the stand-in pattern U1's tests extend)
---

# PII rules that fire in private repos, and a pre-push audit on first push

Delta: first version, from the todo after the two open decisions were confirmed: generic PII findings warn in private repos and block in public ones, a people-list match blocks everywhere, and a public repo's first push reports its GitHub posture as a warning rather than a block.

## 1. Problem

The pre-commit hook scans every commit, but two things slip through it by design. The only names rule is tagged `public-only`, so in a private repo a client staff member's name, a personal email, or an AWS account id is suppressed along with the client's company name, and only the company name deserved that. And nothing runs at the moment a repo's content first leaves the machine: a first push after `gh repo create` is unaudited unless someone remembers to run the full scan by hand, which is what happened on 2026-10-09 (clean, but manual).

## 2. What changes for the user

- `/run-scan-secrets --add-format` asks whether a term names an organization or a person. Organizations stay `public-only`. People are caught in every repo.
- Committing a personal email, phone number, SSN, or AWS account id prints a WARNING in a private repo and blocks in a public one. A term from the people list blocks everywhere.
- The first `git push` to a new remote branch runs the full audit: whole-history scan, the PII rules, gitignore and dangerous-file checks, and a check that the repo's declared visibility matches GitHub's. A mismatch blocks the push. Later pushes scan only the commits being pushed.
- Session start says ACTION REQUIRED when a repo's declared visibility disagrees with what GitHub reports.

## 3. Design

### 3.1 Three rule kinds, one policy function

Today `apply_public_only` drops `public-only` findings in a private repo. It becomes `apply_visibility_policy`, which classifies every finding into one of three kinds by tag and decides two things per finding: whether it is kept, and whether it blocks.

| Kind | Tag | PUBLIC repo | PRIVATE or INTERNAL repo | Visibility unknown |
|---|---|---|---|---|
| ordinary secret | none of the below | kept, blocks | kept, blocks | kept, blocks |
| organization name | `public-only` | kept, blocks | dropped, one summary line (today's behavior) | kept, blocks, with today's note |
| generic PII | `pii` | kept, blocks | kept as WARNING, does not block | kept, blocks |
| person | `private-name` without `public-only` | kept, blocks | kept, blocks | kept, blocks |

A finding that matches both a `pii` rule and a people rule is reported once, as the people finding, and blocks. The report marks non-blocking findings with `WARNING` in the severity column, and the summary line distinguishes "N blocking finding(s)" from "N warning(s)". The exit code is 1 only when at least one blocking finding exists. `scan_repo`, `scan_staged`, `scan_workspace`, and the new `scan_pushed` all go through this one function, so the policy cannot drift between modes.

### 3.2 The people rule is user-owned data

The names themselves never enter a repo (standing rule). The existing org-tier rule `lmf-private-names` carries tags `org`, `public-only`, `private-name`; it keeps working unchanged as the organizations rule. A new org-tier rule `lmf-private-people` carries tags `org`, `private-name` and no `public-only`. `--add-format` writes to one or the other based on the new question, and the org template in `format_loader.ORG_TEMPLATE` documents both. Splitting the existing list into the two rules is a one-time hand edit of the local file, done by the user with the SKILL.md instructions, because the plugin cannot know which existing terms are people.

### 3.3 Generic PII rules, keyed to stay quiet

Five rules join `data/common_secret_formats.toml`, each tagged `pii`, with `keywords` so gitleaks prefilters and the regex only runs near a label:

- `lmf-pii-personal-email`: an address at a personal-mailbox domain (gmail, googlemail, outlook, hotmail, live, icloud, me, mac, yahoo, proton, protonmail, pm.me). Corporate domains are the org tier's business. `users.noreply.github.com` is allowlisted in the rule.
- `lmf-pii-phone`: North American and E.164 shapes, keyed on `tel`, `phone`, `mobile`, `cell`, `fax`, `whatsapp`, or a leading `+` followed by a country code. A bare ten-digit number is not a finding.
- `lmf-pii-ssn`: the US shape with separators, keyed on `ssn`, `social security`, `tax id`, `tin`.
- `lmf-pii-aws-account-id`: twelve digits keyed on `account`, `aws_account`, `arn:aws`, or `:iam::`.
- `lmf-pii-bank-identifier`: IBAN and the common card-number shapes, keyed on `iban`, `card`, `pan`, `account number`.

Severity `low` on all five, so they never outrank a secret in the report. The precision tests in `test_common_rule_precision.py` get a positive and a negative case per rule; the negatives include a ten-digit order id, a twelve-digit invoice number with no AWS keyword, a corporate email, and the GitHub noreply address.

### 3.4 The pre-push hook

`scan_secrets.py --pre-push` reads the lines git passes a pre-push hook on stdin: `<local ref> <local sha> <remote ref> <remote sha>`. For each line:

- A **deleted ref** (local sha all zeros) is skipped.
- A **new remote ref** (remote sha all zeros) is a first push: the audit covers every commit reachable from the local sha. In practice that is a new repo's whole history or a new branch's history, and the cost is paid once.
- An **existing remote ref** is scanned over `remote_sha..local_sha` only.

The content scan is `gitleaks git` with `--log-opts` carrying the range (or the single local sha for a first push), through `_run_gitleaks` with the merged config, the same report-path fail-closed check `scan_staged` uses, and the policy from 3.1. On a first push the audit also runs `repo_auditor`'s gitignore-gap and dangerous-file checks as warnings, the visibility consistency check below, and, when the repo is public, `github_protections.fetch_posture` as a WARNING block (decision 2). Confirmed on this machine: gitleaks 8.30.1 accepts `--log-opts` on the `git` subcommand. `_check_gitleaks` already pins a minimum version and gains the floor this needs for other machines **(specify in U3: the first release that shipped `--log-opts`)**.

**Visibility consistency.** `declared_visibility()` (the `lastmilefirst.visibility` git config) and `check_repo_visibility()` (what `gh repo view` reports) already exist. A declared PRIVATE against a GitHub PUBLIC blocks the push with the remedy printed (make the repo private, or change the declaration and re-run the audit as public); declared PUBLIC against GitHub PRIVATE is a WARNING; no declaration is not a finding, visibility simply resolves as it does today. `gh` missing or unauthenticated resolves to unknown, which the policy treats as public, as today.

**Dispatcher.** `hook_installer.py` grows a second registry, `PRE_PUSH_CHECKS`, with one entry (the scan, `--pre-push`), and `_render_check` takes the flag as a parameter instead of hard-coding `--pre-commit`. `build_hook_script(kind)` renders either hook from the same plugin-root glob, `CHECKS_RUN` counter, and plugin-missing warning; the pre-push dispatcher forwards its stdin to the check (`python3 "$CHECK_PATH" --pre-push < /dev/stdin` is not enough, since bash's stdin is already the hook's stdin; the dispatcher reads nothing itself and the single check inherits it). `install_hooks` writes both files, backs up both, and keeps the existing `core.hooksPath` behavior; `uninstall_hooks` removes both. `HOOK_FILE` stays as the pre-commit path for the existing tests and gains a sibling `PRE_PUSH_HOOK_FILE`.

### 3.5 Overwatch visibility drift

`session_start.py` gains `check_visibility_drift()` beside `check_secret_scan_status`: when the current directory is inside a git repo with a remote, compare `declared_visibility` with the GitHub answer and emit `ACTION REQUIRED: this repo is declared <x> but GitHub reports <y>; run /run-scan-secrets --audit` on a mismatch. The `gh` call is the latency-sensitive part, so the result is cached in Overwatch state per repo for a day, the way `github_protections` caches posture. No remote, or `gh` unavailable, is silent.

## 4. Units

| Unit | Builds | Done when |
|---|---|---|
| U1 | `apply_visibility_policy` replacing `apply_public_only` (kept as a thin alias for one release), the `Blocking` flag through `_format_findings` and every scan mode, the people-rule tag convention, `--add-format` question and `ORG_TEMPLATE` text | `test_public_only.py` passes unchanged; new `test_visibility_policy.py` covers the twelve cells of the table in 3.1 plus the overlap rule; exit codes verified per mode with stand-ins |
| U2 | The five `pii` rules in `common_secret_formats.toml`, allowlist for the noreply domain, precision tests | `test_common_rule_precision.py` has a positive and a negative per rule and passes against the real gitleaks binary (the existing tests already shell out) |
| U3 | `scan_pushed` in `scanner.py`, `--pre-push` in `scan_secrets.py`, the pre-push dispatcher in `hook_installer.py`, visibility consistency and posture warning on first push, `_check_gitleaks` version floor for `--log-opts` | `test_hook_installer.py` asserts both scripts parse, both fail closed, both are installed and removed; new `test_scan_pushed.py` covers stdin parsing (new ref, existing ref, deleted ref, several lines), the range passed to gitleaks (captured by a stand-in), the visibility mismatch block, and the first-push-only audit extras |
| U4 | `check_visibility_drift` in `session_start.py` with the daily cache | `hooks/tests/test_visibility_drift.py` covers match, mismatch both ways, no remote, `gh` unavailable, and cache hit |
| U5 | SKILL.md (rule kinds table, the blocking table from 3.1, `--pre-push`, the hand split of the names list, `--install-hooks` now installing two hooks), the repo CLAUDE.md usage gotcha "scan-secrets hook is pre-commit only" retired, README hook line and version table, CHANGELOG `Unreleased` -> `0.37.0`, the version bump across `plugin.json` and both `marketplace.json` fields per the checklist, `adapters/codex/build.py --check` | docs reviewed with `/run-review-voice`; adapter check passes; `gh release create v0.37.0 --target main --latest` after merge |

U1 and U2 are independent and can run in parallel. U3 depends on U1. U4 depends on nothing but shares `declared_visibility`, so it follows U3 to avoid two edits to the same imports. U5 last.

## 5. Verification

- `../../.venv/bin/pytest -q skills/scan-secrets/tests/ hooks/tests/` green from the repo's documented venv.
- Manual, on this machine after `--install-hooks`: in a scratch private repo with the visibility declared, commit a file containing a personal-mailbox address and see a WARNING and a successful commit; declare it public and see the block. Create an empty private GitHub repo, push, and see the first-push audit run and pass; push again and see the range scan only. Flip the GitHub visibility to public without changing the declaration, push, and see the block with the remedy. Delete the scratch repo afterwards.
- Overwatch: open a session in the mismatched scratch repo and see the ACTION REQUIRED line; fix it and see silence.
- The engagement's new code repo (private, declared private) commits and pushes unchanged after the release, with the people list installed.

## 6. Risks

- **Noise.** The `pii` rules are keyword-gated and low severity, and they only warn in private repos, so a false positive costs one line. If the phone rule still fires on build artifacts, tighten the keyword list before widening the allowlist.
- **First-push cost.** A large history scanned once. Acceptable; the alternative is the manual audit this replaces. The 300-second timeout in `_run_gitleaks` applies and reports as a blocked push with the reason.
- **The hand split of the names list.** Until the user does it, people on the existing list are still `public-only`. The SKILL.md change says so plainly and the release notes carry it as the one post-upgrade step.
- **`gh` dependence.** Both the push-time visibility check and the Overwatch alert need `gh`. Without it they resolve to unknown, treated as public, which is the safe direction and today's behavior.

## 7. Out of scope

A repo-local third config tier (its own todo), server-side push protection on private repos (paid GitHub feature), scanning content already on GitHub, and any change to the identity check in the pre-commit dispatcher.

## Change log

- 1.0 (2026-10-09): first version, after the two open decisions were confirmed.
