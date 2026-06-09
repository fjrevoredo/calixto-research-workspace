# Decision Log: Initial Implementation Plan

## Purpose

This log captures all decisions made during implementation that were not part of the original plan. The plan cannot anticipate every constraint, ambiguity, or discovery. This log is the authoritative record of those in-flight decisions.

## When to Use

Add a decision log entry whenever you:

- Make a choice that the plan does not specify (for example, which Python library to use for a helper function, which file structure to adopt, which error message format to use)
- Interpret an ambiguous requirement in `requirements.md` (for example, "what counts as a valid slug for workspace names?")
- Discover a constraint not anticipated by the plan (for example, "Crawl4AI requires Python 3.10+ on Windows")
- Need to deviate from the plan's specified approach (for example, "Plan says use X, but X doesn't work in environment Y, so using Z instead")
- Change scope, validation criteria, or exit criteria of a task
- Make a tradeoff between competing concerns (for example, performance vs. simplicity, completeness vs. time)

Do NOT add entries for:

- Routine implementation choices that are obvious from context (for example, "I used a for loop to iterate over the list")
- Decisions already specified in the plan or requirements.md
- Decisions that should be elevated to a full ADR

## Entry Format

Each entry must use this structure:

```markdown
## Decision NNN: <Short title>

- **Date:** YYYY-MM-DD
- **Task:** <Task ID and name>
- **Milestone:** <Milestone name>
- **Decision:** <What was decided. Be specific.>
- **Rationale:** <Why this decision was made. What alternatives were considered? What constraints drove the choice?>
- **Impact:** <What does this affect? Does it change other tasks, validation, or the plan?>
```

## Current Entries

## Decision 001: Use pathlib.Path for all file and path operations

- **Date:** 2026-06-06
- **Task:** Task 2.1: Implement init_workspace.py (and by extension all scripts)
- **Milestone:** Milestone 1: Foundation (M0) / Milestone 2: MVP: Search and Persist (M1)
- **Decision:** All Python scripts and providers use `pathlib.Path` for file and path operations instead of `os.path` string-based functions.
- **Rationale:** pathlib provides a modern, object-oriented API that is more readable and less error-prone than string-based os.path operations. It also handles cross-platform path separators (Windows backslash vs Unix forward slash) automatically. Considered: os.path (older, string-based, harder to read), pathlib (chosen), custom path utilities (rejected: reinvention).
- **Impact:** All scripts that create or check file paths must use pathlib. This is a coding standard for the entire toolkit, not a plan change.

## Decision 002: Installer uses .calixto-backup-<timestamp> for backups, not user-controllable backup directory

- **Date:** 2026-06-06
- **Task:** Task 1.10: Create install.sh / Task 1.11: Create install.ps1
- **Milestone:** Milestone 1: Foundation (M0)
- **Decision:** Backups created by the installer are stored in a hidden directory `.calixto-backup-<timestamp>` inside the workspace. The backup path is not user-configurable. The backup is preserved at the end of every update.
- **Rationale:** The plan said "backup before updating" but did not specify a location. Putting the backup inside the workspace keeps it discoverable if the user wants to roll back, and hidden-by-default (leading dot) keeps it out of the way during normal use. Considered: external backup directory (rejected: harder to find, less obvious), in-workspace but visible (rejected: clutters `ls` output), timestamped hidden directory (chosen: balance of discoverability and tidiness).
- **Impact:** Users updating an existing workspace will accumulate `.calixto-backup-*` directories. A future cleanup task may add an `--prune-backups` flag, but for v0.1.0 the user can delete old backups manually.

## Decision 003: Use hatchling as the build backend instead of setuptools

- **Date:** 2026-06-06
- **Task:** Task 1.4: Create pyproject.toml
- **Milestone:** Milestone 1: Foundation (M0)
- **Decision:** `pyproject.toml` uses `hatchling` as the build backend (via the standard `[build-system]` table), not setuptools or flit.
- **Rationale:** hatchling is the modern, fast, standards-compliant build backend that the `uv` ecosystem recommends. It supports `[tool.hatch.build.targets.wheel.force-include]` cleanly, which we need to ship the `templates/`, `skills/`, `docs/`, and `examples/` directories inside the wheel (they are data, not Python packages). Considered: setuptools (rejected: more boilerplate, slower, less aligned with uv), flit (rejected: less flexible for non-Python data files), hatchling (chosen: clean, fast, modern).
- **Impact:** Building and publishing a wheel works out of the box. The `pyproject.toml` references `hatch.build` for include rules. Users running `uv sync` or `pip install .` get the data files in the correct location.

