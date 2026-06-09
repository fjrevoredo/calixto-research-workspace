# Changelog

## 2026-06-10

- Added coordinated workspace search-state commits with locking, staged transaction recovery, and validation for `config.json`, `sources/index.json`, and source markdown files.
- Hardened `workspace_info.py` audit/show to reconcile indexed sources with on-disk files, reject path-qualified source citations such as `papers/src_001`, and surface `next_*` counter drift explicitly.
- Improved web-search UX with duplicate-match reporting, persisted scrape-failure metadata, and a `search_web.py --retry-failed` path that updates previously failed placeholder sources.
- Added Crawl4AI markdown cleanup plus low-signal classification so UI-heavy or thin pages are marked clearly instead of looking like normal research sources.
- Updated workspace research instructions to require sequential search execution, post-search verification, bare `src_NNN` citations, and manual maintenance of finding/insight counters.
