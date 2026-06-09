---
name: literature-review
description: "Produces a structured academic literature review inside a standalone Calixto workspace with full citation tracking and methodology assessment. Use when the user asks for a literature review, related-work section, systematic survey, or scholarly analysis. Emphasizes arXiv search, venue assessment, citation count, and explicit gaps."
license: MIT
compatibility: Requires Python 3.11+, a standalone Calixto workspace, and the bundled search-arxiv, search-web, and workspace-info scripts in this workspace.
metadata:
  category: research
  mode: research
  version: "0.1.0"
---

# Literature Review

Use this workflow from the root of a standalone workspace.

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
| `scripts/search_arxiv.py` | Search arXiv (primary source) |
| `scripts/search_web.py` | Web search for secondary context |
| `scripts/workspace_info.py` | Show or audit this workspace |

## Workflow

### Step 1: Set the question

Update `config.json` with the research question:

```json
{
  "question": "What are the state-of-the-art methods for X, and what are their limitations?"
}
```

### Step 2: Search arXiv first

For academic work, arXiv is the primary source.

Run searches sequentially. Do not queue multiple `search_arxiv.py` or
`search_web.py` commands in one agent message, because many agents execute
tool calls in parallel.

```bash
uv run python scripts/search_arxiv.py "<query>" --workspace . --max-results 15 --category cs.AI
```

Use multiple categories when relevant and run 3-5 queries that cover the main
topic, recent work, benchmark papers, and competing approaches.

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
After writing findings, update `config.json` so `next_finding_id` is still one
higher than the highest finding ID present.

### Step 5: Synthesize themes and gaps

Use `notes/summary.md` for recurring themes, disagreements, and open questions.

After writing insights, update `config.json` so `next_insight_id` is still one
higher than the highest insight ID present.

### Step 6: Write the review

Write `outputs/report.md` with inline `[src_NNN]` citations and clear sections
for background, methods, themes, limitations, and gaps.

### Step 7: Audit the workspace

```bash
uv run python scripts/workspace_info.py audit .
```

Fix broken references before delivering the literature review.
