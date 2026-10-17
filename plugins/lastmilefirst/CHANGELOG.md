# Changelog

All notable changes to the lastmilefirst plugin will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.39.0] - 2026-10-12

**After upgrading, nothing is required.** A repo whose subject is a person on your people list can now be marked approvable; until you mark one, people findings block exactly as before.

### Added

- **scan-secrets: a repo marked approvable for a people rule.** `git config --add lastmilefirst.approvable lmf-private-people` marks a repo whose subject is a person on the list, so committing to it no longer needs `--no-verify` (which also skipped the identity check and every other rule). It is not an exemption: the finding still prints, and each commit and each push needs its own approval. The marker is read from local git config only, applies only while the repo's visibility resolves to private or internal, and names people rules only; a key naming any other rule prints a warning and is ignored. Found when the first commits in a repo whose subject is a person on the people list were blocked on that name in most of its files.
- **scan-secrets: the match, grouped by term.** In a marked repo, people findings are shown with the text they matched, grouped by term with a count and up to five files per term, so a second name from the same rule shows up as its own row. The matched text comes from a second gitleaks pass that runs only the marked people rules unredacted, over both the staged diff and expanded archives such as `.docx`; secrets stay redacted. If that pass cannot produce the text, the commit blocks and nothing is approved.
- **scan-secrets: two ways to answer.** In a terminal the hook asks y/n. Without one (Claude Code, CI, an editor's git client) it blocks and prints the exact re-run, `LMF_APPROVE='<term>[,<term>]' git commit <your arguments>`, and the variable must name every term shown; a bare `1` approves nothing. The approved line names the terms, the count, and how it was answered. Under Claude Code the re-run line tells the agent to get the user's confirmation first, and an approval run that way is marked `agent: claude-code`.
- **scan-secrets: the push asks too.** The pre-push hook shows the same block for the pushed commits and asks the same way, with a `git push` re-run line. The remote's visibility is asked of GitHub on every push that carries a people finding in a marked repo, not only a first push, and a public remote ignores the marker and blocks.
- **scan-secrets: a hint in unmarked repos.** A people finding in a repo that is not marked ends with the command to mark it, so a fresh clone or a second machine (the marker is local config) does not reach for `--no-verify`.

### Changed

- **scan-secrets: a real secret is never approved past.** Any other blocking finding beside a people finding blocks without the question, with the grouped block below it and a line saying it could be approved once the other findings are fixed.

## [0.38.0] - 2026-10-09

**After upgrading, two steps on each machine you use.** Run `/run-organize-device` to see what the machine is missing against your org identity contracts, then `/run-organize-device --snapshot` to write a device manifest from what is installed there. The new skill's scripts need Python 3.11 or newer; the bootstrap installs it, and the audit says so and stops on anything older.

### Added

- **organize-device: the machine audit.** Checks whether this machine can produce the commits and pushes each org's identity contract calls for: a `gh` login for every contract's account, an SSH `Host` block for every SSH host alias with its key on disk, an `includeIf` git identity include for every org directory except the default org's (and a global identity matching the default org). Then the baseline tools, Claude Code marketplaces, plugins, and scan-secrets hooks, AWS profile names, keychain item names, the workspace layout from the workspace `CLAUDE.md` project table, and an optional network provider. Accounts, emails, and aliases are read from the contracts and never copied. Every finding is `missing` (absent, a WARNING) or `wrong` (present and disagreeing, ACTION REQUIRED), and the audit exits 0, 1, 2, or 3 accordingly.
- **organize-device: the device manifest.** The few facts with no other home (extra tools, plugins, AWS profile names, keychain item names, the network provider) live in `~/.config/lastmilefirst/device.toml` (or under `$XDG_CONFIG_HOME`). It holds names only and is optional: the audit runs on the contracts alone without it. `--snapshot` writes one from a machine, `--manifest <path>` reads one carried over, and a commented template ships with the skill.
- **organize-device: checklist and apply.** `--install` prints an ordered checklist with each step tagged `script` or `you` and writes nothing. `--install --apply` runs the `script` steps after one confirmation; from Claude that is a yes in the conversation followed by `--apply --yes`, with each clone named by `--clone`. Apply only creates: it appends a stanza or `Host` block after a backup, never edits or deletes an existing line, and leaves every login, key upload, and `wrong` fix to you with the exact text.
- **organize-device: network providers and the bootstrap.** Providers plug in through a small interface (`detect`, `audit`, `handoff`, one module each); Tailscale ships, and other providers are welcome as contributions of one module, one test file, and one table row. `scripts/bootstrap.sh` takes a machine with only `curl` to a working plugin on macOS (Homebrew) or apt-based Linux, fetched with `curl -fsSL <raw URL> | bash`, where the raw URL is `plugins/lastmilefirst/skills/organize-device/scripts/bootstrap.sh` on the marketplace repository at a release tag (the full command is in the skill), and ends with a handoff of the steps that need a browser or a secret.
- **organize-device: two floors the audit names rather than misreports.** `gh auth token --user` arrived in gh 2.40.0; an older gh (Debian bookworm's apt package is 2.23) answers `unknown flag`, which the audit and the session-start check now treat as undetermined, with a note naming the floor and the upgrade path, instead of reporting every account as not logged in. The scripts need Python 3.11 or newer: the audit and installer stop with one line below it, and the session-start check prints one WARNING a day naming the interpreter version rather than going quiet.
- **organize-device: `includeIf` is read from both user-level git files.** `~/.gitconfig` and `$XDG_CONFIG_HOME/git/config` (default `~/.config/git/config`) are both read by the audit, the session-start check, and the installer's duplicate guard, so a stanza kept in the XDG file counts and is never appended twice.
- **overwatch: device alert.** At session start, for each identity contract, a missing `gh` login for its account or a missing `includeIf` stanza for its org directory (the default org needs none) prints `ACTION REQUIRED: this machine cannot commit as <account> for <org>; run /run-organize-device`. Both probes are local and need no network. A stanza that exists but is wrong does not alert here; the full audit reports it. A clean result is cached for a day, and a failing one is checked again next session so a fixed machine stops alerting at once.

## [0.37.0] - 2026-10-09

**After upgrading, three one-time steps.** Run `/run-scan-secrets --install-hooks` again to get the pre-push hook. Run `/run-scan-secrets --update-formats` to get the PII rules. And split your names rule by hand: people on the existing `lmf-private-names` list are still treated as organization names (suppressed in private repos) until you move them to a `lmf-private-people` rule (see "Splitting an existing names list" in the scan-secrets skill).

### Added

- **scan-secrets: pre-push hook.** `--install-hooks` now installs a global pre-push hook beside the pre-commit one, and `--uninstall-hooks` removes both. The hook runs `scan_secrets.py --pre-push`, which reads the refs git passes on stdin. An existing remote branch is scanned over the pushed range only. A new remote branch (a first push) is scanned over every commit not already on a remote and also gets the audit extras: gitignore gaps and dangerous committed files as warnings, a check of the declared visibility against what GitHub reports, and GitHub's own secret-scanning and push-protection posture as a warning when the repo is public. A repo declared private or internal that GitHub reports as public blocks the push and prints both remedies. GitHub is asked about the remote being pushed to (the URL git passes the hook), and when that remote is public, public-repo rules apply whatever the declaration says. A declaration GitHub cannot confirm prints a warning. Deleted refs are skipped; unreadable hook input and a scan that did not finish block. When the clone lacks the remote commit (e.g. after a force push), the scan widens to every local commit not already on a remote rather than scanning nothing.
- **scan-secrets: five generic PII rules** in the common tier, tagged `pii` and low severity: personal-mailbox email addresses (GitHub noreply addresses are allowed), phone numbers next to a phone label or written in `+` international form, US Social Security numbers next to an SSN or tax-id label, AWS account ids next to an account label or inside an ARN, and IBAN or card numbers next to a banking label. Each needs its label nearby, so a bare ten-digit order id or a twelve-digit invoice number is not a finding. A PII finding is a WARNING that does not block in a private or internal repo, and blocks in a public one or when visibility is unknown.
- **scan-secrets: people rules.** A rule tagged `private-name` without `public-only` names a person and blocks in every repo, private ones included. `--add-format` now asks whether a term names an organization or a person and writes it to `lmf-private-names` or `lmf-private-people`; the org rules template documents both.
- **scan-secrets: `severity-<level>` rule tag.** gitleaks reports no severity, so a rule can declare one (e.g. `severity-low`); untagged rules stay MEDIUM.
- **overwatch: visibility drift alert.** At session start in a git repo with a remote and a declared visibility, a mismatch with GitHub's answer prints `ACTION REQUIRED: this repo is declared <x> but GitHub reports <y>; run /run-scan-secrets --audit`. Session start asks GitHub once and shares the answer with the public-repo check. It is cached for a day (per project, or per repo root outside a project), except an answer that disagrees with the declaration, which is asked again next session so a fixed repo stops alerting. No remote, no declaration, or no answer from `gh` is silent.
- **Codex adapter** at `adapters/codex/`, outside the marketplace plugin. Ten skills-only entry points generated from the plugin sources: a gateway, PARC, expert consultation, and read-only project, org, context, voice, signal, docs, and work reviews, with a bounded audit that reads only explicitly named roots. Editorial reviews are critique-first; a rewrite or file write needs its own authorization. Claude-only mechanisms are rewritten by exact anchor and the build fails closed on drift. Not verified in a live Codex session.

### Changed

- **scan-secrets: one visibility policy for every mode.** `apply_visibility_policy` replaces `apply_public_only` (kept as an alias for one release) and decides per finding whether it is kept and whether it blocks, by rule kind: ordinary secret, organization name (`public-only`), generic PII (`pii`), or person (`private-name` alone). The default scan, `--pre-commit`, `--pre-push`, and `--all` all go through it. A line that matches both a PII rule and a people rule is reported once, as the person. Exit code 1 now means at least one blocking finding, so a commit with only warnings goes through.
- **scan-secrets: report wording.** The summary reads "Found N blocking finding(s) and M warning(s)", WARNING rows sort last with a footnote saying they are personal data in a private repo and do not block, and `--all` shows a repo with only warnings as `clean (N warning(s))` followed by its report.
- **Shared pure helpers** extracted from five scripts (`check_identity.py`, `workspace_types.py`, `aggregator.py`, `review_claude.py`, `organize_project.py`) into `hooks/scripts/markdown_content.py`, `org_resources.py`, and `project_layout.py`, so the adapters and the plugin use one implementation. The canonical call paths keep their defaults; stricter fence, frontmatter, and marker policies are opt-in flags the adapters set. Verified unchanged by differential comparison on crafted inputs.

## [0.36.2] - 2026-10-08

### Fixed

- **overwatch: project checks fire only for a project, at its root.** The session-start CLAUDE.md check read the current directory and never asked whether it was a project, so a session in a scratch folder, in `~/Downloads`, or in a Cowork task on any folder outside the workspace got "No CLAUDE.md in this project" and a directive to present it. From a subdirectory of a real project the same check fired for the wrong directory, and the archetype check stayed silent for the same reason. Both now read the resolved project root and run only inside a project under a configured org. Git status, the workspace sweep reminder, and the workspace summary are unchanged. The docs no longer call Overwatch Claude-Code-only: hooks also load in Cowork and are ignored in Chat.

## [0.36.1] - 2026-09-28

### Fixed

- **scan-secrets: visibility can be declared per repo.** `git config lastmilefirst.visibility private` (or `public`, `internal`) is read before the `gh` lookup. The `gh` active account is machine-global, so a private repo owned by another account read as unknown and `public-only` rules applied where they should have been suppressed. Found on the first live use of the tag.

## [0.36.0] - 2026-09-28

### Added

- **workspace: client directories.** A directory inside an org can carry a `.claude-workspace` marker with `type: client`, meaning it groups the projects for one counterparty and is not a project itself. Every walker (Overwatch's workspace summary, the `--all` secret scan, todos-summary, review-org, review-claude, organize-claude, and the identity audit) descends through it, and nested projects are keyed `org/client/project` in Overwatch state. One shared loader, `hooks/scripts/workspace_types.py`, owns discovery. Layout problems (a client directory carrying its own `org.json`, one that is itself a git repo, a client inside a client) are reported from the container itself. The marker vocabulary is documented in one place, the organize-orgs skill.
- **overwatch: `update_state.py rename --from --to`.** Moves a project's state to a new key after a directory move or rename, refusing when the target already has state. Closes the gap where any rename orphaned a project's history.
- **scan-secrets: `public-only` rule tag.** A rule carrying this tag fires only in repositories whose visibility is public. Intended for names and terms that are allowed inside private repos but must never reach a public one; the terms themselves belong in the user's org rules file, never in the plugin. When visibility cannot be determined the rule fires and the output says why.
- **review-claude: `client` tier.** A CLAUDE.md in a client directory classifies as its own tier, and a nested project's chain is project, client, org. No expected-section list yet; the walk reports client files as not reviewed rather than as missing.

### Fixed

- **organize-claude:** the project-mapping check compares by path, so two clients can each hold a `docs` project; the missing-project hint uses the org's own prefix instead of a hardcoded one; `--scaffold-project` accepts a leaf name or `client/project`.
- **session-start:** Overwatch guidance lookup finds the org CLAUDE.md through the resolved context instead of assuming the parent directory is the org.
- **tests and plans:** fixtures and examples in tracked files use generic placeholders throughout.

## [0.35.0] - 2026-09-27

### Added

- **overwatch: GitHub settings cached with the posture check.** The session-start posture check now caches the repository settings that arrive in the same API response (merge methods, forking, features, Dependabot updates). They are shown in `--audit` and never alerted on.
- **scan-secrets: seven per-call checks in `--audit`.** Rulesets on the default branch and on release tags, classic branch protection, Dependabot alerts, Actions policy, workflow token, webhooks, and deploy keys. Measurements only; unknown is never reported as off.
- **scan-secrets: `--audit --propose` and `--apply`.** `--propose` lists an itemized delta with a consequence per item; `--apply <id> ...` applies exactly the ids named, reads the settings again, and prints before and after. Anything that changes who can push or merge is listed under "consider" and never in the default set.
- **scan-secrets: `--audit --github --deep`** sweeps an account's public repositories.
- **docs:** a new guide, `docs/github-hygiene-for-shared-repos.md`.
- The posture module gains 173 tests (236 in the hooks suite, up from 63).

## [0.34.2] - 2026-09-26

### Changed

- **Metadata:** author attribution in both manifests is now the GruntworkAI handle. No functional change.

## [0.34.1] - 2026-09-26

### Fixed

- **Metadata:** the plugin's repository URL and the marketplace homepage had pointed at a different repo since the first commit. Both now point at this one. No functional change.

## [0.34.0] - 2026-09-24

### Added

- **review-org.** A new skill and `/run-review-org` command: an org health review grouped by what you would do, with no score, and a read-only project roll-up from Overwatch state. Overwatch thresholds are named constants in one place.
- **review-claude: three tiers.** A symlinked CLAUDE.md is classified where it sits, an org is detected by `.claude/org.json` at any depth, `--tier` overrides the classification, and the output says how it decided.
- **review-claude: tables against disk.** Projects tables and the Project Directory Mapping are compared against the directories on disk, and the output names which tiers carry overlapping topics so Claude can read those pairs for contradictions.

### Changed

- **review-project** reviews the project's own CLAUDE.md and records it at project scope, so the project and org health reviews are symmetric.
- The top CLAUDE.md tier is called the workspace tier in user-facing text; `--tier user` remains an alias.
- The README's tiered CLAUDE.md section names who reads each tier, the question it answers, and the test for where a fact goes. Each template carries the same in a comment block.
- Manifest descriptions match the README framing.

## [0.33.0] - 2026-09-24

### Added

- **review-voice: three kinds of rule.** Fingerprints (measured by density), house rules (the author's own, one instance is a finding), and obligation checks (tagline fragments, unfulfilled specificity, audience address; one instance is a finding).
- **review-voice: two new tells.** Session vocabulary (extracted across documents) and heading register (measured by variance).
- **review-voice: layered house rules.** Standing rules, then an engagement voice sheet at `.claude/work/voice-sheet.md`, then the conversation. Pattern sweeps run with a headings pass and metaphor families, and rulings accrete when the author confirms them. `voice-sheet-example.md` ships as example and template.
- **review-voice:** hand-run tests and reconstructed fixtures under `skills/review-voice/tests/`.

### Changed

- **One verdict across review-signal, review-voice, and Ripley:** tiered findings and ship / hold / rework. The X/16 and X/N scores are gone.
- Verification after a rewrite runs the full pass again.

## [0.31.0] - 2026-09-08

### Added

- **parc: entry points and posture.** A handed draft enters at Review directly; discovery is the first move of Plan and the proposal precedes the artifact; the five elements are Plan's completeness test in both directions; "no PARC" is the escape hatch. PARC now applies at every scale, one exchange to a multi-agent build, and every cycle closes on Compound with a one-line ceiling when nothing was found.
- **parc: the Compound close.** Three questions in a fixed order (applied, rhymes, new), a fork table routing a learning by kind rather than by escalation, two named tests (skill or context, operative or project), rhyming lessons as the promotion signal, and a human rung (predict, mechanics, rationale) with `ce-explain` preferred and a three-question fallback in chat.
- **strict-parc:** the final gate requires the Compound close and the human rung.
- **add-wisdom, add-knowledge:** rhyme check before every write. Entries carry `Last applied`, `Rhymes with`, `Promoted to`.
- **search-wisdom:** shows the ledger, serves the Compound close's applied and rhymes queries, and marks entries applied (`--applied`, `--never-applied`, `--applied-before`).
- **overwatch:** counts compound actions per week beside skill invocations, warns when five sessions closed a cycle with nothing compounded, and nudges once per session at turn end when a closing skill ran without a compound skill.

### Fixed

- **overwatch:** the invocation log recorded only the tool kind ("skill" or "agent"), so the weekly "Top:" line never named a real skill. The hook now reads the payload and logs skill name and session id. Legacy lines still parse.

## [0.30.0] - 2026-09-04

### Added

- **review-voice: fingerprint 10, negative-universal setups.** "Nobody does X" / "no one ever" as a framing or opening move, measured per thousand words like the universal-quantifier row and tagged author-calibrated (one essay-series draft carried seven). Single instances stay non-findings. Rewrite guidance: recast with the specific actor, state what happens instead, or name the absence directly.

## [0.29.0] - 2026-09-04

### Added

- **review-voice: house rules.** A second kind of rule alongside fingerprints. House rules are the author's own hard rules (retired phrases, banned constructions), supplied by the author, where one instance is a finding. The skill reads them from the user-level `CLAUDE.md` Voice section, then from the conversation, and otherwise asks. It ships with an example list only. Literal use is exempt (a load-bearing wall). Reported in their own table, never de-duped against fingerprints.
- **review-voice: five author-calibrated fingerprints**, extracted by diffing an author's hand edits against machine drafts: in-clause balanced antithesis as the default contrast shape (1b), universal-quantifier inflation (6), canon-speak definite articles for systems that do not exist yet (7), wit-personification of components (8), and emphasis tags after the semantic landing (9). All density-measured; single instances stay non-findings.
- **review-voice: rewrite guidance** for plain functional subjects over coined compressions, dissolving repeated colon-led feature lists, sizing claims to reality, and contrast as a trailing parenthetical. New guard: homely abbreviations (i.e., e.g., aka) and parenthetical variation are voice, not informality to clean.

### Changed

- **review-voice** prose brought into line with the rules it enforces. The author's-voice exemption now uses a neutral worked example instead of citing a persona's idiolect.
- **Ripley** no longer speaks in "earns its keep," "earns its place," or "load-bearing." Her idiolect is the rent vocabulary that is literal for her (RENT, pay rent, collect the rent, reader cost). Her dual-review protocol gains a step applying the author's house rules as single-instance findings.
- **review-signal** drops two "earn its place / keep" phrasings for rent vocabulary.

## [0.28.1] - 2026-08-31

**After upgrading,** run `/run-scan-secrets --update-formats`; this release changes the rule file.

### Fixed

- **scan-secrets: connection-string rules get an allowlist.** `lmf-postgres-connection-string` and its mysql, mongodb, and redis siblings shipped without one, so the standard local test database (`postgres://postgres:postgres@localhost/...`) matched wherever it appeared. They now carry the fixture-path allowlist the sibling rules already had, plus a shared exclusion for dummy credentials against local hosts.
- **scan-secrets: `lmf-hardcoded-password` stays inside one string.** The value pattern `[^"']{8,}` was not confined to the string that opened it, so a shell prompt such as `sudo -p "Enter your Mac login password: "` was read forward to the next quote and reported as a credential. It is now `[^"'\s]{8,}`, since real hardcoded passwords rarely contain spaces and prompt strings usually do.
- Measured on a 28-repo sweep, findings went from 93 to 45 and the one real finding (a webhook URL in a public repo) still fires. Global test-path allowlisting was considered and rejected, because it would also suppress the provider-key rules inside test directories. 18 new tests, each suppression case paired with one that must still fire.

## [0.28.0] - 2026-08-31

### Added

- **scan-secrets: GitHub secret-scanning posture check.** Alongside the content scan, the plugin now checks whether GitHub's own secret scanning (which notifies the issuing vendor) and push protection (which blocks server-side, where `--no-verify` cannot reach) are on for public repositories. Session start raises ACTION REQUIRED when the current public repo is missing a protection, with the command to fix it; `--audit` shows the full posture beside the visibility line; `--all` makes an account-wide pass over every public repo, including ones not cloned locally.
- One `gh api` call returns visibility and posture together, replacing the call already being made, so session start gets no slower; the result is cached per project for 24 hours. A missing security block (callers without admin) is treated as unknown and stays silent, private repos are skipped before any API call, and nothing is enabled automatically. Accounts for the `--all` pass come from each org's identity contract, and `gh auth switch` is never called. 16 new tests.

## [0.27.1] - 2026-08-18

### Fixed

- **Quieter pre-commit output.** A correct commit printed a five-line `gh` account advisory and a `Fix:` block, and would have done so on every commit in an org whose GitHub account was not the active one. The pre-commit hook now skips the `gh` probe, so a clean commit prints only the secret-scan line. `audit_identity.py` and the plain `check_identity.py` CLI still report it, and blocking behavior is unchanged. No hook reinstall needed; the 0.27.0 dispatcher reads the check scripts from disk at run time.

## [0.27.0] - 2026-08-18

**After upgrading,** run `/reload-plugins`, then `/run-scan-secrets --install-hooks` to pick up the dispatcher. Existing orgs without an `identity` block will block commits once the hook is reinstalled; add a contract, or set `enforcement: warn` while rolling in.

### Added

- **Per-org identity contracts.** An `identity` block in `<org>/.claude/org.json` (`github_account`, `git_user_name`, `git_email`, `owns_remotes`, optional `ssh_host_alias`, and `enforcement` of `block`, `warn`, or `off`) declares which GitHub account commits in that org, mirrored in prose in the org's `CLAUDE.md`.
- **Pre-commit enforcement** (`check_identity.py`). The global hook is now a dispatcher that runs registered checks cheapest first: identity, then the secret scan.
- **Workspace audit** (`audit_identity.py`), run via `/run-organize-orgs`: contract presence, well-formedness, GitHub account liveness, per-repo drift, prose and JSON agreement, and unregistered orgs.
- **overwatch:** session start reports a missing contract before anything is staged.
- `.claude-workspace` type markers (`external`, `scratch`) exempt directories from identity obligations.
- Orgs may decline operatives or stack-wisdom repos with `{"enabled": false}` instead of being warned about them every session.
- Escape hatches: `enforcement` per contract, and `LMF_IDENTITY_OVERRIDE=1` for one-offs, which is logged.

### Notes

- The directory is the governance signal, not the remote. `owns_remotes` is a claim registry rather than an allowlist: an unclaimed owner passes, and only an owner claimed by a different GitHub account blocks, so collaborating on another owner's repo, a fork's `upstream`, and client-owned repos stay silent. Claims key on GitHub account, so two orgs sharing one account do not conflict. Commit identity blocks; `gh`'s active account is advisory only.

## [0.26.0] - 2026-08-15

### Changed

- **organize-project: archetype-aware doc migration.** The root-to-`docs/` migration is skipped for Referenceable projects, where root markdown may be the content the repo exists to hold. Work and debt patterns (`SESSION_`, `TODO_`, `PLAN_`, and the debt prefixes) still apply, and every other archetype, or no archetype, is unchanged.
- Files left in place are reported, even when nothing else moves, and are excluded from the scattered-file counts.
- The README now documents project archetypes, and the Project Structure section shows a filled-in example and a table of what belongs where.

## [0.25.0] - 2026-08-14

### Fixed

- **scan-secrets: shipped rules sync automatically.** Scans read the installed rule file, and seeding only copied it on first run, so a plugin update delivered new rules that never took effect until someone ran `--update-formats`. The installed common tier is now refreshed whenever it differs from what the plugin ships, and the run prints a one-time note when it does. The org tier is user-owned and never overwritten. `--update-formats` still works and is rarely needed.

## [0.24.0] - 2026-08-14

**After upgrading,** the first session shows ACTION REQUIRED because no workspace sweep is on record and the ruleset changed with 0.22.0 and 0.23.0. Run `/run-scan-secrets --all` once to set the baseline.

### Added

- **scan-secrets: workspace sweep timestamp.** `--all` records a workspace-scoped timestamp, so "the whole workspace was swept" can be expressed.
- **scan-secrets: ruleset fingerprint.** Scans record a fingerprint of the ruleset used (installed formats plus plugin version, since scanner behavior can change without any rule changing).
- **overwatch: stale sweep alert.** Session start raises ACTION REQUIRED when no sweep is on record or the ruleset changed since the last one, and a WARNING after 14 days. It is not gated on being inside a project; a recent sweep with the same ruleset is silent.

## [0.23.0] - 2026-08-13

### Added

- **scan-secrets: committed archives are inspected.** Zip, tar, gzip, bzip2, and xz archives (which include Terraform plan files, jars, wheels, npm packs, and office documents) are expanded to a temp directory and scanned with the same merged ruleset, in full and staged scans alike. Findings read `<archive> -> <member>`. An archive that cannot be expanded is reported as `lmf-unscannable-archive` rather than skipped.
- Guardrails: archives over 100MB or with more than 2000 members are reported rather than expanded, member paths are flattened so nothing is written outside the temp directory, and extraction failures are reported without aborting the scan.

## [0.22.0] - 2026-08-12

**After upgrading,** run `/run-scan-secrets --update-formats`, then `/reload-plugins`; without it the new rules are not active.

### Added

- **scan-secrets: LLM vendor API keys.** Seven prefix-anchored rules for Anthropic (`sk-ant-api03-`, `sk-ant-admin01-`), OpenAI (legacy 48-character, `sk-proj-`, `sk-svcacct-`), HuggingFace, Groq, OpenRouter, and Replicate. Neither gitleaks defaults nor the custom rules covered these before. Google AI keys are already covered by gitleaks' built-in `gcp-api-key`.
- Rule authors: gitleaks compiles with Go's RE2, which has no lookahead, and a `(?!...)` panics at config load and takes every rule with it. Run a real scan after any regex change.

## [0.21.0] - 2026-08-01

**After upgrading,** run `/reload-plugins`; the running session keeps the old matcher until you do.

### Added

- **review-claude: gotchas split by audience.** Deployable projects expect `## Dev Gotchas` and `## Deployment Gotchas`, Usable projects `## Dev Gotchas` and `## Usage Gotchas`, and Referenceable projects `## Gotchas`. An undivided `## Gotchas` still satisfies both halves. New scaffolds use a `| Issue | Symptom | Cause / fix |` table.
- **review-claude:** a short alias list for real renames (e.g. `## Common Pitfalls to Avoid` for Gotchas), reported and counted separately from direct matches.
- First tests for `review-claude` (23), and the repo documents its own dev and test setup.

### Changed

- A placement rule in `organize-claude`, with qualifications in `add-wisdom`, `add-knowledge`, and `parc`, settles where gotchas belong (stack-wisdom, stack-knowledge, or project CLAUDE.md).

### Fixed

- **review-claude: match headings, not raw file text.** Section presence was a substring test over the whole file, so prose mentions, fenced code, and a scaffold's YAML frontmatter counted as sections, and an empty scaffolded project reported every section present. Matching now runs against extracted ATX headings with the same substring leniency (heading level is not significant). Open follow-ups: #10, #12, #13.

## [0.20.0] - 2026-07-28

**After upgrading,** run `/run-scan-secrets --update-formats`; scans read the installed formats file and keep the old rule until you do.

### Fixed

- **scan-secrets: committed tfstate flagged once per file.** `lmf-terraform-state` matched `.+`, so every line of a committed `terraform.tfstate` became its own finding, and because gitleaks dedupes per location it also hid the default rules on those lines. It now matches the `"terraform_version":` header key, which appears once per file. On a repo with two state files, findings went from 6,003 to 21 with no real findings lost.

## [0.19.0] - 2026-07-28

### Changed

- **scan-secrets: gitleaks verbs modernized.** `gitleaks detect` becomes `git`, and `protect --staged` becomes `git --pre-commit --staged`, since the old verbs were deprecated in gitleaks 8.19.0. gitleaks 8.19.0 or newer is now required, failing closed with an actionable message.

### Fixed

- **scan-secrets: default rules run too.** The merged config now sets `[extend] useDefault = true`, so gitleaks' built-in rules (AWS keys, GitHub PATs, Stripe and Google keys, and others) run in addition to the custom `lmf-*` formats. Previously only the custom rules loaded. Verified against gitleaks 8.30.1. A non-gitleaks backend is tracked in #7. See PR #8.

## [0.18.0] - 2026-07-27

### Added

- **review-voice.** A new skill and `run-review-voice` command that detects the tells that make prose read as AI-generated and rewrites toward an authentic human voice: a two-tier tell taxonomy, presence and variance detection, and guards against false positives. Gated by default, with `LFG` for one shot. Grounded in published research on AI-generated text.
- **Ripley:** the persona and agent gain AI-tell expertise and a dual-review protocol that runs the signal and voice lenses, settles conflicts, and returns one reconciled result.

### Changed

- **review-signal:** the default is now gated (critique first, rewrite on authorization); `LFG` keeps the old one-shot path. Also fixes a contradiction between the critique and rewrite defaults. See PR #6.

## [0.17.0] - 2026-07-19

**After upgrading,** run `/plugin update lastmilefirst`, then `/run-scan-secrets --install-hooks` if you also want the 0.16.1 hook fix redeployed.

### Added

- **overwatch: network-based plugin-update check.** Overwatch reads the version `/plugin update` would resolve (the upstream marketplace manifest on the repo's default branch) and alerts when it is newer than what is installed, even when Claude Code's local marketplace cache is stale. The refresh runs at most once a day off the hot path, works offline, and skips silently on failure. Alerts clear themselves once acted on. Coverage is GitHub-sourced marketplaces with a version discoverable in the repo; others fall back to the local comparison. All requests go to raw.githubusercontent.com, and nothing fetched is executed. 45 offline tests.

## [0.16.1] - 2026-07-18

### Fixed

- **scan-secrets: the pre-commit hook survives a marketplace rename.** The hook hard-coded the marketplace name in its search path for the scanner, so after the rename to `gruntwork-lastmilefirst` a reinstall could silently disarm it (skip the scan and exit 0). It now globs the marketplace name and version within the `gruntwork-*` namespace, so no unrelated marketplace can supply the scanner it runs, and prefers the newest installed version.

**After upgrading:** `/plugin update lastmilefirst`, then `/run-scan-secrets --install-hooks` to redeploy the hook.

## [0.16.0] - 2026-07-13

### Changed

- **Marketplace renamed** `gruntwork-marketplace` → `gruntwork-lastmilefirst`, adopting the one-purpose-driven-marketplace-per-plugin model. The GitHub repo was renamed (old URL redirects), the marketplace `name` field and plugin key (`lastmilefirst@gruntwork-lastmilefirst`) changed, and all hardcoded cache/runtime paths in the plugin's scripts, skills, and commands now resolve under `gruntwork-lastmilefirst`. Rename only — no feature or behavior changes.
  - **Action required:** re-add the marketplace once (`/plugin marketplace remove gruntwork-marketplace` → `/plugin marketplace add GruntworkAI/gruntwork-lastmilefirst` → `/plugin install lastmilefirst@gruntwork-lastmilefirst`). See `RELEASE-NOTES-0.16.0.md`.

## [0.15.0] - 2026-05-21

### Added

#### Three new Key Hire experts (roster grows 13 → 16)

- **Ripley the Rent Collector** (`ripley`) — Reviewer and Anti-Slop Specialist. Editorial quality, signal density, voice-preserving rewrite. Reviews README/CLAUDE.md/docs/PRD/prompt/AI-output for low-signal writing using the RENT framework (Relevance, Evidence, Newness, Traction). New skill `review-signal`, agent `consult-ripley`, command `/run-review-signal`. Fills the previously-uncovered gap between Shannon (context placement), Reese (source validation), and per-domain review skills.

- **McBain the Senior Partner (TMT)** (`mcbain`) — Pre-delivery review of TMT (tech/media/telecom) engagement materials. Reads decks/primers/reference files as a set; flags cross-artifact drift, version-discipline defects, sector-credibility tells (wrong FCC docket numbers, ARPU charts mixing service and equipment revenue, "5G" labels on LTE-A data, etc.), and engagement-shape gaps. New skill `review-deliverable`, agent `consult-mcbain`, command `/run-review-deliverable`. Sector-narrow by design; redirects non-TMT engagements to sector-appropriate experts.

- **Pam F the PMF Guru** (`pam`) — Product-market-fit discipline distilled from the YC seed-stage canon (Michael Seibel's pitch guide and product talk). Direct, blunt, allergic to founder-speak. Scores Frequency × Intensity × Willingness to Pay on a 1–4 scale; returns Real-PMF / Possible-PMF / No-PMF-yet verdict with one concrete actionable next step. New skill `review-pmf`, agent `consult-pam`, command `/run-review-pmf`.

#### Designed pairings

- **Ripley ↔ `review-claude`**: Ripley reads the prose; `review-claude` decides what belongs and where. Run `review-claude` first for structure, then Ripley for language.
- **McBain ↔ Pam F**: Same artifact, two reads. McBain reads how the board/counterparty sees it; Pam reads how the market sees it. Often opposite verdicts — the disagreement is the value.

#### `audit-plugin` skill and `/run-audit-plugin` command
Wrapper around [Griffith](https://github.com/GruntworkAI/gruntwork-griffith) for plugin evaluation. Shells out to `griffith analyze <source> --json`, parses the result, and renders a markdown summary in the Claude session.
  - Accepts git URLs, `owner/repo` GitHub shorthand, and local paths — supports both pre-install vetting and post-install re-audit
  - `--strict` flag passes through to enable broader (noisier) security rules
  - `--json` flag emits raw Griffith JSON for scripting / comparison
  - Auto-discovers `griffith` binary: PATH first, then `~/Code/gruntwork/gruntwork-griffith/.venv/bin/griffith` dev fallback; clear install instructions if neither
  - Escapes untrusted plugin content (names, paths, finding text) in code fences to prevent prompt injection into the surrounding Claude session
  - Validates `schema_version` before rendering; warns on unknown versions
  - Renders risk-level banner, inventory table, severity breakdown, footprint + efficiency rating, architecture pattern + recommendations, and findings detail grouped by severity (cap 10 per group)

## [0.14.2] - 2026-05-17

Four-bug fix batch from the 2026-05-17 workspace audit. Three shipped fixes covering Overwatch freshness noise and `scan-secrets` reliability; one closed as not-a-bug.

### Fixed

- **Overwatch freshness alerts ignored project activity** — `session_start.check_workspace_summary` flagged repos as "never reviewed" and "stale scan" regardless of whether any commits had landed since the last action. New `_get_last_commit_ts()` helper shells to `git log -1 --format=%ct` (~3ms per project, ~70ms across current workspace) and gates "never X" alerts on commit history and "stale X" alerts on activity since last action. Workspace summary went from "22/23 need review | 22/23 need secret scan" to "21/23 need review" post-fix; the secret-scan line disappeared entirely because activity-gating suppressed all post-scan repos.

- **`scan-secrets` produced unactionable findings in vendor/build directories** — `format_loader.write_merged_config()` now injects a top-level `[allowlist]` paths block excluding `node_modules/`, `.venv/`, `venv/`, `vendor/`, `dist/`, `build/`, `.next/`, `.terraform/`, `target/`. Plugin consumers can't remediate vendor and build content; flagging it was pure noise. Hand-verified: `unstacker` dropped from 26 findings to clean (all was `node_modules`).

- **`scan-secrets` self-matched on its own rule data files** — the same `format_loader` fix excludes the plugin's own `scan-secrets/data/*.toml` rule definitions from scanning. Marketplace repo scan dropped from 3 self-match findings to 2 legitimate meta-discussion findings.

- **`scan-secrets --all` left per-project Overwatch state unset** — `scanner.scan_workspace()` previously wrote only a single global `last_secret_scan` timestamp, so Overwatch reported every just-scanned project as "Never scanned for secrets". Now imports `update_scoped_state` and writes a per-project timestamp for every repo it scans, keyed `f"{org}/{project}"` to match Overwatch's lookup shape. Hand-verified: post-fix, "Never scanned" dropped from 18 to 1 (`splash`, which isn't a git repo).

### Closed as not-a-bug

- **`scan-secrets` apparent double-print of findings** — dual stdout/stderr output is intentional (stdout for Claude context, stderr for user terminal). The apparent duplication was an artifact of capturing with `2>&1`; not a defect.

## [0.14.1] - 2026-05-12

### Fixed
- **`scan-secrets` pre-commit hook silently no-op'd for any rule containing regex escapes** — three reinforcing bugs combined so the hook printed "No secrets detected in staged changes" while gitleaks had aborted during config load. The pre-commit secret scan provided no real defense for an unknown period.
  - `format_loader.py` now serializes string values as TOML literal strings (`'''...'''`) instead of basic strings (`"""..."""`); basic strings interpret backslash sequences, which either hard-errored on `\+` or silently mangled `\s`/`\w` in regex values.
  - `format_loader.py` now serializes dict-value sub-tables (e.g. `[rules.allowlist]`) with their contents, emitted after the parent rule's scalars/lists (per TOML ordering invariant). Previously the dict's contents were dropped entirely, so three shipped rules (`lmf-hardcoded-password`, `lmf-bearer-token-hardcoded`, `lmf-jwt-secret`) lost their test-path allowlists.
  - `scanner.py` `scan_staged` and `scan_repo` now fail-closed when the requested `--report-path` file doesn't exist after gitleaks runs. Gitleaks uses exit code 1 ambiguously for both "leaks found" and "config load failure"; report-file existence is the reliable signal that the scan actually completed.
  - Smoke-tested end-to-end: good config + fixture `oc_p1_*` token → caught (exit 1); deliberately malformed config → fail-closed with stderr surfaced (exit 1).

### Changed
- Aligned version drift across `plugin.json` (was 0.14.0), `marketplace.json` (was 0.11.1), and `README.md` (was 0.10.1) — all now `0.14.1`.

## [0.13.0] - 2026-03-24

### Added
- **Per-Project/Per-Org Overwatch State Tracking** — Overwatch now tracks review, organize, and scan timestamps independently for each project and org, replacing the old single-global-timestamp model
  - State file upgraded to v2 format with `global`, `orgs`, and `projects` scopes
  - Lazy, automatic migration from v1 — no user action needed
  - `update_state.py` rewritten with `--scope` (project/org/global) and `--key` args, auto-detects current project from CWD
  - `update_state.py status` shows current project/org/global state; `--all` shows everything tracked
  - Session start alerts are now context-aware: show project name in messages, skip project-scoped alerts when at workspace root

- **CLAUDE.md Review Tracking** — new `last_review_claude` field tracked at all three levels (user, org, project) with 30-day staleness threshold

- **Skill Overwatch Integration** — `review-project`, `organize-project`, `review-claude`, and `organize-orgs` skills now include an "Update Overwatch" step so state gets recorded after each run

### Changed
- `scan-secrets` now records `last_secret_scan` per-project instead of globally
- `session_start.py` resolves current org/project context before generating alerts
- `overwatch.py` exports new functions: `resolve_context()`, `get_scoped_state()`, `update_scoped_state()`, `update_project_state()`, `update_org_state()`
- `update_state_field()` preserved for backward compatibility (operates on global scope)

## [0.11.0] - 2026-03-06

### Added
- **Secret Scanning** - `/run-scan-secrets` for detecting secrets and credentials
  - Full git history scanning via gitleaks with custom format rules
  - `--all` mode scans entire workspace (all repos under ~/Code/)
  - `--audit` mode checks .gitignore gaps, dangerous committed files, repo visibility
  - `--audit --github` inventories all public repos across GitHub account and orgs
  - `--install-hooks` / `--uninstall-hooks` for global pre-commit hook via `core.hooksPath`
  - `--add-format` interactive flow for org-specific secret patterns
  - `--list-formats` / `--update-formats` for format library management
  - Two-tier format library: common (plugin-shipped) + org (user-managed) in `~/.claude/lastmilefirst/secret-formats/`
  - 16 custom gitleaks rules covering DB connection strings, env vars, terraform, hardcoded creds, webhooks, keys, JWT
  - All output redacted by default to prevent secondary leaks

- **Public Repo Awareness** - woven throughout the plugin
  - Every scan checks repo visibility; public repos get warning banner + severity bump
  - Pre-commit hook reminds on every commit to a public repo
  - Overwatch session start alerts when working in a public repo
  - GitHub account audit flags repos with suspicious names (internal, private, secret, config)

- **Overwatch Integration**
  - `check_secret_scan_status()` — alerts if never scanned or 7+ days stale
  - `check_repo_visibility()` — alerts when working in a public repo
  - `last_secret_scan` field in overwatch state

## [0.10.1] - 2026-02-05

### Added
- **Stack-Knowledge System** - Complement to stack-wisdom for facts and documentation
  - `search-knowledge` skill - find facts, documentation, reference material
  - `add-knowledge` skill - capture client, project, product, domain, and reference knowledge
  - Knowledge types: Client, Project, Product, Domain, Reference
  - Local storage backend (default)
  - Adapter interface for community backends (Confluence, Notion, Sharepoint)
  - `templates/knowledge-adapter.md` - contribution guide for backend adapters
  - `org.json` updated with `stack_knowledge` configuration section

- **Documentation**
  - Stack-Knowledge section in README
  - Knowledge vs Wisdom comparison table

## [0.10.0] - 2026-02-04

### Added
- **PARC Workflow** - Plan, Allocate, Review, Compound
  - Default operating mode for Claude - scales ceremony to task complexity
  - YAGNI vs YAGWYDI tension: YAGNI for features, YAGWYDI for infrastructure
  - `parc` skill documenting the workflow
  - `/run-strict-parc` command for enforced discipline with explicit gates
  - PARC tracking files in `.claude/work/parc/`

- **Org-Level Infrastructure**
  - `organize-orgs` skill - explains orgs, scaffolds infrastructure
  - Orgs as first-class concept (even "personal" is an org)
  - Recommended structure: `personal/` and `work/` orgs
  - `.claude/org.json` configuration file for each org

- **Org-Level Operatives**
  - Three-tier lookup: Project → Org → User
  - Operatives repo per org: `[org]-operatives/`
  - Updated `consult-operative` with org discovery
  - Updated `create-operative` with org-level option

- **Stack-Wisdom System**
  - Wisdom vs Knowledge distinction (patterns vs facts)
  - `search-wisdom` skill - find patterns, insights, circuit breakers
  - `add-wisdom` skill - capture hard-won lessons
  - Stack-wisdom repo per org: `[org]-stack-wisdom/`
  - Templates: `wisdom-pattern.md`, `operatives-readme.md`, `stack-wisdom-readme.md`

- **Overwatch Enhancements**
  - Org infrastructure check (missing org.json, operatives, wisdom repos)
  - Alerts at session start when org infrastructure incomplete
  - Integration with organize-orgs for remediation

- **CLAUDE.md Templates**
  - Workspace-level template includes PARC workflow
  - Org-level template includes PARC, org resources section
  - Templates scaffold PARC-by-default

- **Documentation**
  - Philosophy article link: "Last Mile First: Fast Alone, Far Together"
  - PARC Workflow section in README
  - Stack-Wisdom section in README

### Changed
- `organize-claude` now detects missing org infrastructure and suggests `organize-orgs`
- Plugin description updated to highlight PARC workflow

## [0.9.7] - 2026-02-04

### Fixed
- Windows compatibility: hooks now try `python` before `python3` for cross-platform support
- Added `run.py` launcher script for reliable Python detection across Windows/macOS/Linux

## [0.9.1] - 2026-01-29

### Fixed
- Stop hook JSON validation error (converted from prompt to command type)

## [0.9.0] - 2026-01-29

### Added
- **Cross-project todo aggregation** (`/run-todos-summary`)
  - Scans `.claude/work/todos/` across all projects in an org
  - Multiple output formats: terminal, json, compact, project
  - `--by-project` flag for project-centric view
  - State classification: urgent, blocked, active, stale
  - Overwatch integration shows urgent/blocked at session start
- Workspace configuration at `~/.claude/workspace-config.json`
  - Defines workspace root and org directories
  - Consistent terminology with organize-claude skill
- 5-minute cache for fast repeated queries

## [0.8.0] - 2026-01-29

### Changed
- **BREAKING**: Rewritten Overwatch hooks from Bash to Python for cross-platform support
- Requires Python 3.9+ (previously shell-only)
- Full Windows native support (no longer requires WSL or Git Bash)

### Added
- Cross-platform file locking (`fcntl` on Unix, `msvcrt` on Windows)
- Proper type hints throughout Python code
- UTF-8 encoding on all file operations

### Fixed
- Race condition when logging invocations (now uses file locking)
- Race condition when pruning invocation logs (now uses file locking)
- State file corruption under concurrent access

### Removed
- Bash hook scripts (replaced by Python equivalents)
  - `session-start.sh` → `session_start.py`
  - `update-state.sh` → `update_state.py`
  - `log-invocation.sh` → `log_invocation.py`
  - `check-plugin-updates.sh` (merged into `session_start.py`)
  - `usage-report.sh` (merged into `session_start.py`)

## [0.7.1] - 2026-01-28

### Fixed
- Path traversal vulnerability in operative loading (LMFA-2025-001)
- Predictable temp file location (LMFA-2025-002)
- State file race conditions with flock (LMFA-2025-003)

### Added
- SECURITY.md with formal security advisories
- Plugin update checker for all installed plugins
- Invocation tracking with weekly usage statistics

## [0.7.0] - 2026-01-27

### Added
- Initial Overwatch system with session-start hooks
- Plugin update notifications
- Uncommitted changes detection
- Stale todo reminders
- CLAUDE.md presence checks

## [0.6.0] - 2026-01-20

### Added
- Private operatives system
- Create and consult custom AI personas
- User-level and project-level operative storage

## [0.5.0] - 2026-01-15

### Added
- Public expert agents (Adam, Andor, Charles, Dino, Max, Paloma, Shannon)
- Key hire agents (Maya, Archer, Scout, Quinn, Reese, Otto)
- Scout coordinator for multi-agent orchestration

## [0.4.0] - 2026-01-10

### Added
- Review skills (review-claude, review-project, review-docs, review-work)
- Organize skills (organize-claude, organize-project)
- Get-started onboarding skill

## [0.3.0] - 2026-01-05

### Added
- Initial plugin structure
- Command routing system
- Skill execution framework
