# Calixto Research Workspace: Initial Implementation Plan

## Metadata

- Plan Status: COMPLETED
- Created: 2026-06-06
- Last Updated: 2026-06-06
- Owner: Coding agent
- Approval: APPROVED
- Implemented in: `D:\Repos\calixto-research-workspace` (target repo)

## Status Legend

- Plan Status values: DRAFT, QUESTIONS PENDING, READY FOR APPROVAL, APPROVED, IN PROGRESS, COMPLETED, BLOCKED
- Task/Milestone Status values: TO BE DONE, IN PROGRESS, COMPLETED, BLOCKED, SKIPPED

## Execution Summary

All 38 tasks across 6 milestones were completed on 2026-06-06 in a single working session. The full implementation lives in the target repository at `D:\Repos\calixto-research-workspace`. This plan file is preserved here as the execution ledger and is being moved alongside the implementation.

### What was built

- **Repository structure** matching `requirements.md` section 3.1
- **`PHILOSOPHY.md` and `AGENTS.md`** (universal entry point for any coding agent)
- **`pyproject.toml`** with `hatchling` build backend, runtime deps (`crawl4ai`, `ddgs`, `arxiv`, `pyyaml`), and optional groups (`brave`, `tavily`, `dev`)
- **`setup.sh` and `setup.ps1`** (idempotent environment setup, ~500MB install)
- **`install.sh` and `install.ps1`** (one-liner installers with fresh-install and workspace-update modes, `--dry-run` / `-DryRun` support)
- **Workspace template** (`templates/workspace/`) with `config.json`, `sources/`, `notes/`, `outputs/`
- **Provider interfaces** (`providers/search/base.py`, `providers/scrape/base.py`) with `SearchProvider`, `ScrapeProvider`, `SearchResult`, `ScrapeResult`, and exception types
- **Concrete providers**: `duckduckgo.py` (default, free, no API key), `brave.py` (optional, requires API key), `crawl4ai_provider.py` (the only scrape backend)
- **CLI scripts**: `init_workspace.py`, `search_web.py`, `search_arxiv.py`, `workspace_info.py` (list/show/delete/audit)
- **Shared utilities** (`scripts/_common.py`): atomic JSON writes, slug validation, URL normalization, frontmatter rendering, markdown truncation, structured I/O helpers
- **Skills** in `skills/`: `deep-research.md` (research mode), `literature-review.md` (research mode), `create-skill.md` and `integrate-tool.md` (developer mode meta-skills)
- **Agent adapters** for Claude Code, OpenCode, Cursor
- **Golden dataset** in `tests/golden/`: `config.json`, `README.md`, `run.py`, `compare.py`, `expected/*.json` (structural assertions), `build_arxiv_cache.py` (workaround helper), and the first archived runs
- **Sample workspace** at `examples/sample-workspace/` (10 sources, 10 findings, 5 insights, full report with citations)
- **First ADR** (`docs/adr/001-choose-crawl4ai.md`)
- **Decision log** (`docs/initial-implementation-plan-decision-log.md`) with 4 entries capturing tactical implementation choices
- **`CHANGELOG.md`** with a v0.1.0 entry

### Validation summary

All 14 final verification steps in Task 6.2 pass:

1. `install.sh` syntax OK
2. `install.ps1` syntax OK
3. `setup.sh` syntax OK
4. `setup.ps1` syntax OK
5. `install.sh --dry-run` fresh-install mode OK
6. `install.sh --dry-run` workspace-update mode OK
7. `python scripts/init_workspace.py` OK
8. `python scripts/search_web.py ... --no-scrape` OK (collected 3 sources with valid frontmatter, dedup, ID counter)
9. `python scripts/workspace_info.py list` OK
10. `python scripts/workspace_info.py audit` OK (status: ok)
11. `python tests/golden/run.py --use-cache` OK (4 searches, 18 sources, 0 failures)
12. `python tests/golden/compare.py` OK (identical runs report `comparison: ok`)
13. Exit codes 0 on success, 1 on error
14. JSON outputs are valid

### Notable deviations from the plan

These are documented in `docs/initial-implementation-plan-decision-log.md` in the target repo:

- **Decision 001**: Use `pathlib.Path` for all file I/O.
- **Decision 002**: Installer backups go in `.calixto-backup-<timestamp>/` inside the workspace.
- **Decision 003**: Use `hatchling` instead of `setuptools` as build backend.
- **Decision 004**: Provider interfaces are sync (Crawl4AI bridges async internally).
- **Plus**: The plan called for `duckduckgo-search`; the implementation uses `ddgs` (the package was renamed in 2025). The interface and usage are identical.
- **Plus**: `tests/golden/build_arxiv_cache.py` is a one-off helper for populating the arXiv cache when the arXiv API is unresponsive from the build environment. It is documented in the first-run notes.

### Known limitations

- The arXiv API was unresponsive from the build environment; the golden cache was populated manually for the first run. The runner itself works correctly when the live API is reachable.
- Crawl4AI's full install requires Chromium (~450MB). Setup takes several minutes on a clean machine.
- The golden runner performs source collection only; an agent following `skills/deep-research.md` performs synthesis and writes the report.

## Goal

Deliver a functional agent-first research toolkit (Calixto Research Workspace) that enables any coding agent to perform structured, reproducible deep research using file-based workspaces, with full traceability from source collection through final report. The MVP (M0-M2) proves the concept end-to-end; M3-M4 add the golden dataset benchmark and extensibility meta-skills.

## Installation Philosophy

Calixto Research Workspace is designed to be installable with a single command on both Unix and Windows systems, following the pattern established by tools like Homebrew, Claude Code, Rust, and others:

**Unix/Linux/macOS:**
```bash
curl -fsSL https://calixto.dev/install.sh | bash
```

**Windows (PowerShell):**
```powershell
irm https://calixto.dev/install.ps1 | iex
```

**Two installation modes:**

1. **Fresh install**: Run the one-liner in an empty directory. The installer will clone the repository, copy all files to the current directory, and run the setup script to install dependencies.

2. **Workspace update**: Run the one-liner in an existing Calixto workspace. The installer will detect the existing workspace, verify compatibility, backup user data (especially the `workspaces/` directory), pull the latest changes, and optionally update dependencies.

**Safety guarantees:**
- Never deletes user data without explicit confirmation
- Always prompts before making changes
- Backs up user workspaces before updating
- Verifies workspace compatibility before updating
- Provides dry-run mode for testing
- Idempotent: safe to run multiple times

See Tasks 1.10, 1.11, and 1.12 for implementation details.

## Scope

