---
name: organize-orgs
description: Set up and manage org-level infrastructure - config, operatives, and stack-wisdom repos
---

# Organize Orgs

Set up and manage your orgs - the top-level containers for related projects, shared operatives, and institutional wisdom.

## What Are Orgs?

An **org** (organization) is a grouping of related projects that share:
- **Context** - Common tech stack, deployment patterns, conventions
- **Operatives** - AI specialists tuned to your domain
- **Wisdom** - Patterns and lessons learned over time

### Everyone Has Orgs

Even solo developers have orgs - they just might not call them that:

| You Might Call It | It's An Org Because... |
|------------------|------------------------|
| "My side projects" | Shared conventions, your personal stack |
| "Work stuff" | Company standards, team knowledge |
| "Client X projects" | Client-specific domain, their patterns |
| "Learning/experiments" | Different risk tolerance, more freedom |

### "Personal" Is An Org

Your personal projects are an org - you're a team of one (plus your AI agents). You have:
- Your preferred tech stack
- Your coding conventions
- Operatives tuned to your style
- Wisdom from your past debugging sessions

Don't skip org setup for personal projects. The infrastructure pays dividends.

## Recommended Structure

```
~/Code/                          # Workspace (security boundary)
├── CLAUDE.md                    # Workspace preferences
│
├── personal/                    # Your personal org
│   ├── CLAUDE.md                # Your standards
│   ├── .claude/
│   │   └── org.json             # Org config
│   ├── personal-operatives/     # Your specialists (git repo)
│   └── personal-stack-wisdom/   # Your hard-won insights (git repo)
│
├── work/                        # Primary work org
│   ├── CLAUDE.md                # Team standards
│   ├── .claude/
│   │   └── org.json
│   ├── work-operatives/         # Team specialists
│   └── work-stack-wisdom/       # Team knowledge
│
└── client-acme/                 # Client-specific org
    ├── CLAUDE.md                # Client conventions
    ├── .claude/
    │   └── org.json
    ├── client-acme-operatives/  # Client domain experts
    └── client-acme-stack-wisdom/# Client-specific patterns
```

## What This Skill Does

### 1. Explains Orgs
On first run (or with `--explain`), walks through what orgs are and why they matter.

### 2. Audits Existing Orgs
Scans workspace for org directories and checks infrastructure:
- Does it have `.claude/org.json`?
- Does it have an operatives repo?
- Does it have a stack-wisdom repo?
- Does it declare a valid **identity contract**, and do its repos comply?

Run the identity portion directly:

```bash
python3 scripts/audit_identity.py              # full audit
python3 scripts/audit_identity.py --cheap      # filesystem-only (what session start runs)
python3 scripts/audit_identity.py --json       # machine-readable
```

Exits non-zero when any error-severity finding is present.

### 3. Scaffolds Missing Infrastructure
Creates what's missing:
- `.claude/org.json` from template
- `[org]-operatives/` as git repo with README
- `[org]-stack-wisdom/` as git repo with structure

### 4. Bootstraps New Users
For users without any orgs, offers to create `personal/` and `work/`.

## Usage

```bash
# Full interactive setup (recommended for first time)
/run-organize-orgs

# Explain orgs without making changes
/run-organize-orgs --explain

# Audit only (no changes)
/run-organize-orgs --audit

# Set up a specific org
/run-organize-orgs --org personal
/run-organize-orgs --org work

# Create a new org
/run-organize-orgs --new client-acme
```

## Interactive Flow

### First-Time User

```
$ /run-organize-orgs

============================================================
WHAT ARE ORGS?
============================================================

An org is a container for related projects. Think of it as a
boundary around work that shares context:

  • "personal" - Your side projects, experiments, tools
  • "work" - Your job, company projects, team code
  • "client-x" - A specific client's projects

Even if you work alone, you have orgs. Your personal projects
share your preferences, your patterns, your hard-won lessons.
Setting up org infrastructure means your AI agents can access
that shared context.

Each org gets:
  • org.json     - Configuration (what repos to use)
  • operatives/  - AI specialists for your domain
  • stack-wisdom/ - Patterns and lessons learned

============================================================
SCANNING WORKSPACE: ~/Code
============================================================

Found directories that could be orgs:
  • experiments/  (12 projects, no org infrastructure)
  • freelance/    (3 projects, no org infrastructure)

No orgs with full infrastructure found.

============================================================
RECOMMENDED SETUP
============================================================

For most developers, we recommend starting with two orgs:

  personal/  - Side projects, experiments, personal tools
  work/      - Professional work (job, clients, freelance)

This gives you:
  ✓ Clear separation between personal and professional
  ✓ Different operatives for different contexts
  ✓ Wisdom that stays in the right domain

[P] Create personal/ and work/ orgs (recommended)
[C] Create custom orgs (you specify names)
[M] Migrate existing directories to orgs
[S] Skip for now
```

