---
name: consult-expert
description: Consult a named LastMileFirst expert lens or route a question to the relevant bundled persona for specialized advice. Supports available subagents without assuming installed Claude agents or tools.
---

# Consult an expert

Read [the operating boundaries](../lastmilefirst/SKILL.md), then use
[the shared expert routing guide](../lastmilefirst/references/consult-expert.md) to select
a domain and [the persona index](../lastmilefirst/references/personas.md) to load only the
relevant compact brief. The package contains 16 persona briefs; they are expertise lenses,
not installed agents, external people, or grants of access.

Honor a requested expert. Otherwise route by the question's primary domain; use Scout's
coordination lens when the appropriate specialist is unclear. Accept questions and pasted
artifacts without a repository. Read only supplied material and explicitly approved sources,
and identify any context gap that limits the recommendation. Do not discover private global
configuration or assume access to an organization, repository, network service, or plugin.

When the host exposes subagents and independent work would help, delegate a bounded brief
with the selected persona lens, question, approved context, constraints, and desired result.
Call the actual available host tool; canonical persona names are not tool identifiers.
If subagents are unavailable or unnecessary, respond directly and label the perspective,
for example "Archer lens". Never claim that a separate expert ran, reviewed, or agreed unless
that delegation actually occurred. Distinguish a synthesized multi-lens answer from
independent reviews, and report useful disagreements rather than manufacturing consensus.

Use the shared routing guide's designed pairings only when the question benefits from them.
For Ripley's editorial lens, follow [review-signal](../review-signal/SKILL.md) and/or
[review-voice](../review-voice/SKILL.md), including their critique-first and rewrite boundaries.
Shannon's product expertise remains Claude Code-specific; do not turn it into claims about
Codex mechanics. Verify product behavior from official documentation within permitted access,
or disclose that it is unverified when the task is offline.

Return the selected lens, recommendation, supporting reasoning or evidence, consequential
tradeoffs, and missing checks. Consultation authorizes advice, not implementation, file
changes, issue creation, installation, deployment, or external communication. Propose any
such action separately and act only within the user's authorized scope.
