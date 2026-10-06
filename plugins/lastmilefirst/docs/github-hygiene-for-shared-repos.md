# GitHub hygiene for shared repositories

**v1.1 (2026-10-06).** Adds what a purge of a published sensitive commit actually requires, under the fork pull request section.

**v1.0 (2026-09-27).** First version.

A checklist for anyone who maintains repositories that people and coding agents both push to. It
covers the settings a person sets once on an account, the settings each repository needs, and
which of them this plugin measures for you. Settings names are GitHub's as of the date above.
GitHub renames things; when a name does not match, look for the same idea on the same page.

## Why this matters for shared repositories

A common way to let an agent contribute without handing it the keys is a fork-scoped token. The
agent gets a fine-grained token that can write only to a fork, it pushes a branch there and opens
a pull request, and a human reviews and merges. The agent never holds write access to the
upstream, and every change passes a person. That arrangement is sound, and it moves the risk to
the account settings and the merge step, which are easy to leave at their defaults.

The merge method is where the defaults bite. A squash merge (or any edit made on github.com)
writes a new commit on the server, and GitHub stamps it with the pull request author's primary
email unless that account has email privacy turned on. The fork's commits can carry a clean
noreply address and the squashed commit on the default branch can still publish a real one. A
merge commit keeps the original author line. On a public repository that commit is permanent in
practice, so the check belongs before the merge, not after it.

## Account settings a person sets once

**Emails**
- [ ] Keep my email addresses private, so web operations use the noreply address.
- [ ] Block command line pushes that expose my email, so a push carrying a real address is
      rejected at push time.
- [ ] The primary email is one you control and can receive security mail at, and it is verified.
- [ ] A backup email exists on a different provider. Unused addresses are removed.

**Two-factor and sessions**
- [ ] Two-factor on, with a passkey or an authenticator app as the primary method (SMS only as a
      fallback, or not at all).
- [ ] Recovery codes stored in a password manager, not in a repository.
- [ ] At least one passkey enrolled, so a lost phone does not lock the account.
- [ ] Active sessions reviewed; anything unrecognized signed out.

**Keys and signing**
- [ ] Every SSH and GPG key listed is one you can name the machine for. Delete the rest.
- [ ] Commit signing set up (SSH or GPG) and the signing key added to the account.
- [ ] Vigilant mode on, so an unsigned commit under your name shows as unverified.
- [ ] If one machine holds more than one GitHub account, remotes use a per-account SSH host alias,
      so the transport identity is fixed per repository rather than resolved from a cached
      credential.

**Applications and tokens**
- [ ] Authorized OAuth apps and GitHub Apps: revoke what you do not use, and narrow "all
      repositories" to the ones each app needs.
- [ ] No classic personal access tokens. Fine-grained tokens only.
- [ ] Every token has an expiry, a name that says what uses it, and the fewest repositories that
      work. A token handed to an agent is scoped to one fork, never to the account.
- [ ] Tokens live in the OS keychain or a secrets manager, never in a dotfile in a repository.

**Code security defaults**
- [ ] Dependabot alerts and security updates enabled automatically on new repositories.
- [ ] Secret scanning and push protection enabled automatically on new repositories.
- [ ] Push protection for yourself on, so pushes to any public repository are checked even where
      the repository setting is off.

**Profile, security log, notifications**
- [ ] Public profile email blank; location, company, and links say only what you would tell a
      stranger.
- [ ] Security log read at each review, looking for sign-ins, keys, tokens, and app
      authorizations you did not make.
- [ ] Dependabot and secret scanning alerts go to email, not only to the web inbox.

## Repository settings

**General**
- [ ] Description and topics set.
- [ ] Wikis, Projects, Discussions, and Sponsorships off unless used. Each is a surface that can
      carry content nobody reviewed.
- [ ] Merge method chosen deliberately. For repositories that take pull requests from another
      account's fork, default to merge commits, or confirm that account has email privacy on.