### Existing User with Gaps

```
$ /run-organize-orgs

============================================================
ORG AUDIT: ~/Code
============================================================

FOUND ORGS:
  ✓ personal/
      org.json:       ✓ exists
      operatives:     ✗ missing (expected: personal-operatives/)
      stack-wisdom:   ✓ exists

  ✓ work/
      org.json:       ✗ missing
      operatives:     ✗ missing (expected: work-operatives/)
      stack-wisdom:   ✗ missing (expected: work-stack-wisdom/)

INFRASTRUCTURE GAPS:
  • personal/ needs: operatives repo
  • work/ needs: org.json, operatives repo, stack-wisdom repo

[F] Fix all gaps (create missing infrastructure)
[I] Interactive (choose what to create)
[A] Audit only (no changes)
```

## Scaffolding Details

### org.json

Created from template with org name substituted:

```json
{
  "name": "personal",
  "operatives": {
    "repo": "personal-operatives"
  },
  "stack_wisdom": {
    "repo": "personal-stack-wisdom"
  },
  "workflow": {
    "complexity_threshold": "moderate",
    "auto_compound": true
  },
  "identity": {
    "github_account": "REPLACE_ME",
    "git_user_name": "REPLACE_ME",
    "git_email": "REPLACE_ME",
    "owns_remotes": [],
    "enforcement": "block"
  }
}
```

An org may decline the operatives and stack-wisdom repos with
`{"enabled": false}` in place of `{"repo": ...}`. Overwatch then stops
reporting them as missing, rather than warning about them every session.

**The identity block ships with placeholders on purpose.** Scaffolding it
half-configured means the pre-commit hook fails loudly with a clear message,
which is enforcement; leaving the key out entirely would mean the org silently
has no contract until someone remembers. Fill in the placeholders as part of
creating the org — instructions can be skipped, the hook cannot.

## Identity Contracts

An org's `identity` block declares who commits there. Three surfaces read it,
with deliberately different budgets:

| Surface | Cost | Network | Question |
|---|---|---|---|
| `check_identity.py` (pre-commit) | instant, blocking | never | does *this* commit match? |
| Session start (Overwatch) | sub-second | never | is any contract missing or malformed? |
| `audit_identity.py` (this skill) | seconds | yes | do all repos actually comply? |

The per-repo drift walk and the GitHub account probe stay out of session start,
which shares a 10-second budget with every other check.

**`owns_remotes` is a claim registry, not an allowlist.** An owner nobody claims
passes — collaborating on someone else's repo, a fork's `upstream`, and OSS
contributions are all normal. Only an owner claimed by a *different GitHub
account* blocks. Claims key on account rather than org directory, so two
workspace orgs sharing one account is not a conflict.