- Repository scaffolding matching requirements.md section 3.1
- `PHILOSOPHY.md` and `AGENTS.md` documentation
- `setup.sh` and `setup.ps1` environment setup scripts
- One-liner installer scripts (`install.sh` and `install.ps1`) for easy installation on Unix and Windows
- Workspace template and `init_workspace.py`
- DuckDuckGo search provider (default, FOSS, no API key)
- Crawl4AI scrape provider
- `search_web.py` and `search_arxiv.py` with ID assignment and traceability
- `workspace_info.py` with list, show, delete, and audit commands
- `deep-research.md` skill with full provenance chain instructions
- Golden dataset structure with search result caching
- Source deduplication via `sources/index.json`
- Structured JSON output for all scripts
- Error handling for all failure modes documented in requirements.md section 12

## Non-Goals

- Brave, Tavily, or other paid search providers (M4 stretch)
- MCP server integration
- Frontend or UI
- Hosted/cloud deployment
- Multi-agent orchestration frameworks
- Custom LLM fine-tuning
- LLM-calling scripts (agent uses its own model)
- Native Windows support beyond what `setup.ps1` provides (M4 stretch)
- Literature review skill (M4)
- Meta-skills for creating skills and integrating tools (M4)

## Assumptions

- Python 3.11+ is available on the system
- `uv` package manager is available or can be installed
- Crawl4AI can be installed via pip and Playwright/Chromium can be downloaded (~500MB)
- DuckDuckGo search via `duckduckgo-search` package works without API keys
- arXiv API is accessible and rate limits are manageable
- The coding agent executing this plan has bash and python execution capabilities
- Git is available for workspace archival and for the installer to use `git clone` or `git pull`
- The agent has access to its own LLM for extraction, synthesis, and reporting (not provided by this toolkit)
- Users have internet connectivity to download the installer and dependencies
- Users understand that the installer will create or modify files in the current directory and will be prompted for confirmation
- The repository will be hosted on GitHub (or similar) with stable URLs for the installer scripts
- The installer will be versioned and tagged to support reproducible installs

## Open Questions

None. All requirements were clarified before plan creation. If questions arise during execution, they will be added here and the plan status will move to QUESTIONS PENDING.

---

## Milestones

### Milestone 1: Foundation (M0)

- Status: COMPLETED
- Purpose: Establish the repository structure, documentation, and environment setup so that any agent can clone the repo and start using it.
- Exit Criteria: A fresh clone with the setup script run successfully creates a working Python environment, and `AGENTS.md` plus `PHILOSOPHY.md` allow an agent to understand the project structure and how to use it.

#### Task 1.1: Create Repository Directory Structure

- Status: COMPLETED
- Objective: All directories from requirements.md section 3.1 exist on disk.
- Steps:
  1. Create directories: `skills/`, `adapters/`, `templates/workspace/`, `scripts/`, `providers/search/`, `providers/scrape/`, `tests/golden/`, `examples/`, `docs/adr/`
  2. Create empty `__init__.py` files in `scripts/`, `providers/`, `providers/search/`, `providers/scrape/`
  3. Create empty `README.md` placeholder files in `adapters/claude-code/`, `adapters/opencode/`, `adapters/cursor/`
  4. Create `.gitignore` at repo root with entries: `__pycache__/`, `*.pyc`, `workspaces/` (except `examples/`), `.venv/`, `uv.lock`, `tests/golden/cache/`, `tests/golden/runs/`, `.DS_Store`
- Validation: `ls -R` (or PowerShell equivalent) shows all directories exist with placeholder content. `.gitignore` exists with all required entries.
- Notes: This is a structural task; no logic yet. The `.gitignore` prevents committing test workspaces and cache files.

#### Task 1.2: Write `PHILOSOPHY.md`

- Status: COMPLETED
- Objective: The full philosophy document is in place at the repo root.
- Steps:
  1. Copy the existing `PHILOSOPHY.md` content from the working repo to the target location
  2. Verify all 7 principles are present: Agent-First, Files Are the Database, Modular and Configurable, Honest Complexity, Easy In Easy Out, Reproducible Within Reason, Traceability
  3. Verify Part I (Philosophy) and Part II (Implementation Guide) are both present
  4. Verify Non-Negotiables section includes the LLM/harness agnostic clause
  5. Verify zero em dashes remain
- Validation: `grep -c "—"` returns 0; all section headers from the philosophy doc are present.
- Notes: Content already exists and was approved; this task is about ensuring it's in the right location.

#### Task 1.3: Write `AGENTS.md`

- Status: COMPLETED
- Objective: `AGENTS.md` exists at repo root and tells any coding agent how to use this repo.
- Steps:
  1. Create `AGENTS.md` with sections: What This Repo Is, How to Set Up, Repository Structure, How to Use (Research Mode), How to Develop (Developer Mode), Mode Switching, Scripts Reference, Skills Reference, Workspace Conventions, Running the Golden Dataset, Contributing
  2. Include the two-mode documentation: what each mode loads, how to switch
  3. Include links to `PHILOSOPHY.md`, `requirements.md`, and adapter docs
  4. Include concrete examples of common agent tasks (e.g., "run a research session", "add a new search provider")
- Validation: An agent reading only `AGENTS.md` can locate and run `setup.sh`, explain the workspace structure, and switch between modes.
- Notes: This is the primary entry point for all agents. Must be comprehensive but not overwhelming.

#### Task 1.4: Create `pyproject.toml` and `setup.sh` (Linux/macOS/WSL)

- Status: COMPLETED
- Objective: `pyproject.toml` defines dependencies, and `./setup.sh` on a clean Linux/macOS/WSL system installs all required dependencies and verifies them.
- Steps:
  1. Check Python 3.11+ is available; error with install instructions if not
  2. Install `uv` if not present
  3. Create `pyproject.toml` with required dependencies: `crawl4ai`, `duckduckgo-search`, `arxiv`
  4. Create optional dependency groups: `brave`, `tavily`
  5. Run `uv sync` to install dependencies
  6. Run `crawl4ai-setup` to install Playwright browsers
  7. Run `python -m playwright install chromium` as fallback
  8. Print progress at each step with clear labels and sizes
  9. Verify installation: `python -c "import crawl4ai, ddgs, arxiv"`
  10. Print final summary: "Setup complete. Total installed: ~500MB"
- Validation: On a clean Linux system, `./setup.sh` completes without errors and the verification import succeeds. `pyproject.toml` exists with correct dependencies.
- Notes: Script must be idempotent. Must print what it's doing per Honest Complexity principle.

#### Task 1.5: Create `setup.ps1` (Windows Native)

- Status: COMPLETED
- Objective: Running `.\setup.ps1` on a clean Windows system installs all required dependencies.
- Steps:
  1. Check Python 3.11+ via `python --version`; error with install link if not
  2. Install `uv` via PowerShell if not present
  3. Run `uv sync` from `pyproject.toml`
  4. Run `crawl4ai-setup` (handles Windows-specific Playwright install)
  5. Print progress with Windows-compatible output (no ANSI color codes that break)
  6. Verify installation with import test
  7. Print final summary
