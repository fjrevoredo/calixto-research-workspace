# Calixto Research Workspace: Requirements

## 1. Vision

An agent-first research toolkit that treats research like a coding project. Any coding agent (Claude Code, OpenCode, Cursor, Codex, etc.) can use our skills, scripts, and templates to perform structured, reproducible deep research, from web search to final report.

We are **not** building an app. We are building **infrastructure**: the skills, tools, and conventions that multiple agents can use consistently.

### 1.1 Core Principles

- **Agent-first.** The project is designed to be understood, modified, extended, and maintained by coding agents. Comprehensive documentation enables agents to work autonomously.
- **Two modes of operation.** Research mode (default) for performing research. Developer mode for modifying, extending, or maintaining the toolkit. Each mode loads only the context it needs.
- **File-based state.** Every research session is a workspace folder. All state lives in files (Markdown, JSON). No databases, no servers.
- **Toolkit root plus standalone workspaces.** The repository root is the toolkit source and factory. Each generated workspace is a self-contained runtime snapshot that can be copied elsewhere and continue after local dependency setup.
- **Traceability.** Every piece of information has a unique ID and can be traced back to its origin through the full provenance chain.
- **Modular and configurable.** Each tool does exactly one thing. Opinionated defaults work out of the box, but every choice can be overridden.
- **Honest about dependencies.** Crawl4AI + Playwright + Chromium is ~500MB. We make setup easy but don't pretend it's lightweight.
- **Separate search from scraping.** Search providers find URLs. Crawl4AI scrapes them into clean markdown. These are distinct layers.
- **LLM and harness agnostic, pragmatically.** Agnostic solutions first. Specialized features when they deliver significantly better results. The agnostic path must always work.
- **Reproducible within reason.** Web search results change over time. We cache aggressively and accept "similar" not "identical" for golden runs.

---

## 2. Scope

### 2.1 In Scope

| Layer | What we build | Notes |
|---|---|---|
| **Skills** | Markdown instruction files for agents | Research preparation, deep research, literature review, meta-skills |
| **Scripts** | Python CLI helpers | Top-level research/open/runtime orchestration plus lower-level search and workspace helpers |
| **Providers** | Pluggable search and scrape backends | DuckDuckGo (default), Brave, Tavily, Crawl4AI |
| **Templates** | Workspace folder structure conventions | Copied on workspace creation |
| **Examples** | Golden dataset research workspace | Reproducible benchmark + reference implementation |
| **Setup** | One-shot environment setup script | Installs deps, verifies everything works |

### 2.2 Out of Scope (for now)

- MCP servers (may add later if needed)
- Frontend / UI
- Hosted / cloud deployment
- Multi-agent orchestration frameworks (LangGraph, CrewAI, etc.)
- Custom LLM fine-tuning or training
- LLM-based extraction scripts (agent does this directly with its own model)

---

## 3. Architecture

### 3.1 Repository Structure

``` 
research-workspace/
├── README.md
├── PHILOSOPHY.md                 # Guiding principles and decision framework
├── AGENTS.md                     # How any coding agent uses this repo
├── requirements.md               # This file
├── setup.sh                      # One-shot env setup (bash)
├── setup.ps1                     # One-shot env setup (PowerShell for Windows)
│
├── skills/
│   ├── research-preparation/
│   │   └── SKILL.md              # Toolkit-side question triage and workspace handoff
│   ├── deep-research/
│   │   └── SKILL.md              # Toolkit-side handoff into a standalone workspace
│   ├── literature-review/
│   │   └── SKILL.md              # Toolkit-side handoff into a standalone workspace
│   ├── create-skill/
│   │   └── SKILL.md              # Meta: how to add new skills
│   ├── integrate-tool/
│   │   └── SKILL.md              # Meta: how to add new tools/providers
│   └── research-retrospective/
│       └── SKILL.md              # Toolkit-only maintainer meta-skill
│
├── adapters/
│   ├── claude-code/              # Claude Code skill installation
│   │   └── README.md             # How to wire skills into Claude Code
│   ├── opencode/                 # OpenCode skill installation
│   │   └── README.md
│   └── cursor/                   # Cursor rules setup
│       └── README.md
│
├── runtime/                      # Standalone workspace runtime sources + manifest
│   ├── workspace-manifest.json
│   └── workspace/
│       ├── AGENTS.md
│       ├── setup.sh / setup.ps1
│       └── skills/
├── templates/
│   └── workspace/                # Seed research-state files copied into workspaces
│       ├── config.json           # Research params, providers, scope
│       ├── sources/
│       │   ├── index.json        # Source registry with IDs
│       │   ├── web/              # Crawled pages as markdown
│       │   ├── papers/           # arXiv papers / metadata
│       │   └── code/             # GitHub repos, docs, SO posts
│       ├── notes/
│       │   ├── findings.md       # Extracted facts with IDs (fnd_NNN)
│       │   ├── summary.md        # Agent's synthesis with insight IDs (ins_NNN)
│       │   └── gaps.md           # Identified gaps / follow-up questions
│       └── outputs/
│           ├── report.md         # Final deliverable
│           └── bibliography.md   # All sources with quality ratings
│
├── docs/
│   └── adr/                      # Architecture Decision Records
│       └── 001-choose-crawl4ai.md
│
├── scripts/
│   ├── init_workspace.py         # Create workspace from template
│   ├── search_web.py             # Search + scrape pipeline
│   ├── search_arxiv.py           # arXiv API helper
│   ├── search_pubmed.py          # PubMed / MEDLINE helper
│   └── workspace_info.py         # List, inspect, delete workspaces
│
├── providers/
│   ├── search/
│   │   ├── base.py               # Abstract search provider interface
│   │   ├── duckduckgo.py         # Free, no API key (default)
│   │   ├── brave.py              # Paid, better quality
│   │   └── tavily.py             # Paid, AI-optimized
│   └── scrape/
│       └── crawl4ai_provider.py  # Crawl4AI wrapper for all scraping
│
├── tests/
│   └── golden/
│       ├── README.md             # Golden dataset spec and how to run
│       ├── config.json           # Research config for the golden run
│       ├── cache/                # Cached search results for reproducibility
│       └── expected/             # Reference outputs for comparison
│
├── examples/
│   └── sample-workspace/         # Reference standalone workspace
└── workspaces/                   # Generated standalone workspaces
```