- [ ] Automatically delete head branches on.
- [ ] Auto-merge off unless a status check gates it.

**Collaborators**
- [ ] The list is people who work on it now, each at the lowest role that works.

**Rulesets**
- [ ] A ruleset on the default branch that blocks force pushes and restricts deletions. Add a
      pull request requirement and status checks where the workflow supports them (a pull request
      requirement also blocks direct commits, which some solo repositories rely on).
- [ ] A ruleset on release tags (`v*`) that blocks updates and deletions. Consumer surfaces such
      as Claude Desktop install a plugin from its release tag, not from the default branch, so a
      tag that can be moved changes what every such user installs.
- [ ] Immutable releases on where GitHub offers them.

**Code security**
- [ ] Dependency graph, Dependabot alerts, and Dependabot security updates on. Version updates (a
      `dependabot.yml`) for repositories with a manifest.
- [ ] Code scanning (CodeQL default setup) on for repositories with code in a supported language.
- [ ] Secret scanning and push protection on.
- [ ] Private vulnerability reporting on, with a `SECURITY.md` that says how to report.

**Actions**
- [ ] Allowed actions restricted to GitHub-owned, verified creators, and a named list, not "all
      actions."
- [ ] Third-party actions pinned to a full commit SHA in workflow files, not a tag.
- [ ] Default workflow token read-only. Grant `write` per job in the workflow file.
- [ ] "Allow GitHub Actions to create and approve pull requests" off.
- [ ] Workflows from fork pull requests require approval before they run, at least for
      first-time contributors.
- [ ] Deploys to a cloud use OIDC federation to a role, not a long-lived key stored as a secret.

**Webhooks, deploy keys, environments, secrets**
- [ ] Every webhook has a consumer you can name, uses HTTPS, and has a secret set.
- [ ] Deploy keys are read-only unless a deploy writes, and each is named for its host.
- [ ] Deploy environments have required reviewers, and deploy-only secrets live on the
      environment rather than the repository.

**Community files and content**
- [ ] `LICENSE` present and matching what the README says.
- [ ] `SECURITY.md` present; `CODEOWNERS` where more than one person reviews.
- [ ] Committed examples are reconstructed rather than copied from real clients or people, and
      security notes describe the class of problem rather than the incident.
- [ ] `.gitignore` covers build output, local state, and any `.env` shape the project uses.

## Private repositories

Everything above applies, with three differences.

- [ ] Rulesets and branch protection on a private repository owned by a personal account need a
      paid plan. On a free plan the default branch is unprotected, so keep automation from
      pushing to it directly.
- [ ] Forking off unless a specific fork is wanted. A fork of a private repository is a second
      copy under someone else's control.
- [ ] Before any change to public, run the content check and the plugin's secret scan over the
      full history, not just the working tree. History travels with the change.

## Pull requests from a fork

- [ ] Before merging, confirm what the merge will write. Check whether the author's account
      publishes an email (`gh api users/<login> --jq .email`), or merge with a merge commit so the
      original author line is kept.
- [ ] After merging, read the author back with `git log -1 --format='%an <%ae>'`.
- [ ] A token given to an agent for this pattern is fine-grained, scoped to the fork, and
      expires. The agent cannot push to the upstream; a person merges.

**If a commit with sensitive data has already been published**, rewriting history is the first
step and not the last. GitHub serves a commit by its hash for as long as anything references it:
a branch, a tag, a fork in the same network, or a pull request. Every pull request merged after
the commit landed carries it in its reference set, so the number of pull requests Support has to
touch grows with each merge you make before asking. Act before merging anything else. The purge
itself is a Support ticket: they confirm nothing references the hash, remove the pull request
references (either the whole pull request, or only its diffs with the conversation kept), run
garbage collection, and clear the cache. Delete any fork you own first. Verify yourself
afterward, with the commit page, the `.patch` URL, and the REST API all returning 404, before
treating the ticket as solved. And treat the data as exposed regardless; the purge cleans the
history, it does not un-publish what was seen.

