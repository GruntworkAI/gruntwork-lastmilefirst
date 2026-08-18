# Per-Org Identity Contract + Fail-Closed Pre-Commit Enforcement

**Date:** 2026-08-17
**Status:** Phases 0–2 implemented (2026-08-18). Phase 3 next — see §10.
**Driver:** Campaign site shared with the `outsideshot` GitHub account must not be committed or pushed as `GruntworkAI`.
**Proof of concept for:** different rules for different orgs, declared at org level and mechanically enforced.

---

## 1. Problem

Two GitHub accounts, one machine. Three independent layers can disagree, and today none of them check each other:

| Layer | Current state | What goes wrong |
|---|---|---|
| `gh` CLI | Single account `GruntworkAI`, token in keyring | `gh auth switch` is machine-global — no per-directory binding |
| git commit identity | Global `GruntworkAI / admin@gruntwork.ai`, no `includeIf` | Campaign commits are authored by the studio identity |
| git push credential | `osxkeychain` (from `/Library/Developer/CommandLineTools/usr/share/git-core/gitconfig`) | **One credential per host.** `github.com` resolves to whichever account is cached, regardless of `gh` state |

The layers are genuinely separate. Switching `gh` does not re-point the keychain. Setting `user.email` does not change who pushes.

**Decided approach:** shared `gh` config with `gh auth switch`, plus **fail-closed** pre-commit enforcement driven by org-level config — no contract means no commit, absent an explicit override.

---

## 2. What already exists (revises the first draft of this plan)

Two discoveries change the design materially:

**`.claude/org.json` is already the org config surface.** Both orgs have one; `organize-orgs` scaffolds and audits it; Overwatch already alerts when org infrastructure is missing.

```json
{ "name": "gruntwork",
  "operatives": { "repo": "gruntwork-operatives" },
  "stack_wisdom": { "repo": "gruntwork-stack-wisdom" },
  "stack_knowledge": { "type": "local", "path": "stack-knowledge" },
  "workflow": { "complexity_threshold": "moderate", "auto_compound": true } }
```