### 3.2 Workspace Structure

Every research session creates a standalone workspace folder. The agent works inside it like a coding project:

```
workspaces/
└── <research-topic-slug>/
    ├── AGENTS.md                 # Workspace-local research entry point
    ├── pyproject.toml            # Workspace dependency manifest
    ├── setup.sh / setup.ps1      # Workspace-local bootstrap
    ├── skills/
    │   ├── research-preparation/
    │   │   └── SKILL.md
    │   ├── deep-research/
    │   │   └── SKILL.md
    │   └── literature-review/
    │       └── SKILL.md
    ├── scripts/
    │   ├── search_web.py
    │   ├── search_arxiv.py
    │   ├── search_pubmed.py
    │   └── workspace_info.py
    ├── providers/
    │   ├── search/
    │   └── scrape/
    ├── config.json
    ├── sources/
    │   ├── index.json            # Source registry with IDs
    │   ├── web/
    │   │   ├── src_001.md        # Crawled page with metadata header
    │   │   ├── src_002.md
    │   │   └── ...
    │   ├── papers/
    │   │   ├── src_010.md
    │   │   └── ...
    │   └── code/
    │       └── ...
    ├── notes/
    │   ├── research-brief.md     # Question triage, assumptions, scope, handoff
    │   ├── findings.md           # Extracted facts with IDs (fnd_NNN)
    │   ├── summary.md            # Agent's synthesis with insight IDs (ins_NNN)
    │   └── gaps.md               # Identified gaps / follow-up questions
    └── outputs/
        ├── report.md             # Final research report with citations
        └── bibliography.md       # All sources with quality ratings
```

### 3.3 Search vs. Scrape Architecture

These are two distinct layers. Search finds URLs. Scrape gets content.

```
User query
    │
    ▼
┌─────────────────┐
│  Search Provider │  ← Finds URLs (DuckDuckGo, Brave, Tavily)
│  returns: URLs   │
└────────┬────────┘
         │ list of URLs
         ▼
┌─────────────────┐
│  Scraper         │  ← Fetches + cleans content (Crawl4AI)
│  returns: markdown│
└────────┬────────┘
         │
         ▼
  sources/web/*.md   ← Saved to workspace with frontmatter
```

### 3.4 Dependencies

| Dependency | Purpose | Required | Size |
|---|---|---|---|
| Python 3.11+ | Runtime | Yes | (none) |
| uv | Python package manager | Yes | ~10MB |
| Crawl4AI | Web scraping (URL → markdown) | Yes | ~50MB |
| Playwright + Chromium | Browser for Crawl4AI | Yes | ~450MB |
| ddgs | Free web search (default) | Yes | ~1MB |
| arxiv (Python) | arXiv API client | Optional | ~1MB |
| brave-search | Brave search API client | Optional | ~1MB |
| tavily-python | Tavily search API client | Optional | ~1MB |

**Total required install: ~500MB** (mostly Chromium). Setup script handles this.

---

## 4. Script Interfaces

### 4.1 `calixto`

Top-level managed workflow for creating, reopening, and maintaining workspaces.

``` 
calixto research "<question>" [--name slug] [--path DIR] [--agent none|opencode|claude|codex] \
    [--json] [--check-updates | --skip-update-check] [--require-update-check] [--update-before-create]
calixto open <slug-or-path> [--agent none|opencode|claude|codex] [--prepare-harness] [--setup-local]
calixto runtime list
calixto runtime prune [--key KEY] [--apply] [--force]
```