Directories marked `external` or `scratch` in a `.claude-workspace` marker carry
no identity obligation, so the hook and the audit skip them. See
[Workspace Markers](#workspace-markers).

### Operatives Repo

Creates `[org]-operatives/` with:

```
[org]-operatives/
├── .git/
├── README.md
└── .gitkeep
```

README explains what operatives are and how to create them.

### Stack-Wisdom Repo

Creates `[org]-stack-wisdom/` with:

```
[org]-stack-wisdom/
├── .git/
├── README.md
├── stack-wisdom/
│   └── .gitkeep
├── circuit-breakers/
│   └── .gitkeep
└── triggers/
    └── .gitkeep
```

README explains wisdom vs. knowledge and the compound loop.

## Workspace Markers

This section is the one place the marker vocabulary is documented. Other skills
link here rather than restating it.

A `.claude-workspace` file in a directory says what kind of directory it is.
Only its `type:` line is read, line by line rather than as YAML, because the
pre-commit hook must not depend on PyYAML. A missing or unreadable marker means
the default: an ordinary, governed directory.

| `type` | Where it goes | What it does |
|---|---|---|
| `studio` | an org | Nothing beyond the default. Useful for being explicit. |
| `external` | any directory | Cloned third-party code. The identity checks (the pre-commit hook and `audit_identity.py`) skip it and everything below it. |
| `scratch` | any directory | Personal working files. The identity checks skip it and everything below it. |
| `client` | one level inside an org | A client directory: a container for one counterparty's projects. Its children are projects; it is not one. |

Only the identity checks honor `external` and `scratch`. Overwatch, the secret
scan, and the review and organize skills treat those directories like any other.

### Client directories

An advisory org's unit of work is often the counterparty rather than the repo.
One client can bring several repos at once (an engagement workspace, a clone of
their code, a deliverable that becomes code), and a client directory keeps them
together:

```
~/Code/acme/
├── .claude/org.json               # the org's contract governs everything below
├── practice/                      # project, key acme/practice
└── northwind/                     # client directory (not a project)
    ├── .claude-workspace          # type: client
    ├── CLAUDE.md                  # optional, reviewed as tier "client"
    ├── web/                       # project, key acme/northwind/web
    └── docs/                      # project, key acme/northwind/docs
```

The rules:

- **Nested only.** `type: client` is recognized one level inside an org and
  nowhere else. A marker at the top level does nothing. A client that is a
  whole org is an ordinary org with its own `org.json` and needs no marker.
- **One level.** A client directory inside a client directory is treated as a
  project, and Overwatch prints a note saying so.
- **No `org.json` in a client directory.** The org's contract governs the repos
  inside it, and the pre-commit hook walks up through the client directory to
  find it. A client directory carrying `.claude/org.json` is flagged as
  ACTION REQUIRED at session start, even when the client directory is empty.
  Remove the file.
- **Not a repo itself.** A client directory that is a git repo is flagged as a
  WARNING. Overwatch and review-org do not track its own contents as a
  project; the secret scan and identity audit still cover it as the flat
  `org/client` repo. Move its files into a project inside it.
- **No state of its own.** Overwatch keys projects by their path relative to
  the workspace (`acme/northwind/web`). The client directory itself has no
  record: `update_state.py` run from inside it says "container directory, not
  tracked."
- **Names are the org's business.** The plugin does not care what a client
  directory is called. An org that wants pseudonyms for counterparties writes
  that rule in its own CLAUDE.md.

A marker may also carry `status: active | paused | archived` for a client
directory. It is recorded for later use; nothing reads it yet.

**Moving a repo into a client directory** changes its Overwatch key, so its
history would read as "never scanned" until the next sweep. Move the record
with it:

```bash
python3 ~/.claude/plugins/marketplaces/gruntwork-lastmilefirst/plugins/lastmilefirst/hooks/scripts/update_state.py rename --from acme/web --to acme/northwind/web
```

`rename` refuses when the new key already has a record, so nothing is
overwritten. It works for any directory rename, not only this one.

## Integration

### With organize-claude

`organize-claude` can detect missing org infrastructure and offer to run `organize-orgs`:

```
$ /run-organize-claude

Found org: work/
  ✓ CLAUDE.md exists
  ✗ No org.json (operatives and wisdom not configured)

[O] Run organize-orgs to set up org infrastructure
[S] Skip and continue with CLAUDE.md audit
```

### With organize-project

`organize-project` benefits from org infrastructure being in place - it can reference the org's operatives and wisdom.

### With Overwatch

Overwatch proactively alerts when org infrastructure is missing:

```
-----------------------------------------------------------
|  OVERWATCH                                              |
-----------------------------------------------------------
⚠️ Org 'work' missing infrastructure:
   - No .claude/org.json
   - No work-operatives/ repo

   Run `/run-organize-orgs` to set up
```

This means you'll be reminded at session start if your current org is missing infrastructure - you don't have to remember to run organize-orgs manually.

## Update Overwatch

After completing org organization, update the org's Overwatch state:

```bash
python3 ~/.claude/plugins/marketplaces/gruntwork-lastmilefirst/plugins/lastmilefirst/hooks/scripts/update_state.py organize --scope org
```

## Related Skills

- `organize-claude` - CLAUDE.md file hierarchy
- `organize-project` - Project structure (docs/, .claude/)
- `create-operative` - Create operatives (uses org path from org.json)
- `add-wisdom` - Add patterns (uses wisdom repo from org.json)