The first draft proposed a fenced ` ```yaml identity ` block inside `CLAUDE.md`. **Withdraw that.** `org.json` is better on every axis: stdlib JSON parsing instead of fence-regex-plus-hand-rolled-YAML, already scaffolded, already audited, already Overwatch-wired.

The original ask — org-level `CLAUDE.md` driving the rules — is still honored, because both files carry it and serve different readers:

| File | Reader | Role |
|---|---|---|
| `.claude/org.json` → `identity` block | the **hook** | machine-enforceable contract |
| org `CLAUDE.md` → Identity section | **Claude** | so the model behaves correctly at session start |
| — | `organize-orgs` | **validates the two agree**; disagreement is a finding |

Prose alone can't be fail-closed against — it can't be parsed reliably enough to block a commit on. Splitting readers is what makes hard enforcement safe.

**The workspace-types spec is already drafted** (`.claude-workspace` markers; Studio / Client / External / Scratch; Phase 0 complete, awaiting review). Fail-closed enforcement needs exactly that boundary — see §4.

---

## 3. The contract

Added to each governed org's `.claude/org.json`:

```json
"identity": {
  "github_account": "outsideshot",
  "git_user_name": "outsideshot",
  "git_email": "outsideshot@gmail.com",
  "owns_remotes": ["outsideshot"],
  "ssh_host_alias": "github-personal",
  "enforcement": "block"
}
```

- `enforcement`: `block` (default) | `warn` | `off`. **`off` must be written here, never carried in a shell alias** — see §6.
- **Nearest wins.** Walk up from repo root; first `.claude/org.json` with an `identity` block is authoritative. A project may override its org.
- The mirrored `CLAUDE.md` section is human prose stating the same account, email, and owned remotes.

### `owns_remotes` is a claim registry, not an allowlist

The first draft of this field was `allowed_remote_owners`, validated as "the remote must be one of these." **That was wrong** — it treats remote ownership as the governance signal, when the governance signal is the *directory*. You declared the context by choosing where the repo lives; the remote is downstream of that and is frequently someone else's:

| Case | Remote owner | Correct identity | Allowlist semantics |
|---|---|---|---|
| Campaign repo as shared | `andyfish3` | outsideshot | ❌ blocks |
| Fork with an `upstream` remote | you + them | you | ❌ blocks on upstream |
| OSS contribution | `facebook` | (yours) | ❌ blocks |
| Client repo in the client's org | client | studio | ❌ blocks |
| Ordinary studio repo | `GruntworkAI` | GruntworkAI | ✅ passes |

One row in five. A check that is wrong more often than right gets overridden into uselessness.

**Revised semantics.** `owns_remotes` declares "this org owns repos under these owners," and the check reads across *all* org contracts rather than only the local one:

| Remote owner is… | Result |
|---|---|
| Claimed by **this** org | pass |
| Claimed by **another** org | **block** — genuine cross-context leakage |
| Claimed by **no** org | **pass** — identity check still applies |

Every row of the table above resolves correctly. The campaign repo under `andyfish3` passes because nothing claims `andyfish3`, while commit identity stays enforced. Pushing a `GruntworkAI`-claimed remote from `~/Code/outsideshot/` still blocks — the error actually worth catching.

**Consequence for the whole design: identity is the blocking check; remote owner is only a cross-context guard.** Attribution — whose name and email land on the commit — is the invariant. Where it pushes is a separate question, and unclaimed remotes are normal rather than suspicious. This stays safe as a blocking check precisely because *absence* never fires it; only an explicit competing claim does.

---

## 4. Fail-closed — and the boundary that makes it survivable

`core.hooksPath` is **global**. Naive fail-closed would block commits in every repo on this machine: `~/Code/every/` (third-party clone), `~/Code/drafts/` (scratch), the plugin cache repos, and everything outside `~/Code` entirely. That is not a rollout, it's an outage.

The bootstrap problem: you cannot use the contract to decide whether a contract is required. So governance is decided by **location plus registration**:

| Repo location | Governed? | Missing contract → |
|---|---|---|
| Outside `~/Code/` | No | exit 0, silent |
| Under a dir with `.claude/org.json` | **Yes** | **BLOCK** |
| Direct child of `~/Code/` with no `org.json`, no External/Scratch marker | **Yes — "unregistered org"** | **BLOCK**: "looks like an org but isn't registered" |
| Marked External or Scratch | No | exit 0 |

The third row is the one that matters. Without it, creating `~/Code/outsideshot/` and committing before running `organize-orgs` lands campaign commits under the studio identity — precisely the failure this whole plan exists to prevent. An unregistered org must be treated as governed-but-unconfigured, not as ungoverned.

**Day-one cost, and its fix.** Turning this on makes `~/Code/every/` and `~/Code/drafts/` block, since both are unregistered direct children today. Fix: write their `.claude-workspace` markers (`external` and `scratch`) **in the same change**. Two files. Do not ship the enforcement without them.

This also means the interim rule (`org.json` presence = governed) lets enforcement land **without waiting on workspace-types Phase 1**. Only the two marker files are needed now; the full type resolver remains the correct long-term home and supersedes the interim rule when it lands.

### Hook logic

1. `git rev-parse --show-toplevel`; not a repo → exit 0.
2. Repo root not under `~/Code` → exit 0.
3. Walk up for `.claude/org.json`; classify per the table above.
4. Governed with contract → check:

   | Check | Compare | On mismatch |
   |---|---|---|
   | Commit email | effective `git config user.email` vs `git_email` | block |
   | Commit name | effective `git config user.name` vs `git_user_name` | block |
   | Remote owner | **every** remote's owner vs the union of all orgs' `owns_remotes` | block **only** if claimed by a different org (skip if no remote yet) |
   | `gh` active account | `gh auth status` vs `github_account` | **warn only** — affects later `gh` commands, not this commit |

5. Governed without contract → block, naming the file to fix and the command to run.
6. Print the exact remedy (`git config user.email …`). **Never auto-fix** — a hook that silently rewrites identity is worse than one that stops.

### Constraints

- **No network, ever.** The `gh` check reads local config only; skip if `gh` is missing or slow.
- Fast path first: `git rev-parse` + a path prefix test rejects most repos before any file read.
- Must survive worktrees and detached HEAD.
- `--no-verify` bypasses this entirely. State it in the docs; pre-push (§8, Phase 4) is the backstop.

---

## 5. `organize-orgs` — the hard check

Fail-closed at commit time is only humane if the gap is surfaced earlier. `organize-orgs` owns that.

**At org creation — refuse to finish without identity data.** No silent skip. Choosing to skip writes `"enforcement": "off"` explicitly, so the exemption is a recorded decision rather than an omission. An org that exits creation with no `identity` key at all is the state this plan exists to eliminate.

**At audit — six checks:**

| # | Check | Why |
|---|---|---|
| 1 | `identity` block present, all required keys | The thing the hook needs |
| 2 | Well-formed: email parses; `github_account` matches GitHub username rules; **no owner claimed by two orgs** | A typo'd contract blocks every commit with a confusing message; a double-claimed owner makes the cross-context check ambiguous |
| 3 | **Live** (network OK here, never in the hook): `gh api users/{account}` resolves; `gh auth status` shows a token for it | Catches "account declared but never logged in" before it becomes a mystery block |
| 4 | **Drift audit:** every repo under the org — `git config user.email` and remote owner vs contract | Finds repos already committed under the wrong identity. The retroactive check the hook can't do |
| 5 | `CLAUDE.md` Identity section agrees with `org.json` | Prevents the model reading one truth while the hook enforces another |
| 6 | Unregistered direct children of `~/Code/` | Surfaces new org dirs before they collect mis-attributed commits |

**Exit non-zero on 1, 2, or 3**, and emit ACTION REQUIRED to Overwatch state.

### Overwatch is what keeps fail-closed from ambushing you

The failure mode of hard enforcement is learning about it mid-commit with a dirty tree. Overwatch already fires org-infrastructure alerts at session start and already has an update hook (`hooks/scripts/update_state.py organize --scope org`). Wire missing/invalid identity contracts into it so the alert arrives at session start — before there's anything staged.

**This is not optional polish.** Fail-closed without session-start surfacing produces exactly the friction that gets a check aliased away.

---

## 6. Override design

Two distinct needs, deliberately unequal in convenience:

| Need | Mechanism | Cost |
|---|---|---|
| One-off bypass | `LMF_IDENTITY_OVERRIDE=1 git commit …` | Prints what was skipped; appended to `~/.claude/lastmilefirst/invocations.log` (pattern already exists) |
| Permanent exemption | `"enforcement": "off"` in `org.json`, or External/Scratch marker | Recorded in config, visible to audit, reviewable in git history |

**If the only override is an env var, it gets aliased and the check is dead.** The one-off path must stay mildly inconvenient and always leave a trace; the permanent path must be a config edit someone can find later. `warn` exists as the middle setting for rolling an org in gradually.

---

## 7. `outsideshot` as a named org

First-class peer to `gruntwork` and `lastmilefirst.ai` — not "personal" — so per-org divergence gets exercised for real.

```
~/Code/
├── CLAUDE.md              # workspace root — needs amendment, see below
├── gruntwork/
├── lastmilefirst.ai/
├── every/                 # + .claude-workspace: external   ← §4 day-one fix
├── drafts/                # + .claude-workspace: scratch    ← §4 day-one fix
└── outsideshot/           # NEW
    ├── CLAUDE.md
    ├── .claude/org.json   # carries the identity contract
    └── {campaign-site}/