## What the plugin checks for you, and what only a person can set

The plugin's `/run-scan-secrets` skill reads repository settings through the GitHub API. It
measures and reports; it changes a setting only when you pick that change.

At session start, on a public repository you administer, the plugin alerts when secret scanning
or push protection is off. Those are the only session-start alerts from this check. Merge
methods, forking, and wiki are policy choices, and an alert on a choice teaches people to ignore
the alerts that are not.

`--audit` reports the rest as measurements: visibility, allowed merge methods, forking,
delete-branch-on-merge, which features are on, Dependabot status, rulesets on the default branch
and on release tags, Actions policy, the default workflow token, webhooks without a secret, and
writable deploy keys. A setting the API does not return to your account (common without admin)
reads as unknown, not as off.

`--audit --propose` adds an itemized list of changes. Each item names the setting, the value it
would take, the reason, and the consequence (e.g. "blocks force pushes to main; direct pushes
still work"). `--apply` takes the item ids you choose and applies exactly those, then re-reads
each setting and prints before and after. The default proposal leaves out anything that changes
who can push or merge (a pull request requirement, merge methods, collaborators); those appear
under "consider" and are applied only if you name them. Nothing is applied at session start.

The account settings in this guide are yours to set. Email privacy and two-factor status are not
readable through the API at all, so no tool can confirm them for you; check them on the Settings
pages. The same goes for sessions, recovery codes, app authorizations, and the merge-method check
on a fork pull request, which happens on github.com where no local hook runs.

## Audit commands

All read-only. Run with `gh` authenticated as the account being audited. The account-level reads
(emails, keys) need scopes the default login does not grant; add them once per account with
`gh auth refresh -h github.com -s user -s read:public_key`. Without them those calls return a
bare 404, which looks like "no keys" and is not.

```bash
gh auth status   # which account gh acts as; the switch is machine-global

# Account
gh api user/emails --jq '.[] | "\(.email) primary=\(.primary) verified=\(.verified) vis=\(.visibility)"'
gh api user/keys --jq '.[] | "\(.id) \(.title)"'
gh api user/ssh_signing_keys --jq '.[] | "\(.id) \(.title)"'
gh api user/gpg_keys --jq '.[] | "\(.key_id) \(.emails[].email)"'

# One repository
OWNER=<owner>; R=<repo>
gh api "repos/$OWNER/$R" --jq '"\(.visibility) squash=\(.allow_squash_merge) merge=\(.allow_merge_commit) fork=\(.allow_forking)"'
gh api -i "repos/$OWNER/$R/vulnerability-alerts" | head -1   # 204 on, 404 off
gh api "repos/$OWNER/$R/rulesets" --jq '.[] | "\(.name) \(.target) \(.enforcement)"'
gh api "repos/$OWNER/$R/actions/permissions" --jq '"enabled=\(.enabled) allowed=\(.allowed_actions)"'
gh api "repos/$OWNER/$R/actions/permissions/workflow" --jq '"token=\(.default_workflow_permissions) can_approve_prs=\(.can_approve_pull_request_reviews)"'
gh api "repos/$OWNER/$R/hooks" --jq '.[] | "\(.id) \(.config.url) insecure_ssl=\(.config.insecure_ssl)"'
gh api "repos/$OWNER/$R/keys" --jq '.[] | "\(.id) \(.title) read_only=\(.read_only)"'
gh api "repos/$OWNER/$R/collaborators" --jq '.[] | "\(.login) \(.role_name)"'
```

## Cadence

- **On creating an account or repository:** the account or repository section in full.
- **Quarterly:** the audit commands on every account; sessions, keys, tokens, and apps;
  collaborators and webhooks.
- **Before any repository goes public:** the last item under private repositories.
- **After a security event:** read the security log, rotate what it touched, and add the missing
  check to this list with a one-line reason.
