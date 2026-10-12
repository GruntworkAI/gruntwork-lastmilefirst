---
title: A repo marked approvable for a people-rule finding: show the match, then ask
version: 1.3
date: 2026-10-12
status: planned
type: feat
component: skills/scan-secrets/scripts/{scanner.py,scan_secrets.py}, skills/scan-secrets/tests/, skills/scan-secrets/SKILL.md, CHANGELOG.md, README.md
target_version: 0.39.0
refs:
  - .claude/work/todos/feature-scan-secrets-approvable-repo.md (the spec this plan details; the "show the match, then ask" decision confirmed 2026-10-12)
  - .claude/work/plans/2026-10-09-001-feat-pii-rules-and-pre-push-audit-plan.md (the policy function and pre-push scan this extends)
  - .claude/work/todos/feature-scan-secrets-repo-local-config.md (rules that travel with a repo; a different mechanism, not touched)
  - skills/scan-secrets/tests/test_visibility_policy.py (the stand-in pattern the new tests extend)
---

# A repo marked approvable for a people-rule finding: show the match, then ask

Delta (1.3): the review's two decisions, both user-settled 2026-10-12. Under Claude Code the hook tells the agent to get the user's confirmation before re-running and marks agent-run approvals (the soft route; a hard refusal of the variable was rejected because the hook cannot tell the user's `!` command from the agent's). The push asks the same way the commit does (rejected: gating on a log line, which is per machine; reporting without asking, which is an exemption on the push path). With no gate to feed, the approvals log is dropped. Units stay at four.

Delta (1.2): the review's approved batch. The marker is read from local git config only and applies only while visibility resolves private or internal, at commit as well as push; PII rules are no longer eligible. The approval variable names the terms that were shown, a bare `1` approves nothing, a failed unredacted pass blocks without asking, and a term is the rule's capture group rather than the whole match. An unmarked repo's block says how to mark it. The audit section, push-time approval count, Overwatch notice, and full-scan label are dropped to considered-and-not-built; units renumbered, four instead of five.

Delta (1.1): review corrections. The public-remote exception on push now resolves the remote's visibility on every push, not only a ref's first push (the existing branch never ran on later pushes). The unredacted second pass runs inside both scanners, the diff scan and the archive scan, so `.docx` findings get their matched text; its enable-rule ids come from the findings, not the marker keys. The approvals log resolves the common git dir so worktrees share it.

Delta (1.0): first version, from the todo after the one open design decision was confirmed: the approval is always given against the matched text, with a tty prompt where there is one and an environment variable where there is not.

## 1. Problem

A repo whose subject is a person on the people list cannot commit. The first commit in a
campaign-website repo after the 0.37.0 names split was blocked on the candidate's surname
in every copy document and session note, and the only way through was `git commit
--no-verify`, which also skipped the identity check and every other rule, twice (once at
commit, once at push). Taking the name off the list weakens it in every other repo. A
per-repo exemption makes the finding disappear, and a second stray name from the same rule
would disappear with it.

The report also showed rule, file, and line for each of 42 findings and nothing about what
matched. The user had to trust a reading that it was the surname.

## 2. What changes for the user

- `git config --add lastmilefirst.approvable lmf-private-people` marks the repo approvable
  for that rule. Local git config, never a file in the repo. Only people rules can be
  marked; naming any other rule prints a warning and does nothing. The marker applies only
  while the repo's visibility resolves to private or internal.
- In such a repo, a commit whose only blocking findings come from approvable rules prints
  them grouped by matched term, in the clear, and asks. In a terminal the hook reads y/n.
  Under Claude Code, CI, or an editor's git client it blocks and prints the exact re-run,
  with the terms it showed in the variable: `LMF_APPROVE='<term>' git commit ...`. Under
  Claude Code that line also tells the agent to get the user's confirmation first, and the
  approval line says an agent ran it. The identity check and every other rule run as
  before.
- In a repo that is not marked, a people-rule block says how to mark it, so the next repo
  whose subject is a listed person does not reach for `--no-verify`.
- A push to a private remote shows the same block and asks the same way. A push to a
  remote GitHub reports as PUBLIC ignores the marker and blocks.
- Nothing is logged; the printed approval line beside the terms is the record.

## 3. Design

### 3.1 The marker