```

**Path convention:** `~/Code/outsideshot/{projectname}` — no repo-name prefix, matching `lastmilefirst.ai` rather than the `gruntwork-{name}` pattern.

**Deliberate divergence:** `~/Code/gruntwork/CLAUDE.md` and `~/Code/lastmilefirst.ai/CLAUDE.md` are symlinks into `gruntwork-stack-wisdom/claude/claude-md-files/`. Following that for `outsideshot` would store the separated org's rules inside a Gruntwork repo — recoupling the thing being separated, and making the campaign's rules unreadable whenever stack-wisdom isn't checked out. **`~/Code/outsideshot/CLAUDE.md` is a real file.** It's also the more honest POC: the mechanism must work for orgs that don't share Gruntwork's storage.

**Required edit to `~/Code/CLAUDE.md`.** It currently says the default account is `GruntworkAI`, that `outsideshot` is "personal repos only", and lists three workspaces. All three become wrong once `~/Code/outsideshot/` exists. Without the edit the root file contradicts the new org on every session load, and the model keeps defaulting campaign work to the studio account no matter what the hook enforces. Needs: `outsideshot` in the tree and path conventions; the accounts table reframed (an org with its own contract, not a personal-repo exception); a line stating org identity contracts are authoritative; an `outsideshot` section in the Project Directory Mapping table.

---

## 8. The gap enforcement does not close

**Pre-commit fires at commit time. The push credential resolves at push time.**

With `osxkeychain` holding one `github.com` entry, a correctly-authored `outsideshot` commit can still be pushed on the cached `GruntworkAI` credential. Commit metadata right, push actor wrong. No pre-commit hook can see this.

**(a) SSH host alias — recommended, and orthogonal to the `gh` decision.** A second key plus a `~/.ssh/config` alias, campaign remote as `git@github-personal:outsideshot/{repo}.git`. Transport then bypasses both keychain and `gh` state. This does *not* reintroduce the `GH_CONFIG_DIR` isolation that was declined: `gh auth switch` governs `gh` commands, the SSH alias governs git transport — different layers, different decisions. `ssh_host_alias` is already in the schema to make it checkable.

**(b) Pre-push hook.** Same contract, same parser, and able to check the *resolved* remote. A pre-push secret scan is already a standing todo in this repo; the two must land on **one dispatcher**, not as two competing `pre-push` files.

---

## 9. Hook plumbing

- **Source:** `plugins/lastmilefirst/skills/organize-orgs/scripts/check_identity.py`. `organize-orgs` owns org-level infrastructure — correct home. Not a scan-secrets concern; must not live under it.
- **Dispatcher refactor:** `scan-secrets/scripts/hook_installer.py` currently *owns* `pre-commit` as a single-purpose script. It must become a dispatcher running registered checks in order, failing on first non-zero. Identity first (cheap — `git config` + one JSON read), secret scan second. This refactor is the prerequisite for any future third check.
- Never edit `~/.claude/lastmilefirst/git-hooks/pre-commit` directly — install output. Change source, bump, reinstall, `/reload-plugins`.

---

## 10. Phases

| Phase | Work | Notes |
|---|---|---|
| 0 | Create `~/Code/outsideshot/` + `org.json` with identity block; write `.claude-workspace` markers for `every/` + `drafts/`; amend root `CLAUDE.md` | Markers are **required** before Phase 2 or day one breaks |
| 1 | Repo-level `git config` by hand as interim guard | Removes the immediate risk before any code |
| 2 | `check_identity.py` + dispatcher refactor + override handling | Needs a real contract from Phase 0 to test against |
| 3 | `organize-orgs` hard checks (§5) + Overwatch wiring | **Ship with or before Phase 2's fail-closed default**, or enforcement ambushes at commit time |
| 4 | Backfill identity blocks into `gruntwork` + `lastmilefirst.ai` org.json — **where the POC pays off** | Roll in at `warn` first, then `block` |
| 5 | Pre-push, merged with the existing pre-push secret-scan todo | Closes §8(b) |

Phases 0–1 remove the immediate risk on their own. 2–5 are the compounding part.

**Sequencing hazard:** Phase 2 at `block` without Phase 3 means the only signal is a failed commit. If they can't ship together, default Phase 2 to `warn` and flip to `block` when Phase 3 lands.

---

## 11. Open decisions

1. **Campaign repo on GitHub** — the draft lives at `andyfish3/heather-thomason-2026`, shared with `outsideshot`. Options: work in Andy's repo as a collaborator; fork to `outsideshot`; or clone and push to an `outsideshot`-owned repo (history and Andy's authorship carry over either way). **Fork vs. clean copy hinges on whether Andy keeps contributing** — a hard copy diverges immediately and reconciling later is painful. Under revised §3 semantics all three work without contract changes, since `andyfish3` is unclaimed.
2. **Repo name** — `~/Code/outsideshot/heather-thomason-2026`.
3. **`ssh_host_alias`** — adopt §8(a) now, or accept the push-layer gap until Phase 5?
4. **Data classification** — campaign work can carry voter/donor data with real handling constraints. The `gruntwork` org CLAUDE.md has a Data Classification section; `outsideshot` likely needs its own rather than inheriting studio defaults. Settle in Phase 0 while the file is being written.
5. **Workspace-types spec** — this plan's interim rule (`org.json` presence = governed) unblocks enforcement now, but the spec is the proper resolver and is still awaiting review. Promote it to Phase 6, or fold it in earlier?

---

## 12. Changed during implementation (2026-08-18)

Four corrections the build surfaced. Each is already reflected above.

1. **Claims are keyed by GitHub account, not org directory.** `gruntwork/` and `lastmilefirst.ai/` are separate workspace orgs that both push to `GruntworkAI` — verified against real remotes. Keying claims by directory would have made that legitimate arrangement read as cross-context leakage. The check now blocks only when an owner is claimed by a *different account* than the one governing the directory. Phase 3's "double-claimed" validation follows the same rule.

2. **The gruntwork and lastmilefirst.ai backfill moved from Phase 4 into Phase 2.** Without it, every commit in the studio orgs would hit "org.json exists but has no `identity` block" and block immediately — the plan's own rollout would have broken the repo it was being written in. Both now carry contracts at `enforcement: block`. *Note: lastmilefirst.ai may get its own GitHub account later; that is a two-field edit (`github_account`, `owns_remotes`) with no code change.*

3. **Override env var name settled: `LMF_IDENTITY_OVERRIDE`.** §4 and §6 of the first draft disagreed (`LMF_SKIP_IDENTITY_CHECK` vs `LMF_IDENTITY_OVERRIDE`); the §6 name won.

4. **The dispatcher needed a `CHECKS_RUN` counter.** Globbing to the plugin *root* instead of to a specific script means the root can resolve while the check scripts are missing — a state that would pass every commit in silence and read as coverage. The old single-purpose hook could not have this bug, because its glob targeted the script itself. Regression test added.

**`.claude-workspace` markers for `every/` and `drafts/` were deliberately skipped** (Fish, 2026-08-18): `drafts/` contains no git repos at all and `every/` contains one third-party clone that is never committed to. Blast radius is a repo nobody commits in. The markers remain correct for the workspace-types spec, just not urgent.

---

## 13. Compounding note

The reusable asset is not the campaign setup — it's the pattern: **`org.json` as a machine-readable per-org policy surface, `CLAUDE.md` as its human/model-facing mirror, a hook dispatcher enforcing whatever the nearest contract declares, and Overwatch surfacing gaps before they block.** Identity is the first contract. Data classification, required review gates, and allowed deploy targets are the same shape and ride the same parser, dispatcher, and alerting.
