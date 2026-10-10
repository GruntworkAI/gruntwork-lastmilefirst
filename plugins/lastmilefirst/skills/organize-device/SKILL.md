---
name: organize-device
description: Bootstrap a new machine and audit any machine against your org identity contracts and a small device manifest - tools, GitHub logins, SSH keys and aliases, git identity, Claude Code plugins, AWS profile names, keychain item names, workspace layout, and an optional network provider
---

# Organize Device

Check whether this machine can produce the commits and pushes your orgs call for, and hand you a checklist for whatever it cannot.

## What This Skill Is For

A fresh device is an existing device with a long checklist. The skill is built for the existing one, because "is this machine's plumbing right" comes up every week and a new machine comes up about once a year. On a machine you already use, it reports what has drifted (a GitHub login that expired, an org directory with no git identity set up for it, an SSH key that moved). On a new machine, the same audit produces a much longer list, and working that list is the setup.

It answers one question: can this machine commit and push as the account each org expects? It does not change how your orgs are configured, and it does not judge the repos themselves. That is organize-orgs' job.

## Where Each Fact Lives

A value that already has an authoritative home is read from there and never copied. The skill derives almost everything from files you already keep.

| Fact | Where it lives | Which skill checks it |
|---|---|---|
| Accounts, commit emails, SSH host aliases, which org is the default | each org's `.claude/org.json`, the `identity` block (its "identity contract") | organize-device checks this machine can honor it |
| Which org directories exist and which repos belong where | the project directory table in the workspace `CLAUDE.md` | organize-device checks the layout on disk |
| Tools, plugins, AWS profile names, keychain item names, network provider | the device manifest (below) | organize-device |
| Whether each repo commits as the right identity, who owns each remote | the repos themselves | organize-orgs (`audit_identity`) and scan-secrets |

organize-orgs answers "do the contracts and repos agree." organize-device answers "can this machine produce what the contracts call for." They meet at git's `includeIf` setting, which tells git to use a different name and email for every repo under a given directory. organize-orgs notices the wrong author on a commit after the fact; organize-device notices the missing `includeIf` that will cause it.

## The Device Manifest

The manifest is a small TOML file (a plain-text settings format) at `~/.config/lastmilefirst/device.toml`. If `$XDG_CONFIG_HOME` is set, the file lives at `$XDG_CONFIG_HOME/lastmilefirst/device.toml` instead. It describes the device rather than any workspace, so it sits outside every workspace: one machine can hold several workspaces, and the tools, profiles, and network setup are the same for all of them.

It holds only facts that have no other home, and every key is optional:

| Table | Holds |
|---|---|
| `[workspace]` | `root`, the workspace directory (defaults to `~/Code`) |
| `[tools]` | `extra`, tools beyond the baseline that this machine should have |
| `[claude]` | `marketplaces`, `plugins`, and `hooks` (the scan-secrets git hooks expected installed) |
| `[aws]` | `profiles`, profile names only, and `default_profile_is`, a label the audit repeats beside the default profile |
| `[keychain]` | `items`, names of keychain entries whose presence is checked |
| `[network]` | `provider`, either `"none"` (the default) or a shipped provider name |
| `[network.<provider>]` | that provider's own keys (see Network Providers) |

The manifest never holds key material, tokens, passwords, AWS credentials, keychain values, or the name of any client or person. It also never holds a value an identity contract already declares (an account, an email, an SSH alias), because a second copy is a copy that drifts. It records names of things, and the checks look up whether those things exist without printing what is inside them.

The baseline tools (git, gh, jq, python3, node, ripgrep, and claude) are not in the manifest. They are built into the plugin, because the plugin's own scripts need them.

The plugin ships a commented template, `scripts/device_template.toml`, and never a filled copy.

An unknown table or key, or a value of the wrong type, stops the audit with exit code 3 and a message naming it, because a misspelled key would otherwise be ignored and the audit would quietly check less than you think. A missing manifest is not an error.

### Getting the manifest onto a new machine

Because the manifest lives outside your workspace, cloning your workspace does not bring it along. Three things cover that:

