# Golden Dataset: Calixto Research Workspace

## Purpose

The golden dataset is a reproducible benchmark that exercises the full research pipeline end-to-end. It exists to:

1. **Validate the workflow**: prove that init -> search -> save -> audit works on a real research question.
2. **Benchmark changes**: when we change a search provider, a model, a skill, or a script, we can re-run the golden dataset and compare structurally to the baseline.
3. **Reference implementation**: agents and users can see what a completed workspace looks like.

The question, search queries, and expected structural properties are all fixed. Only the upstream search results and the agent's synthesis may vary.

## Research Question

> What are the best open-source LLMs for local deployment in 2025?

### Why this question?

- **Stable**: the topic of "open-source LLMs" has been a major category for multiple years, so the question is unlikely to become meaningless.
- **Non-trivial**: requires multiple search angles (top models, hardware requirements, recent releases, benchmarks).
- **Demonstrates the full pipeline**: needs web search, arXiv search, synthesis, and citations.
- **Repeatable**: structural evaluation (source count, section coverage, citation coverage) is meaningful; the specific models listed will evolve but the question structure remains.

## File Layout

```
tests/golden/
|-- README.md           # This file
|-- config.json         # Fixed research parameters (question, queries, etc.)
|-- cache/              # Cached search results (provider + query_hash.json)
|-- expected/           # Structural assertions for evaluation
|   |-- source_count_range.json
|   |-- report_sections.json
|   `-- quality_checks.json
|-- run.py              # Execute the full golden dataset workflow
|-- compare.py          # Compare two golden runs structurally
`-- runs/               # Historical run results (timestamped subdirectories)
```

## How to Run

### Fresh run (calls live search providers)

```bash
python tests/golden/run.py --clear-cache
```

This will:

1. Load `tests/golden/config.json`
2. Create a new timestamped workspace
3. Execute each search in the config (web + arXiv)
4. Save the complete workspace to `tests/golden/runs/<timestamp>/`
5. Run `workspace_info.py audit` on the result
6. Print a summary

### Reproducible run (uses cached search results)

```bash
python tests/golden/run.py --use-cache
```

This is the fast path. It uses cached search results, so it does not hit the network. The full search-and-save flow still runs, exercising the persistence layer.

### Compare two runs

```bash
python tests/golden/compare.py tests/golden/runs/run-A tests/golden/runs/run-B
```

Compares two runs structurally. Exits 0 if all checks pass within tolerance, 1 if any check fails.

## Reproducibility Strategy

Web search is inherently non-deterministic. We accept "similar" not "identical" results:

- **Search results are cached** in `tests/golden/cache/`. The first run populates the cache. Subsequent runs with `--use-cache` use the cache, producing identical results.
- **Evaluation is structural**, not content-based. We check that the report has the expected sections, that the source count is within range, that citations are present. We do not check exact wording.
- **Each run is timestamped** under `tests/golden/runs/`, so we can compare historical runs to detect drift.

## Evaluation Criteria

See `tests/golden/expected/` for the structural assertions. The criteria are:

| Criterion | Tolerance | File |
|---|---|---|
| Source count | min-max range | `source_count_range.json` |
| Report sections | all required sections present | `report_sections.json` |
| Unique domains | >= minimum | `quality_checks.json` |
| Citation coverage | >= minimum | `quality_checks.json` |
| All IDs valid | 100% | `quality_checks.json` |
| No duplicate URLs | 0 | `quality_checks.json` |
| ID counter valid | exact match | `quality_checks.json` |

These are all structural checks, not content checks. The full specification is in `requirements.md` section 10.4.

## Extending the Dataset

To add a new golden question:

1. Add a new entry to `tests/golden/config.json` (or create a sibling config)
2. Update `tests/golden/expected/` to reflect the new question's structural expectations
3. Update this README
4. Run a fresh baseline and document it in the "Results" section below

## Results

### First Run

| Date | Provider | Sources collected | Cache | Notes |
|---|---|---|---|---|
| 2026-06-06 | duckduckgo + arxiv | 18 | none | Baseline run |

For the full report excerpt and observations, see `tests/golden/runs/first-run-20260606/REPORT_NOTES.md` after a fresh run is completed.

## See Also

- `requirements.md` section 10: Golden dataset specification
- `skills/deep-research/SKILL.md`: the toolkit-side handoff into the standalone research workflow
- `scripts/workspace_info.py audit`: the traceability check used in evaluation
