# Changelog

## 2026-06-21

- Added the toolkit-only `research-retrospective` meta-skill for independent
  adversarial workspace review, a report-derived non-leading questionnaire for
  the original research agent, and synthesis of the returned answers into
  concrete Calixto improvements. The user mediates the cross-session file
  handoff, and the skill remains outside the standalone workspace runtime
  bundle.

## 2026-06-20

- Added the top-level `calixto` CLI with `research`, `open`, and `runtime` commands so the default workflow is one command instead of manual `init_workspace.py` + `cd` + workspace-local setup.
- Added toolkit-local managed runtimes under `.calixto/`, keyed from the bundled workspace dependency files plus host compatibility dimensions, with runtime listing and pruning support.
- Updated toolkit setup to prepare the current managed runtime eagerly, install a context-aware `calixto` launcher instead of a checkout-bound shim, and replace forced `crawl4ai-setup` browser reinstall behavior with a shared runtime probe plus conditional Chromium installation.
- Added `scripts/runtime_probe.py` to both toolkit and workspace runtimes so root and standalone setup paths verify the actual scraper/browser runtime consistently.
- Added supported harness preparation and launch paths for OpenCode, Claude Code, and Codex, including generated project skill mirrors while preserving canonical bundled skills under `skills/`.
- Remediated philosophy-contract gaps in the streamlined CLI by making harness mirror refresh non-destructive by default, adding explicit JSON mode coverage for `research`, `open`, `runtime list`, and `runtime prune`, and replacing the root-bound global launcher with a context-discovering dispatcher.
- Fixed toolkit updates in installed roots with existing `workspaces/` trees so the installer no longer recursively hashes every protected workspace file before and after update, which could make Windows updates appear stuck after clone.

## 2026-06-17

- Added a pre-create toolkit freshness check to `scripts/init_workspace.py`, including interactive update prompts, non-interactive control flags, and git-derived toolkit commit/build metadata stamped into new workspace `config.json` files.
- Added `workspace_info.py audit --strict-traceability` plus `report_sources_not_in_findings` reporting so final-report citations that bypass findings, unresolved pending sources, and used-but-uncited sources can fail deliberately.
- Added `workspace_info.py verify-citations` to generate `outputs/citation-check.md`, a deterministic manual citation-review checklist with cited report lines, source metadata, and lexical excerpt candidates.
- Added deterministic source quality tier metadata (`quality_tier`, `quality_reasons`, `quality_requires_corroboration`) across web, arXiv, and PubMed source collection, and surfaced tier counts in workspace summaries.
- Added `search_pubmed.py` for biomedical literature search via NCBI E-utilities, with shared workspace IDs, caching, and standalone-runtime bundling.
- Added biomedical-topic warnings and relevance controls to `search_arxiv.py`, including `--must-contain` and `--min-query-token-overlap`.
- Updated runtime skills, workspace docs, templates, and golden comparison metrics to require strict final-report traceability and manual citation verification for finished reports.

## 2026-06-10

- Added coordinated workspace search-state commits with locking, staged transaction recovery, and validation for `config.json`, `sources/index.json`, and source markdown files.
- Hardened `workspace_info.py` audit/show to reconcile indexed sources with on-disk files, reject path-qualified source citations such as `papers/src_001`, and surface `next_*` counter drift explicitly.
- Improved web-search UX with duplicate-match reporting, persisted scrape-failure metadata, and a `search_web.py --retry-failed` path that updates previously failed placeholder sources.
- Added Crawl4AI markdown cleanup plus low-signal classification so UI-heavy or thin pages are marked clearly instead of looking like normal research sources.
- Updated workspace research instructions to require sequential search execution, post-search verification, bare `src_NNN` citations, and manual maintenance of finding/insight counters.

## 2026-06-11

- Added `workspace_info.py sync-counters` so finding and insight counters can be synchronized from note contents without hand-editing `config.json`.
- Added structured source review state plus `workspace_info.py review-source` so uncited sources can be distinguished as pending, discarded, or used instead of showing up as ambiguous orphan warnings.
- Added soft `max_sources` overrun reporting in `workspace_info.py show` and `workspace_info.py audit`.
- Filtered obviously invalid DuckDuckGo result URLs before they reach the scrape pipeline.
- Updated bundled runtime docs and seed note templates so workspace-local skill loading, counter sync, source triage, gaps, bibliography, and canonical underscore ID formats are all documented consistently.