1. The audit runs without a manifest at all. The identity contracts alone drive the GitHub, SSH, and git identity checks; the manifest only adds the extras.
2. `--snapshot` on the old machine writes the manifest from what is installed there, so you carry over a file you did not have to write.
3. `--manifest <path>` reads a manifest from anywhere (a synced folder, a USB stick) before it is in place, and `--install` offers to copy it to `~/.config/lastmilefirst/`.

## Usage

```bash
/run-organize-device                          # audit (the default; writes nothing)
/run-organize-device --json                   # audit, machine-readable
/run-organize-device --full                   # audit plus the checks that go over the network
/run-organize-device --install                # ordered checklist; writes nothing
/run-organize-device --install --apply        # run the script steps, after your yes
/run-organize-device --snapshot [--force]     # write the manifest from this machine
/run-organize-device --manifest <path>        # read the manifest from another path
/run-organize-device --workspace-root <path>  # override the manifest's workspace root
```

The scripts behind the command:

```bash
python3 scripts/audit_device.py [--audit] [--json] [--full] [--no-liveness] [--manifest PATH] [--workspace-root PATH]
python3 scripts/install_device.py [--apply | --snapshot] [--yes] [--clone DIR_NAME]... [--force] [--manifest PATH] [--workspace-root PATH]
```

Both scripts need Python 3.11 or newer. `--audit` is accepted as another way of asking for the default audit, and `--install` the same for the default checklist. `--no-liveness` keeps `--full` off the network.

`audit_device.py` exits with one of four codes:

| Code | Meaning |
|---|---|
| 0 | clean (notes only) |
| 1 | at least one `wrong` finding (ACTION REQUIRED) |
| 2 | only `missing` findings (WARNING) |
| 3 | the audit could not run: Python older than 3.11, a manifest that is not valid, or a bad argument |

`install_device.py` exits 0 when it finished, found nothing to do, or was declined; 1 when an `--apply` step failed; and 3 when it could not run (the same three causes, plus `--snapshot` refusing to overwrite a manifest). `--yes` works only with `--apply`, `--clone` only with `--yes`, and `--force` only with `--snapshot`.

`--json` prints one object with `mode` (`cheap` or `full`), `manifest` (the path read, or null), `workspace_root`, `findings`, `summary` (counts of `wrong` and `missing`), and `exit_code`. Each finding carries `severity`, `org`, `section`, `message`, `remedy`, `you` (a step only a person can do), `class` (`missing`, `wrong`, or null for a note), and `action` (see Adding a provider).

## The Bootstrap

A machine with nothing on it but `curl` starts here. `scripts/bootstrap.sh` is published at a tagged raw URL on the public marketplace repository:

```bash
curl -fsSL https://raw.githubusercontent.com/GruntworkAI/gruntwork-lastmilefirst/<tag>/plugins/lastmilefirst/skills/organize-device/scripts/bootstrap.sh | bash
```

It also runs as a downloaded file (`bash bootstrap.sh`). It is the only shell script in the skill, because Python is one of the things it installs. In order, it:

1. Detects the platform. On macOS it installs Homebrew if it is absent. On Linux with `apt` it refreshes the package list. On any other Linux it stops and names the package manager it found. On Windows (including the older WSL1) it stops and points you to WSL2.
2. Installs the baseline tools that are missing: git, gh, jq, python3, node, ripgrep. python3 counts as present only at version 3.11 or newer, because the audit needs it. On macOS an older one is replaced by Homebrew's, which is put first on PATH; on apt-based Linux it warns, names the version it found, and leaves the upgrade to you.
3. Installs Claude Code with Anthropic's native installer if `claude` is not already on the machine.
4. Adds the lastmilefirst marketplace and installs the plugin, unless both are already there. If either command does not complete, it prints the two commands for you to run.
5. Prints the handoff.

Every step checks before it acts, so rerunning it on a set-up machine changes nothing. It knows nothing about your orgs, workspace, or accounts. The only coordinates it names are the public marketplace's.

### The handoff

The bootstrap ends by listing what needs you, in order:

