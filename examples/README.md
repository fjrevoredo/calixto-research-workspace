# Sample Workspace

This directory contains a complete, agent-synthesized Calixto Research Workspace. It demonstrates the full workflow from source collection through report generation, with every claim traceable to a source.

## What this example shows

- **Workspace structure**: a populated `config.json`, `sources/`, `notes/`, and `outputs/`
- **Mixed source types**: 5 web sources (`sources/web/`) and 3 arXiv papers (`sources/papers/`)
- **Full traceability chain**: `search -> source -> finding -> insight -> report`
- **Quality ratings**: each source in `bibliography.md` has a quality rating and notes
- **Gaps and limitations**: explicit identification of what the research does not cover

## Research Question

> What are the trade-offs of Python's asyncio for I/O-bound workloads compared to threading and multiprocessing?

The question was chosen because:

- It is a non-trivial technical question with multiple correct answers
- It has authoritative primary sources (Python docs, arXiv papers)
- It is relevant to working developers (not too academic)
- A reasonable scope: 1-2 page report, 5-10 sources

## ID Map

- `src_001` through `src_005`: web sources on asyncio (Reddit, Real Python, Python docs, blog posts, BBC engineering)
- `src_006` through `src_008`: arXiv papers (some unrelated, included to demonstrate paper sources)
- `src_009` and `src_010`: test data from an unrelated query (included to show how the workspace handles "junk" sources via quality ratings)
- `fnd_001` through `fnd_010`: findings extracted from the web sources
- `ins_001` through `ins_005`: insights synthesized from findings
- Report sections: cite `[src_NNN]` inline

## Audit Result

Running `python scripts/workspace_info.py audit sample-workspace` from the repo root should report:

- Sources in index: 10
- Sources cited in findings: 5 (the 5 web sources on asyncio)
- Sources cited in report: 5 (same as findings)
- Orphaned sources: 5 (the 3 arXiv papers and 2 unrelated web sources)
- Invalid references: 0
- ID counter valid: true
- Status: OK with warnings

The 5 orphaned sources are intentional: the agent rated them as low-quality or unrelated and chose not to cite them. This is correct behavior, not a bug.

## How this example was made

This workspace was synthesized to demonstrate the workflow. In a real session, the agent would:

1. Read `skills/deep-research.md`
2. Run `init_workspace.py sample-workspace` and set the question
3. Run `search_web.py` and `search_arxiv.py` to collect sources
4. Read each source and extract findings
5. Synthesize insights
6. Write the report with inline citations
7. Run `workspace_info.py audit` to verify

The output you see here is what that end-to-end session would produce.
