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

## Workflow

### Step 1: Triage the raw question at the toolkit boundary

Assess the raw request for clarity, scope, intended output, domain, stakes,
time sensitivity, likely source mix, and expected uncertainty.

Choose one outcome:

- proceed directly
- ask targeted clarification
- proceed with explicit assumptions

Use the same discipline as the workspace-local preparation skill: ask only the
questions that materially change scope, source choice, stakes handling, or the
final deliverable.

### Step 2: Create or choose the workspace boundary

For a new topic, create a standalone workspace with the refined question:

```bash
calixto research "<refined question>" --agent none
```

If the workspace already exists and already contains
`skills/research-preparation/SKILL.md`, you may enter that workspace and
continue there instead of creating a new one.

Do not rewrite older generated workspaces in place from the toolkit root.
If an older workspace predates this skill, prefer creating a new workspace or
continue only with an explicit user-directed manual workaround.

### Step 3: Write the durable brief into the workspace

Write or paste the approved brief into `notes/research-brief.md` inside the
selected workspace.

The brief should capture:

- the original question
- the refined question
- the triage summary
- assumptions and clarifications
- the evidence plan
- the report shape
- the handoff choice

Keep `config.json.question` concise and aligned with the refined question.

### Step 4: Hand off to the workspace-local source of truth

Once you are inside the workspace, the canonical instructions live in:

- `AGENTS.md`
- `skills/research-preparation/SKILL.md`

Use the workspace-local `research-preparation` skill as the source of truth for
any additional preparation, then continue with:

- `skills/deep-research/SKILL.md`, or
- `skills/literature-review/SKILL.md`