1. Make one SSH key (an `ed25519` key, the current standard type) for your default GitHub account.
2. Add it on GitHub, with `gh ssh-key add` or on GitHub's SSH keys settings page.
3. Clone the repository that holds your workspace `CLAUDE.md` into your workspace root.
4. If you carried a `device.toml` over, copy it to `~/.config/lastmilefirst/`.
5. Start Claude and run `/run-organize-device`.

Step 3 is the only place anything private enters a new machine, and it enters by your hand. From there the audit reads your contracts and takes over.

### What is new on each device and what you bring

| Credential | New or existing | How it arrives |
|---|---|---|
| SSH key | new on each device | generated with `ssh-keygen`, then added to your GitHub account |
| GitHub logins | existing accounts | `gh auth login` in a browser, once per account |
| Claude login | existing account | a browser sign-in when you first start Claude; no API key is needed |
| Network provider | existing account | that provider's own sign-in, if you use one |
| AWS credentials | existing | `aws configure` or your own process; the skill checks profile names only |

## The Audit

The audit compares this machine with what the contracts and manifest expect, and ignores everything else. A tool, plugin, AWS profile, or SSH host the manifest does not name is not a finding, and nothing is ever removed. The default checks read only the local disk; `--full` adds the few that go over the network (an `ssh -T` greeting per host, a question to AWS about the default profile, and asking `claude` for its marketplaces when the file that lists them cannot be read). The report prints these sections in this order.

A few words recur below. The **default org** is the one whose contract has no `ssh_host_alias`, so its account owns the plain `github.com` host. There is a default only when exactly one account lacks an alias; two orgs sharing that one account is fine. An **includeIf stanza** is the `[includeIf "gitdir:<org dir>/"]` entry in `~/.gitconfig` that points git at a small file (an "include file," e.g. `~/.gitconfig-<org>`) holding the name and email for every repo under that directory.

**Device manifest.** Which manifest was read, or that none was found and the checks ran on the contracts alone.

**Platform.** Operating system, processor architecture, package manager, and shell, as a note. On Windows (including Cygwin, MSYS, and MinGW shells) this is one `wrong` finding pointing to WSL2, and the audit stops there because the remaining checks do not apply.

**Tools.** Each baseline tool and each `tools.extra` entry is on PATH. The remedy is `brew install <package>` or `sudo apt-get install -y <package>`, or Anthropic's installer for `claude`. With no Homebrew or apt on the machine, the remedy says so in words.

**GitHub logins.** For every account a contract names, `gh auth token --user <account>` succeeds, which shows the account is logged in without going to the network (the token itself is thrown away, never printed). A missing login's remedy is `gh auth login --hostname github.com --git-protocol ssh --web`, with a browser step telling you which account to sign in as. If `gh` does not answer in time, that account becomes a "could not check" note. The report names `gh`'s active account and reminds you that `gh auth switch` changes it for every terminal on the machine. `--full` adds nothing here.

**SSH.** For every contract with an `ssh_host_alias` (a nickname in `~/.ssh/config` that selects which key to use for GitHub): a `Host <alias>` block exists, has `HostName github.com`, points its `IdentityFile` at a key that exists on disk, and sets `IdentitiesOnly yes`. An absent block is `missing`, with the block to append and the `ssh-keygen` command for the key; a block that gets any of those wrong is `wrong`, with the whole corrected block. For the default org, a `Host github.com` block is optional; if one exists and names a key that is not on disk, that is `wrong`. More than one account without an alias is also `wrong`, because only one account can own plain `github.com`; the remedy is the alias to add to each other contract. With `--full`, `ssh -T git@<host>` must greet the expected username: no greeting is `missing`, and a greeting for a different account is `wrong`.

**git identity.** For every org directory with a contract, except the default org's, an includeIf stanza exists. An absent one is `missing`, and the remedy is the stanza plus the include file to create. One that exists is `wrong` if its `gitdir` uses an absolute home path such as `/Users/<login>/...` (which breaks on a machine with a different login name), lacks the trailing slash (`/` or `/**`), has no `path =` line, uses an absolute home path for its include file, names an include file that does not exist, or names one whose `user.name` or `user.email` differs from the contract. The default org uses your global identity instead: a global `user.name` or `user.email` that differs from its contract is `wrong`, and one that is unset is `missing`. Three notes follow, none of them flagged: commit signing per org (on or off, the format, and whether the key file exists), the credential helper, and a count of repos under non-default orgs whose origin uses HTTPS, because the keychain holds one HTTPS login per host and those pushes go out as whichever account it last cached.

