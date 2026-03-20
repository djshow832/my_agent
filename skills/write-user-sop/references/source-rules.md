# Source Rules

Use verified sources only. This skill is for user-facing SOPs, so every operational step must be traceable to a source.

## Source Priority

1. Existing Feishu docs that already describe the user flow
2. Replay-tool code and repo docs for exact commands, flags, paths, and behavior
3. Official AWS docs for cloud-side setup and UI actions
4. Other official product docs only when the first three do not fully cover the task

## What Counts As Valid Evidence

- Existing user documentation
- Official vendor documentation
- Source code
- Checked-in examples or scripts in the relevant repo
- Exact UI labels or flows from official docs

## What Does Not Count

- Memory of how the system probably works
- Internal assumptions not backed by code or docs
- Old notes that cannot be verified
- Generic cloud advice that does not match the actual task

## When To Link Instead Of Rewrite

Link to an existing document when all of these are true:

- it is already a complete user guide
- it is still accurate
- it matches the user's target workflow closely

Then write only:

- the environment-specific prerequisites
- the exact custom commands or config values the user must use here
- the FAQ items that are specific to this workflow

## How To Extract User Steps From Code

Use code to verify:

- required binaries or repos
- exact commands and flags
- config keys and accepted values
- environment variables
- file paths that the user must touch
- checkpoints or expected outputs that can be safely shown to users

Do not expose internal-only implementation details unless they directly change the user action.

## Resolving Conflicts

- If code and docs conflict on behavior, treat code as the source of truth for behavior.
- If UI wording is needed, prefer the official current user doc or console flow.
- If a conflict affects the user's steps and cannot be resolved, stop and ask instead of guessing.

## Brevity Rules

- Keep one simplest path.
- Remove repeated explanations.
- Convert background into steps only when the background is required to avoid user error.
- Prefer one strong example over several variants.

## FAQ Scope

Add an FAQ item only if it is:

- likely to happen during execution
- supported by the sources
- actionable for the user
