---
name: research-preparation
description: "Normalizes a raw or underspecified research topic inside a standalone Calixto workspace before source gathering. Use when the question is ambiguous, too broad, high-stakes, time-sensitive, subjective, or missing a clear output shape. The workflow triages the request, asks targeted clarification only when needed, writes notes/research-brief.md, updates config.json.question when approved or safely assumed, and then hands off to deep-research or literature-review."
license: MIT
compatibility: Requires Python 3.11+, a standalone Calixto workspace, and the bundled workspace-local files in this directory.
metadata:
  category: research
  mode: research
  version: "0.1.0"
---

# Research Preparation

Use this workflow from the root of a standalone workspace before you gather
sources for a new or underspecified topic.

## Goal

Turn a raw topic into a research-ready operating contract:

- a refined question in `config.json` when refinement is approved or safely assumed
- a complete `notes/research-brief.md`
- a clear handoff into `deep-research` or `literature-review`

Do not start source gathering until the brief is complete enough to guide it.

## Workspace Inputs

Review these workspace-local files first:

- `config.json`
- `notes/research-brief.md`
- `AGENTS.md`

Use the workspace state command only as an inspection aid:

```bash
uv run python scripts/workspace_info.py show .
```

## Phase 1: Triage The Question

Start from the user's latest request and the current `config.json.question`.
Evaluate the topic across these dimensions:

- clarity of the core question
- scope and boundaries
- intended outcome or decision
- domain and likely evidence types
- stakes or harm if the framing is wrong
- time sensitivity or need for current information
- subjectivity versus factual answerability
- expected uncertainty or contested areas
- source needs, including authoritative or scholarly requirements
- report shape, comparison axes, or deliverable format

Choose exactly one triage outcome:

1. Proceed directly:
   Use this when the question is already specific enough to search and the
   expected output is obvious.
2. Ask targeted clarification:
   Use this only when an answer would materially change scope, source choice,
   stakes handling, or the final deliverable.
3. Proceed with explicit assumptions:
   Use this when the remaining ambiguity is low-risk and a reasonable default
   is obvious. Record the assumptions in the brief and state them clearly.

Clarification policy:

- Ask the smallest number of questions needed for correctness.
- Ask about missing decision-critical information, not general curiosity.
- Prefer proceeding with explicit assumptions over blocking on minor ambiguity.
- For high-stakes health, safety, legal, or financial topics, be more willing
  to clarify scope and intended use before searching.

Examples:

- Simple medical self-care:
  If the user asks a general question such as "What helps with mild sunburn?",
  route the evidence plan toward authoritative clinical sources and document
  red-flag symptoms or escalation criteria. Do not give personalized medical
  advice or pretend the question is low-stakes if symptoms, dosage, or
  vulnerable populations are unclear.
- Broad philosophical question:
  If the user asks "What is a good life?", narrow the intended output before
  searching. A comparative survey of schools of thought needs a different brief
  from a practical decision aid.
- Open-ended business strategy:
  If the user asks "How should we enter this market?", clarify geography,
  customer segment, timeframe, and success metric if those choices would change
  the sources or recommendation criteria. Otherwise proceed with explicit
  assumptions and record them.

## Phase 2: Write The Research Brief

Populate `notes/research-brief.md` completely enough that another agent could
continue without rereading the original chat.

At minimum, fill in:

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

Update `config.json.question` only when the refined question is either:

- explicitly approved by the user, or
- a safe, low-risk refinement that follows directly from the request and the
  assumptions you documented

Keep `config.json.question` concise. Put the fuller reasoning in
`notes/research-brief.md`, not in `config.json`.

## Phase 3: Choose The Downstream Skill

End the preparation pass with a deliberate handoff:

- use `skills/deep-research/SKILL.md` for mixed-source, market, product,
  policy, technical, or general research
- use `skills/literature-review/SKILL.md` for paper-heavy scholarly work,
  especially when methodology and academic corpus quality matter

Record the chosen path in `notes/research-brief.md` under `Handoff Notes`.