**Claude Code.** The `claude --version` line, as a note. Each manifest marketplace appears in `~/.claude/plugins/known_marketplaces.json` (matched by name, repository, URL, or path). Each manifest plugin is enabled in `~/.claude/settings.json`: one that is absent is `missing` with `claude plugin install`, and one that is present but disabled is `missing` with `claude plugin enable`. For the scan-secrets git hooks the manifest expects (only `pre-commit` and `pre-push` are recognized; anything else gets a note), the hook files must be in `~/.claude/lastmilefirst/git-hooks/` and git's `core.hooksPath` setting must point there. Absent files or an unset `core.hooksPath` is `missing` with `/run-scan-secrets --install-hooks`; a `core.hooksPath` pointing somewhere else is `wrong`, because then the hooks never run. Whether plugins are up to date is Overwatch's job and is not repeated here.

**AWS.** Runs only when the manifest names profiles. Each profile name appears as a section in the AWS config or credentials file (`~/.aws/config` and `~/.aws/credentials`, or wherever `AWS_CONFIG_FILE` and `AWS_SHARED_CREDENTIALS_FILE` point). A missing profile is `missing` with `aws configure --profile <name>` as a step for you. If the `aws` command itself is absent, that is one finding rather than one per profile (and only a note if `tools.extra` already lists it, since Tools reports it). When `default` is one of the profiles and `default_profile_is` is filled in, the report repeats that label. With `--full`, the default profile is asked which account it is, and the report shows the account alias, or the account id when there is no alias. No key is read or printed.

**Keychain.** Runs only when the manifest names items. On macOS this uses `security find-generic-password -s <name>`; on Linux, `secret-tool lookup service <name>` when `secret-tool` is installed. Output is thrown away, so the value is never read. Otherwise the section is one note saying it cannot check on this platform. A missing item is `missing` with no command to run, only a step for you (adding it by hand, which prompts for the value). An answer the check does not recognize becomes a "could not check" note for that item.

**Network (optional).** Runs only when `network.provider` names a provider. With the default `"none"`, the section is one note saying no network provider is configured and how to declare one. A provider name that is not shipped is `wrong`. See Network Providers.

**Workspace.** The root exists (`wrong` if not). The workspace `CLAUDE.md` is present (`missing` if not, with a step for you to clone the repository that holds it) and, if it is a link, resolves (`wrong` if not). The skill reads the project directory table from that file; without one, the layout is not checked. Rows outside the workspace root are counted and skipped. Every org directory the table names exists (`missing` if not, with `mkdir` and a pointer to `/run-organize-orgs`) and has `.claude/org.json` (`wrong` if not). Every project row that is not on disk is `missing`, with a clone command as its remedy. The command uses the directory's own name as the repository name and the governing org's account as the owner, as `git clone git@<alias>:<owner>/<repo>.git <path>` when the org has an SSH alias and `gh repo clone <owner>/<repo> <path>` when it does not. That is a guess, so check it before running it. When no contract governs the row, the owner shows as `(specify)` and the step is yours. A row whose other cells say "removed" or "paused" is skipped with a note.

### Two kinds of finding

Every alert is one of two classes, and the class decides what `--apply` may do. Everything else is a note, which never changes the exit code.

| Class | Meaning | Label | `--apply` |
|---|---|---|---|
| `missing` | the expected thing is absent (no stanza, no SSH block, no file, no package) | WARNING | may create it, if the step is one it knows how to run |
| `wrong` | the thing exists and disagrees with the contract or manifest (an absolute home path in an includeIf stanza, a `Host` block pointing at a key that is not there, an include file with the wrong email) | ACTION REQUIRED | never; the finding shows the exact replacement text for you to put in by hand |

A wrong setting is the louder alert because it is producing bad commits or failed pushes now, while a missing one will only bite at some future clone.

## `--install`: The Checklist