## Decision 004: Search and scrape providers are pure-Python, no daemon processes

- **Date:** 2026-06-06
- **Task:** Task 1.7: Create Provider Interface Base Classes
- **Milestone:** Milestone 1: Foundation (M0)
- **Decision:** Both SearchProvider and ScrapeProvider interfaces are synchronous and stateless. The Crawl4AI provider handles async internally (AsyncWebCrawler) but exposes a sync `scrape()` method to callers.
- **Rationale:** Per the "no servers or daemons" non-negotiable, our providers must be run-and-exit. The sync interface makes them composable in scripts and tests without requiring asyncio context. Crawl4AI is async under the hood, but the public interface stays sync. Considered: full async (rejected: more complex for script callers, harder to test), thread pool wrappers (rejected: hidden complexity), sync interface with internal async (chosen: simple to call, idiomatic to implement).
- **Impact:** All scripts can call `provider.scrape(url)` and `provider.search(query, n)` without async/await. Tests are simpler. The `Crawl4AIProvider` is the only place that needs to bridge sync/async, and it does so cleanly with `asyncio.run`.

## Decision 005: Use `ddgs` package (renamed from `duckduckgo-search`) for the default search provider

- **Date:** 2026-06-06
- **Task:** Task 2.2: Implement DuckDuckGo Search Provider
- **Milestone:** Milestone 2: MVP: Search and Persist (M1)
- **Decision:** Depend on `ddgs` (>=9.0.0) in `pyproject.toml` rather than the legacy `duckduckgo-search` package. The DuckDuckGoProvider class imports from `ddgs` first, with a fallback import from `duckduckgo_search` for older installs.
- **Rationale:** The `duckduckgo-search` package was renamed to `ddgs` in 2025. Newer installs of `duckduckgo-search` emit a `RuntimeWarning` recommending `ddgs`. The package on PyPI is the same project, just renamed. Considered: pinning to the old name (rejected: deprecated, prints warnings), hard-failing on the old name (rejected: unnecessary break for existing users), dual-import with `ddgs` primary (chosen: forward-compatible without breaking legacy).
- **Impact:** `pyproject.toml` lists `ddgs` as the dependency. Users running fresh installs get `ddgs`; existing users with `duckduckgo_search` already installed keep working. The `DuckDuckGoProvider` is a thin wrapper that handles both import paths transparently.

## Decision 006: arXiv cache has a manual `build_arxiv_cache.py` workaround

- **Date:** 2026-06-06
- **Task:** Task 4.3: Create Golden Dataset Runner Script
- **Milestone:** Milestone 4: Golden Dataset (M3)
- **Decision:** Provide `tests/golden/build_arxiv_cache.py`, a one-off helper that parses a downloaded arXiv API XML response and writes a properly formatted cache file. The helper looks for the XML at `C:\Users\Francisco\AppData\Local\Temp\opencode\arxiv.xml` (or `/tmp/arxiv.xml` on Unix) and writes to `tests/golden/cache/arxiv/<sha256-key>.json`.
- **Rationale:** The arXiv API was unresponsive (TCP timeout) from the build environment during the first golden run. The Python `arxiv` package's `Client.results()` blocked indefinitely. A direct `curl` to the arXiv HTTP API worked. Rather than blocking the build on a network issue, we documented the manual workflow: the user runs curl, then `build_arxiv_cache.py` writes the cache file in the format the runner expects. Considered: switching to direct HTTP in the script (rejected: adds complexity, the `arxiv` package is the long-term solution), failing the build (rejected: not a code defect), providing a manual helper (chosen: pragmatic, documented, and lets the build complete).
- **Impact:** The golden runner continues to use the `arxiv` Python package. The `build_arxiv_cache.py` helper is a tool for the maintainer, not a runtime dependency. The first golden run's notes document the workflow. Future runs from a healthy environment will not need it.

## Decision 007: Sample workspace intentionally contains unrelated sources to demonstrate quality rating

