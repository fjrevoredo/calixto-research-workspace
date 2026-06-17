# ADR 002: Strict Traceability, Citation Checks, and Biomedical Routing

## Status

Accepted

## Date

2026-06-17

## Context

The methylene-blue retrospective exposed four gaps that structural workspace
audits alone did not catch:

1. Report citations could bypass `notes/findings.md` while still looking
   structurally valid.
2. Final report claims needed a deterministic pre-handoff verification aid, but
   the toolkit cannot solve that with LLM calls inside scripts.
3. Agents needed a clearer evidence-quality signal before promoting sources
   into findings and reports.
4. Biomedical literature questions were being routed to arXiv even when PubMed
   was the better scholarly source.

These gaps had to be addressed without breaking the toolkit's file-based,
agent-first contract or rewriting existing workspaces in place.

## Decision

We introduced four coordinated changes:

1. `workspace_info.py audit` now reports `report_sources_not_in_findings`, and
   `--strict-traceability` promotes report-only citations, unresolved pending
   cited-source review, and used-but-uncited sources into deliberate failures.
2. `workspace_info.py verify-citations` generates
   `outputs/citation-check.md`, a deterministic manual review artifact that
   lists cited report lines, source metadata, and lexical excerpt candidates.
   The script prepares review; it never claims semantic correctness.
3. Source collection scripts now assign deterministic quality metadata:
   `quality_tier`, `quality_reasons`, and
   `quality_requires_corroboration`.
4. Biomedical scholarly search is routed through a dedicated
   `search_pubmed.py` workflow, while `search_arxiv.py` warns for likely
   biomedical queries and exposes basic relevance controls for broad lexical
   matches.

## Consequences

### Positive

- Final-report traceability can be enforced deliberately without breaking
  exploratory or partial runs by default.
- Citation verification stays deterministic, local, and file-based.
- Agents see evidence-quality and corroboration prompts before report writing.
- Biomedical research workflows have an account-free path that is better suited
  than arXiv for clinical and pharmacology questions.

### Tradeoffs

- Source quality tiers are heuristic and sometimes conservative.
- Citation verification still requires agent or human judgment; scripts only
  narrow the review surface.
- arXiv now exposes more flags and warnings, which slightly increases script
  complexity.

## Rejected Alternatives

- Automatically verifying semantic citation correctness with embeddings or LLM
  calls inside scripts. Rejected because it violates the toolkit's
  no-LLM-in-scripts rule and would create false confidence.
- Making strict traceability the default audit mode immediately. Rejected
  because existing exploratory and collection-only workspaces would become
  invalid overnight.
- Replacing arXiv globally with PubMed. Rejected because arXiv remains the
  right primary scholarly source for CS, math, physics, and computational
  topics.