- `research` creates a standalone workspace, stores the exact question in `config.json`, prepares harness skill mirrors when requested, and uses the toolkit-managed runtime only when the workspace is eligible
- `open` reopens a workspace through the exact compatible managed runtime or a validated workspace-local `.venv`
- `runtime list` reports managed runtime keys and references
- `runtime prune` removes old managed runtime keys conservatively
- `--json` is valid only with `--agent none`
- `init_workspace.py` remains the lower-level workspace factory for automation

### 4.2 `init_workspace.py`

Create a new standalone research workspace snapshot.

``` 
uv run python scripts/init_workspace.py <name> [--path ./workspaces] \
    [--check-updates | --skip-update-check] \
    [--require-update-check] \
    [--update-before-create]
```

- Creates `workspaces/<name>/` as a standalone runtime snapshot
- In interactive terminals, checks whether the toolkit root is behind the
  remote default branch before creating the workspace
- `--skip-update-check` suppresses the interactive freshness check
- `--check-updates` forces the freshness check in non-interactive runs
- `--require-update-check` fails before workspace creation if the check cannot
  be completed
- `--update-before-create` prints the exact installer update command and exits
  without creating a workspace when the toolkit is behind
- Copies bundled scripts, providers, skills, setup helpers, and seed state files
- Writes explicit workspace metadata into `config.json`
- Prints structured JSON including the workspace path and runtime metadata

### 4.3 `search_web.py`

Search the web and scrape results into the workspace.

```
python scripts/search_web.py "<query>" --workspace <path> \
    [--max-results 10] \
    [--search-provider duckduckgo|brave|tavily] \
    [--no-scrape] \
    [--truncate 5000]
```

- Runs search provider to find URLs matching the query
- Scrapes each URL via Crawl4AI into clean markdown
- Assigns sequential source IDs (src_NNN) to each result
- Saves each result as `sources/web/src_NNN.md` with YAML frontmatter
- Appends search record to `config.json` searches array
- Updates `sources/index.json` with source ID, URL, and metadata
- Deduplicates by URL (skips if already in workspace)
- `--no-scrape` saves only URLs + snippets (faster, no Chromium needed)
- `--truncate N` caps each source at N words

### 4.4 `search_arxiv.py`

Search arXiv for academic papers.

```
python scripts/search_arxiv.py "<query>" --workspace <path> \
    [--max-results 10] \
    [--category cs.AI] \
    [--must-contain "exact phrase"] \
    [--min-query-token-overlap 2]
```

- Queries arXiv API (rate limited: 1 req/3s)
- Assigns sequential source IDs (src_NNN) to each result
- Saves paper metadata as markdown in `sources/papers/src_NNN.md`
- Updates `sources/index.json` with source ID and metadata
- Optionally downloads PDFs
- Deduplicates by arXiv ID
- Warns when a likely biomedical query is sent to arXiv without a fitting `q-bio` category
- `--must-contain` filters obviously irrelevant lexical matches before they consume source slots
- `--min-query-token-overlap` marks low-overlap saved results as corroboration-required instead of silently treating them as normal evidence

### 4.5 `search_pubmed.py`

Search PubMed / MEDLINE for biomedical papers.

```
python scripts/search_pubmed.py "<query>" --workspace <path> \
    [--max-results 10] \
    [--email you@example.com] \
    [--api-key <key>]
```

- Uses NCBI E-utilities over HTTPS; no API key is required for basic use
- Saves paper metadata and abstracts as markdown in `sources/papers/src_NNN.md`
- Updates `sources/index.json` with shared workspace `src_NNN` IDs
- Stores PubMed ID, journal, authors, publication date, DOI, and abstract when available
- Uses the same cache conventions as the other search scripts

### 4.6 `workspace_info.py`

Manage existing workspaces.

```
python scripts/workspace_info.py list [--path ./workspaces]
python scripts/workspace_info.py show <name> [--path ./workspaces]
python scripts/workspace_info.py delete <name> [--path ./workspaces]
python scripts/workspace_info.py audit <name> [--path ./workspaces] [--strict-traceability]
python scripts/workspace_info.py verify-citations <name> [--path ./workspaces] [--output PATH] [--json-only]
```

- `list`: shows all workspaces with source counts and last modified date
- `show`: displays workspace summary (question, sources, searches done)
- `delete`: removes a workspace folder
- `audit`: verifies traceability chain integrity (all IDs valid, no orphans, references resolve)
- `audit --strict-traceability`: fails when report citations bypass findings, cited sources remain pending, or used sources are uncited
- `verify-citations`: generates `outputs/citation-check.md`, a deterministic manual citation-review checklist with report lines, cited source metadata, and candidate source excerpts

---

## 5. Provider Interfaces

### 5.1 Search Provider Contract

All search providers implement the same interface:

```python
class SearchResult:
    url: str
    title: str
    snippet: str
    score: float  # relevance score if available

class SearchProvider:
    def search(self, query: str, max_results: int = 10) -> list[SearchResult]: ...
```

### 5.1.1 Scrape Provider Contract

All scrape providers implement the same interface:

```python
class ScrapeResult:
    url: str
    title: str
    markdown: str
    word_count: int
    metadata: dict  # additional metadata (date, author, etc.)

class ScrapeProvider:
    def scrape(self, url: str) -> ScrapeResult: ...
```

### 5.2 Default Provider: DuckDuckGo

- Free, no API key required
- Uses the `ddgs` Python package
- Rate limited (~20 requests/minute)
- Good enough for most research tasks

### 5.3 Optional Providers

| Provider | API Key | Quality | Rate Limit | Cost |
|---|---|---|---|---|
| DuckDuckGo | None | Good | ~20/min | Free |
| Brave Search | Yes | Better | 2000/month free | Free tier / paid |
| Tavily | Yes | Best (AI-optimized) | 1000/month free | Free tier / paid |

### 5.4 Scrape Provider: Crawl4AI

All scraping goes through Crawl4AI. It provides:
- Clean LLM-friendly markdown
- Metadata extraction (title, date, description)
- Link extraction
- JavaScript rendering
- Caching (avoids re-scraping same URL)

### 5.5 Adding New Providers

See `skills/integrate-tool.md` for instructions on:
- Adding a new search provider (implement `SearchProvider` interface)
- Adding a new scrape backend (implement scrape interface)
- Updating `search_web.py` to use new providers

---

## 6. Skills

### 6.1 `research-preparation`: Question Triage And Brief Creation

The preparation skill runs before source gathering when the user's topic needs
normalization. It teaches the agent to:

1. Triage the raw question for clarity, scope, domain, stakes, time sensitivity, source needs, and report shape
2. Decide whether to proceed directly, ask targeted clarification, or proceed with explicit assumptions
3. Write a durable `notes/research-brief.md`
4. Keep `config.json.question` as the concise refined question
5. Hand off into `deep-research` or `literature-review`

This skill is bundled into standalone workspaces and is also available as a
toolkit-root handoff skill for starting a new workspace cleanly.

### 6.2 `deep-research.md`: General Deep Research Workflow

The main skill. Teaches any agent how to perform research from start to finish:

1. **Initialize**: Confirm the prepared brief or refine the question and scope first
2. **Search**: Run web/paper searches with the right scholarly provider, collect sources (scripts assign src_NNN IDs)
3. **Evaluate**: Assess source quality, identify gaps
4. **Extract**: Agent reads sources and extracts key facts, assigning fnd_NNN IDs and referencing source IDs
5. **Synthesize**: Write summary with ins_NNN IDs, referencing finding IDs, connecting findings
6. **Report**: Generate final markdown report with source ID citations, strict traceability audit, and citation-check artifact
7. **Iterate**: Refine, expand, or start over

Must work for any topic: consumer advice, technical research, academic literature, competitive analysis, etc.

**Key design decision**: The agent does extraction, synthesis, and reporting using its own LLM capabilities. We do NOT provide LLM-calling scripts. This keeps us model-agnostic and avoids API key dependencies.

**Traceability requirement**: The skill explicitly instructs the agent to maintain the full provenance chain (src > fnd > ins > report) by assigning and referencing IDs at each step.

### 6.3 `literature-review.md`: Academic Variant

Focused on academic research: domain-aware scholarly-provider selection, citation tracking, methodology assessment, and structured literature review format. arXiv stays primary for CS/math/physics; PubMed is preferred for biomedical and clinical questions.

### 6.4 `create-skill.md`: Meta-Skill

Instructions for creating new research skills:
- Skill file format and conventions
- How to reference scripts and templates
- How to define workflow stages
- Examples of good skill structure

### 6.5 `integrate-tool.md`

Instructions for adding new tools/providers:
- How to add a new search provider (implement the interface)
- How to add a new scrape backend
- How to add a new data source (e.g., Semantic Scholar, PubMed)
- Script conventions and interfaces
- How to update skills to use new tools

### 6.6 `research-retrospective`: Maintainer Meta-Skill

Developer-mode workflow for evaluating completed research and improving the
toolkit:

- Produce an independent adversarial review of a completed workspace.
- Convert the adversarial findings into a case-specific but non-leading
  questionnaire for the original research agent.
- Pause while the user transfers the questionnaire to the original research
  session and returns that agent's answers.
- Preserve the questionnaire answers verbatim.
- Triangulate workspace evidence, Agent B findings, and Agent A feedback into
  prioritized, testable improvements.
- Consider fixes, missing features, removals, simplifications, process changes,
  scaffold changes, runtime/setup issues, and documentation/test gaps.

This skill is toolkit-root only. It is not included in
`runtime/workspace-manifest.json` and must not be copied into standalone
research workspaces.