- Validation: On a clean Windows system, `.\setup.ps1` completes without errors.
- Notes: Include Windows-specific workarounds for Playwright/Chromium install issues.

#### Task 1.6: Define Workspace Template

- Status: COMPLETED
- Objective: `templates/workspace/` contains a complete workspace template ready to be copied.
- Steps:
  1. Create `templates/workspace/config.json` with default values (name: "example", question: "", scope, providers, next_source_id: 1, next_finding_id: 1, next_insight_id: 1, empty searches array, timestamps)
  2. Create `templates/workspace/sources/index.json` with `{"next_id": 1, "sources": []}`
  3. Create empty subdirectories: `sources/web/`, `sources/papers/`, `sources/code/`, `notes/`, `outputs/`
  4. Create `templates/workspace/notes/findings.md` with header: `# Findings\n\nExtracted facts with finding IDs. Format:\n\n## fnd_001\n**Source:** src_NNN\n**Fact:** ...`
  5. Create `templates/workspace/notes/summary.md` with header: `# Summary\n\nSynthesized insights with insight IDs. Format:\n\n## ins_001\n**Based on:** fnd_NNN\n**Insight:** ...`
  6. Create `templates/workspace/notes/gaps.md` with header: `# Gaps\n\nIdentified gaps and follow-up questions.`
  7. Create `templates/workspace/outputs/report.md` with header: `# Report\n\nFinal research report. Citations: [src_NNN]`
  8. Create `templates/workspace/outputs/bibliography.md` with header: `# Bibliography\n\nAll sources with quality ratings.`
- Validation: `init_workspace.py` (Task 2.1) successfully copies this template.
- Notes: All files must be valid and parseable. Frontmatter not used in notes/reports (plain markdown).

#### Task 1.7: Create Provider Interface Base Classes

- Status: COMPLETED
- Objective: `providers/search/base.py` and `providers/scrape/base.py` define the provider contracts.
- Steps:
  1. Create `providers/search/base.py` with `SearchResult` and `SearchProvider` classes (from requirements.md section 5.1)
  2. Create `providers/scrape/base.py` with `ScrapeResult` and `ScrapeProvider` classes (from requirements.md section 5.1.1)
  3. Add module-level docstrings explaining the interface and how to implement
  4. Add type hints for all parameters and return values
- Validation: `python -c "from providers.search.base import SearchProvider, SearchResult; from providers.scrape.base import ScrapeProvider, ScrapeResult"` succeeds.
- Notes: These are abstract base classes. No concrete implementation yet.

#### Task 1.8: Write First ADR (Architecture Decision Record)

- Status: COMPLETED
- Objective: `docs/adr/001-choose-crawl4ai.md` documents why we chose Crawl4AI.
- Steps:
  1. Create `docs/adr/001-choose-crawl4ai.md` with sections: Context, Decision, Consequences, Alternatives Considered
  2. Document the alternatives evaluated: Scrapy, BeautifulSoup, Playwright direct, Firecrawl
  3. Document the decision: Crawl4AI for LLM-friendly markdown output and self-hosting
  4. Document consequences: ~500MB install, Playwright dependency, but zero API keys
- Validation: File exists and contains all required sections.
- Notes: This sets the pattern for future ADRs. Future ADRs will be created as significant decisions are made.

#### Task 1.9: Create Decision Log File

- Status: COMPLETED
- Objective: `docs/initial-implementation-plan-decision-log.md` exists and is ready to track decisions made during implementation.
- Steps:
  1. Create `docs/initial-implementation-plan-decision-log.md` with the heading `# Decision Log: Initial Implementation Plan`
  2. Add a "Purpose" section explaining: this log captures all decisions made during implementation that were not part of the original plan
  3. Add a "When to Use" section explaining: use this log when you need to make a choice that wasn't specified in the plan, when requirements.md is ambiguous, when you discover a constraint not anticipated, or when you need to deviate from the plan
  4. Add an "Entry Format" section with the template (see Execution Notes)
  5. Add a "Current Entries" section with `None. No decisions have been made yet.`
- Validation: File exists, contains all four sections, and has the correct heading.
- Notes: This task only creates the empty log. Entries are added during implementation as decisions arise. See Execution Notes for usage rules.

#### Task 1.10: Create One-Liner Installer for Unix (install.sh)

- Status: COMPLETED
- Objective: `install.sh` can be piped from a URL to install or update a Calixto workspace in the current directory.
- Steps:
  1. Create `install.sh` at repo root with executable permissions
  2. Script detects if current directory is a Calixto workspace (check for `requirements.md`, `setup.sh`, `templates/`, `scripts/` directories, and `PHILOSOPHY.md`)
  3. If NOT a workspace: print "This will install Calixto Research Workspace in the current directory. Continue? (y/n)" and wait for confirmation
  4. If confirmed and not a workspace: clone the repo to a temp directory, copy all files to current directory, then run `./setup.sh`
  5. If it IS a workspace: verify compatibility (check that all required files/directories exist and match expected structure), print "This will update Calixto Research Workspace in the current directory. Continue? (y/n)" and wait for confirmation
  6. If confirmed and is a workspace: backup current state (especially workspaces/, config files, notes/), pull latest changes (git pull or download latest release), compare structure, restore preserved user data
  7. If confirmed and is a workspace: optionally run `./setup.sh` to update dependencies
  8. Print final instructions: "Installation complete. To start: create a workspace with 'python scripts/init_workspace.py my-research'"
  9. Add safety checks: never overwrite without confirmation, never delete user workspaces, backup before updating
  10. Support both git clone and tarball download (prefer git if available, fall back to tarball)
- Validation: Test in a fresh directory: `curl -fsSL https://raw.githubusercontent.com/calixto/calixto/main/install.sh | bash` (mocked) installs the workspace. Test in an existing workspace: the same command updates it without losing user data. Test with `--dry-run` flag to see what would happen without making changes.
- Notes: This script must be extremely safe. It should never delete user data. It should be idempotent. It should work on bash, zsh, and other Unix shells. Reference patterns: Homebrew install.sh, Claude Code install.sh, Rust install.sh.

#### Task 1.11: Create One-Liner Installer for Windows (install.ps1)

