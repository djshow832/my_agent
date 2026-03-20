---
name: write-user-sop
description: Write or revise an English end-user SOP in a new Feishu document based on verified sources such as existing Feishu docs, replay-tool code, and official AWS documentation. Use when the user asks for a user-facing SOP, runbook, how-to guide, step-by-step setup doc, FAQ, or a Feishu document that must be concise, source-grounded, and ordered by user actions.
---

# Write User SOP

Use this skill to produce an English SOP for end users and deliver it to a new Feishu document.

The SOP must be concise, factual, and easy to execute step by step. It is not an engineering design doc.

## Non-Negotiable Rules

- Write in English only.
- Create or update a new Feishu document. Do not stop at local markdown unless the current session cannot access Feishu.
- Before drafting the full SOP, send the user a concise outline and wait for confirmation.
- Base every operational step on verified sources only:
  - existing Feishu docs
  - replay-tool code
  - official AWS docs
  - other official user documentation when directly relevant
- Do not invent commands, UI labels, configuration keys, defaults, permissions, paths, screenshots, or expected outputs.
- Prefer one simplest path. Do not present many alternatives unless the user explicitly asks.
- Keep the SOP concise. Remove repeated explanations and overlapping cautions.
- Write for end users. Avoid internal implementation details unless the user must run a command or set a value.
- Put steps in execution order so a user can follow them from start to finish.
- Make implicit prerequisites explicit. If the user must click something in a UI or run a setup command first, write that step clearly.
- Show concrete commands and config examples when the user must execute them. Prefer full command sequences over vague prose.
- If a complete external user doc already exists, link to it instead of rewriting it. Add only the product-specific or environment-specific steps the user still must do.
- The final doc must include a short FAQ with troubleshooting steps grounded in verified sources.
- Ensure `zhangming@pingcap.com` has permission to edit and move the document. Verify this explicitly through Feishu sharing and ownership controls. Do not assume it is already true.

## Workflow

1. Clarify the target task and audience only if a missing fact would materially change the SOP. Otherwise proceed.
2. Gather sources in this order:
   - existing Feishu docs or user-provided Feishu links
   - replay-tool code and repo docs
   - official AWS docs
   - other official product docs only when needed
3. Read only the files and pages needed for the user task.
4. Establish the user flow from the sources:
   - prerequisites
   - exact commands
   - exact UI actions
   - expected checkpoints
   - failure points worth adding to FAQ
5. Decide whether the result should be:
   - a concise Feishu doc that mostly links to an existing full user guide plus a few required custom steps
   - or a full step-by-step SOP
6. Draft a short outline and send it to the user. Wait for confirmation before writing the full SOP.
7. Create a new Feishu document when full drafting starts.
8. Share the document with `zhangming@pingcap.com` and verify edit and move capability.
9. Write the SOP in the Feishu document following the required structure.
10. Run a final QA pass for accuracy, brevity, user readability, and source coverage.
11. Return the Feishu doc link and the short source list.

## Source Rules

Read [references/source-rules.md](./references/source-rules.md) before drafting.

Apply these rules:

- Prefer official or first-party sources over secondary explanations.
- When code and docs conflict about actual behavior, treat code as ground truth for behavior and docs as ground truth for user-facing wording only if they still match the code.
- If a critical step cannot be verified, do not guess. Ask the user, or state that the Feishu doc cannot be completed yet.
- Do not convert an internal implementation detail into a user instruction unless the user actually needs to perform that action.

## Feishu Delivery Rules

Read [references/feishu-delivery-checklist.md](./references/feishu-delivery-checklist.md) when creating or finishing the document.

- If the current session has no Feishu or Lark write capability, stop and tell the user that you cannot satisfy the direct-to-Feishu requirement in this session.
- If Feishu permissions cannot be changed or verified from the current toolset, stop and tell the user exactly what remains unverified.

## Required SOP Structure

Use [references/sop-template.md](./references/sop-template.md) as the base shape.

The final document should usually contain:

- Title
- Before you begin
- Step 1, Step 2, Step 3, ...
- FAQ
- Related links

Use the smallest structure that still lets the user complete the task cleanly.

## Writing Rules

- Favor short paragraphs and short step descriptions.
- Each step should tell the user exactly what to do next.
- Prefer imperative wording such as "Open", "Copy", "Run", "Verify", and "Wait".
- Include concrete command blocks when commands are required.
- Include concrete UI actions when UI work is required.
- Include a verification cue when helpful, such as what the user should see next.
- Avoid deep background sections. Add only the minimum context needed to unblock the steps.
- Do not present multiple methods. Choose one recommended path.
- Do not write redundant warnings in several places.
- Do not expose repo structure, package names, or internal architecture unless necessary for the user action.

## FAQ Rules

- Include only issues that are likely during execution and supported by verified sources.
- Format each FAQ as:
  - symptom
  - how to check
  - how to fix
- Keep each FAQ entry short and action-oriented.

## Output Back To The User

After the Feishu doc is ready, return:

- the Feishu document link
- whether `zhangming@pingcap.com` can edit and move it
- the source list used
- any unresolved verification gap, if one remains
