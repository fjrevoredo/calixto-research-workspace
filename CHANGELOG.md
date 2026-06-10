# Changelog

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