---

## 7. Traceability

### 7.1 ID System

Every piece of information in a workspace has a unique ID for full provenance tracking:

| ID Type | Format | Assigned By | Location |
|---|---|---|---|
| Source | `src_NNN` | Scripts (`search_web.py`, `search_arxiv.py`) | `sources/index.json`, source file frontmatter |
| Finding | `fnd_NNN` | Agent during extraction | `notes/findings.md` |
| Insight | `ins_NNN` | Agent during synthesis | `notes/summary.md` |

IDs are:
- Sequential within each workspace (src_001, src_002, ...)
- Never reused (if a source is deleted, its ID is retired)
- Workspace-scoped (forking preserves all IDs)

### 7.2 Provenance Chain

The full traceability chain:

```
search query "best GPU under $500"
  → src_003 (tomshardware.com review)
    → fnd_001 (price-performance claim)
      → ins_001 (VRAM-first purchasing advice)
        → report.md paragraph 2
```

### 7.3 Traceability Rules

- Every finding MUST reference at least one source ID
- Every insight MUST reference at least one finding ID
- Every report claim MUST reference at least one source ID
- Skills instruct the agent to maintain these references explicitly

### 7.4 Traceability Audit

The agent or a future script can verify:
- Are all source IDs in findings present in `index.json`?
- Are all finding IDs in insights present in `findings.md`?
- Are all source IDs cited in the report present in `index.json`?
- Are there orphaned sources (collected but never cited)?

---

## 8. Two Modes of Operation

### 8.1 Research Mode (Default)

The agent is performing research inside a workspace. It loads only:
- The active skill (e.g., `research-preparation` or `deep-research`)
- Script usage (help text, arguments)
- Workspace structure and conventions

It does NOT load:
- Internal architecture docs
- Provider implementation details
- Meta-skills (`create-skill.md`, `integrate-tool.md`)
- Development guides
- Code-level documentation

### 8.2 Developer Mode

The agent is modifying, extending, or maintaining the toolkit itself. It loads:
- `AGENTS.md` (full repo overview)
- Provider interfaces and implementations
- Meta-skills
- Architecture Decision Records
- Test infrastructure and golden dataset
- Contribution guidelines
- Code-level documentation

### 8.3 Mode Switching

Mode switching is explicit and user-driven:
- User says "switch to developer mode" or asks for a development task
- Agent loads additional context as needed
- When development task is done, agent returns to research mode
- Agent never loads developer context during research unless explicitly asked

### 8.4 Documentation in `AGENTS.md`

`AGENTS.md` documents:
- How to switch between modes
- What context each mode loads
- When to use each mode
- How mode switching affects agent behavior

---

## 9. Agent Adapters

### 9.1 The Problem

Our skills live in `skills/*.md` but each agent loads instructions differently:

| Agent | How it loads skills | How it reads conventions |
|---|---|---|
| Claude Code | `.claude/skills/` or skill system | `CLAUDE.md` |
| OpenCode | `.opencode/skills/` | `AGENTS.md` |
| Cursor | `.cursor/rules/` | `.cursorrules` |
| Codex | `AGENTS.md` | `AGENTS.md` |

### 9.2 Our Approach

- `AGENTS.md` at repo root: universal entry point for any agent
- `adapters/<agent>/README.md`: agent-specific setup and launch instructions
- Each adapter explains the toolkit-root vs workspace-root boundary for that agent
- Skills themselves are agent-agnostic markdown, with canonical workspace copies bundled into standalone workspaces and harness-native mirrors generated when supported

### 9.3 `AGENTS.md`

A single file at the repo root that tells any coding agent:
- What this repo is and how to use it
- How to set up the environment (`setup.sh` / `setup.ps1`)
- How to run scripts
- Where to find skills and how to load them
- Workspace conventions
- How to run the golden dataset test
- Links to agent-specific adapter docs
- How to switch between research and developer modes

### 9.4 Adapter Docs

Each `adapters/<agent>/README.md` covers:
- How to install/link skills for that agent
- Any agent-specific configuration
- Known limitations or quirks
- Example workflow for that agent

---

## 10. Golden Dataset

### 10.1 Purpose

A reproducible research example that serves as:
- **Validation**: Proves the workflow works end-to-end
- **Benchmark**: Measures impact of changes (search provider, model, prompts)
- **Reference**: Shows agents what a completed workspace looks like

### 10.2 Reproducibility Strategy

Web search results change over time. We handle this by:
- **Caching search results** in `tests/golden/cache/`: first run caches, subsequent runs use cache
- **Accepting "similar" not "identical"**: evaluation checks structure and quality, not exact content
- **Versioning golden runs**: each run is timestamped, we track how results drift over time
- **Fixed search queries**: the golden config specifies exact queries, not dynamic ones

### 10.3 Structure

