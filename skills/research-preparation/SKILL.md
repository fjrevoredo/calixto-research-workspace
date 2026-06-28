---
name: research-preparation
description: "Toolkit-side handoff for Calixto research preparation. Use when starting from the toolkit root and the user's topic needs clarification, normalization, or a durable brief before source gathering. This skill triages the raw question, asks targeted clarification only when needed, creates or selects a standalone workspace boundary, writes notes/research-brief.md, and hands off to the workspace-local preparation or downstream research skill."
license: MIT
compatibility: Requires Python 3.11+, the Calixto toolkit root, and the top-level `calixto` launcher or equivalent repo-root scripts.
metadata:
  category: research
  mode: research
  version: "0.1.0"
---

# Research Preparation

Use this skill when you are at the toolkit root and the user needs the topic
normalized before research begins.

## Goal

Do the minimum front-end preparation needed to start a clean standalone
workspace with a durable brief and a research-ready question.

This is a toolkit-side handoff skill, not the canonical preparation workflow.
Use it to get the topic to the workspace boundary cleanly, then switch to the
workspace-local instructions.

## Workflow

### Step 1: Triage the raw question at the toolkit boundary

Assess the raw request for clarity, scope, intended output, domain, stakes,
time sensitivity, likely source mix, and expected uncertainty.

Choose exactly one outcome:

- proceed directly
- ask targeted clarification
- proceed with explicit assumptions

Ask clarification only when the answer would materially change:

- the scope or exclusions
- the evidence standard or source choice
- the stakes handling
- the report shape or decision criteria

Do not ask broad exploratory questions at the toolkit boundary. If the
remaining ambiguity is minor, proceed with explicit assumptions and record
them in the brief.

Before leaving this step, be able to state all of the following in one or two
sentences each:

- the refined research question
- what the user is actually trying to decide or learn
- what the final deliverable should look like
- what kind of sources will probably be needed
- whether the downstream path is `deep-research` or `literature-review`

### Step 2: Draft the brief content before workspace creation

Prepare the content that will be written into `notes/research-brief.md`.

At minimum, have concrete content for:

- original question
- refined question
- triage summary
- user intent
- intended output
- scope
- assumptions
- clarifications
- evidence plan
- report plan
- expected uncertainty
- handoff notes

Keep the refined question concise. The brief carries the fuller framing and
assumptions; `config.json.question` should stay short.

### Step 3: Create or choose the workspace boundary

Use an existing workspace only when all of these are true:

- the workspace already exists
- it already contains `skills/research-preparation/SKILL.md`
- reusing it matches the user's intent better than starting clean

Otherwise create a new standalone workspace with the refined question:

```bash
calixto research "<refined question>" --agent none
```

Do not rewrite older generated workspaces in place from the toolkit root.
If an older workspace predates this skill, prefer creating a new workspace or
continue only with an explicit user-directed manual workaround.

### Step 4: Persist the brief and question into the workspace

Inside the selected workspace:

1. Write or paste the prepared brief into `notes/research-brief.md`.
2. Ensure `config.json.question` matches the concise refined question.
3. Do a quick sanity check that the brief and `config.json.question` do not
   contradict each other.

Do not start source gathering from the toolkit root after this point.

### Step 5: Hand off to the workspace-local source of truth

Once you are inside the workspace, the canonical instructions live in:

- `AGENTS.md`
- `skills/research-preparation/SKILL.md`

Use the workspace-local `research-preparation` skill as the source of truth for
any additional preparation, validation, or refinement. Then continue with:

- `skills/deep-research/SKILL.md`, or
- `skills/literature-review/SKILL.md`

The handoff is complete only when:

- the brief exists in `notes/research-brief.md`
- `config.json.question` is aligned
- the downstream skill choice is explicit in `Handoff Notes`
- the next work happens from the workspace root, not the toolkit root
