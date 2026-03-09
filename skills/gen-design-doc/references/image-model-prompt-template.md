# Image Model Prompt Template

Use this as a starting point when requesting an architecture diagram from an image model.

```text
Create a clean technical architecture diagram on a light background.

Subject:
- TiProxy design for <feature name>

Include these verified components:
- <component 1>
- <component 2>
- <component 3>

Show these flows:
- <client request flow>
- <control or metadata flow>
- <failure or fallback flow, if relevant>

Style requirements:
- professional engineering diagram
- clear labeled boxes and arrows
- minimal decoration
- consistent spacing and alignment
- no invented components
- readable text at document scale

Optional callouts:
- <callout 1>
- <callout 2>
```

Before sending the prompt, replace placeholders with components and flows verified from TiProxy code, docs, and the proposal.