```
tests/golden/
├── README.md                 # Spec: question, config, how to run, how to compare
├── config.json               # Fixed research parameters
├── cache/                    # Cached search API responses
│   └── duckduckgo/
│       └── <query_hash>.json
├── expected/
│   ├── source_count_range.json   # Expected source count (min-max)
│   ├── report_sections.json      # Expected report sections (names, not content)
│   └── quality_checks.json       # Structural assertions
└── runs/                     # Historical run results
    └── <timestamp>/
        ├── config.json
        ├── sources/
        ├── notes/
        └── outputs/
```

### 10.4 Evaluation Criteria

| Criterion | How we check | Tolerance |
|---|---|---|
| Sources collected | Count of files in `sources/` | ±30% of expected |
| Source diversity | Unique domains | ≥3 different domains |
| Report completeness | Expected sections present | All sections present |
| Citation quality | Sources referenced in report | ≥80% of sources cited |
| Traceability | All IDs properly referenced in chain | 100% valid references |
| ID counter validity | `next_id` in index.json matches actual count | Exact match |
| Frontmatter valid | YAML parses correctly | 100% valid |
| No duplicates | No duplicate URLs | 0 duplicates |

### 10.5 Running the Golden Dataset

```
# Fresh run (no cache)
python tests/golden/run.py

# Run with cache (reproducible)
python tests/golden/run.py --use-cache

# Compare two runs
python tests/golden/compare.py <run1> <run2>
```

---

## 11. File Formats

### 11.1 Source Files (`sources/web/src_NNN.md`)

```markdown
---
id: src_001
url: https://example.com/article
title: "Article Title"
date_crawled: 2025-01-15T10:30:00Z
date_published: 2025-01-10
provider: crawl4ai
search_provider: duckduckgo
query: "original search query"
word_count: 1523
truncated: false
quality_tier: scholarly
quality_reasons:
  - scholarly_record
quality_requires_corroboration: false
---

# Article Title

[cleaned markdown content from Crawl4AI]
```

### 11.2 Config (`config.json`)

```json
{
  "name": "research-topic-slug",
  "question": "The research question",
  "next_source_id": 11,
  "next_finding_id": 8,
  "next_insight_id": 3,
  "scope": {
    "domains": ["web", "papers", "code"],
    "max_sources": 20,
    "search_depth": 2
  },
  "providers": {
    "search": "duckduckgo",
    "scrape": "crawl4ai",
    "papers": "arxiv"
  },
  "toolkit_commit_created_with": "abc123def4567890abc123def4567890abc123de",
  "toolkit_build_number_created_with": 42,
  "toolkit_ref_created_with": "master",
  "searches": [
    {
      "query": "search query used",
      "provider": "duckduckgo",
      "timestamp": "2025-01-15T10:30:00Z",
      "results_count": 10,
      "urls_found": ["https://...", "https://..."]
    }
  ],
  "created_at": "2025-01-15T10:00:00Z",
  "updated_at": "2025-01-15T10:30:00Z"
}
```

The `next_source_id`, `next_finding_id`, and `next_insight_id` fields track the next available ID for each type. Scripts and the agent increment these when creating new items.
`toolkit_commit_created_with` is the authoritative toolkit identity for the
workspace snapshot when toolkit provenance is available.
`toolkit_build_number_created_with` is the git commit-count build number for
that snapshot when full history is available, and
`toolkit_ref_created_with` records the local symbolic ref when available.
`question` stores the concise refined research question; the fuller
normalization record belongs in `notes/research-brief.md`, including the raw
question, assumptions, scope, evidence plan, and handoff notes.

### 11.3 Deduplication Registry (`sources/index.json`)

Tracks all collected sources to prevent duplicates:

```json
{
  "next_id": 11,
  "sources": [
    {
      "id": "src_001",
      "url": "https://example.com/article",
      "file": "web/src_001.md",
      "url_normalized": "example.com/article",
      "added_at": "2025-01-15T10:30:00Z",
      "query": "original search query",
      "word_count": 1523,
      "quality_tier": "scholarly",
      "quality_reasons": ["scholarly_record"],
      "quality_requires_corroboration": false
    }
  ]
}
```

The `next_id` field tracks the next available source ID. Scripts increment this when adding new sources. The `url_normalized` field strips protocol, www, trailing slashes, and query params for dedup matching.
`quality_tier`, `quality_reasons`, and `quality_requires_corroboration` are deterministic triage metadata, not semantic proof.

### 11.4 Findings (`notes/findings.md`)

Extracted facts with finding IDs and source references:

```markdown
## fnd_001
**Source:** src_003
**Fact:** The RTX 4060 offers the best price-to-performance ratio under $500.
**Quote:** "For $399, the RTX 4060 delivers 90% of the 4070's performance."
**Confidence:** high

## fnd_002
**Source:** src_001, src_005
**Fact:** VRAM is the primary bottleneck for local LLM inference.
**Confidence:** medium
```