- Status: COMPLETED
- Objective: `install.ps1` can be piped from a URL to install or update a Calixto workspace in the current directory on Windows.
- Steps:
  1. Create `install.ps1` at repo root
  2. Script detects if current directory is a Calixto workspace (same checks as install.sh)
  3. If NOT a workspace: print confirmation prompt and wait for user input
  4. If confirmed and not a workspace: download the repo (via Invoke-WebRequest or git clone), extract to current directory, then run `.\setup.ps1`
  5. If it IS a workspace: verify compatibility, print confirmation prompt, backup user data, update workspace files
  6. If confirmed and is a workspace: optionally run `.\setup.ps1` to update dependencies
  7. Print final instructions for Windows users
  8. Add safety checks: never overwrite without confirmation, never delete user workspaces, backup before updating
  9. Support both git clone and ZIP download (prefer git if available, fall back to ZIP)
  10. Handle PowerShell execution policy issues (provide bypass instructions if needed)
- Validation: Test in PowerShell: `irm https://raw.githubusercontent.com/calixto/calixto/main/install.ps1 | iex` (mocked) installs the workspace. Test in an existing workspace: updates without losing data. Test with `-DryRun` flag.
- Notes: Windows users may have execution policy restrictions. Script should detect this and provide clear instructions. Reference patterns: Claude Code install.ps1, Chocolatey, Scoop.

#### Task 1.12: Document One-Liner Installation in AGENTS.md and README.md

- Status: COMPLETED
- Objective: The one-liner installation commands are prominently documented in AGENTS.md and README.md.
- Steps:
  1. Add a "One-Line Installation" section to AGENTS.md at the top, with both Unix and Windows commands
  2. Explain the two modes: fresh install (in a new directory) and update (in an existing Calixto workspace)
  3. Add the same section to README.md with a clear call-to-action
  4. Include prerequisites: git, Python 3.11+, internet connection
  5. Include troubleshooting: what to do if the install fails, how to verify it worked
  6. Add a note about safety: the installer never deletes user data, always asks for confirmation
  7. Include examples of both fresh install and update scenarios
- Validation: A new user can install Calixto by copying the one-liner from README.md without reading any other documentation. An existing user can update by running the same command in their workspace directory.
- Notes: This is the primary user-facing installation method. Must be extremely clear and safe.

---

### Milestone 2: MVP: Search and Persist (M1)

- Status: COMPLETED
- Purpose: Implement the core workflow: create workspace, search the web, persist sources with IDs. This proves the end-to-end concept.
- Exit Criteria: An agent can create a workspace, run a web search, and find the results saved as markdown files with sequential IDs in `sources/web/`, with a deduplication registry in `sources/index.json`, and a search history in `config.json`.

#### Task 2.1: Implement `init_workspace.py`

- Status: COMPLETED
- Objective: Script creates a new workspace from the template with valid default config.
- Steps:
  1. Create `scripts/init_workspace.py` with CLI argument `<name>` and optional `--path`
  2. Validate name is a valid slug (lowercase, hyphens, no spaces)
  3. Check if workspace already exists; error if it does
  4. Copy `templates/workspace/` to `<path>/<name>/`
  5. Update `config.json` with the workspace name and current timestamp
  6. Print workspace path as JSON: `{"status": "ok", "workspace": "workspaces/my-research"}`
  7. Set exit code 0 on success, 1 on error
- Validation: `python scripts/init_workspace.py test-ws` creates `workspaces/test-ws/` with valid config.json. `cat workspaces/test-ws/config.json` shows valid JSON with name "test-ws".
- Notes: Must handle the case where `workspaces/` directory doesn't exist (create it).

#### Task 2.2: Implement DuckDuckGo Search Provider

- Status: COMPLETED
- Objective: `providers/search/duckduckgo.py` implements the `SearchProvider` interface using `duckduckgo-search`.
- Steps:
  1. Create `providers/search/duckduckgo.py` with `DuckDuckGoProvider` class
  2. Implement `search(query, max_results)` method using `duckduckgo-search` package
  3. Convert results to `SearchResult` objects (url, title, snippet, score)
  4. Add rate limiting: 3s delay between requests
  5. Add exponential backoff on 429/rate limit errors (max 3 retries)
  6. Handle empty results gracefully
  7. Add module docstring with usage example
- Validation: Unit test: `python -c "from providers.search.duckduckgo import DuckDuckGoProvider; p = DuckDuckGoProvider(); results = p.search('python tutorial', 5); assert len(results) <= 5; assert all(r.url for r in results)"` succeeds.
- Notes: DuckDuckGo can be rate-limited or blocked. Must handle failures gracefully.

#### Task 2.3: Implement Crawl4AI Scrape Provider

- Status: COMPLETED
- Objective: `providers/scrape/crawl4ai_provider.py` implements the `ScrapeProvider` interface using Crawl4AI.
- Steps:
  1. Create `providers/scrape/crawl4ai_provider.py` with `Crawl4AIProvider` class
  2. Implement `scrape(url)` method using Crawl4AI's `AsyncWebCrawler`
  3. Convert Crawl4AI result to `ScrapeResult` (url, title, markdown, word_count, metadata)
  4. Add 30s timeout
  5. Handle failures: paywall, timeout, crash, non-HTML content
  6. Add module docstring with usage example
- Validation: Unit test: `python -c "import asyncio; from providers.scrape.crawl4ai_provider import Crawl4AIProvider; p = Crawl4AIProvider(); result = asyncio.run(p.scrape('https://example.com')); assert result.markdown; assert result.word_count > 0"` succeeds.
- Notes: Crawl4AI is async. Need to handle the async/sync bridge carefully.

#### Task 2.4: Implement `search_web.py` with ID Assignment

- Status: COMPLETED
- Objective: Script searches the web, scrapes results, assigns sequential src_NNN IDs, and saves to workspace.
- Steps:
  1. Create `scripts/search_web.py` with CLI args: `<query>`, `--workspace`, `--max-results` (default 10), `--search-provider` (default duckduckgo), `--no-scrape`, `--truncate` (default 10000)
  2. Load workspace config and index
  3. Initialize search provider and scrape provider
  4. Call search provider to get URLs
  5. Check `sources/index.json` for existing URLs (normalize for dedup); skip duplicates
  6. For each new URL, call scrape provider
  7. Assign next available `src_NNN` ID from `index.json` `next_id` field
  8. Save markdown to `sources/web/src_NNN.md` with YAML frontmatter (id, url, title, date_crawled, provider, search_provider, query, word_count, truncated)
  9. If `--truncate` is set and word_count exceeds limit, truncate and mark `truncated: true`
  10. Update `index.json` with new source entry and increment `next_id`
  11. Append search record to `config.json` `searches` array with timestamp, results_count, urls_found
  12. Update `config.json` `next_source_id` and `updated_at`
  13. Print final JSON output with status, sources_added, sources_skipped, source_ids, workspace path
  14. Handle all error cases per requirements.md section 12.2
