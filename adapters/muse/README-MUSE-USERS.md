# LastMileFirst for Muse: User Guide

A Muse-optimized skill package ported from the [GruntworkAI LastMileFirst](https://github.com/gruntworkai/gruntwork-lastmilefirst)
Claude Code plugin. It gives your Muse agent a proven working method for
substantive build, implementation, and review tasks.

There is no Muse skill marketplace, so this repo is the distribution:
you build the skill package with one command and copy one directory
into your workspace.

## What you get

- **PARC workflow**: Plan → Allocate → Review → Compound becomes your
  agent's default method for substantive work. Say "quick question" or
  "no PARC" to skip it for anything small.
- **Review checklists**: structured review for docs and for prose that
  needs to sound human.
- **Secret scanning**: the plugin's scanner runs unchanged via a thin
  wrapper; your agent's Review phase includes a secret scan before anything
  is committed.
- **16 expert personas**: a generated roster your agent uses to brief
  specialist subagents (AWS, Python, QA strategy, and more).
- **Overwatch-style hygiene**: the plugin's drift checks, mapped to
  scheduled jobs (design plus a ready-to-paste weekly recipe below;
  nothing is scheduled without your go-ahead).

## Requirements

- A Muse environment with workspace skills (`~/workspace/skills/`)
- Linux (Muse runs on Linux; the scanner install below downloads the Linux x64 gitleaks binary)
- `git`, `bash`, `python3` (3.11 or newer; the builder uses only the standard library)
- `gitleaks` ≥ 8.19 (only needed for secret scanning)

## Data note

Your Muse workspace is a VM in Meta's cloud: anything you put there —
including repos you clone to scan — lives on Meta's infrastructure, not just
your device. Conversations are not end-to-end encrypted and may be logged and
reviewed by Meta; they also contribute to the development of AI at Meta unless
you opt out in Settings > Data Controls. (Details: the [Muse Privacy
Policy](https://muse.ai/privacy) and [Privacy Center](https://www.facebook.com/privacy/genai).)
Public repos are fine to scan. Think before cloning a private repo into the
workspace.

## Install

```bash
# 1. Clone the repo (pick any location; the default below is just a convention)
git clone https://github.com/gruntworkai/gruntwork-lastmilefirst ~/workspace/repos/gruntwork-lastmilefirst
cd ~/workspace/repos/gruntwork-lastmilefirst

# 2. Build the skill package (dist/ is generated at install time, never committed)
python3 adapters/muse/build.py

# 3. Install the skill
mkdir -p ~/workspace/skills
cp -r adapters/muse/dist/skills/lastmilefirst ~/workspace/skills/
chmod +x ~/workspace/skills/lastmilefirst/bin/scan-secrets

# 4. Install gitleaks (for the secret scanner)
mkdir -p ~/workspace/bin /tmp/gitleaks-install
curl -sL -o /tmp/gitleaks-install/gitleaks.tar.gz \
  "https://github.com/gitleaks/gitleaks/releases/download/v8.27.2/gitleaks_8.27.2_linux_x64.tar.gz"
tar -xzf /tmp/gitleaks-install/gitleaks.tar.gz -C ~/workspace/bin gitleaks
```

If you cloned the repo somewhere other than
`~/workspace/repos/gruntwork-lastmilefirst`, tell the scanner where it lives:

```bash
export LMF_REPO=/path/to/gruntwork-lastmilefirst
```

## Verify

From the repo root:

```bash
python3 adapters/muse/build.py --check   # the built package matches its sources
python3 adapters/muse/build.py --lint    # no leftover Claude Code-isms in the output
~/workspace/skills/lastmilefirst/bin/scan-secrets --list-formats  # the scanner runs
```

All three should exit cleanly. If `--check` fails, re-run
`python3 adapters/muse/build.py` and re-copy `adapters/muse/dist/skills/lastmilefirst/`
over your installed skill. `dist/` is generated, never edited by hand.

## Use

Once installed, the skill is automatic: for substantive tasks your agent
plans first, allocates work, reviews it hard, and compounds what was
learned into memory. You don't invoke anything.

- **Skip the ceremony:** start a message with "quick question" or "no PARC".
- **Consult an expert:** ask your agent to get a specialist's take (e.g.
  "have the AWS expert review this"); it briefs a subagent with the matching
  persona from the roster.
- **Scan for secrets:** ask your agent to scan a repo, or run
  `~/workspace/skills/lastmilefirst/bin/scan-secrets` there yourself.

## Optional: weekly hygiene check

Paste this to your agent to get the Overwatch-style scheduled check:

> Set up a weekly Monday-morning repo hygiene check: for each repo under
> ~/workspace/repos, report uncommitted changes, run the lastmilefirst
> skill's scan-secrets, and flag stale todos. Report only when something
> needs attention and stay silent when clean. Never commit or push anything
> as part of the check.

## For contributors

The port follows one rule: **copy nothing, refactor the mechanism, keep the
judgment.** Canonical content lives in `plugins/lastmilefirst/`; the Muse
package in `adapters/muse/` is derived from it:

- `adapters/muse/mapping.toml`: mechanism translations (Claude Code-isms → Muse equivalents)
- `adapters/muse/build.py`: applies the mapping to canonical sources; `--check`
  fails if `dist/` is stale, `--lint` fails on leftover Claude Code-isms
- `adapters/muse/adapter/`: hand-written Muse-specific design (the operational
  SKILL.md core, the scan-secrets wrapper, the Overwatch mapping); copied
  verbatim into `dist/`
- `adapters/muse/dist/`: generated at install time; gitignored, never committed,
  do not edit by hand

To change the port, edit the canonical source or the adapter, re-run
`python3 adapters/muse/build.py`, and confirm `--check` and `--lint` pass. See
`adapters/muse/README.md` for the builder's view.
