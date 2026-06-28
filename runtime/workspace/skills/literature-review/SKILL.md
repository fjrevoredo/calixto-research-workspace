---
name: literature-review
description: "Produces a structured academic literature review inside a standalone Calixto workspace with full citation tracking and methodology assessment. Use when the user asks for a literature review, related-work section, systematic survey, or scholarly analysis. Emphasizes domain-appropriate scholarly search, venue assessment, citation count, quality tiers, and explicit gaps."
license: MIT
compatibility: Requires Python 3.11+, a standalone Calixto workspace, and the bundled search-arxiv, search-web, and workspace-info scripts in this workspace.
metadata:
  category: research
  mode: research
  version: "0.1.0"
---

# Literature Review

Use this workflow from the root of a standalone workspace.
Read this file directly from `skills/literature-review/SKILL.md`. Generic skill
loaders may not discover workspace-local skills.

## Goal

Produce a structured literature review with:

- a corpus of relevant academic papers
- methodology and quality assessment
- synthesized themes, agreements, and disagreements
- explicit gaps and open questions
- full traceability from claim to paper

## Scripts And Tools

Run the bundled scripts from this workspace root:

| Script | Purpose |
|---|---|
| `scripts/search_arxiv.py` | Search arXiv for CS, math, physics, and computational topics |
| `scripts/search_pubmed.py` | Search PubMed for biomedical, pharmacology, and clinical topics |
| `scripts/search_web.py` | Web search for secondary context |
| `scripts/workspace_info.py` | Show or audit this workspace |

## Workflow

### Step 1: Confirm the question and brief

Read `notes/research-brief.md` first when it is present and populated.
Use it to confirm academic scope, evidence standard, likely scholarly
providers, and expected review structure.

If the topic is still raw, ambiguous, or unclear about corpus type, review
shape, or stakes, run `skills/research-preparation/SKILL.md` before scholarly
search unless the user already supplied a clearly scoped literature-review
question.

Update `config.json` with the research question:

```json
{
  "question": "What are the state-of-the-art methods for X, and what are their limitations?"
}
```

Continue only after the brief and `config.json.question` agree on the intended
review.

### Step 2: Choose the right scholarly provider first

Use arXiv first for CS, math, physics, and adjacent computational work.
Use PubMed first for biomedical, pharmacology, clinical, safety, and health
questions.

Run searches sequentially. Do not queue multiple `search_arxiv.py` or
`search_web.py` commands in one agent message, because many agents execute
tool calls in parallel.

```bash
uv run python scripts/search_arxiv.py "<query>" --workspace . --max-results 15 --category cs.AI
uv run python scripts/search_pubmed.py "<biomedical query>" --workspace . --max-results 15
```

Use multiple categories when relevant and run 3-5 queries that cover the main
topic, recent work, benchmark papers, and competing approaches.
For broad multi-word arXiv queries, use `--must-contain` and
`--min-query-token-overlap` to keep low-relevance lexical matches visible.

After each search batch, verify the workspace state:

```bash
uv run python scripts/workspace_info.py show .
uv run python scripts/workspace_info.py audit .
```

### Step 3: Add selective web context

Use web search for surveys, benchmark explainers, and industry commentary:

```bash
uv run python scripts/search_web.py "<query>" --workspace . --max-results 5
```

Treat these as secondary evidence unless they cite primary sources.

### Step 4: Extract findings

Append findings to `notes/findings.md` and note methodology, venue, dataset,
baseline quality, reproducibility, and obvious limitations.

Use bare `src_NNN` citations only, never file paths such as `papers/src_001`.
If a source is tangential or low-value, mark it with
`workspace_info.py review-source . src_NNN discarded --note "reason"`.
Capture source quality tier notes as you triage so the bibliography shows which
papers are authoritative, scholarly, or corroboration-required.
After writing findings, run `workspace_info.py audit .` and, if needed,
`workspace_info.py sync-counters .` so `next_finding_id` stays aligned with the
highest finding ID present.

### Step 5: Synthesize themes and gaps

Use `notes/summary.md` for recurring themes, disagreements, and open questions.

Record unresolved questions and follow-up search ideas in `notes/gaps.md`.
After writing insights, run `workspace_info.py audit .` and, if needed,
`workspace_info.py sync-counters .` so `next_insight_id` stays aligned with the
highest insight ID present.

### Step 6: Write the review

Write `outputs/report.md` with inline `[src_NNN]` citations and clear sections
for background, methods, themes, limitations, and gaps.

Populate `outputs/bibliography.md` before handoff with quality notes for the
papers and web context you kept, including quality tier and conflict notes.

### Step 7: Audit the workspace

```bash
uv run python scripts/workspace_info.py audit . --strict-traceability
uv run python scripts/workspace_info.py verify-citations .
```

Fix broken references before delivering the literature review.