- **Date:** 2026-06-06
- **Task:** Task 5.6: Create Sample Completed Workspace
- **Milestone:** Milestone 5: Extensibility and Polish (M4)
- **Decision:** The sample workspace at `examples/sample-workspace/` includes 2 web sources about "Calixto Corrium" (a Skyrim NPC, unrelated to the research question) and 3 arXiv papers unrelated to asyncio. These are explicitly rated `Quality: low` or `Quality: medium` in `bibliography.md` and are intentionally orphaned (not cited in the report).
- **Rationale:** A perfect sample (only on-topic, well-cited sources) does not teach the agent how to handle the real-world messiness of research. By including real data from the actual e2e-test runs, the sample demonstrates: (a) quality rating as a workflow, (b) orphaned-but-rated sources in `audit` output, and (c) the workspace's ability to be a faithful record of what was collected, not a curated exhibit. Considered: only curated sources (rejected: unrealistic), no unrelated sources (rejected: does not show quality rating), include them with explicit ratings (chosen: shows the real flow).
- **Impact:** The `workspace_info.py audit examples/sample-workspace` command reports 5 orphaned sources out of 10. This is the expected state. The `examples/README.md` explains the choice.

## Decision 008: Skills follow the Agent Skills specification (SKILL.md in directory, YAML frontmatter)