### 11.5 Summary (`notes/summary.md`)

Synthesized insights with insight IDs and finding references:

```markdown
## ins_001
**Based on:** fnd_001, fnd_002
**Insight:** For users focused on local AI workloads, VRAM should be the primary purchasing criterion, making the RTX 4060 Ti (16GB) the best value despite its higher price.

## ins_002
**Based on:** fnd_003, fnd_004, fnd_007
**Insight:** The GPU market in 2025 is segmented into three clear tiers under $500...
```

### 11.6 Citation Check (`outputs/citation-check.md`)

Generated by `workspace_info.py verify-citations`.

- Lists each report line that cites one or more `src_NNN` IDs
- Resolves cited source file paths, review status, and quality tier metadata
- Includes short lexical-overlap excerpts from the cited source files
- Leaves verification status and notes blank for manual completion

This artifact is deterministic and file-based. It prepares a semantic review pass; it does not claim a citation is correct by itself.

---

## 12. Error Handling

### 12.1 Search Failures

| Failure | Behavior |
|---|---|
| Search returns 0 results | Log warning, suggest agent refine query |
| Rate limited by search provider | Exponential backoff, max 3 retries |
| Search provider API error | Fall back to error message in output |
| Invalid query | Validate before sending, return clear error |

### 12.2 Scrape Failures

| Failure | Behavior |
|---|---|
| Page blocked / paywalled | Save source with error note in frontmatter, continue |
| Timeout (>30s) | Skip page, log in source as "timeout" |
| Crawl4AI crash | Save partial results, log error, continue |
| Page too large (>100k words) | Truncate to `--truncate` limit, mark as truncated |
| Non-HTML content (PDF, video) | Skip, log as "unsupported content type" |

### 12.3 Workspace Errors

| Failure | Behavior |
|---|---|
| Workspace already exists | Error with suggestion to use different name or `--force` |
| Config file corrupted | Validate JSON on read, error with recovery suggestion |
| Disk full | Catch IOError, report clearly |
| Concurrent writes to config.json | Sequential writes only (documented constraint) |

### 12.4 Error Output Convention

All scripts use structured error output:
```json
{
  "status": "error",
  "error": "rate_limited",
  "message": "DuckDuckGo rate limit hit. Wait 60s and retry.",
  "retry_after": 60
}
```

Success output:
```json
{
  "status": "ok",
  "sources_added": 8,
  "sources_skipped": 2,
  "source_ids": ["src_001", "src_002", "src_003", "src_004", "src_005", "src_006", "src_007", "src_008"],
  "workspace": "workspaces/my-research"
}
```

Partial success output (some sources failed):
```json
{
  "status": "partial",
  "sources_added": 5,
  "sources_skipped": 3,
  "source_ids": ["src_001", "src_002", "src_005", "src_007", "src_008"],
  "sources_failed": 2,
  "errors": [
    {"url": "https://example.com/blocked", "error": "paywalled"},
    {"url": "https://example.com/timeout", "error": "timeout"}
  ],
  "workspace": "workspaces/my-research"
}
```

---

## 13. Source Deduplication

### 13.1 URL-Level Dedup

- `search_web.py` checks `sources/index.json` before scraping
- URLs are normalized: strip protocol, `www.`, trailing slashes, tracking params
- If URL already exists, skip and log

### 13.2 Content-Level Dedup (Best Effort)

- If two different URLs return near-identical content (>90% text overlap), flag in frontmatter
- Agent decides whether to keep both

### 13.3 Idempotent Searches

- Running the same query twice does not duplicate sources
- New URLs from the same query are added; existing ones are skipped
- `config.json` searches array records all queries with timestamps

---

## 14. Large Content Handling

### 14.1 Truncation

- `--truncate N` flag on `search_web.py` caps each source at N words (default: 10000)
- Truncated sources have `truncated: true` in frontmatter with original word count
- Truncation preserves headings structure (keeps first N words per section)

### 14.2 Agent Strategy (documented in skill)

The skill should instruct the agent to:
- Read source frontmatter first to assess relevance before reading full content
- Process sources in batches if there are many
- Extract key facts into `notes/findings.md` with fnd_NNN IDs as it reads each source
- Synthesize findings into `notes/summary.md` with ins_NNN IDs, referencing finding IDs
- Use `notes/gaps.md` to track what still needs investigation

### 14.3 Context Window Awareness

- Skill should warn agent when source count exceeds ~15 sources
- Agent should process sources incrementally, not all at once
- Summary file serves as compressed context for later stages

---

## 15. Rate Limiting

| Provider | Rate Limit | Our Handling |
|---|---|---|
| DuckDuckGo | ~20 req/min | 3s delay between requests, backoff on 429 |
| arXiv API | 1 req/3s | 3.5s delay between requests |
| Brave Search | 2000/month (free) | Track usage in config, warn at 80% |
| Tavily | 1000/month (free) | Track usage in config, warn at 80% |
| Crawl4AI (local) | No hard limit | 1s delay between page scrapes to be polite |