`approvable_rules(repo_path) -> set[str]` in `scanner.py` reads `git config --local
--get-all lastmilefirst.approvable`, lower-cased, beside `declared_visibility`. **Local
scope only**: without `--local`, one `git config --global --add` would mark every repo on
the machine approvable, and the marker is a per-repo decision. Invalid or missing is the
empty set. No new config module; the key sits next to the visibility key it resembles.

Eligibility is decided per finding, not per key: a finding is **approvable** when its
`RuleID` is in the set and `_finding_kind` returns `person`. PII rules are not eligible in
this version: `apply_visibility_policy` already makes a `pii` finding non-blocking in a
private or internal repo, and the marker only applies in those (3.5), so marking one would
change nothing. A key naming an ordinary secret rule, an organization rule, a PII rule, or
no rule in the merged config never matches, and `scan_staged` prints
`lastmilefirst.approvable names <rule>, which is not a people rule; ignored` once per such
key so the misconfiguration is visible rather than silent.

### 3.2 The matched text

`_run_gitleaks` always passes `--redact`, so every `Match` and `Secret` in the report reads
`REDACTED`. That stays for the first pass. When at least one approvable finding exists, a
second pass runs with no `--redact` and `--enable-rule <id>` for each **distinct `RuleID`
among the approvable findings from the first pass**, never the raw marker keys: those ids
are eligible by construction and exist in the merged config, whereas an unknown id makes
gitleaks abort before writing a report (`FTL Requested rule ... not found`, confirmed on
8.30.1), which would fail every commit closed. Only people rules are enabled on that pass,
so an unredacted secret never leaves gitleaks.

The second pass has to reach the same targets as the first, and findings come from two
places. `_gitleaks_report` scans the staged diff (or the pushed range); `scan_archives`
expands each staged archive (a `.docx` is a zip) into a `mkdtemp` directory, runs
`gitleaks dir` on it, rewrites `File` to `<archive> -> <member>`, and removes the directory
before returning. A later pass "over the same target" therefore cannot see archive findings,
and the plan's own example has half its findings in a `.docx`. So `_run_gitleaks` gains
`redact: bool = True` and `enable_rules: list[str] | None = None` (threaded through
`_gitleaks_report` and `scan_archives`, so the test stand-ins that monkeypatch it keep
intercepting), and each of the two scanners runs its own unredacted enable-rule pass on
its own target before cleanup, attaching `Match` to the approvable findings it already
returns. Diff findings join on `Fingerprint` (falling back to `File`, `StartLine`, `RuleID`);
archive findings join on `(File, StartLine, RuleID)`, because their `File` is rewritten
consistently and their `Fingerprint` carries a per-run temp path. The unredacted report is
written inside a `tempfile.mkdtemp()` directory and removed in a `finally`, so an
interrupted hook leaves nothing behind. Confirmed on this machine: gitleaks 8.30.1 has
`--enable-rule strings` on both the `git` and `dir` subcommands; `_check_gitleaks` gains no
new floor because the flag predates `LOG_OPTS_MIN_GITLEAKS_VERSION`.

The unredacted pass fails closed, the same stance `_gitleaks_report` takes for the first
pass. When it writes no report, or any approvable finding has no joined `Match`,
`scan_staged` blocks with today's table and one line (`could not fetch the matched text
for <rule>; nothing was approved`), skips the ask, and writes no log line. An approval is
never taken against a blank term.

### 3.3 Rendering, grouped by term

`_format_approvable(findings) -> str` renders the approvable findings only:

```
lmf-private-people in 2 files (42 lines)
  <term>     42×   .claude/work/plans/copy-review/<copy-doc>.md (21)
                   .claude/work/plans/copy-review/<copy-doc>.docx (21)
