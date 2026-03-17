---
name: gen-design-doc
description: Write or revise English Markdown design documents for TiProxy features, behavior changes, and architectural proposals. Use when the user asks for a TiProxy design doc, RFC, proposal, alternatives analysis, future work section, or a review-ready markdown document based on background, problems, and an initial idea.
---

# TiProxy Design Docs

Write the document in English Markdown.

Ask the user before drafting if any important fact is unclear. Do not guess about scope, current behavior, compatibility, rollout, or ownership when the answer affects the design.

## Workflow

1. Gather the minimum inputs from the user:
- Background and motivation
- Problem to solve
- Initial proposal or constraints
- Expected operators or users
- Compatibility, rollout, or performance constraints
- Open questions

2. Establish the current state before proposing changes:
- Prefer a local repo checkout if the user provides one.
- Otherwise inspect the most relevant upstream repos (often `https://github.com/pingcap/tiproxy`).
- When something is uncertain, search code first in:
  - `tidbcloud/*` GitHub org
  - `pingcap/*` GitHub org (non-cloud modules)
  - plus the official docs: https://docs.pingcap.com/tidb/dev/
- Read only the files relevant to the topic, but always check `AGENTS.md`, `README.md`, `docs/`, and the touched packages before describing current behavior.
- Distinguish verified facts from inference.
- If code and docs conflict, treat code as ground truth (docs may be stale).
- Link or cite exact files when the proposal depends on implementation details.

3. Research external systems only when it materially improves the proposal:
- Prefer official vendor docs and primary sources for ProxySQL, MariaDB MaxScale, Amazon Aurora or RDS Proxy, PolarDB Proxy, or other directly relevant systems.
- Focus on the exact design dimension under discussion, such as routing, read/write split, failover, session handling, multiplexing, health checks, load balancing, observability, auth, TLS, or config UX.
- Summarize the pattern, the tradeoff, and whether it fits TiProxy.
- Do not add competitor research just to make the document longer.

4. Draft the document around the problem and the chosen design:
- Required sections: `Background`, `Goals`, `Non-Goals`, `Proposal`, `Alternatives`, `Future Work`.
- Add sections only when they clarify the design, such as `Current State`, `Requirements`, `Detailed Design`, `Compatibility`, `Risks`, `Observability`, `Rollout`, or `Open Questions`.
- In `Alternatives`, explain why each option is not chosen.
- Keep the proposal concrete when relevant: APIs, config keys, control flow, failure handling, metrics, logs, compatibility impact, operational behavior, and migration path.
- If the design depends on existing metrics, APIs, or config keys, extract the list from code (do not invent names).
- When proposing an approach, validate feasibility against the current code paths and constraints; call out any required refactors explicitly.
- State unresolved questions explicitly instead of hiding them.

5. Create an architecture diagram with an image model when a diagram helps:
- Use an image model to generate a clean architecture diagram for the current and proposed flow.
- Base the diagram on verified components and the proposed data flow or control flow.
- If the image model is unavailable, ask the user before substituting Mermaid or ASCII.

## Writing Rules

- Write for reviewers who know distributed systems but may not know this feature.
- Prefer short paragraphs, precise headings, and explicit tradeoffs.
- Do not use the term “Session Manager” (deprecated/outdated naming).
- Headings must not use outline labels like `A1`, `A2`, etc.
- Do not split a single sentence into an unordered list; keep it as a sentence/paragraph.
- State the current pain, target outcome, and acceptance criteria early.
- Avoid vague claims such as "simple", "safe", or "industry standard" unless the document justifies them.
- If assumptions remain, add `Open Questions` instead of pretending certainty.

## Reference Map

- Use [`references/design-doc-template.md`](./references/design-doc-template.md) when starting from scratch.
- Use [`references/competitor-research-checklist.md`](./references/competitor-research-checklist.md) when comparing with other proxies.
- Use [`references/image-model-prompt-template.md`](./references/image-model-prompt-template.md) when prompting an image model for the architecture diagram.

## Repo References

- TiDB-X Premium (cluster service): https://github.com/tidbcloud/cluster-service-ng
