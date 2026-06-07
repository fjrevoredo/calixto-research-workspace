---
name: literature-review
description: Produces a structured academic literature review with full citation tracking and methodology assessment. Use when the user asks for a literature review, related-work section, systematic survey, or scholarly analysis. Emphasizes arXiv search, venue assessment, citation count, and the standard academic review format (Introduction, Methodology, Themes, Gaps, Conclusions). Heavier on papers and citation count than deep-research.
license: MIT
compatibility: Requires Python 3.11+, Calixto Research Workspace installed, and the search-arxiv and workspace-info scripts at the repo root.
metadata:
  category: research
  mode: research
  version: "0.1.0"
---

# Literature Review

The academic variant of the deep-research workflow. Produces a structured literature review with quality-rated sources, methodology assessment, and a taxonomy of themes.

## When to Use

- The user asks "what does the literature say about X?"
- The user is preparing a related-work section for a paper or thesis
- The user wants a systematic survey of a research area
- The user wants academic citations with proper attribution
- The user wants to assess methodology and quality of papers

Do NOT use this skill for quick web research, single-paper reading, or for writing the paper itself (this skill gathers sources, not drafts prose).

## Goal

Produce a structured literature review with:

- A corpus of relevant academic papers, properly cited
- An assessment of methodology and quality (venue, citations, methodology, reproducibility)
- A synthesis of themes, agreements, and disagreements
- Explicit identification of gaps and open questions
- Full traceability from claim to paper

## Scripts and Tools

This skill references scripts at the repo root, not bundled inside the skill.

| Script | Purpose |
|---|---|
| `scripts/init_workspace.py` | Create a workspace from the template |
| `scripts/search_arxiv.py` | Search arXiv (primary source) |
| `scripts/search_web.py` | Web search (secondary: blog posts, industry analyses) |
| `scripts/workspace_info.py` | List, show, audit, delete workspaces |

## Workflow

### Step 1: Initialize

Create a workspace with a slug that reflects the topic (e.g., `transformer-survey-2025`).

```bash
python scripts/init_workspace.py <slug>
```

Set the research question in `config.json`:

```json
{
  "question": "What are the state-of-the-art methods for X, and what are their limitations?"
}
```

### Step 2: Search arXiv (primary)

For academic work, arXiv is the default source. Web search is a complement, not the primary.

```bash
python scripts/search_arxiv.py "<query>" --workspace workspaces/<slug> --max-results 15 --category cs.AI
```

Use multiple arXiv categories when appropriate (cs.LG, cs.CL, stat.ML). Run 3-5 queries:

- The main topic
- Recent: "transformer 2024"
- Methods comparison
- Specific subtopic
- Benchmarks

### Step 3: Search the web (secondary)

Web search is useful for survey articles, industry analyses, citation tracking (Semantic Scholar, Google Scholar), and recent blog posts explaining a paper.

```bash
python scripts/search_web.py "transformer survey 2024" --workspace workspaces/<slug> --max-results 5
```

Save these as web sources, not as papers. They are secondary context.

### Step 4: Evaluate (academic quality)

For each paper, assess:

- **Venue**: arXiv preprint, peer-reviewed conference, journal? Peer-reviewed > preprint, but high-quality preprints are fine.
- **Citation count**: high count is a quality signal (check Semantic Scholar or Google Scholar).
- **Methodology**: are the methods described in enough detail to reproduce?
- **Reproducibility**: is the code available?
- **Recency**: for fast-moving fields, prefer <2 years; for established topics, foundational older papers are valuable.
- **Author reputation**: are the authors established in the field?

Mark each source with a quality rating in `notes/findings.md`:

```markdown
## fnd_001
**Source:** src_003
**Paper:** "Attention Is All You Need" (Vaswani et al., 2017)
**Fact:** The transformer architecture uses self-attention to model sequence dependencies without recurrence.
**Quote:** "We propose a new simple network architecture, the Transformer, based solely on attention mechanisms."
**Confidence:** high
**Quality:** high
**Venue:** NeurIPS 2017
**Citations:** 80000+
```