`--install` turns the audit's findings into one numbered checklist in the order a person would do them: packages first, then a carried manifest, SSH keys, SSH aliases, GitHub logins, git identity, Claude Code, AWS, keychain, network, the workspace, and clones last. Each step carries its exact command and a tag:

- `script` when the right result is fully determined by a contract or the manifest, so the skill can do it;
- `you` when it needs a browser, a secret, or your judgment.

A note can carry a `you` step too (a stopped Tailscale's `tailscale up`, for example). The checklist shows it marked "(optional)", and it never counts as an alert.

`--install` writes nothing. You can print it, paste it into notes, or hand it to someone setting up a machine for you.

### Running the script steps

`--apply` runs only the `script` steps, and it only ever creates things that are `missing`:

- packages, via Homebrew or apt;
- an include file `~/.gitconfig-<org>` and its includeIf stanza, appended to `~/.gitconfig` after a backup copy is taken (if an include file of that name already exists with a different name or email, it stops and adds nothing);
- an SSH `Host` block appended to `~/.ssh/config`, same backup rule, refusing if a block of that name already exists in any form, including in files the config pulls in with `Include`;
- `claude plugin marketplace add` and `claude plugin install` for manifest entries;
- a copy of a `--manifest` file into `~/.config/lastmilefirst/`, when none is there;
- project clones, each approved on its own.

Backups sit beside the original as `<file>.bak-<date and time>`. It never modifies or deletes an existing line, whoever wrote it, including files the skill wrote on an earlier run. `wrong` findings stay in the checklist as `you` steps with their replacement text. A machine halfway through setup needs no saved state: the next run audits again, and the checklist is whatever is still missing or wrong. Rerunning after each fix and watching the list shrink is the progress view.

How the confirmation works depends on who runs it:

- **From `/run-organize-device --install --apply` (Claude runs it).** The installer's own prompt cannot be answered from Claude's shell, which has no terminal, so it reads as "no" and nothing runs. Claude instead runs the checklist (`install_device.py`), shows it to you, and asks in the conversation. After your yes, it runs `install_device.py --apply --yes`. Clones never run under `--yes` unless each one is named: Claude asks about each clone by name and adds `--clone <dir-name>` for every one you approve (the directory name, e.g. `--clone example-tool`). A clone you did not name is skipped and the output says how to run it.
- **In your own terminal.** `install_device.py --apply` without `--yes` prints the checklist, asks once, and then asks again before each clone.

### What is never automated

These are always `you` steps, and `--apply` never runs them:

- every `gh auth login`;
- every network provider sign-in (`tailscale up` for Tailscale);
- every key upload to GitHub;
- every `aws configure`.

Each one needs a browser or a secret. The skill's job is to hand you the exact command, not to hold the credential.

Three more steps are fully determined but are still left to you, because each changes an existing setting rather than creating something new: setting your global `user.name` and `user.email` with `git config --global`, `claude plugin enable` for a disabled plugin, and `/run-scan-secrets --install-hooks` (which sets git's global `core.hooksPath`, a setting other tools may own).

## `--snapshot`

`--snapshot` is the audit run backwards: it writes `device.toml` from this machine, names only. It fills:

- `workspace.root`, from `--workspace-root` if you pass one, otherwise `~/Code`;
- `tools.extra`, from a fixed list of common extras found on PATH (uv, poetry, terraform, awscli, gitleaks, deno, ffmpeg, docker, shellcheck);
- the `claude` tables, from `claude`'s own lists (falling back to its settings files), keeping only plugins that are enabled for you as a user, and the scan-secrets hooks whose files are installed;
- `aws.profiles`, from the section names in `~/.aws/config` and `~/.aws/credentials`, with `default_profile_is` left as `"(specify)"` for you to fill in;
- `network.provider` and its table, only when a shipped provider is detected running; otherwise `"none"`.

It leaves `keychain.items` empty with a comment, because the skill cannot know which keychain entries matter to you. `--manifest PATH` says where to write it (the default is `~/.config/lastmilefirst/device.toml`). It checks the file it wrote is a valid manifest before saving, and it refuses to overwrite an existing manifest unless you pass `--force`.

## Network Providers

How devices reach each other privately is a choice, and people make different ones: Tailscale, plain WireGuard, ZeroTier, NetBird, a Cloudflare tunnel, or nothing beyond SSH. The network section is optional and off by default. One provider ships, because one is what has been run so far, behind an interface small enough that adding another is a contribution rather than a redesign.

| Provider | `network.provider` | Manifest keys | What the audit checks |
|---|---|---|---|
| none (default) | `"none"` | none | nothing; prints one note saying no provider is configured |
| Tailscale | `"tailscale"` | `tailnet` (the network name `tailscale status` reports; ignored while it reads `"(specify)"`), `ssh` (true when Tailscale SSH should be on) | see below |

For Tailscale, in order:

1. **Installed.** On macOS, the app in `/Applications/Tailscale.app` or a `tailscale` command on PATH; on Linux, `tailscale` on PATH. If neither, that is `missing`, with `brew install --cask tailscale-app` on macOS or Tailscale's install script (`curl -fsSL https://tailscale.com/install.sh | sh`) on Linux, then `tailscale up` as a step for you.
2. **The command-line tool works.** On macOS with the app installed, `tailscale` must be on PATH and `tailscale version` must run. If it is not on PATH, or fails with the error that comes from a link into the app bundle, that is `wrong`, and the remedy swaps the link for Homebrew's standalone build. A version that differs from the app's is a note, since a small difference is harmless.
3. **The background service answers** `tailscale status --json`. If it is not running, that is `missing`, with a step for you (open the app on macOS, `sudo systemctl enable --now tailscaled` on Linux, then `tailscale up`).
4. **The service's state.** Running is fine. Stopped is a note carrying an optional `tailscale up`, because stopping it can be deliberate. Waiting for sign-in is `missing`, with `tailscale up` as a browser step. Waiting for approval in the tailnet is `missing`, with approval in the admin console as your step. Any other state is a note.
5. **The tailnet** matches `tailnet`, when one is declared. A different one is `wrong`, with `tailscale switch <tailnet>` (and `tailscale login` first if that tailnet is not signed in on this device yet).
6. **Tailscale SSH** is on when `ssh = true`, judged by whether the device reports SSH host keys (their contents are not read). Off while running is `missing`, with `tailscale set --ssh`; while not running it is a note.
7. **The device's MagicDNS name** (its name inside the tailnet), as a note.

On Linux the commands that need it are prefixed with `sudo`. A provider setting with the wrong type, or a key Tailscale does not know, is `wrong`. What your tailnet is for, its access rules, and what each host does belong in your org's stack-wisdom, not here.

### Adding a provider

Contributions are welcome. A provider is one Python module, `scripts/network/<name>.py`, with three functions:

- `detect() -> dict` returns at least `installed` and `running`, plus any of the provider's own table keys it can read safely (Tailscale adds `tailnet` and `ssh`). `--snapshot` uses it, writing the extra keys as the provider's table.
- `audit(manifest_table, ctx) -> list[Finding]` checks the machine against the `[network.<name>]` table. `ctx` is the audit's context, and findings are built with the audit's `missing`, `wrong`, and `note` helpers.
- `handoff(manifest_table) -> list[str]` returns the sign-in or join commands for a person to run. Today the checklist builds its `you` steps from the findings themselves and does not call it.

`scripts/network/__init__.py` exposes `available()`, the shipped provider names (it lists files and imports nothing), and `load(name)`, which imports a provider only if its name is in that list, so a manifest value can never become an arbitrary import. A provider that raises an error becomes one `wrong` finding naming the provider, and the rest of the audit carries on.

A `missing` finding can also carry an optional `action`: a small dictionary with a `kind` and the parameters needed, so the installer can run the step without reading the remedy text. The installer understands six kinds: `package`, `git_include`, `ssh_block`, `plugin_marketplace_add`, `plugin_install`, and `clone`. A finding with any other kind (or none) stays a `you` step, so a provider that sets no action is safe by default.

The module's docstring documents its manifest keys, and that docstring is what the table above is built from. Tests follow the existing pattern: a stub of the tool's binary on PATH and one test per finding. A provider reads names and states and never a key, token, or auth key. A contribution is a pull request with one module, one test file, and one row in the table.

## Overwatch

Session start runs one cheap device check. For each identity contract, it looks for a `gh` login for the contract's account (read from the local keyring, no network) and, for every org directory except the default org's, an includeIf stanza in `~/.gitconfig`. Each org that is missing either one prints one line:

```
ACTION REQUIRED: this machine cannot commit as <account> for <org>; run /run-organize-device
```

Only an absent stanza alerts here; a stanza that exists but is wrong is left to the full audit. A clean result is cached for a day, and a failing one is checked again next session, so the alert stops as soon as the fix is in. The check stays silent when `gh` is not installed, when Python is older than 3.11, when there are no contracts, or when `gh` does not answer in time. Tools and the network provider do not alert at session start, because a missing optional tool is not urgent.

## Platforms

| Platform | Support |
|---|---|
| macOS | supported, with Homebrew |
| Debian-family Linux (Debian, Ubuntu, and relatives using `apt`) | supported |
| Other Linux | detected; the bootstrap stops and names the package manager it found |
| Windows | detected and declined; install WSL2 (Microsoft's Linux layer for Windows) and run everything inside it |

## Example

An invented machine with three orgs: example-studio is the default org, example-client pushes through the alias `github-example-client`, and example-side has a contract but no includeIf stanza yet.

```
$ /run-organize-device

Device audit (cheap checks, local disk only)

Device manifest
note: Read ~/.config/lastmilefirst/device.toml.

Platform
note: macOS 15 on arm64; package manager: brew; shell: zsh.

Tools
clean

GitHub logins
note: gh logins present: example-studio, example-client.
note: gh's active account is example-studio. `gh auth switch` is machine-global: switching in one shell changes it for every shell on this machine.

SSH
note: Hosts present with keys on disk: github-example-client, github.com.

git identity
ACTION REQUIRED: The includeIf stanza for ~/Code/example-client/ is wrong: gitdir uses an absolute home path (/Users/<login>/Code/example-client/).
       → Replace the stanza in ~/.gitconfig with:
         [includeIf "gitdir:~/Code/example-client/"]
             path = ~/.gitconfig-example-client
WARNING: No includeIf stanza for ~/Code/example-side/ in ~/.gitconfig, so commits there use the global identity instead of side@example.com.
       → Append to ~/.gitconfig:
         [includeIf "gitdir:~/Code/example-side/"]
             path = ~/.gitconfig-example-side
         Create ~/.gitconfig-example-side with:
         [user]
             name = Example Side
             email = side@example.com
note: Commit signing: example-studio off; example-client off; example-side off.
note: credential.helper is osxkeychain (from ~/.gitconfig).
note: No repo under a non-default org directory uses an HTTPS origin.

Claude Code
note: claude --version: <version> (Claude Code).

AWS
note: Profile default is labeled studio (aws.default_profile_is).

Keychain
clean

Network
note: No network provider is configured. To check one, set `provider` in the [network] table of ~/.config/lastmilefirst/device.toml (shipped: tailscale) and add its [network.<provider>] table.

Workspace
WARNING: example-tool is not cloned at ~/Code/example-client/example-tool.
       → git clone git@github-example-client:example-client/example-tool.git ~/Code/example-client/example-tool
note: 11 of 12 project rows present (1 not cloned).

Result: 1 action required, 2 warnings.
```

`/run-organize-device --install` would then list three steps: the example-side stanza and include file as `script`, the example-client clone as `script` (run only once you approve it by name), and the example-client stanza replacement as `you`.

## History

This skill replaces a set of new-machine setup scripts that used to live in a stack-wisdom repository. They carried one GitHub account, one SSH key, and a copy of the repo list, so they fell behind as soon as identity moved into per-org contracts. Their still-true advice (a new SSH key per device, browser sign-in rather than API keys, which credentials are new and which you bring) is in the bootstrap section above.

## Related Skills

- `organize-orgs` - identity contracts and org infrastructure; checks the repos, where this skill checks the machine
- `scan-secrets` - the git hooks this skill checks are installed
- `overwatch` - the session-start alert
