---
name: deep-research
description: "Performs structured, reproducible research with full source-to-claim traceability. Use when the user asks for a research report, comparison, literature scan, or any task that needs multiple cited sources. Workflow: create workspace, search the web and arXiv, extract findings (fnd_NNN), synthesize insights (ins_NNN), write a report with inline [src_NNN] citations, audit the traceability chain. Works for any topic: consumer advice, technical research, competitive analysis, background reading."
license: MIT
compatibility: Requires Python 3.11+, Calixto Research Workspace installed, and the deep-research, search-web, search-arxiv, and workspace-info scripts at the repo root.
metadata:
  category: research
  mode: research
  version: "0.1.0"
---

# Deep Research

The 7-step research workflow used by Calixto to produce a cited report from a question. Follow the steps in order; iterate if gaps appear.

## When to Use

- The user asks for a research report, comparison, or analysis of options
- The user wants multiple cited sources backing a claim
- The user wants literature or background on any topic
- The user asks "research X" or "find out about Y"

Do NOT use this skill for single lookups ("what is the capital of X"), code-only tasks, or when the user only wants their own context synthesized.

## Goal

Produce a report where every claim traces back to a source URL:

```
search query
  -> src_NNN (URL)
    -> fnd_NNN (fact extracted from that source)
      -> ins_NNN (insight synthesized from findings)
        -> report.md paragraph
```

## Scripts and Tools

This skill references scripts at the repo root, not bundled inside the skill. Run them with `python scripts/<name>.py ...`.

| Script | Purpose |
|---|---|
| `scripts/init_workspace.py` | Create a workspace from the template |
| `scripts/search_web.py` | Search the web and scrape results into a workspace |
| `scripts/search_arxiv.py` | Search arXiv and save paper metadata |
| `scripts/workspace_info.py` | List, show, audit, delete workspaces |

## Workflow

### Step 1: Initialize the workspace

If the user has not already created a workspace, create one. The slug should be lowercase, hyphen-separated, 2-64 characters (e.g. `python-asyncio`, `best-gpu-2025`).

```bash
python scripts/init_workspace.py <slug>
```

Then set the research question in the workspace's `config.json`:

```json
{
  "question": "What are the trade-offs between async and sync Python for I/O-bound workloads?"
}
```

Verify the workspace is set up:

```bash
cat workspaces/<slug>/config.json
```

### Step 2: Search for sources

Mix web and paper searches. Run 3-5 queries with different angles. Good queries:

- The topic directly: "python asyncio best practices"
- A specific subtopic: "asyncio vs threading performance"
- A counter-perspective: "python asyncio limitations"
- Authoritative sources: "PEP 3156 asyncio"
- Recent: "asyncio 2025"

**Web search:**

```bash
python scripts/search_web.py "<query>" --workspace workspaces/<slug> --max-results 10
```

**arXiv search (for technical or academic topics):**

```bash
python scripts/search_arxiv.py "<query>" --workspace workspaces/<slug> --max-results 5
```

Each search assigns sequential `src_NNN` IDs and saves results to `sources/web/` or `sources/papers/`. Dedup is automatic. If results are poor, refine the query. If a search returns 0 results, try a broader query.

### Step 3: Evaluate the sources

After collecting 10-20 sources, read their frontmatter and skim the content. Assess each source for:

- **Relevance**: does it actually address the research question?
- **Authority**: reputable source? (peer-reviewed > official docs > reputable blog > random blog > SEO spam)
- **Recency**: for fast-moving topics, prefer <2 years old
- **Bias**: clear agenda?

Skip sources that fail these checks. Note what you were looking for but did not find in `notes/gaps.md`.

### Step 4: Extract findings

For each relevant source, extract 1-5 key facts. Append to `notes/findings.md`:

```markdown
## fnd_001
**Source:** src_003
**Fact:** The asyncio library was added to Python's standard library in 3.4 (PEP 3156).
**Quote:** "asyncio is a library to write concurrent code using the async/await syntax."
**Confidence:** high
```

Rules:

- Every finding MUST reference at least one source ID
- Use `Confidence: high|medium|low` based on source quality and directness
- Quote the source verbatim when possible
- Be specific. "Python is good" is not a finding. "asyncio.run() added in 3.7 replaced asyncio.get_event_loop()" is.

If a source has many findings, give them separate `fnd_NNN` entries. Do not bundle unrelated facts.

### Step 5: Synthesize insights