---

## 16. Workspace Lifecycle

### 16.1 Create

``` 
calixto research "your question" --agent none
```

Lower-level automation path:

``` 
uv run python scripts/init_workspace.py <name>
```

### 16.2 List

```
python scripts/workspace_info.py list
```

Output:
```
workspaces/
  ai-safety-2025       12 sources  last modified: 2025-01-15
  best-gpu-500          8 sources  last modified: 2025-01-14
  space-exploration     15 sources  last modified: 2025-01-13
```

### 16.3 Inspect

```
python scripts/workspace_info.py show ai-safety-2025
```

### 16.3.1 Audit

```
python scripts/workspace_info.py audit ai-safety-2025
```

Checks the traceability chain:
- All source IDs in `findings.md` exist in `index.json`
- All finding IDs in `summary.md` exist in `findings.md`
- All source IDs cited in `report.md` exist in `index.json`
- No orphaned sources (collected but never cited in findings or report)

Returns:
```
Audit results for ai-safety-2025:
  Sources in index: 12
  Sources cited in findings: 10
  Sources cited in report: 11
  Orphaned sources: 1 (src_007)
  Invalid references: 0
  Status: OK (with warnings)
```

### 16.4 Resume

Managed reopening:

```
calixto open <name> --agent codex
```

Agent reads `config.json` to see what searches have been done and what state the workspace is in. No special resume command needed. The files ARE the state.

### 16.5 Fork

```
cp -r workspaces/ai-safety-2025 workspaces/ai-safety-2025-v2
```

Agent can fork a workspace by copying it, then continuing research with different queries or parameters.

### 16.6 Delete

```
python scripts/workspace_info.py delete ai-safety-2025
```

### 16.7 Archive

Agent can commit workspace to git for archival. All files are text, so git works naturally.

---

## 17. Platform Support

### 17.1 Linux (Primary)

- `setup.sh` handles everything
- Full support

### 17.2 macOS (Primary)

- `setup.sh` handles everything
- Full support

### 17.3 Windows (Native)

- `setup.ps1` PowerShell equivalent
- Crawl4AI on Windows has known quirks (Playwright browser install)
- Setup script includes Windows-specific workarounds

### 17.4 Windows (WSL)

- Use `setup.sh` as on Linux
- Full support

---

## 18. Non-Functional Requirements

- **Setup time**: < 5 minutes from clone to first search (excluding Chromium download)
- **Zero API keys required** for basic web search (DuckDuckGo + Crawl4AI)
- **No daemon/server**: Everything runs as CLI commands
- **Git-friendly**: All workspace files are text, diffable, committable
- **Idempotent**: Running the same search twice does not duplicate sources
- **Sequential writes**: All file writes are sequential (no concurrent write support)
- **Structured output**: All scripts output JSON for agent consumption
- **Graceful degradation**: Partial failures don't lose already-collected data
- **Agent-first documentation**: All code, scripts, and skills documented well enough for agents to understand, use, and extend
- **Traceability**: All information traceable to origin via ID system

---

## 19. Milestones

### M0: Foundation
- [ ] Repo structure created
- [ ] `AGENTS.md` written (with two-mode documentation)
- [ ] `setup.sh` and `setup.ps1` working
- [ ] Workspace template defined
- [ ] Provider interfaces defined (`providers/search/base.py`)

### M1: MVP (search + persist)
- [ ] `init_workspace.py` working
- [ ] DuckDuckGo search provider implemented
- [ ] Crawl4AI scrape provider implemented
- [ ] `search_web.py` working (search, scrape, save with ID assignment)
- [ ] Source deduplication via `sources/index.json`
- [ ] Sources saved as markdown with frontmatter including ID
- [ ] `research-preparation` skill and `notes/research-brief.md` template
- [ ] Basic `deep-research.md` skill (with traceability instructions)

### M2: Analyze + report
- [ ] `search_arxiv.py` working (with ID assignment)
- [ ] `workspace_info.py` working (list, show, delete)
- [ ] Skill covers full workflow through report generation
- [ ] Traceability chain documented (src > fnd > ins > report)
- [ ] Large content truncation working
- [ ] Error handling for all scripts

### M3: Golden dataset
- [ ] Golden dataset question and config defined
- [ ] Search result caching implemented
- [ ] First golden run completed
- [ ] Evaluation criteria and comparison tooling (including traceability checks)
- [ ] Results documented

### M4: Extensibility
- [ ] `research-preparation` workflow documented and bundled
- [ ] `create-skill.md` meta-skill
- [ ] `integrate-tool.md` meta-skill
- [ ] `literature-review.md` variant skill
- [ ] Brave and Tavily search providers
- [ ] Agent adapter docs (Claude Code, OpenCode, Cursor)
- [ ] Example workspace completed and documented