```

A finding's term is its `Secret` (gitleaks' capture group, which for the people rule is
the name alternation) when non-empty, else its `Match`; then lower-cased and
whitespace-collapsed, so a different casing of the same name is one row. `Match` alone
would carry a rule's label text along with the value. Files under a term are listed with their line counts, longest first,
capped at five with `... and N more files`. A second term is its own row. Non-approvable
findings keep today's table, printed above this block, because they are what still blocks.

### 3.4 The ask

`_approval(prompt_lines) -> tuple[bool, str]` returns `(approved, source)`:

1. `LMF_APPROVE` carries the approved terms as a comma-separated list, matched
   case-insensitively against the grouped terms: every grouped term listed gives
   `(True, "env")`; a term shown but not listed stays blocking and the block is
   reprinted; a bare `1`, empty, or `0` approves nothing. The variable is an answer to the
   specific list the blocked run printed, so a term staged between that run and the re-run
   cannot ride through unseen. Checked first, so a scripted run never touches the tty.
2. Otherwise, try `open("/dev/tty", "r+")`. If it opens, write the rendered block and
   `Approve these for this commit? [y/N] `, read one line, and return `(True, "tty")` on
   `y` or `yes`, else `(False, "tty")`. Any `OSError` means no terminal.
3. No terminal: `(False, "none")`.

The hook never asks before the block is printed, and the block is printed in full even when
`LMF_APPROVE` short-circuits the question, so the approval is always visible beside what it
approved.

**Under Claude Code the agent is the reader, so the person has to be put back in the loop
by the hook's own words** (decision settled in review 2026-10-12: the soft route, over a
hard refusal of the variable under Claude Code, because the hook cannot tell the user's
`!`-prefixed command from the agent's own run and a hard gate would move every content
round into a separate terminal). `/dev/tty` fails there (confirmed: errno 6 from the Bash
tool), so the variable is the only route. When `CLAUDECODE` is set in the hook's
environment, the re-run line reads `show the user the terms above and get their
confirmation, then re-run: LMF_APPROVE='<term>[,<term>]' git commit <your arguments>`, and
the `approved:` line carries `agent: claude-code` so an agent-run approval reads
differently from one typed by a person. The plugin's skill text, and the campaign repo's
own CLAUDE.md, state the rule in one sentence: Claude never sets `LMF_APPROVE` or
`lastmilefirst.approvable` unless the user confirmed in the conversation after the block
was shown. The permission layer treating the variable as a bypass is acceptable, not a
failure: a prompt is a human in the loop. The failure this guards against is the
opposite one, the variable passing silently.

### 3.5 Where it sits in `scan_staged`

After `apply_visibility_policy`, a new pass `apply_approvals(findings, approvable,
approved) -> (findings, approvable_subset)` sets `Blocking=False` and `Approved=True` on
each approvable finding when `approved` is true. The sequence in `scan_staged`:

1. Policy as today. If `visibility` did not resolve to PRIVATE or INTERNAL (declared
   PUBLIC, `gh` says PUBLIC, or unknown), treat the marker as absent and print `this repo
   is marked approvable for <rule>, but it is public or unconfirmed; the marker applies to
   private repos only`. Otherwise partition kept findings into `approvable` and `other`.
   Without this gate a public repo would approve a name at commit and block it at push,
   leaving a history rewrite as the only way out.
2. If `other` has a blocking finding: block with today's report, append the approvable
   block with a line `the <rule> findings above could be approved once the blocking
   findings are fixed`, and skip the ask. A real secret is never approved past.
3. Else if `approvable` is non-empty: fetch matches (3.2), render (3.3), ask (3.4). On
   approval print `approved: <rule>, terms: <t>[, <t>] (<n> findings) [tty|env]`, with
   `agent: claude-code` appended when the hook ran under Claude Code, exit 0. On refusal or no terminal print the block, the re-run line with the
   terms just shown (the hook does not know the user's arguments, so it prints
   `LMF_APPROVE='<term>[,<term>]' git commit <your arguments>`), and the warning
   `--no-verify would also skip the identity check`, exit 1.
4. Else: today's path, with one addition: when a blocking finding's kind is `person` and
   the repo is not marked for its rule, append `if this repo's subject is on the list, mark
   it approvable: git config --add lastmilefirst.approvable <rule> (the match is then shown
   and asked about on each commit)`. The marker is local config, so a fresh clone or a
   second machine meets this path first; without the line the only visible exit is
   `--no-verify` again.

`scan_repo` and `scan_workspace` do not ask and do not change; a full scan is for reading.

### 3.6 No log

There is no approvals log (decision settled in review 2026-10-12). Its only candidate
consumer was a push-time gate, and the push asks for itself (3.7); a log line is also per
machine, so it could never vouch for a commit made elsewhere. The `approved:` line printed
at commit and at push is the record, and it sits beside the terms it approved. An
append-only log is cheap to add later if a reader for it appears.

### 3.7 Pre-push

`scan_pushed` reads the same marker and asks the same way `scan_staged` does (decision
settled in review 2026-10-12: the push asks too, over gating on a log line or reporting
without asking; "show the match, then ask" applies wherever the hook can block). After the
policy and the visibility gate below, the sequence of 3.5 runs on the pushed findings: a
blocking finding from any other rule blocks without an ask; otherwise the unredacted pass
runs over the pushed range (3.2), the grouped block renders (3.3), and `_approval` asks
(3.4). The pre-push hook's stdin carries git's ref lines, and the tty prompt reads
`/dev/tty`, not stdin, so the two do not collide. The re-run line reads
`LMF_APPROVE='<term>[,<term>]' git push <your arguments>`. A commit approved at commit
time is shown and asked about again at push; that is one extra answer per push in an
approvable repo, and it means a commit made with `--no-verify`, or approved on another
machine, is never pushed on a printed line alone.

The exception is the remote. Today `scan_pushed` asks GitHub about the pushed remote only
inside its `first_push` branch; every later push resolves visibility from the declaration
alone and never asks, so a repo declared private whose remote is (or has become) public
would have the marker honored on every push after the first. So when the policy leaves at
least one approvable finding, `scan_pushed` resolves the pushed remote's visibility on
**every** push: `_fetch_github_posture(repo_path, repo=github_repo_from_url(remote_url))`,
falling back to the default repo as the first-push branch does. One `gh` call per push,
paid only in approvable repos with approvable findings. When that answer (or `visibility`)
is PUBLIC the marker is ignored and the findings block as today with one added line: `this
repo is marked approvable for <rule>, but the remote is public; the marker applies to
private remotes only`. When GitHub gives no answer, the declaration is honored and the
existing `could not confirm` warning prints.

## 4. Units

| Unit | Builds | Done when |
|---|---|---|
| U1 | `approvable_rules`, eligibility, the `redact` and `enable_rules` parameters through `_run_gitleaks`, `_gitleaks_report`, and `scan_archives`, the unredacted enable-rule pass in each with its join, `_format_approvable`, `apply_approvals` | new `test_approvable.py` covers: marker parsing (none, one, two, invalid kind warned), eligibility per finding kind, the enable-rule ids taken from findings (never marker keys), the join on fingerprint for diff findings and on file/line/rule for an archive finding (both with stand-in gitleaks), grouping by term with mixed case and the five-file cap; `test_visibility_policy.py` passes unchanged |
| U2 | `_approval` and the `scan_staged` sequence in 3.5, the Claude Code wording in 3.4 | `test_approvable.py` adds: env var carrying all shown terms (approved, source env, block printed), env var missing one shown term (blocked, block reprinted), bare `1` (blocked), tty stand-in answering y and n, no tty (blocked, re-run line with terms and `--no-verify` warning present), `CLAUDECODE` set (re-run line asks for the user's confirmation; approved line carries the agent marker), a real secret alongside an approvable finding (blocked, no ask), the unredacted pass writing no report (blocked, no ask), declared PUBLIC and unknown visibility (marker ignored, line printed, block as today), unmarked repo with a people finding (the marker hint line present), exit codes per branch |
| U3 | `scan_pushed` in 3.7 | `test_scan_pushed.py` adds: approvable findings on a private remote with no approval (blocked, grouped block and `git push` re-run line present), with the terms in the variable (allowed, approved line present), with a tty stand-in answering y and n, on a public remote on a first push and on a later push of an existing ref (both blocked with the one added line, no ask), GitHub giving no answer (declaration honored, warning printed) |
| U4 | SKILL.md section "Marking a repo approvable" beside "Splitting an existing names list", with the grouped-block example, the two ways to answer, the one-sentence rule that Claude never sets the variable or the marker without the user's confirmation after seeing the block, and a line that the variable is never exported; the same one-sentence rule added to the campaign repo's CLAUDE.md as the first consumer; CHANGELOG `Unreleased` -> `0.39.0`; README version table; the version bump across `plugin.json` and both `marketplace.json` fields; `adapters/codex/build.py --check` | docs reviewed with `/run-review-voice`; adapter check passes; `gh release create v0.39.0 --target main --latest` after merge |

U1 first. U2 and U3 depend on U1 and are independent of each other. U4 last.

## 5. Verification

- `../../.venv/bin/pytest -q skills/scan-secrets/tests/` and `hooks/tests/` green from the
  repo's documented venv, each suite on its own.
- Manual, in a scratch private repo with a throwaway people term added to the local people
  rule for the duration, then removed:
  1. Commit a file carrying the term with no marker: blocked, as today, no ask.
  2. Add the marker. Commit from Terminal: the grouped block prints, the prompt reads `n`,
     the commit is blocked; again with `y`, the commit lands with the approved line.
  3. Commit from Claude Code's Bash tool, with Bash permission prompts on rather than auto
     mode: blocked, and the re-run line tells the agent to get the user's confirmation.
     The agent shows the terms and asks; after the user's yes it re-runs with the terms
     in the variable. Record whether a permission prompt appeared on that re-run (either
     answer is acceptable) and that the approved line carries the agent marker. Then
     re-run with a bare `1`: blocked.
  4. Add a second throwaway term to the same file: two rows in the block, and a variable
     naming only one of them blocks with the block reprinted.
  5. Stage a fake AWS key beside the term: blocked, no ask, the approvable block appears
     below the secret with the "could be approved once" line.
  6. Push to a private scratch remote: blocked with the grouped block and the `git push`
     re-run line; re-run with the terms: allowed. Flip the remote to public, push a
     further commit to the existing branch: blocked with the public-remote line and no
     ask. Delete the scratch repo and remote afterwards.
- The campaign repo, with `lastmilefirst.approvable lmf-private-people` set, commits its
  next content round with the terms in `LMF_APPROVE` and no `--no-verify`, and pushes
  clean.

## 6. Risks

- **The second gitleaks pass sees unredacted matches.** Mitigated by enabling only the
  approvable rules on that pass, so a secret rule's match is never in the unredacted
  report; the temp file is unlinked as today. If a PII rule's regex can overlap a secret
  (none of the five do today), the overlap shows as PII text, which is what the user asked
  to see.
- **`/dev/tty` from a hook.** Terminal and iTerm expose it; Cursor's git client and Claude
  Code's Bash tool do not, which is the designed fallback. A tty that opens but blocks on
  read (a detached session) is bounded by the hook's own patience; no timeout is added in
  this version, and the manual step 2 confirms the prompt returns.
- **The agent as approver.** Under Claude Code the hook's reader is the agent, and no
  mechanism in a git hook can tell an agent's re-run from a person's. The soft route (3.4)
  relies on the hook's wording, the marked approval line, and the standing rule in the
  skill text and the repo's CLAUDE.md. If an agent-run approval ever lands without the
  user's confirmation in the conversation, the hard route (refuse the variable under
  Claude Code, require a hand-run commit) is the fallback and is a small change to
  `_approval`. The permission layer prompting on the variable is a help, not a problem.
- **Scope creep into exemptions.** The marker must never suppress a finding. Every branch
  that lets a commit through prints the grouped block first; U2's tests assert the block's
  presence in the output on the approved path, not only the exit code.

## 7. Out of scope

Per-term markers (the grouped block makes a second term visible without them; the
variable already names terms), PII rules as approvable (already non-blocking where the
marker applies), a hard refusal of the variable under Claude Code (the fallback named in
section 6), and any change to the pre-commit dispatcher's identity check.

Considered and not built, because the approval is already printed beside the terms at
commit and at push, and each would be cheap to add later: an approvals log, an approvals
section in `--audit`, an Overwatch session-start notice for an approvable repo, and an
`approvable` label in full-scan output.

## Change log

- 1.3 (2026-10-12): doc review round one, two decisions: soft route under Claude Code; push asks too; log dropped.
- 1.2 (2026-10-12): doc review round one, approved batch of seven: local-scope marker, private-only at commit, people rules only, terms in the variable, fail-closed second pass, capture-group terms, marker hint in unmarked repos, display-only surfaces dropped.
- 1.1 (2026-10-12): doc review round one applied: push-time visibility on every push, archive findings reach the unredacted pass, enable-rule ids from findings, common git dir for the log.
- 1.0 (2026-10-12): first version, after the "show the match, then ask" decision was confirmed.