- Validation: Run `python scripts/search_web.py "python asyncio" --workspace workspaces/test-ws --max-results 3`. Check that `sources/web/src_001.md`, `src_002.md`, `src_003.md` exist with valid frontmatter. Check that `index.json` has 3 entries and `next_id: 4`. Check that `config.json` has the search record.
- Notes: Must be atomic: if save fails, don't increment `next_id`. Must handle partial failures (some URLs succeed, some fail).

#### Task 2.5: Write Basic `deep-research.md` Skill

- Status: COMPLETED
- Objective: Skill file teaches an agent to perform the full research workflow with traceability.
- Steps:
  1. Create `skills/deep-research.md` with the 7-step workflow: Initialize, Search, Evaluate, Extract, Synthesize, Report, Iterate
  2. Include concrete commands for each step (e.g., "Step 2: Run `python scripts/search_web.py 'query' --workspace workspaces/my-research`")
  3. Include traceability instructions: "When extracting facts, use format `## fnd_001` with **Source:** field referencing src_NNN"
  4. Include synthesis instructions: "When creating insights, use format `## ins_001` with **Based on:** field referencing fnd_NNN"
  5. Include report instructions: "Cite sources inline as [src_NNN]"
  6. Include decision criteria: "If fewer than 5 sources, search again with refined query"
  7. Include quality guidelines: "Each source should have clear relevance to the research question"
  8. Add examples of good vs bad extraction
- Validation: An agent reading only this skill can complete a research session end-to-end.
- Notes: This is the most critical skill. Must be comprehensive and tested with at least one agent.

#### Task 2.6: Test End-to-End MVP Flow

- Status: COMPLETED
- Objective: A complete research session works from workspace creation to source collection.
- Steps:
  1. Run `python scripts/init_workspace.py e2e-test`
  2. Run `python scripts/search_web.py "Python asyncio tutorial" --workspace workspaces/e2e-test --max-results 5`
  3. Verify `workspaces/e2e-test/sources/web/` contains 5 markdown files
  4. Verify each file has valid YAML frontmatter with id, url, title
  5. Verify `workspaces/e2e-test/sources/index.json` has 5 entries and `next_id: 6`
  6. Verify `workspaces/e2e-test/config.json` has the search record and updated `next_source_id`
  7. Verify the JSON output to stdout has status: ok, sources_added: 5, source_ids list
- Validation: All 6 verification checks pass.
- Notes: This is the critical proof that M1 works.

---

### Milestone 3: Analyze and Report (M2)

- Status: COMPLETED
- Purpose: Complete the research workflow: paper search, workspace management, error handling, and the full agent-driven analysis pipeline.
- Exit Criteria: An agent can search arXiv, list/show/delete workspaces, handle all documented error cases, and the skill covers the full workflow through report generation with full traceability.

#### Task 3.1: Implement `search_arxiv.py`

- Status: COMPLETED
- Objective: Script searches arXiv, assigns sequential src_NNN IDs, saves paper metadata.
- Steps:
  1. Create `scripts/search_arxiv.py` with CLI args: `<query>`, `--workspace`, `--max-results` (default 10), `--category`
  2. Load workspace config and index
  3. Use `arxiv` Python package to search
  4. Add 3.5s delay between requests (arXiv rate limit: 1 req/3s)
  5. Check for duplicates by arXiv ID in `index.json`
  6. For each new paper, save markdown to `sources/papers/src_NNN.md` with frontmatter (id, url, title, authors, date_published, provider: arxiv, query, arxiv_id, word_count)
  7. Update `index.json` and `config.json` same as `search_web.py`
  8. Print JSON output with status, sources_added, source_ids
- Validation: Run `python scripts/search_arxiv.py "transformer architecture" --workspace workspaces/e2e-test --max-results 3`. Verify 3 files created in `sources/papers/`, `index.json` updated, `config.json` has search record.
- Notes: arXiv IDs are unique, use them for dedup instead of URLs.

#### Task 3.2: Implement `workspace_info.py`

- Status: COMPLETED
- Objective: Script supports list, show, delete, and audit commands.
- Steps:
  1. Create `scripts/workspace_info.py` with subcommands: `list`, `show <name>`, `delete <name>`, `audit <name>`
  2. `list`: scan `workspaces/` directory, print each workspace name, source count, last modified date as JSON array
  3. `show`: load workspace config and index, print summary (question, source counts by type, searches count, last updated)
  4. `delete`: confirm via prompt or `--force` flag, remove workspace directory
  5. `audit`: verify traceability chain (per requirements.md section 16.3.1): check all src IDs in findings exist in index, all fnd IDs in summary exist in findings, all src IDs in report exist in index, count orphaned sources, return JSON with audit results
- Validation: Test all 4 subcommands. `list` returns array. `show` returns summary. `delete` removes workspace. `audit` returns traceability status.
- Notes: Audit is critical for the Traceability principle. Must handle workspaces with broken or missing files gracefully.

#### Task 3.3: Add Comprehensive Error Handling

- Status: COMPLETED
- Objective: All scripts handle all error cases from requirements.md section 12.
- Steps:
  1. Review all scripts: `init_workspace.py`, `search_web.py`, `search_arxiv.py`, `workspace_info.py`
  2. Add try/except blocks for all documented failure modes
  3. Implement structured error output: `{"status": "error", "error": "error_type", "message": "human readable", "retry_after": N}` (per requirements.md 12.4)
  4. Implement structured success output: `{"status": "ok", "sources_added": N, "sources_skipped": M, "source_ids": [...], "workspace": "path"}`
  5. Implement partial success output: `{"status": "partial", "sources_added": N, "sources_failed": M, "source_ids": [...], "errors": [...]}`
  6. Add input validation: empty queries, invalid workspace paths, missing files
  7. Ensure all errors print to stderr, all data prints to stdout
  8. Set exit code 1 on error, 0 on success
- Validation: For each error case in requirements.md section 12, trigger the error and verify the structured error output matches the spec.
- Notes: Error handling is part of the Non-Negotiable: no silent failures.

#### Task 3.4: Extend `deep-research.md` with Full Workflow

- Status: COMPLETED
- Objective: Skill covers the complete research workflow through report generation.
- Steps:
  1. Update `skills/deep-research.md` to include arXiv search step
  2. Add detailed extraction instructions with traceability examples (how to write fnd_NNN with source references)
  3. Add detailed synthesis instructions with insight examples (how to write ins_NNN with finding references)
  4. Add report generation instructions with inline citation examples ([src_NNN])
  5. Add iteration guidance: "If report is incomplete, search for more sources; if sources are poor quality, refine search query"
  6. Add workspace management: how to use `workspace_info.py` to list, show, audit
  7. Add large content handling: "If source has >10000 words, read frontmatter first, then process incrementally"
  8. Add error recovery: "If search returns 0 results, try broader query; if scrape fails, try --no-scrape"