- **Date:** 2026-06-06
- **Task:** Post-M4 audit fix (user feedback)
- **Milestone:** Post-M4 (correctness audit)
- **Decision:** Convert all 4 skills from flat markdown files (`skills/deep-research.md`, etc.) to the Agent Skills spec format: a directory per skill with a `SKILL.md` file at the root, with YAML frontmatter containing `name` (matches directory), `description` (1-1024 chars, includes "what" and "when" with trigger keywords), and optional `license`, `compatibility`, `metadata` fields.
- **Rationale:** The original plan placed skills as flat files because that matched the `requirements.md` section 3.1 layout. After the v0.1.0 build, the user pointed out that the [Agent Skills specification](https://agentskills.io/specification) is the de-facto standard for portable agent skills. Skills packaged per the spec are recognizable to any compliant agent (Claude Code, OpenCode, Cursor, etc.) and can be loaded without custom conventions. Considered: keep flat files (rejected: ignores the standard, hurts portability), dual format (rejected: duplication, drift risk), migrate to spec (chosen: portability, agent compatibility).
- **Impact:** All 4 skills are now in `skills/<name>/SKILL.md` form. `AGENTS.md` and `README.md` were updated to reflect the new paths. `tests/validate_skills.py` exists to programmatically check that all skills pass the spec. The `name` frontmatter field must match the directory name; `description` must be 1-1024 chars. `skills-ref` (from the spec's reference library) can validate further when available.

## Decision 009: pyproject.toml uses `requests` only as an optional `brave` extra

- **Date:** 2026-06-06
- **Task:** Post-M4 audit fix (user feedback)
- **Milestone:** Post-M4 (correctness audit)
- **Decision:** The `requests` package is not in `[project.dependencies]`. It lives only in the `brave` optional extra. The `tavily` extra is removed entirely (no Tavily provider is shipped in v0.1.0).
- **Rationale:** The core workflow (DuckDuckGo + Crawl4AI + arXiv) does not need `requests`. Adding it to the main dependencies would inflate the install for users who never use Brave. Per the Honest Complexity principle (PHILOSOPHY.md), we only add what we use. Considered: include `requests` in main deps (rejected: unused by default), ship a `tavily` provider stub (rejected: half-implementation, document later when implemented), keep `brave` extra with `requests` only there and drop the unused `tavily` extra (chosen: minimum required deps, accurate extras).
- **Impact:** Users running `pip install calixto-research-workspace` get a smaller install. Users who want Brave run `pip install 'calixto-research-workspace[brave]'` to add `requests`. The `[tavily]` extra is removed from the published metadata. If a future version ships a Tavily provider, the extra can be re-added.

## Decision 010: Fresh install and update use separate filesystem contracts

- **Date:** 2026-06-08
- **Task:** Remaining Issues Fix Plan, Phase 1
- **Milestone:** Post-M4 installer reliability
- **Decision:** Fresh install and update now use different application rules, enforced by shared installer core logic. Fresh install copies the complete toolkit into a verified empty target. Update preserves protected user data and repository metadata while applying only toolkit-owned top-level entries.
- **Rationale:** The previous shared move helper made fresh install inherit update-only protection rules, which could silently omit root toolkit files such as `config.json` in future or custom sources. The plan explicitly separates the two operations because their safety invariants differ.
- **Impact:** The installers now document and enforce distinct fresh-install and update behavior. Tests cover both paths independently.

## Decision 011: Archive roots are discovered structurally, not by repository name

- **Date:** 2026-06-08
- **Task:** Remaining Issues Fix Plan, Phase 2
- **Milestone:** Post-M4 installer reliability
- **Decision:** Archive extraction now validates member paths, extracts into staging, and selects the single top-level extracted directory structurally instead of searching for a `calixto-*` prefix.
- **Rationale:** GitHub archive roots are named after the repository, so forks and custom repository names cannot safely be handled by a hard-coded `calixto-*` pattern. Structural discovery is the only repository-agnostic rule that stays correct for the default repository and for renamed forks.
- **Impact:** Archive fallback works for arbitrary GitHub repository names as long as the archive contains exactly one top-level extracted directory. Ambiguous or malformed archives now fail before target mutation.

## Decision 012: Updates use a rollback transaction plus managed-entry ownership metadata

- **Date:** 2026-06-08
- **Task:** Remaining Issues Fix Plan, Phases 1 and 3
- **Milestone:** Post-M4 installer reliability
- **Decision:** Updates now use `.calixto-managed-entries` as the authority for toolkit-owned top-level entries and `.calixto-update-transaction/` as the rollback mechanism for partially applied toolkit replacements.
- **Rationale:** Without ownership metadata, the installer could not safely delete entries absent from a later release. Without a rollback transaction, a mid-update failure could leave the toolkit partially replaced. The combined approach keeps update behavior conservative for legacy installs while making modern installs recoverable.
- **Impact:** Successful installs and updates write managed-entry metadata. Failed updates restore the previous toolkit files and leave transaction diagnostics behind for inspection.

## Decision 013: Production archive downloads stay narrow and always verify TLS

- **Date:** 2026-06-08
- **Task:** Remaining Issues Fix Plan, Phase 2
- **Milestone:** Post-M4 installer reliability
- **Decision:** Production repository URLs are limited to `https://github.com/<owner>/<repo>` (optionally with `.git`). The old insecure TLS bypass is removed. Integration tests use explicit test-only archive URL and CA-certificate overrides guarded by `CALIXTO_TEST_MODE=1`.
- **Rationale:** The previous implementation had broadened URL claims beyond what was actually tested and supported. The plan called for a narrow, accurate production contract and for test-only transport overrides instead of a production-facing insecure-TLS escape hatch.
- **Impact:** Production archive fallback now always verifies TLS. Tests retain controlled flexibility without expanding the supported production surface.

## Decision 014: Installer integration tests are real platform executions, not helper redefinitions

- **Date:** 2026-06-08
- **Task:** Remaining Issues Fix Plan, Phase 4
- **Milestone:** Post-M4 installer reliability
- **Decision:** The installer tests now execute the actual `install.sh` and `install.ps1` entrypoints from isolated checkout copies, use explicit pytest markers for Unix/Windows/archive paths, and remove the older static PowerShell helper-redefinition tests.
- **Rationale:** The old tests proved too little: they could pass while the real installer paths still failed, and they leaked assumptions from the developer checkout into fixture expectations. Running the real installers from isolated checkouts is slower but materially more trustworthy.
- **Impact:** CI can target required installer paths explicitly, and those tests now validate source selection, archive fallback, managed-entry behavior, rollback, interrupted-transaction recovery, and dry-run guarantees against the actual installer scripts.

## Decision 015: The toolkit root is a factory; new workspaces are standalone runtime snapshots

- **Date:** 2026-06-09
- **Task:** Self-contained workspace redesign
- **Milestone:** Standalone workspace architecture reset
- **Decision:** `scripts/init_workspace.py` now creates a standalone workspace snapshot instead of copying only the data template. The snapshot bundles research-facing scripts, providers, skills, setup helpers, dependency metadata, and workspace state files. The toolkit root remains the source used to generate future workspaces.
- **Rationale:** The previous model drifted into a mixed root/workspace runtime where updates had to preserve, infer, and sometimes roll back research state inside the same tree as toolkit files. That boundary made the installer and docs more complex than the product needed. Treating the toolkit root as a factory and each workspace as the execution unit is simpler, more portable, and closer to the original vision.
- **Impact:** New workspaces can be copied elsewhere and continue after local dependency setup. Research mode now belongs in the generated workspace, not the toolkit root. Toolkit updates affect future workspaces only. The runtime bundle is defined by `runtime/workspace-manifest.json` and validated by tests.