Read the findings. Group them by theme. For each theme, write an insight that connects 2+ findings into a higher-level claim. Append to `notes/summary.md`:

```markdown
## ins_001
**Based on:** fnd_001, fnd_005
**Insight:** For I/O-bound workloads in Python, asyncio provides better scalability than threading because of the GIL and lower per-task memory overhead [fnd_001, fnd_005].
```

Rules:

- Every insight MUST reference at least one finding ID
- Insights should connect, not just list. "X is true. Y is true." is not an insight. "X and Y together imply Z" is.
- Aim for 5-15 insights total

### Step 6: Generate the report

Write the final report to `outputs/report.md`. Cite sources inline:

```markdown
# Python asyncio vs threading for I/O-bound workloads

## Summary

For I/O-bound workloads, asyncio generally outperforms threading in Python due to the GIL and lower per-task overhead [src_001, src_003]. However, threading is still preferable when working with libraries that lack async support [src_005].

## Background

The asyncio library was added to Python's standard library in 3.4 [src_001]. ...

## Findings

### Performance characteristics

In benchmark tests on a 4-core machine, asyncio handled 10,000 concurrent HTTP requests in 2.3s, compared to 18.7s for threading [src_003].

## Recommendations

For new projects with I/O-bound workloads, use asyncio if the ecosystem supports it [src_001]. For legacy code or libraries without async, threading remains the pragmatic choice [src_005].
```

Rules:

- Every factual claim MUST reference at least one source ID as `[src_NNN]`
- Use multiple source IDs when a claim is supported by several sources: `[src_001, src_003]`
- 5-10 paragraphs is usually the right length
- Quality over quantity

Also generate `outputs/bibliography.md`:

```markdown
- **src_001** - [Python asyncio docs](https://docs.python.org/3/library/asyncio.html) - Quality: high - Notes: official Python documentation
- **src_002** - [Real Python asyncio tutorial](https://realpython.com/async-io-python/) - Quality: high - Notes: comprehensive tutorial
```

### Step 7: Iterate and audit

Run the audit to verify the traceability chain:

```bash
python scripts/workspace_info.py audit <slug>
```

If the audit reports issues, fix them:

- Orphaned sources (collected but never cited) -> either cite them or remove
- Invalid references -> fix the IDs in the notes/report

If the report is incomplete:

- Run additional searches with refined queries
- Extract more findings from sources you have
- Synthesize new insights

If the report is sufficient, present it to the user. Mention any gaps explicitly (in `notes/gaps.md` and/or in the report's "Limitations" section).

## Decision Criteria

- **Minimum sources**: 5+ for non-trivial questions
- **Minimum findings**: 5+
- **Minimum insights**: 3+ that connect findings
- **Report length**: 500-2000 words for most questions
- **Citation coverage**: at least 80% of sources should be cited somewhere

## When to Stop

You are done when:

1. The research question is answered
2. The report has at least 5 cited sources
3. The traceability chain is complete (audit passes)
4. The user has been told what the report is and where to find it

## Common Pitfalls

- **Hallucinated IDs**: Always check that the source ID you reference actually exists in `sources/index.json`. Do not invent `src_NNN` IDs.
- **Uncited claims**: Every sentence in the report should be either a citation, a transition, or a clearly-marked synthesis.
- **Skipping the audit**: Run `workspace_info.py audit` before declaring the research done.
- **Too many sources**: 50 sources is not better than 10 high-quality ones. Be selective.
- **Too few sources**: 2 sources is rarely enough for a non-trivial question.

## Output Convention

All scripts print structured JSON to stdout.

- Success: `{"status": "ok", "sources_added": N, "source_ids": [...], ...}`
- Partial: `{"status": "partial", "sources_added": N, "errors": [...], ...}`
- Error: `{"status": "error", "error": "<type>", "message": "..."}` to stderr

## Workspace Conventions

- Sources go in `sources/web/`, `sources/papers/`, `sources/code/`
- Findings go in `notes/findings.md`
- Insights go in `notes/summary.md`
- Gaps go in `notes/gaps.md`
- Report goes in `outputs/report.md`
- Bibliography goes in `outputs/bibliography.md`

## Examples

A minimal end-to-end session: `examples/sample-workspace/` in the Calixto repo.

## See Also

- `skills/literature-review/SKILL.md`: the academic variant
- `skills/integrate-tool/SKILL.md`: how to add a new search or scrape provider
- `requirements.md` section 6.1: the deep-research skill specification
