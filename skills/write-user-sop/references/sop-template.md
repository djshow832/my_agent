# <SOP Title>

Use this template only as a starting point. Remove sections that do not help the user finish the task.

## Before you begin

- What the user must already have
- The single environment or account requirement
- The exact tool or access requirement

If the user must prepare something, write the exact UI action or command.

Example:

```bash
git clone https://github.com/pingcap/tiproxy.git
cd tiproxy
make
```

## Step 1: <First user action>

Explain the first action in one short paragraph.

If the user must use a UI, write the click path.

Example:

`In the AWS Console, open <service> -> <page> -> <button>.`

If the user must run commands, show the full sequence.

```bash
<command 1>
<command 2>
```

Add one short verification cue when useful.

`You should now see <expected result>.`

## Step 2: <Next user action>

Keep the same pattern.

## Step 3: <Next user action>

Keep the same pattern.

## FAQ

### <Symptom>

Check:

- <one short check>

Fix:

- <one short fix>

### <Symptom>

Check:

- <one short check>

Fix:

- <one short fix>

## Related links

- <existing full user doc, if it already covers most of the flow>
- <official AWS doc or product doc>

## Link-First Variant

If an existing full user guide already covers the task well, do not rewrite it. Use this shorter structure instead:

### Start here

Follow this guide:

- <full user guide link>

### What you still need to do in this environment

1. <required custom step>
2. <required custom step>
3. <required custom step>

### FAQ

Only include environment-specific troubleshooting that the linked guide does not cover.