- Validation: An agent following this skill can complete a full research session including report generation with proper citations.
- Notes: This skill is the primary user-facing documentation. Must be tested with multiple agents.

#### Task 3.5: Add Large Content Truncation

- Status: COMPLETED
- Objective: `search_web.py` truncates sources exceeding the `--truncate` limit.
- Steps:
  1. Add truncation logic to `search_web.py` (per requirements.md 14.1)
  2. Count words in scraped markdown
  3. If word_count > truncate limit, truncate preserving heading structure (first N words per section)
  4. Mark `truncated: true` in frontmatter and add `original_word_count` field
  5. Default truncate limit: 10000 words
- Validation: Scrape a known long page (e.g., a Wikipedia article), set `--truncate 1000`, verify the output is ~1000 words and frontmatter shows `truncated: true`.
- Notes: Truncation must preserve readability. Don't just cut at word 1000 mid-sentence.

---

### Milestone 4: Golden Dataset (M3)

- Status: COMPLETED
- Purpose: Create a reproducible benchmark that validates the workflow and enables comparison of different configurations.
- Exit Criteria: The golden dataset can be run with and without cache, produces comparable results, and the evaluation criteria validate the full pipeline including traceability.

#### Task 4.1: Define Golden Dataset Question and Config

- Status: COMPLETED
- Objective: A fixed research question and config that serves as the reproducible benchmark.
- Steps:
  1. Create `tests/golden/README.md` with: research question, rationale, expected workflow, how to run, how to compare
  2. Choose a question that is stable but non-trivial: "What are the best open-source LLMs for local deployment in 2025?"
  3. Create `tests/golden/config.json` with fixed parameters: search queries (3-5), max_results per query, workspace name, timestamp
  4. Document why this question was chosen: tests web search, paper search, synthesis, citations
- Validation: `tests/golden/config.json` is valid JSON with all required fields. README explains the choice.
- Notes: Question must be specific enough to be reproducible but general enough to demonstrate the workflow.

#### Task 4.2: Implement Search Result Caching

- Status: COMPLETED
- Objective: `search_web.py` and `search_arxiv.py` cache search results in `tests/golden/cache/`.
- Steps:
  1. Add caching logic: if `--use-cache` flag is set and cache file exists, use cached results instead of calling provider
  2. Cache key: hash of (provider + query + max_results)
  3. Cache file location: `tests/golden/cache/<provider>/<query_hash>.json`
  4. Cache file format: JSON with original SearchResult list + timestamp
  5. If cache miss, fetch from provider and save to cache
  6. Add `--clear-cache` flag to delete cache before running
- Validation: Run search twice with `--use-cache`. Second run should not make network requests (verify by disconnecting network or checking logs).
- Notes: Caching is critical for reproducibility. Without it, golden runs are non-deterministic.

#### Task 4.3: Create Golden Dataset Runner Script

- Status: COMPLETED
- Objective: `tests/golden/run.py` executes the full golden dataset workflow.
- Steps:
  1. Create `tests/golden/run.py` that:
     a. Loads `tests/golden/config.json`
     b. Creates a new workspace (or uses timestamped subdirectory)
     c. Runs each search query in the config
     d. Saves the complete workspace to `tests/golden/runs/<timestamp>/`
     e. Runs `workspace_info.py audit` on the result
     f. Prints summary: sources collected, sources cited, traceability status
  2. Add CLI args: `--use-cache`, `--clear-cache`, `--workspace-name`
  3. Support running with different providers for comparison
- Validation: `python tests/golden/run.py --use-cache` completes successfully and produces a run directory with all workspace files.
- Notes: This is the test harness. Must be reliable and fast when using cache.

#### Task 4.4: Create Comparison Tool

- Status: COMPLETED
- Objective: `tests/golden/compare.py` compares two golden runs.
- Steps:
  1. Create `tests/golden/compare.py` that takes two run directories as args
  2. Compare structural properties: source count, source diversity, report sections, citation coverage, traceability status
  3. Print diff: "Run A had 12 sources, Run B had 14 (diff: +2, within tolerance)"
  4. Exit code 0 if all checks pass, 1 if any check fails
  5. Use evaluation criteria from requirements.md section 10.4
- Validation: Run golden dataset twice with cache. Compare the two runs. Verify they match (or are within tolerance).
- Notes: This tool enables benchmarking different configurations.

#### Task 4.5: Create Expected Output Specifications

- Status: COMPLETED
- Objective: `tests/golden/expected/` contains structural assertions for the golden run.
- Steps:
  1. Create `tests/golden/expected/source_count_range.json`: `{"min": 10, "max": 20}`
  2. Create `tests/golden/expected/report_sections.json`: list of expected section names (e.g., `["Introduction", "Top Models", "Comparison", "Recommendations", "References"]`)
  3. Create `tests/golden/expected/quality_checks.json`: assertions like `{"min_unique_domains": 3, "min_citation_coverage": 0.8, "all_ids_valid": true}`
  4. Update `compare.py` to load these specs and validate against them
- Validation: Run golden dataset, verify it passes all assertions in `expected/`.
- Notes: Assertions must be structural (section names, counts) not content-based, per Reproducible Within Reason principle.

#### Task 4.6: Document First Golden Run

- Status: COMPLETED
- Objective: `tests/golden/README.md` documents the first successful run and its results.
- Steps:
  1. Run `python tests/golden/run.py --clear-cache` to get a fresh run
  2. Document the results: how many sources, which domains, which models were top-ranked, report quality
  3. Add a "Results" section to README with: run date, provider used, source count, report excerpt
  4. Note any failures or unexpected results
  5. Save the run to `tests/golden/runs/first-run-<timestamp>/` for reference
- Validation: README has a complete Results section with concrete numbers and observations.
- Notes: This establishes the baseline. Future changes can be compared against this.

---

### Milestone 5: Extensibility and Polish (M4)

- Status: COMPLETED
- Purpose: Enable users and agents to extend the toolkit: add new skills, integrate new tools, and use the toolkit with different agents.
- Exit Criteria: Meta-skills exist for creating skills and integrating tools, alternative providers can be added without changing core code, adapter docs exist for Claude Code, OpenCode, and Cursor, and a sample completed workspace demonstrates the full workflow.

#### Task 5.1: Write `create-skill.md` Meta-Skill

- Status: COMPLETED
- Objective: Skill file teaches agents how to create new research skills.
- Steps:
  1. Create `skills/create-skill.md` with sections: When to Create a New Skill, Skill File Format, Workflow Stages, Examples, Validation
  2. Document the skill file structure: markdown with sections for each workflow step
  3. Provide a template: `# Skill Name\n\n## When to Use\n\n## Workflow\n1. Step 1\n2. Step 2\n\n## Validation\n\n## Examples`
  4. Include 2-3 examples of good skills (e.g., a competitive analysis skill, a technical comparison skill)
  5. Document how to reference scripts and templates