### Step 5: Extract findings

For each paper, extract the problem, the method, the key results, the limitations, and how it relates to other papers. Append to `notes/findings.md`.

### Step 6: Synthesize themes

Group findings by theme. A literature review typically organizes by:

- **Methods**: which approaches have been proposed?
- **Benchmarks**: which datasets and metrics are used?
- **Results**: which methods work best on which problems?
- **Limitations**: what are the open challenges?
- **Trends**: how has the field evolved?

Append to `notes/summary.md`:

```markdown
## ins_001
**Based on:** fnd_001, fnd_005, fnd_012
**Insight:** The transformer architecture has become the dominant approach for sequence modeling, but it has known scalability limitations for very long sequences [fnd_001, fnd_005]. Several recent papers (Linformer, Performer, Longformer) propose approximations to address this [fnd_012].
```

### Step 7: Write the review

Follow the standard academic structure in `outputs/report.md`:

```markdown
# A Survey of Transformer Architectures

## Abstract

One-paragraph TL;DR.

## 1. Introduction

Why this topic matters. Scope of this review. What is not covered.

## 2. Methodology

How papers were selected. Search queries used. Inclusion/exclusion criteria. Date range.

## 3. Background

Brief technical context for readers not deep in the field. Cite foundational papers.

## 4. Methods

Organize by method family. For each: representative papers, key contributions, differences.

## 5. Comparison and Benchmarks

Which methods are best on which benchmarks. Tables comparing approaches.

## 6. Limitations and Open Questions

What the field has not solved. Where the gaps are. What the next breakthroughs might address.

## 7. Conclusion

Summary of the state of the field. Recommendations for practitioners and researchers.

## References

See `bibliography.md`. Use a consistent citation style (IEEE, ACM, etc.).
```

Citation conventions for the report:

- Inline: `[src_NNN]` (Calixto ID) or `[Vaswani et al., 2017]` (human-readable)
- The bibliography file should have both: `src_NNN` and the human-readable form

Example bibliography entry:

```markdown
- **src_003** - [Attention Is All You Need](https://arxiv.org/abs/1706.03762) - Vaswani et al., 2017 - arXiv:1706.03762 - Quality: high - Foundational paper for the transformer architecture
```

### Step 8: Audit and iterate

```bash
python scripts/workspace_info.py audit <slug>
```

Refine: more searches, more findings, better synthesis. The audit ensures no broken references.

## Differences from deep-research

| Aspect | deep-research | literature-review |
|---|---|---|
| Primary source | Web | arXiv |
| Citation style | Inline `[src_NNN]` | Inline `[src_NNN]` + human-readable |
| Quality criteria | Source authority | Peer review, citation count, methodology |
| Output style | Executive report | Academic review with structured sections |
| Source types | Mostly web | Mostly papers + selective web |
| Time horizon | Recent preferred | Foundational + recent |
| Minimum sources | 5+ | 20-30+ for a real review |

## Quality Guidelines

- Aim for 20-30 high-quality sources for a proper academic review
- Include seminal / foundational papers even if old
- Note when a finding is from a single paper (low confidence) vs. multiple papers (high confidence)
- Identify the publication venue for each paper (arXiv, NeurIPS, ICML, etc.)
- Distinguish preprints from peer-reviewed work
- When papers disagree, present both views and try to explain the disagreement

## Common Pitfalls

- **Treating arXiv preprints as peer-reviewed**: they are not. Mark them as preprints.
- **Ignoring methodology**: a paper with flawed methodology should not be cited as authoritative.
- **Skipping negative results**: failed approaches are part of the literature too.
- **Citation count gaming**: high citations do not equal high quality. Some influential papers are controversial.
- **Surveying only one school of thought**: include diverse perspectives.

## See Also

- `skills/deep-research/SKILL.md`: the general workflow
- `skills/create-skill/SKILL.md`: how to create domain-specific skills
- `requirements.md` section 6.2: literature review
