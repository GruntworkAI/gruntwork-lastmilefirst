---
title: organize-device, a device bootstrap and audit skill, replacing the stack-wisdom setup scripts
version: 1.6
date: 2026-10-09
status: approved
type: feat
component: skills/organize-device/{SKILL.md,scripts/bootstrap.sh,scripts/audit_device.py,scripts/device_manifest.py,scripts/install_device.py,scripts/network/,tests/}, commands/run-organize-device.md, hooks/scripts/session_start.py, hooks/tests/, README.md, CHANGELOG.md; plus a cleanup PR on gruntwork-stack-wisdom/setup-scripts/
target_version: 0.38.0
refs:
  - gruntwork-stack-wisdom/setup-scripts/ (setup.sh, verify.sh, configs/, last substantive edit 2026-01-28; the thing this replaces)
  - .claude/work/plans/2026-08-17-001-feat-per-org-identity-contract-plan.md (the contracts this skill reads; the boundary with organize-orgs)
  - .claude/work/plans/2026-10-09-001-feat-pii-rules-and-pre-push-audit-plan.md (0.37.0, in flight as PR #38; this plan targets the release after it)
  - .claude/work/todos/feature-skill-environment-declarations.md (this skill needs filesystem + shell; declare it when that lands)
  - skills/organize-orgs/scripts/audit_identity.py (the Finding shape and the cheap/full split to reuse)
  - gruntwork-stack-wisdom/stack-wisdom/github-account-and-repo-hygiene.md (the private checklist whose machine-level items this automates)
---

# organize-device, a device bootstrap and audit skill, replacing the stack-wisdom setup scripts

Delta: 1.6 simplifies the write rule to two finding classes: `missing` (apply may create) and `wrong` (ACTION REQUIRED, never auto-fixed, replacement text shown); the marker-comment rewrite rule is dropped, so `--apply` only ever creates. 1.5 stated the existing-machine behavior (3.9): append-only means a wrong existing stanza is a `you` step with the replacement text, and `--apply` rewrites only files it created and marked; verification step 2 corrected to match. 1.4 closed decision 8.3 (signing is reported, not required, in v1; a `signing` field on the identity contract is the follow-up) and marks the plan approved for build. 1.3 closed decision 8.2: `--install` prints a complete checklist and writes nothing; `--install --apply` performs the deterministic steps after one confirmation. 1.2 settled the manifest location at `~/.config/lastmilefirst/device.toml` (decision 8.1 closed: it describes the device, so it lives outside any workspace) and adds how a new machine receives it. 1.1 made the network section optional and provider-based (3.4, 3.8). Tailscale is the one provider shipped in v1, off unless the manifest names it, behind a small interface that a contributor can implement for another tool. Earlier decisions stand: same plugin, not a new marketplace entry; nothing personal in the plugin; Mac and Linux both supported, Windows detected and declined; mobile SSH guide and config wizard dropped.

## 1. Problem

The new-device setup lives in `gruntwork-stack-wisdom/setup-scripts/` as a 38KB bash script, a 20KB verifier, and a JSON config. It was last substantively edited 2026-01-28 and every fact that defines a working machine today arrived after that: three GitHub accounts instead of one (2026-09-27/28), per-org identity contracts in `org.json`, SSH host aliases per account, a per-org `includeIf`, commit signing on one org, the `lastmilefirst.visibility` declaration, and two orgs the script has never heard of. The script carries one `github_username`, one SSH key, and a repo list that duplicates the project directory table in the workspace CLAUDE.md. Resurrecting it means maintaining a second copy of facts that already have homes.

The machine it would be rebuilding is also not fully right today. The `includeIf` stanza covers only `~/Code/lastmilefirst.ai/`; outsideshot repos rely on per-repo `user.email`, so a fresh clone there commits as the studio account until the fail-closed pre-commit hook blocks it. The one `includeIf` that exists points at an absolute `/Users/<login>/...` path, which will not survive a machine with a different login name. Tailscale is installed and stopped. Nothing reports any of this, because the only thing that audits identity (organize-orgs) audits contracts and repos, not whether the machine can honor them.

A new device happens about once a year. "Is this machine's plumbing right" is a weekly question. The old project answered the rare one and could not answer the common one.

## 2. What changes for the user

- A fresh Mac or Debian-family Linux box goes from nothing to a running Claude Code with the plugin installed by one curl-able script that knows nothing about any org. The script ends by saying what to do next: make one SSH key, clone the repo that holds your workspace CLAUDE.md, start Claude, run `/run-organize-device`.
- `/run-organize-device` audits the machine against the org contracts it finds on disk and a small device manifest, and prints findings with remedies in the same shape as organize-orgs: tools, GitHub logins, SSH keys and aliases, git identity includes, Claude Code plugins and hooks, AWS profile names, keychain item names, workspace layout, and, when the manifest names one, a network provider (Tailscale in v1).
- `/run-organize-device --install` prints a complete, ordered checklist from the audit's findings: every step, with the exact command, marked either `script` (deterministic, the skill can do it) or `you` (needs a browser or a secret). `--install --apply` performs the `script` steps after one confirmation and leaves the `you` steps in the printed checklist. It never writes a secret and never logs in on your behalf.
- `/run-organize-device --snapshot` writes the device manifest from the current machine, names only, so the manifest is produced rather than authored.
- Session start says ACTION REQUIRED when the machine cannot honor a contract: a declared GitHub account with no `gh` login, or an org directory with a contract and no matching git identity include.
- The stack-wisdom `setup-scripts/` directory shrinks to the one unrelated script that still lives there, plus a pointer.

## 3. Design

### 3.1 Where each fact lives, and the boundary with organize-orgs

The rule from the identity-contract work holds: a value with an authoritative home is read from there, never copied. Three homes exist already, and the skill derives everything it can from them.

| Fact | Home | How the skill uses it |
|---|---|---|
| Accounts, emails, SSH host aliases, which org is default | each org's `.claude/org.json` `identity` block | expectations for `gh` logins, SSH config, `includeIf` |
| Which org directories exist and which repos belong where | the workspace CLAUDE.md project directory table | workspace layout check; optional per-row clone offer |
| Per-repo effective identity, remote claims, visibility declaration | organize-orgs `audit_identity`, scan-secrets | not re-checked here |

organize-orgs answers "do the contracts and repos agree." organize-device answers "can this machine produce the commits and pushes the contracts call for." The two meet at `includeIf`: organize-orgs would notice the wrong author on a commit, organize-device notices the missing stanza that will cause it.

Facts with no home today get one, the device manifest (3.2). Facts the skill must never hold: key material, tokens, AWS credentials, keychain values, and any client or person name. The manifest records names of things (a profile name, a keychain item name, a tailnet name) and the plugin's checks look up presence without printing contents.

### 3.2 The device manifest

A TOML file at `~/.config/lastmilefirst/device.toml` (`$XDG_CONFIG_HOME` honored). It describes the device, not a workspace, so it lives outside every workspace: one machine may carry several workspaces and the tools, profiles, keychain items, and network provider are the same for all of them. The plugin ships a commented template and the loader, never a filled copy. The cost of living outside the seed is that a new machine does not receive it with the first clone, and three things cover that: the audit runs without a manifest at all (the contracts alone drive the identity checks, and the manifest only adds extras), `--snapshot` on the old machine produces the file to carry over, and `--audit --manifest <path>` reads one from anywhere so a copy in iCloud Drive or a USB key works before it is installed. `--install` offers to copy a `--manifest` file into place. Contents, all optional with defaults:

```toml
[workspace]
root = "~/Code"

[tools]
extra = ["uv", "poetry", "terraform", "awscli", "gitleaks", "deno", "ffmpeg"]   # beyond the baseline

[claude]
marketplaces = ["GruntworkAI/gruntwork-lastmilefirst", "GruntworkAI/gruntwork-travel-skills"]
plugins = ["lastmilefirst@gruntwork-lastmilefirst", "compound-engineering@every-marketplace"]
hooks = ["pre-commit", "pre-push"]          # scan-secrets hooks expected installed

[aws]
profiles = ["default"]                      # names only
default_profile_is = "studio"               # a label the audit repeats when a client profile is in play

[keychain]
items = ["tradecraft-acceptance"]           # names only; presence checked, value never read

[network]
provider = "none"                           # "none" (default) or a shipped provider name; v1 ships "tailscale"

[network.tailscale]                         # read only when provider = "tailscale"
tailnet = "(specify)"                       # the tailnet name tailscale status reports
ssh = true                                  # Tailscale SSH expected on this device
```

The baseline tool list (git, gh, jq, python3, node, ripgrep, claude) is in the plugin, not the manifest, because the plugin's own scripts need it. `--snapshot` fills `tools.extra`, `claude.*`, `aws.profiles`, and, if a shipped provider is detected running, `network.provider` and its table, from the live machine and leaves `keychain.items` empty with a comment, because the skill cannot know which keychain items matter.

### 3.3 The bootstrap script

`scripts/bootstrap.sh`, reachable at a tagged raw URL so a machine with only `curl` can fetch it. It is the only bash in the skill (the plugin standard for logic is Python, but Python is one of the things it installs). Steps, each idempotent:

1. Detect platform. macOS: install Homebrew if absent. Linux with `apt`: `apt-get update`. Any other Linux: stop and say which package manager it wanted. Windows (`MSYS`, `CYGWIN`, `MINGW`, or `/proc/version` mentioning Microsoft without WSL): stop with "unsupported; use WSL2 and run this inside it." WSL2 is the Linux path and is not special-cased in v1.
2. Install the baseline: git, gh, jq, python3, node, ripgrep, from one platform-keyed table at the top of the file.
3. Install Claude Code with the native installer if `claude` is absent (verify the current installer command against the docs at build time; do not copy it from the old script, which used npm).
4. `claude plugin marketplace add GruntworkAI/gruntwork-lastmilefirst` and `claude plugin install lastmilefirst@gruntwork-lastmilefirst`. Both subcommands exist in the installed CLI; confirm they run unattended before relying on them, and fall back to printing the two commands if they prompt.
5. Print the handoff: generate one ed25519 key for the default account, add it on GitHub, clone the repository that holds your workspace CLAUDE.md into the workspace root, copy your `device.toml` to `~/.config/lastmilefirst/` if you carried one over, start Claude, run `/run-organize-device`.

The script names the public marketplace and nothing else. It does not know the workspace root, the orgs, or any repo; step 5 is the only place a private seed enters, and it enters by the user's hand.

### 3.4 The audit

`scripts/audit_device.py`, reusing the `Finding` dataclass and the cheap/full split from `audit_identity.py`. Cheap findings touch only the local disk. Full findings add network liveness. Output is the same text shape as organize-orgs, or `--json`.

Checks, grouped as the report prints them:

**Platform.** OS, architecture, package manager, shell. Informational.

**Tools.** Baseline present. Each `tools.extra` present. Remedy is the platform's install command.

**GitHub logins.** For every contract's `github_account`, `gh auth token --user <account>` succeeds (that is the reliable non-interactive probe; `gh auth status --json` exposes only `hosts`). Report which account is active and remind that `gh auth switch` is machine-global. Full mode: scopes include `repo` and `workflow`; `admin:public_key` only if key upload is wanted. Remedy: `gh auth login` with the account named.

**SSH.** For every contract with `ssh_host_alias`: a `Host <alias>` block exists, `HostName github.com`, its `IdentityFile` exists on disk, `IdentitiesOnly yes`. For the default org: the plain `github.com` block authenticates as that account. Full mode: `ssh -T git@<alias>` greets the expected username. Remedy writes the missing block (3.5) or prints the keygen command.

**git identity.** For every org directory with a contract: a `[includeIf "gitdir:<org dir>/"]` stanza (trailing slash, `~`-relative, never an absolute home path) pointing at a file whose `user.name` and `user.email` equal the contract. Global `user.name`/`user.email` equal the default org's contract. Signing is reported (on or off, key path exists) and not enforced in v1; see open decision 3 in section 8. Also reported: the credential helper, and a count of remotes under non-default orgs that use HTTPS, because the keychain holds one HTTPS credential per host and those pushes will go out as whoever is cached.

**Claude Code.** `claude` version. Each manifest marketplace known, each manifest plugin enabled in `~/.claude/settings.json`. The scan-secrets global hooks installed if the manifest expects them. Plugin update freshness is Overwatch's job already and is not repeated.

**AWS.** Each manifest profile name present in `~/.aws/config` or `credentials`. Full mode: `sts get-caller-identity` on the default profile, reported as the account alias only, with the `default_profile_is` label beside it. No key material is read or printed.

**Keychain.** Each manifest item present: macOS `security find-generic-password -s <name>` with output discarded; Linux `secret-tool lookup` when available, otherwise "cannot check on this platform." Presence only.

**Network (optional).** Runs only when `network.provider` names a provider; with the default `none` the section prints one line saying no network provider is configured and how to declare one. Each provider implements the interface in 3.8. The Tailscale provider checks: installed (app bundle and CLI), CLI on PATH and matching the app (the mismatch the old `fix-tailscale-cli.sh` repaired; its remedy becomes this check's remedy text), daemon running, logged in, tailnet equals the manifest, Tailscale SSH on if expected, MagicDNS name reported. On Linux the CLI comes from the official apt repository and the checks are identical. The private details (which tailnet, ACLs, what each host is for) live in a stack-wisdom procedure the skill points at generically ("your org's stack-wisdom"), the way the hygiene checklist is referenced today.

**Workspace.** Root exists; workspace CLAUDE.md present and, if a symlink, resolving; every org directory the table names exists and carries `.claude/org.json`; every project row cloned or listed as absent. Absent rows are informational, and `--install` offers each one as a `gh repo clone` using the governing org's SSH alias URL, one confirmation per row.

### 3.5 `--install`, `--snapshot`, and what is never automated

`install_device.py` has two outputs from one plan. `--install` renders the checklist: each finding's remedy as a numbered step with its exact command, tagged `script` when the desired state is fully determined by a contract or the manifest, `you` otherwise, and in the order a person would do them (keys before aliases, logins before clones). It writes nothing, so it is safe to print, paste into notes, or hand to someone setting up a machine for you. `--install --apply` runs the `script` steps after showing the same checklist and asking once. The `script` steps are:

- packages via the platform table;
- a `~/.gitconfig-<org>` file and its `includeIf` stanza, appended to `~/.gitconfig` with a backup copy taken first, never rewriting an existing stanza;
- an SSH `Host` block appended to `~/.ssh/config`, same backup rule, pointing at a key path, and the keygen command printed if that key does not exist;
- `claude plugin marketplace add` and `claude plugin install` for manifest entries.

The `you` steps, which `--apply` never runs: every `gh auth login`, every network provider login (`tailscale up` in v1), every key upload, every `aws configure`. Those need a browser or a secret, and the skill's job is to hand over the exact command, not to hold the credential. A rerun after the human steps shows the checklist shrinking, which is the progress view.

`--snapshot` is the inverse of the audit: it writes `device.toml` from the current machine, names only, and refuses to overwrite an existing manifest without `--force`.

### 3.6 Overwatch

One cheap check in `session_start.py`, cached for a day like the posture check: for each contract, a `gh` login exists (`gh auth token --user`, local keyring only, no network) and an `includeIf` stanza exists for the org directory. Either absence prints one line: `ACTION REQUIRED: this machine cannot commit as <account> for <org>; run /run-organize-device`. The network provider and tools do not alert at session start; a stopped daemon can be deliberate and a missing optional tool is not urgent.

### 3.7 Sunsetting the old scripts

In `gruntwork-stack-wisdom/setup-scripts/`: delete `setup.sh`, `verify.sh`, `setup-mobile.sh`, `MOBILE_SSH_GUIDE_V2.md`, `config-wizard.html`, `configs/`, `check-plugin-updates.sh` (Overwatch does this), and `fix-tailscale-cli.sh` (folded into the Tailscale check). Keep `domain-transfer-preflight.sh` (2026-10-08, unrelated) and replace `README.md` with a short file saying where setup went and how to fetch the bootstrap script. Add the private Tailscale procedure to `stack-wisdom/`. The old README's prose that is still true (new key per device, OAuth not API keys, which credentials are new versus existing) moves into the SKILL.md, reworded so it names no account.

### 3.8 Network providers are pluggable

Device-to-device network security is a choice, not a given, and the people who would use this skill have made different ones: Tailscale, plain WireGuard, ZeroTier, NetBird, a Cloudflare tunnel, or nothing beyond SSH. The skill ships one provider because one is what has been run here, and it ships it behind an interface small enough that adding another is a contribution rather than a redesign.

A provider is one Python module in `scripts/network/<name>.py` exposing three functions: `detect()` returns whether the tool is present and running (used by `--snapshot`), `audit(manifest_table)` returns a list of `Finding`, and `handoff(manifest_table)` returns the login or join commands `--install` prints. The manifest table it reads is `[network.<name>]`, and the provider documents its own keys in its module docstring, which the SKILL.md renders into the provider table. `audit_device.py` dispatches on `network.provider` and knows nothing provider-specific.

The SKILL.md and the plugin README carry a short request for contributions under the provider table, naming the three functions, the test pattern (stubbed binary on PATH, one test per finding), and the rule that a provider reads names and states and never a key, token, or auth key. Contributions arrive as a pull request adding one module, one test file, and one row in the table.

### 3.9 An existing machine

A fresh device is an existing device with a long checklist; the skill is built for the existing one. The bootstrap checks before each install and adds nothing twice. The audit reports differences from what the contracts and manifest expect and ignores everything else: a tool, plugin, profile, or SSH host the manifest does not name is not a finding, and nothing is ever removed. The checklist lists only what is missing or wrong, and rerunning after each fix shows it shrink.

Every finding is one of two classes, and the class decides what `--apply` may do:

| Class | Meaning | Severity in the report | `--apply` |
|---|---|---|---|
| `missing` | the expected thing is absent (no stanza, no block, no file, no package) | WARNING | may create it, after the one confirmation |
| `wrong` | the thing exists and disagrees with the contract or manifest (absolute home path in an `includeIf`, a `Host` block pointing at a missing key, an include file with the wrong email) | ACTION REQUIRED | never; the finding carries the exact replacement text as a `you` step |

So `--apply` only ever creates. It never modifies or deletes an existing line, whoever wrote it, including files the skill itself wrote on an earlier run. Editing a file in place is where a script does damage, and a wrong setting is a louder alert than a missing one because it is producing bad commits or failed pushes right now rather than at some future clone. A machine mid-setup needs no saved state: the next run audits again and the checklist is whatever is still missing or wrong.

## 4. Units

Each unit is shippable alone and lands with its tests.

| Unit | Delivers | Tests |
|---|---|---|
| U1 | `bootstrap.sh` with the platform table, SKILL.md skeleton, `run-organize-device.md`, README row | shellcheck; a run in a fresh macOS user account on this Mac up to "claude installed"; an Ubuntu container run to the same point |
| U2 | manifest loader and template; `audit_device.py` cheap checks for platform, tools, GitHub logins, SSH, git identity; text and `--json` output | pytest against a fake `HOME` (temp ssh config, gitconfig, contracts) and a stub `gh` on PATH; one test per finding, one for the clean case |
| U3 | `--install` checklist renderer with `script`/`you` tagging and ordering; `--install --apply` for packages, includeIf files, SSH blocks, plugin adds; `--snapshot` | pytest on the renderer (ordering, tags, a checklist run writes nothing) and on the writers against temp files, asserting backups, append-only behavior, and `~`-relative paths; snapshot round-trips to a clean audit |
| U4 | Claude Code, AWS, keychain, workspace checks; the network provider interface with the Tailscale module and the `none` default; full-mode liveness probes behind `--no-liveness` | pytest with stubbed `claude`, `aws`, `security`, `tailscale` binaries; one test proving `provider = "none"` runs no provider code |
| U5 | Overwatch cheap device check with the daily cache | hooks tests in the existing pattern |
| U6 | stack-wisdom cleanup PR, private Tailscale procedure, provider table and contributions ask in SKILL.md and README, CHANGELOG, version 0.38.0, release tag | `adapters/codex/build.py --check` before tagging; `gh release create v0.38.0 --target main --latest` |

U2 is the one to build first after U1, because its audit run on this machine is the acceptance test for the whole idea (section 5).

## 5. Verification

The loop closes on the current machine before any new hardware is involved.

1. After U2, run `--audit` here. Expected findings today, in this order: outsideshot has a contract and no `includeIf`; the lastmilefirst `includeIf` path is absolute; three `gh` logins present (clean); SSH aliases present and keys on disk (clean). Anything else it reports is either a real gap or a bug, and the run decides which.
2. After U3, `--snapshot` then `--audit` again: clean except for the real gaps. `--install` prints a checklist with the missing outsideshot `includeIf` tagged `script` and the absolute-path lastmilefirst stanza tagged `you` with its replacement text; `--install --apply` closes the first, the hand edit closes the second, and the audit is clean.
3. After U4, with `provider = "tailscale"` in the manifest the network section reports installed-and-stopped here, which is correct; with the default it prints the one-line not-configured notice. AWS reports one profile labeled studio.
4. Fresh-machine pass: a new macOS user account on this Mac. Run the bootstrap from the tagged URL, do the handoff steps by hand, run `--install` and work the checklist, run `--install --apply`, run `--audit`. Count the `you` steps; the target is that every one of them needed a browser or a secret.
5. Linux pass: an Ubuntu container or Multipass VM through bootstrap and `--audit`, with no network provider declared, so the run also proves the default path.
6. The hygiene checklist's section E audit commands still agree with what the device audit reports for `gh`.

## 6. Risks

- **Writing to `~/.gitconfig` and `~/.ssh/config`.** Append-only, backup first, checklist shown before writing, and the SSH writer refuses if a `Host` block of that name already exists in any form. A wrong SSH block locks you out of a remote; a wrong git include makes wrong commits. Both are why writing needs the explicit `--apply` and a confirmation, and why `--audit` and the checklist are the defaults.
- **Probing `gh` and `claude` from scripts.** Output formats are not stable contracts. The audit uses exit codes (`gh auth token --user`) over parsed text wherever it can, and the stubs in tests pin the shapes relied on so a CLI change fails a test, not a user.
- **Unattended plugin install.** If `claude plugin install` prompts, the bootstrap prints the commands instead; this is decided at build time, not guessed.
- **Overlap with organize-orgs.** The boundary in 3.1 is stated in both SKILL.md files so a later check lands on the right side.
- **A second manifest format.** TOML matches the scan-secrets formats file. The manifest holds only facts without another home, and the template says so at the top, so the pull to copy contract values into it is resisted in the artifact itself.
- **Scope creep into dotfiles.** Shell, editor, and prompt configuration are out (section 7). The skill sets up identity, tools, and the agent, and stops.

## 7. Out of scope

Windows beyond detection and the WSL2 pointer. Dotfiles (shell, editor, prompt). Cursor settings. Moving secrets between machines (iCloud Keychain or by hand; the audit reports the names that are missing). Cloning every project repo automatically (offered per row, never bulk). The mobile SSH guide, which Remote Control made obsolete. Commit-signing enforcement (reported only; see 8.3). Any network provider beyond Tailscale; those are invited as contributions against the 3.8 interface, and a second provider arriving is also the moment to decide whether the network section wants a skill of its own (tradecraft is the likely second consumer, since a self-hosted always-on agent host needs the same checks).

## 8. Open decisions for review

1. **Manifest location.** Closed 2026-10-09: `~/.config/lastmilefirst/device.toml`. It services the whole device, so it sits outside any workspace; transfer is covered by `--snapshot`, `--manifest <path>`, and a manifest-less audit (3.2).
2. **What `--install` runs versus prints.** Closed 2026-10-09: both, split by flag. `--install` is the checklist generator and writes nothing; `--install --apply` runs the `script`-tagged steps after one confirmation. The checklist is useful on its own (notes, a second person, a machine where you do not want the skill writing), and the apply path still removes the hand errors.
3. **Commit signing as a contract field.** Closed 2026-10-09: report only in v1. The audit prints, per org, whether signing is on and which key path it uses, and flags nothing. Follow-up (its own todo, organize-orgs): add a `signing` field to the identity contract (`"signing": {"format": "ssh", "key": "~/.ssh/<name>.pub"}` or absent), after which the device audit can require it and `--apply` can write the signing lines into the org's include file. Whether an org signs is a per-org fact, so the manifest is not its home.

## Change log

- 1.6 (2026-10-09): two finding classes, `missing` and `wrong`; apply creates only; marker rule dropped.
- 1.5 (2026-10-09): existing-machine behavior stated as 3.9; marker-comment rule for rewrites; verification step 2 corrected.
- 1.4 (2026-10-09): decision 8.3 closed as report-only with a contract-field follow-up; status approved.
- 1.3 (2026-10-09): `--install` prints a tagged checklist; `--install --apply` performs the `script` steps; decision 8.2 closed.
- 1.2 (2026-10-09): manifest location closed at `~/.config/lastmilefirst/device.toml`; manifest-less audit, `--manifest <path>`, and the handoff copy step added.
- 1.1 (2026-10-09): network section made optional and provider-based; Tailscale is the one shipped provider, off by default; interface and contributions ask added as 3.8.
- 1.0 (2026-10-09): first version.