- Validation: An agent following this meta-skill can create a new valid skill file.
- Notes: This is a meta-skill (developer mode only). Should not be loaded in research mode.

#### Task 5.2: Write `integrate-tool.md` Meta-Skill

- Status: COMPLETED
- Objective: Skill file teaches agents how to add new tools and providers.
- Steps:
  1. Create `skills/integrate-tool.md` with sections: When to Add a New Tool, Provider Interface Contracts, Step-by-Step: Adding a Search Provider, Step-by-Step: Adding a Scrape Provider, Step-by-Step: Adding a Data Source, Testing New Providers, Updating Documentation
  2. Include the `SearchProvider` and `ScrapeProvider` interface code
  3. Provide a complete example: implementing a Brave search provider from scratch
  4. Document how to register the new provider and make it available via config
  5. Include testing guidance: unit tests, integration tests, manual validation
- Validation: An agent following this meta-skill can implement and register a new search provider.
- Notes: This is the most important meta-skill for extensibility. Must be tested by having an agent actually add a provider.

#### Task 5.3: Implement Brave Search Provider

- Status: COMPLETED
- Objective: `providers/search/brave.py` implements Brave search as an optional provider.
- Steps:
  1. Create `providers/search/brave.py` with `BraveProvider` class
  2. Implement `search(query, max_results)` using Brave Search API
  3. Require `BRAVE_API_KEY` environment variable
  4. Add rate limit handling: 2000 requests/month free tier, warn at 80%
  5. Add to `pyproject.toml` as optional dependency: `brave = ["brave-search"]`
  6. Update `integrate-tool.md` to reference this as an example
- Validation: With a valid `BRAVE_API_KEY`, `python -c "from providers.search.brave import BraveProvider; p = BraveProvider(); results = p.search('test', 5)"` returns results.
- Notes: This serves as a reference implementation for the meta-skill.

#### Task 5.4: Write `literature-review.md` Skill

- Status: COMPLETED
- Objective: Academic-focused skill variant for literature reviews.
- Steps:
  1. Create `skills/literature-review.md` with academic-specific workflow
  2. Emphasize arXiv search, citation tracking, methodology assessment
  3. Include structured literature review format: Introduction, Methodology, Themes, Gaps, Conclusions
  4. Include guidance on assessing paper quality: peer-reviewed vs preprint, citations, journal impact
  5. Reference `search_arxiv.py` extensively
- Validation: An agent using this skill can produce a structured literature review with proper academic citations.
- Notes: Demonstrates that the skill system supports domain-specific variants.

#### Task 5.5: Write Agent Adapter Documentation

- Status: COMPLETED
- Objective: `adapters/<agent>/README.md` exists for Claude Code, OpenCode, and Cursor.
- Steps:
  1. Create `adapters/claude-code/README.md`: how to install skills into Claude Code, how to configure, example workflow
  2. Create `adapters/opencode/README.md`: same for OpenCode
  3. Create `adapters/cursor/README.md`: how to create `.cursor/rules/` from skills, example workflow
  4. Each adapter explains: installation, configuration, known limitations, example session
  5. Include screenshots or example command sequences
- Validation: A user can follow the adapter docs to set up the toolkit with their preferred agent.
- Notes: These are the primary entry points for users of specific agents.

#### Task 5.6: Create Sample Completed Workspace

- Status: COMPLETED
- Objective: `examples/sample-workspace/` contains a complete research example.
- Steps:
  1. Perform a full research session on a simple question (e.g., "What is the difference between async and sync Python?")
  2. Save the complete workspace to `examples/sample-workspace/`
  3. Include: config.json, sources/ (5-10 sources), notes/findings.md (10-20 findings), notes/summary.md (5-10 insights), notes/gaps.md, outputs/report.md (full report with citations), outputs/bibliography.md
  4. Add `examples/README.md` explaining what this example demonstrates
  5. Verify traceability: every finding references a source, every insight references findings, every report claim cites sources
- Validation: `examples/sample-workspace/` is complete and `workspace_info.py audit examples/sample-workspace` returns status: OK.
- Notes: This serves as a reference for agents and users. Must be high quality.

#### Task 5.7: Write `CHANGELOG.md`

- Status: COMPLETED
- Objective: Document all changes in a changelog file.
- Steps:
  1. Create `CHANGELOG.md` with sections for each version
  2. Add entry for v0.1.0: initial release with M0-M4 complete
  3. Document: features added, known limitations, breaking changes (none for v0.1.0)
  4. Use Keep a Changelog format: Added, Changed, Deprecated, Removed, Fixed, Security
- Validation: CHANGELOG.md exists and has a v0.1.0 entry summarizing all M0-M4 work.
- Notes: Required by the Cleanup phase of the manual-planning skill.

---

### Milestone 6: Cleanup And Final Verification

- Status: COMPLETED
- Purpose: Ensure the repository contains only intentional final artifacts and the complete change is verified.
- Exit Criteria: Intermediate artifacts are removed, all final verification passes, and the plan status is COMPLETED.

#### Task 6.1: Cleanup Intermediate Artifacts

- Status: COMPLETED
- Objective: Remove artifacts created only to support implementation.
- Steps:
  1. Inspect the worktree for temporary documentation, one-off scripts, scratch tests, generated data, logs, and obsolete plan fragments
  2. Remove only artifacts that are not part of the intended final repository state
  3. Keep maintainable tests, fixtures, docs, and generated files that are part of the repository contract
  4. Remove `workspaces/test-ws/` and `workspaces/e2e-test/` (test workspaces from M1/M2)
  5. Remove any `__pycache__/` directories
  6. Remove any `.pyc` files
  7. Verify `.gitignore` excludes: `__pycache__/`, `*.pyc`, `workspaces/` (except examples), `.venv/`, `uv.lock` (or keep if part of contract)
- Validation: Worktree diff contains only intended final changes. No test workspaces, no cache files, no temporary scripts.
- Notes: Do not remove user-provided files or unrelated worktree changes.

#### Task 6.2: Final Verification

