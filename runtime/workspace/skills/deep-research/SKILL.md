---
name: deep-research
description: "Performs structured, reproducible research with full source-to-claim traceability inside a standalone Calixto workspace. Use when the user asks for a research report, comparison, literature scan, or any task that needs multiple cited sources. Workflow: confirm the workspace question, search the web and the right scholarly provider, extract findings (fnd_NNN), synthesize insights (ins_NNN), write a report with inline [src_NNN] citations, run strict traceability checks, and generate a manual citation-review artifact."
license: MIT
compatibility: Requires Python 3.11+, a standalone Calixto workspace, and the bundled search-web, search-arxiv, and workspace-info scripts in this workspace.
metadata:
  category: research
  mode: research
  version: "0.1.0"
---

# Deep Research

Use this workflow from the root of a standalone workspace.
Read this file directly from `skills/deep-research/SKILL.md`. Generic skill
loaders may not discover workspace-local skills.

## Goal

Produce a report where every claim traces back to a source URL:

```text
search query
  -> src_NNN (URL)
    -> fnd_NNN (fact extracted from that source)
      -> ins_NNN (insight synthesized from findings)
        -> report.md paragraph
```

## Scripts And Tools

Run the bundled scripts from this workspace root:

| Script | Purpose |
|---|---|
| `scripts/search_web.py` | Search the web and scrape results into this workspace |
| `scripts/search_arxiv.py` | Search arXiv and save paper metadata |
| `scripts/search_pubmed.py` | Search PubMed for biomedical and clinical literature |
| `scripts/workspace_info.py` | Show or audit this workspace |

Use `uv run python ...` if you set up the workspace with `uv`.

## Workflow

### Step 1: Confirm the workspace question and brief

Read `notes/research-brief.md` first when it is present and populated.
Use it as the operating contract for scope, intended output, evidence plan,
and obvious uncertainty.

If the topic is still raw, ambiguous, high-stakes, or missing a brief, run
`skills/research-preparation/SKILL.md` before you search unless the user has
already provided a clearly scoped question and you can proceed safely.

Set or refine the research question in `config.json` before you search.

```json
{
  "question": "What are the trade-offs between async and sync Python for I/O-bound workloads?"
}
```

Check the current workspace state:

```bash
uv run python scripts/workspace_info.py show .
```

Continue to source gathering only after the question and any needed brief are
consistent with each other.

### Step 2: Search for sources

Mix web and paper searches. Run 3-5 queries with different angles.
For biomedical, pharmacology, clinical, or safety questions, prefer
`search_pubmed.py` over `search_arxiv.py`.

Important: do not queue multiple `search_web.py` / `search_arxiv.py` commands in
one agent message. Many agents execute tool calls in parallel, which can make
the session harder to inspect even though the workspace now serializes writes.
Run searches sequentially, inspect the workspace after each search or batch,
then continue.

```bash
uv run python scripts/search_web.py "<query>" --workspace . --max-results 10
uv run python scripts/search_arxiv.py "<query>" --workspace . --max-results 5
uv run python scripts/search_pubmed.py "<biomedical query>" --workspace . --max-results 5
```

Good queries:

- the topic directly
- a specific subtopic
- a counter-perspective
- authoritative sources
- recent developments

After each search or search batch, verify that the workspace recorded it:

```bash
uv run python scripts/workspace_info.py show .
uv run python scripts/workspace_info.py audit .
```

Confirm the search count increased as expected before moving on.

### Step 3: Triage, read, and evaluate sources

Start with `sources/index.json` or `workspace_info.py show .` before opening a
large batch of files.

Prioritize sources that are not marked `low_signal`, `snippet_only`, or `error`.
Treat those low-signal markers as a triage hint, not an automatic ban.
Also inspect `quality_tier`, `quality_reasons`, and
`quality_requires_corroboration` before you promote a source into findings.

When a source is irrelevant, weak, redundant, or only useful for context, mark
it explicitly:

```bash
uv run python scripts/workspace_info.py review-source . src_NNN discarded --note "short reason"
```

Record open questions and follow-up searches in `notes/gaps.md` as you go.

Before you write the final report, every source that still matters must be in
one of three states:

- cited in at least one finding
- explicitly discarded with `review-source`
- intentionally deferred in `notes/gaps.md`

### Step 4: Extract findings

Append facts to `notes/findings.md`:

```markdown
## fnd_001
**Source:** src_003
**Fact:** ...
**Quote:** "..."
**Confidence:** high
```

Every finding must cite at least one `src_NNN`.
Use only bare `src_NNN` identifiers. Do not cite file paths such as
`papers/src_001`.

After you append findings, update `config.json` so `next_finding_id` remains
one higher than the highest finding ID present in `notes/findings.md`.

Run an audit immediately after writing findings. If the audit reports counter
drift, sync the counters before continuing:

```bash
uv run python scripts/workspace_info.py audit .
uv run python scripts/workspace_info.py sync-counters .
```

### Step 5: Synthesize insights

Append to `notes/summary.md`:

```markdown
## ins_001
**Based on:** fnd_001, fnd_002
**Insight:** ...
```

Every insight must cite at least one `fnd_NNN`.

After you append insights, update `config.json` so `next_insight_id` remains
one higher than the highest insight ID present in `notes/summary.md`.

Run the audit again after writing insights. If the audit reports counter drift,
run `workspace_info.py sync-counters .` before moving on.

### Step 6: Write the report

Write `outputs/report.md` and cite sources inline as `[src_NNN]`.
Never use `[papers/src_001]`, `[web/src_001]`, or any other path-qualified
source reference.

Keep claims proportional to the evidence quality. If evidence conflicts, say so
explicitly instead of smoothing it over.

Populate `outputs/bibliography.md` with human-readable source quality notes
before handoff.
Include quality tier and obvious conflicts or corroboration needs.

### Step 7: Audit the workspace

Run the stricter final-review commands:

```bash
uv run python scripts/workspace_info.py audit . --strict-traceability
uv run python scripts/workspace_info.py verify-citations .
```

Strict traceability will fail when:

- a report-cited source bypasses findings
- a cited source is still pending review
- a source marked `used` is uncited

Generate `outputs/citation-check.md` and complete its manual verification
fields before you hand the report back. The script surfaces candidate excerpts,
but semantic judgment stays with the agent or reviewer.