- Status: COMPLETED
- Objective: Validate the integrated change after cleanup.
- Steps:
  1. Run `./setup.sh` on a clean environment (or verify it would work)
  2. Run `python scripts/init_workspace.py final-test`
  3. Run `python scripts/search_web.py "test query" --workspace workspaces/final-test --max-results 3`
  4. Run `python scripts/workspace_info.py list`
  5. Run `python scripts/workspace_info.py audit workspaces/final-test`
  6. Run `python tests/golden/run.py --use-cache`
  7. Run `python tests/golden/compare.py tests/golden/runs/first-run-* tests/golden/runs/latest`
  8. Verify all scripts exit with code 0
  9. Verify all JSON outputs are valid
  10. Verify all workspace files have valid frontmatter/structure
  11. Remove `workspaces/final-test/` after verification
  12. Test one-liner installer in a temp directory: `curl -fsSL https://raw.githubusercontent.com/calixto/calixto/main/install.sh | bash --dry-run` (or local equivalent) verifies fresh install mode
  13. Test one-liner installer in existing workspace: same command in the test workspace verifies update mode without losing data
  14. Verify install.sh and install.ps1 have executable permissions and are syntactically valid
- Validation: All 14 verification steps pass without errors.
- Notes: This is the final proof that the complete toolkit works end-to-end, including the one-liner installer.

---

## Approval Gate

Implementation was approved and executed on 2026-06-06 in a single working session. All 38 tasks across 6 milestones were completed in the target repository at `D:\Repos\calixto-research-workspace`. This plan file is preserved as the execution ledger and is being moved alongside the implementation.

## Plan Self-Check

- [x] Plan location follows the default location rule (docs/ directory).
- [x] Scope, non-goals, assumptions, and open questions are explicit.
- [x] No unresolved open questions remain.
- [x] Tasks are grouped into milestones because the plan has more than 10 tasks.
- [x] Every task has concrete steps and validation.
- [x] Every milestone has exit criteria.
- [x] Cleanup and final verification are included.
- [x] The plan avoids vague actions without concrete targets.
- [x] The plan can be executed by a coding agent without reading the original conversation.
- [x] Plan follows milestoned-plan-template structure.
- [x] All task statuses use the allowed values (TO BE DONE, IN PROGRESS, COMPLETED, BLOCKED, SKIPPED).
- [x] All plan statuses use the allowed values (DRAFT, QUESTIONS PENDING, READY FOR APPROVAL, APPROVED, IN PROGRESS, COMPLETED, BLOCKED).
- [x] Every task has an Objective, Steps, Validation, and Notes section.
- [x] Every milestone has Status, Purpose, Exit Criteria, and owned tasks.
- [x] All cross-references between tasks are correct and point to the right task numbers.
- [x] .gitignore is created in Task 1.1 (not just referenced in cleanup).
- [x] pyproject.toml creation is part of Task 1.4 (not implicit).
- [x] Decision log file creation is Task 1.9, and usage rules are in the Decision Log Usage section.
- [x] Decision log format, numbering, and escalation rules are explicit.
- [x] No circular references or dependencies between tasks.
- [x] One-liner installer for Unix is Task 1.10 (install.sh).
- [x] One-liner installer for Windows is Task 1.11 (install.ps1).
- [x] Installer supports both fresh install and workspace update modes.
- [x] Installer safety: never deletes user data, always asks confirmation, backs up before updating.
- [x] One-liner documentation is Task 1.12 (AGENTS.md and README.md).
- [x] Scope section explicitly includes one-liner installer scripts.

## Execution Notes

- Update milestone and task status before starting and after validation.
- Update each task to COMPLETED immediately after its validation passes.
- Mark tasks or milestones BLOCKED with a short reason when progress cannot continue.
- The plan file is the execution ledger. Keep it accurate before moving forward.
- When a task is blocked, record the blocker in the task's Notes section and consider adding to Open Questions.

## Decision Log Usage

**Location:** `docs/initial-implementation-plan-decision-log.md`

**Purpose:** This log captures all decisions made during implementation that were not part of the original plan. The plan cannot anticipate every constraint, ambiguity, or discovery. This log is the authoritative record of those in-flight decisions.

**When to add an entry:** You MUST add a decision log entry whenever you:
- Make a choice that the plan does not specify (e.g., which Python library to use for a helper function, which file structure to adopt, which error message format to use)
- Interpret an ambiguous requirement in `requirements.md` (e.g., "what counts as a valid slug for workspace names?")
- Discover a constraint not anticipated by the plan (e.g., "Crawl4AI requires Python 3.10+ on Windows")
- Need to deviate from the plan's specified approach (e.g., "Plan says use X, but X doesn't work in environment Y, so using Z instead")
- Change scope, validation criteria, or exit criteria of a task
- Make a tradeoff between competing concerns (e.g., performance vs. simplicity, completeness vs. time)

**When NOT to add an entry:** Do NOT add entries for:
- Routine implementation choices that are obvious from context (e.g., "I used a for loop to iterate over the list")
- Decisions already specified in the plan or requirements.md
- Decisions that should be elevated to a full ADR (see below)

**Entry format:** Each entry must be a markdown section with this exact structure:

```markdown
## Decision NNN: <Short title>

- **Date:** YYYY-MM-DD
- **Task:** <Task ID and name, e.g., "Task 2.4: Implement search_web.py with ID Assignment">
- **Milestone:** <Milestone name, e.g., "Milestone 2: MVP: Search and Persist (M1)">
- **Decision:** <What was decided. Be specific.>
- **Rationale:** <Why this decision was made. What alternatives were considered? What constraints drove the choice?>
- **Impact:** <What does this affect? Does it change other tasks, validation, or the plan?>

```

**Numbering:** Use sequential 3-digit numbers (001, 002, 003, ...). Never reuse a number.

**When to consider an ADR instead:** If a decision represents a significant architectural choice with long-term consequences, create a full ADR in `docs/adr/` instead of (or in addition to) a decision log entry. ADRs are for decisions that future maintainers need to understand. Decision log entries are for tactical implementation choices.

**When to ask the user:** If a decision has significant user-facing impact, changes the project direction, or affects multiple milestones, STOP and ask the user before proceeding. Add the question to Open Questions in this plan and set plan status to QUESTIONS PENDING. Do not make such decisions unilaterally.

**Example entry:**

```markdown
## Decision 001: Use pathlib.Path instead of os.path for file operations

- **Date:** 2026-06-06
- **Task:** Task 1.1: Create Repository Directory Structure
- **Milestone:** Milestone 1: Foundation (M0)
- **Decision:** All scripts will use `pathlib.Path` for file and path operations instead of `os.path` functions.
- **Rationale:** pathlib provides a more modern, object-oriented API that is easier to read and less error-prone than string-based os.path operations. It also handles cross-platform path separators automatically. Considered: os.path (older, string-based), pathlib (chosen), custom path utilities (rejected: reinvention).
- **Impact:** All scripts that create or check file paths must use pathlib. This is a coding standard, not a plan change.
```

**Enforcement:** The plan is incomplete without decision log entries for all non-trivial implementation decisions. Reviewers should check the decision log when reviewing the final repository to ensure the implementation is fully traceable.
