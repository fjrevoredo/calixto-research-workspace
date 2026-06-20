# PHILOSOPHY.md

_Last updated: 2026-06-09, applies to v0.1.0+_

This document defines the guiding principles for Calixto Research Workspace. Every feature decision, architectural choice, and contribution must align with these values. When in doubt, refer back here.

The architectural boundary is explicit:

- the repository root is the toolkit source and factory
- each generated workspace is a standalone research runtime snapshot
- toolkit updates affect future workspaces only, not existing ones

---

## Part I: Philosophy

### 1. Agent-First

This project is designed to be understood, modified, extended, and maintained by coding agents. Every aspect of the codebase (architecture, conventions, workflows, and extension points) is documented so thoroughly that an agent can work on it autonomously without hallucinating or needing to ask the maintainer.

**What this means:**
- **Internal documentation is comprehensive.** Every module, script, provider, and skill has inline documentation explaining its purpose, interface, and constraints.
- **Architecture decisions are recorded.** Why we chose Crawl4AI, why we separate search from scrape, why IDs are sequential, all documented in comments, README files, or ADRs (Architecture Decision Records).
- **Extension points are explicit.** Adding a new search provider, creating a new skill, or modifying the workspace structure follows documented patterns with examples.
- **The agent is a first-class contributor.** A user can ask their agent to "add support for Semantic Scholar" or "create a competitive analysis skill" and the agent can do it correctly by reading the docs.
- **Upstream contributions are easy.** Because everything is documented for agents, users can have their agents implement features and submit PRs without needing to understand the codebase deeply themselves.

**Documentation layers:**
1. **`AGENTS.md`**: Entry point for any coding agent. Explains what this repo is, how to set it up, where to find things, and how to contribute.
2. **Inline code comments**: Every function, class, and module has docstrings explaining purpose, parameters, return values, and edge cases.
3. **`skills/`**: Workflow instructions that teach agents how to use the tools.
4. **`skills/create-skill.md`**: Meta-skill teaching agents how to create new skills.
5. **`skills/integrate-tool.md`**: Meta-skill teaching agents how to add new providers and tools.
6. **`tests/golden/README.md`**: How to run and extend the golden dataset.
7. **Architecture Decision Records (ADRs)**: In `docs/adr/` when we make significant design choices.

**When considering a new feature, ask:**
- Can an agent implement this by reading the existing documentation?
- Are the extension points and patterns clear enough that the agent won't need to guess?
- Does this change require updating documentation so future agents understand it?
- Would a user's agent be able to contribute this upstream as a PR?

**The litmus test:** If a user clones this repo, opens it in their favorite coding agent, and says "add support for PubMed search," can the agent do it correctly by reading the docs, without the user needing to explain the codebase or the agent needing to hallucinate the implementation? If not, our documentation is insufficient.

**Agent as orchestrator:**
- Scripts do one thing: fetch data, create a workspace, list results. They don't decide what to search for, when to stop, or what to write.
- Skills teach workflows but don't enforce them. The agent can skip steps, reorder them, or improvise.
- We never call LLMs from our scripts. The agent brings its own model and its own reasoning.
- If the agent wants to do something our tools don't support, it can use any other tool available to it (curl, python, browser, etc.)

**The agent is both user and contributor.** It uses the tools to perform research, and it can extend the tools to add new capabilities. This dual role is only possible with exceptional documentation.

**Two modes of operation:**

The agent operates in one of two modes at any given time. These modes control what context the agent loads, keeping it focused and preventing information overload.

- **Research mode** (default): The agent is performing research inside a standalone workspace snapshot. It loads only the skill it's following and has access to the workspace-local scripts and workspace files. It does NOT load toolkit architecture docs, provider implementation details, meta-skills, or development guides. The agent's job is to search, collect, analyze, and report, not to think about how the tools work internally.

- **Developer mode**: The agent is modifying, extending, or maintaining the toolkit itself. It loads the full documentation: architecture, provider interfaces, meta-skills, ADRs, test infrastructure, and contribution guidelines. The agent's job is to understand the codebase deeply enough to make correct changes.

**Mode switching is explicit and user-driven:**
- The user says "switch to developer mode" or asks the agent to do something that requires it (e.g., "add a new search provider", "create a new skill", "fix this bug")
- The agent loads the additional context it needs for the task
- When the development task is done, the agent returns to research mode
- The agent never loads developer context during research unless explicitly asked

**Why this matters:**
- Research agents don't need to know how Crawl4AI's provider is implemented internally
- Loading architecture docs during research wastes context window and can confuse the agent
- Development tasks require deep context that would be noise during research
- Clean separation means the agent is always focused on the task at hand
- Users can contribute upstream without leaving their research workflow, they just switch modes

**What each mode loads:**

| Context | Research Mode | Developer Mode |
|---|---|---|
| Active skill (e.g., `deep-research.md`) | Yes | No |
| Script usage (help text, arguments) | Yes | Yes |
| Workspace structure and conventions | Yes | Yes |
| `AGENTS.md` (full repo overview) | No | Yes |
| Provider interfaces and implementations | No | Yes |
| Meta-skills (`create-skill.md`, `integrate-tool.md`) | No | Yes |
| Architecture Decision Records | No | Yes |
| Test infrastructure and golden dataset | No | Yes |
| Contribution guidelines | No | Yes |
| Code-level documentation | No | Yes |

---

### 2. Files Are the Database

All state lives in files inside a workspace folder. No databases, no servers, no hidden state, no magic.

**What this means:**
- A workspace is a self-contained folder with markdown files, JSON files, bundled runtime assets, and a clear structure
- Any tool that can read files can inspect a workspace
- Git works as version control, diff tool, and collaboration layer
- If our repo disappears tomorrow, every workspace remains usable after local dependency setup, because the runtime assets are copied into the workspace itself
- Configuration, search history, sources, notes, and reports are all plain text

**File format choices:**
- **Markdown** for human-readable content (sources, notes, reports)
- **JSON** for structured data (config, findings, indexes)
- **YAML frontmatter** in markdown files for metadata (URL, date, provider)
- No binary formats except optionally cached PDFs

**When considering a new data type, ask:**
- Can it be represented as markdown or JSON?
- Can a human read and edit it in a text editor?
- Does `git diff` produce meaningful output for it?

---

### 3. Modular and Configurable

Each tool does exactly one thing and every choice can be overridden. We provide opinionated defaults so users don't have to configure anything, but every default is replaceable without forking.

**Separation of concerns:**
- Search providers find URLs. They don't scrape.
- The scraper fetches URLs and returns markdown. It doesn't search.
- `search_web.py` composes search + scrape into one command for convenience, but each layer is independently usable.
- `init_workspace.py` creates folders. It doesn't search, extract, or analyze.
- Scripts accept `--workspace <path>` to know where to read/write. They don't assume a global workspace location.

**The Unix philosophy, applied to research:**
- Each script reads from files or stdin
- Each script writes to files or stdout
- Scripts communicate through the filesystem, not through each other
- The agent is the pipeline that connects them

**Opinionated defaults:**
- Default search provider: DuckDuckGo (free, no API key)
- Default scraper: Crawl4AI (self-hosted, no API key)
- Default workspace location: `./workspaces/`
- Default file formats: Markdown + JSON + YAML frontmatter
- Default skill: `deep-research.md`

**But everything is replaceable:**
- Want Brave Search instead? Change one config value.
- Want to use Tavily? Add the API key, swap the provider.
- Want a different workspace structure? Fork the template.
- Want a different skill? Write your own following our meta-skill guide.
- Want to add a new data source? Implement the provider interface.

**When considering a new script, ask:**
- Can this be described in one sentence?
- Does it depend on the output of another script, or does it work standalone?
- If we removed every other script, would this one still be useful?

**The 80/20 rule:**
- 80% of users should never need to change a default
- 20% of users should be able to change anything in under 30 minutes
- 0% of users should need to fork the repo to customize their workflow

---

### 4. Honest Complexity

We don't pretend this is lightweight. We document the real cost of every dependency and make setup as painless as possible without hiding the truth.

**What this means:**
- Crawl4AI + Playwright + Chromium is ~500MB. We say so upfront.
- Setup scripts explain what they install and why.
- We don't add dependencies to make the README look impressive.
- Every dependency must justify its size: what capability does it unlock that we can't get more cheaply?
- Optional dependencies are truly optional. The core workflow works without them.

**Dependency budget:**

| What | Why it's worth the cost |
|---|---|
| Crawl4AI (~50MB) | Best FOSS web-to-markdown pipeline available |
| Playwright + Chromium (~450MB) | Required by Crawl4AI for JS-rendered pages |
| ddgs (~1MB) | Free search with no API key |
| arxiv (~1MB) | Only sane way to query arXiv programmatically |

**When considering a new dependency, ask:**
- What does it add in MB?
- Can we get 80% of the value with something smaller?
- Is it truly required, or can it be optional?
- Does it introduce a server, daemon, or background process? (If yes, it doesn't belong here.)

---

### 5. Easy In, Easy Out

Users should be able to adopt this toolkit in minutes and abandon it at any time without losing their work.

**Easy in:**
- Clone the toolkit, run `setup.sh`, then start research with `calixto research "your question" --agent none`
- No accounts, no API keys required for basic use
- Skills tell the agent what to do. No configuration needed
- Works with whatever coding agent the user already has

**Easy out:**
- Workspaces are plain folders. Copy them anywhere.
- No proprietary formats. Every file is readable by any text editor.
- No lock-in to our scripts. An agent can read the workspace files directly.
- If this repo becomes unmaintained, every workspace remains fully functional.

**No lock-in:**
- Source files have metadata in YAML frontmatter, parseable by any tool
- Config is standard JSON
- Reports are standard Markdown
- The workspace structure is a convention, not a requirement. An agent can create the folders manually.

**The test:** Could someone who has never heard of this project open a workspace folder and understand what it contains? If not, we've failed.

---

### 6. Reproducible Within Reason

We accept that web research is inherently non-deterministic. We optimize for "similar enough" rather than "byte-identical.". We want to make the process reproducible, not necesarely the results, we are embracing the power of LLM Agents not creating a dev tool we are just providing enough guardrails so the process is smooth without locking the LLM out of its "magic".

**What this means:**
- Search results change daily. We cache aggressively but don't promise identical results.
- Same query + same config + same cache = same results. That's our reproducibility guarantee.
- Golden dataset runs are compared structurally (sections present, source count range, citation quality), not by exact content match.
- Every search is logged in `config.json` with timestamp, query, provider, and result count.
- Workspaces are git-friendly, so every run can be committed and compared.

**What we don't promise:**
- That live web search will return the same URLs tomorrow
- That scraped content will be identical (pages change)
- That different search providers will return the same results

**When considering reproducibility features, ask:**
- Does this help the user understand what changed between runs?
- Does it add complexity that outweighs the reproducibility gain?
- Are we fighting the inherent non-determinism of web research, or managing it?

---

### 7. Traceability

Every piece of information in a workspace must be traceable back to its origin. We assign unique IDs to sources, findings, and insights so the full provenance chain is always visible.

**What this means:**
- Every source gets a unique ID (e.g., `src_001`, `src_002`) assigned when collected
- Every finding extracted by the agent references the source ID(s) it came from
- Every insight or claim in the summary references the finding IDs that support it
- The final report cites source IDs in a bibliography
- The full chain is: `search → source → finding → insight → report`

**Why this matters:**
- Users can verify any claim by following the ID chain back to the original source
- When results are wrong, you can identify which source or extraction step failed
- Different runs can be compared by tracing which sources led to which conclusions
- Agents can be evaluated on whether they properly cite their sources
- The research process becomes auditable and debuggable

**ID format:**
- Sources: `src_NNN` (sequential per workspace, e.g., `src_001`)
- Findings: `fnd_NNN` (sequential per workspace, e.g., `fnd_001`)
- Insights: `ins_NNN` (sequential per workspace, e.g., `ins_001`)

**When considering a new data type, ask:**
- Does it need a unique ID for traceability?
- Can it reference other IDs to show provenance?
- Will the ID persist across workspace operations (copy, fork, merge)?

**The test:** Given any sentence in the final report, can you trace it back through findings to the original source URL in 3 steps or fewer? If not, traceability is broken.

---

## Decision Framework

When proposing or reviewing changes, validate against all seven principles:

1. **Agent-first?** Is this documented well enough that an agent can understand, use, and extend it without hallucinating?
2. **File-based?** Is all state in readable, diffable files?
3. **Modular and configurable?** Does this tool do one thing, and can defaults be overridden?
4. **Honest cost?** Are we transparent about what this adds in complexity and size?
5. **Portable?** Can a user walk away with their data in standard formats?
6. **Reproducibility impact?** Does this help or hurt run-to-run consistency?
7. **Traceable?** Can every piece of information be traced back to its origin via IDs?

If any principle is violated without strong justification, the proposal should be reconsidered.

---

## Non-Negotiables

Some principles are absolute:

- **LLM and harness agnostic, pragmatically.** When designing any feature, we always try the fully agnostic solution first: plain CLI scripts, plain markdown, plain files. But if a harness-specific feature (e.g., subagents, MCP servers, tool-use protocols) delivers significantly better results, we can use it as an optional enhancement behind a provider interface. The agnostic path must always work; the specialized path is an upgrade, not a requirement. We don't guarantee identical behavior across every model and every harness. Different agents have different capabilities, context windows, and quirks. The toolkit is open and modular so users can adapt it to their preferred stack. If something doesn't work with your agent, the documentation is good enough that your agent can fix it.
- **No LLM calls in our scripts.** Our tools are model-agnostic. The agent brings its own model. We never call OpenAI, Anthropic, or any LLM API from our code. This keeps us provider-neutral and avoids hidden costs.
- **No servers or daemons.** Everything runs as CLI commands. No background processes, no API servers, no Docker daemons required. If you need a server, you're building an app, not infrastructure.
- **No proprietary formats.** Every file in a workspace must be readable by `cat`. No binary databases, no custom serialization, no encrypted blobs.
- **No silent failures.** Every script reports success or failure in structured JSON. Partial results are saved, not discarded. If something breaks, the agent knows exactly what happened and what was preserved.

---

## Closing Thoughts

Calixto Research Workspace is intentionally narrow. It does one thing: give coding agents the tools and instructions to perform structured, reproducible research. It doesn't think for the agent, it doesn't host anything, and it doesn't lock you in.

If a feature doesn't serve that goal, it doesn't belong here. If an existing tool already does it well, we integrate rather than reinvent. If a user wants something different, we make it easy to customize without forking.

The best research tool is the one that gets out of the way.

---
---

## Part II: Implementation Guide

This section explains how each principle from Part I translates into concrete decisions in the codebase. It is the "how" to Part I's "what and why". Keep this section updated as the architecture evolves.

---

### Principle 1: Agent-First in Practice

This project is designed so that any coding agent can understand, use, extend, and maintain it by reading the documentation. No tribal knowledge, no guessing, no hallucination required.

**Documentation hierarchy:**

1. **`AGENTS.md`** (repo root): The entry point. Tells any agent:
   - What this repo is and what it does
   - How to set up the environment
   - Where to find skills, scripts, and providers
   - How to run tests and the golden dataset
   - How to contribute changes upstream
   - Links to deeper documentation

2. **Inline code documentation**: Every Python module, class, and function has:
   - Module-level docstring explaining purpose and role in the architecture
   - Class docstrings explaining the interface and when to use it
   - Function docstrings with parameters, return values, exceptions, and examples
   - Inline comments for non-obvious logic or edge cases

3. **Skills** (`skills/*.md`): Workflow instructions that teach agents how to use the tools:
   - `deep-research.md`: General research workflow
   - `literature-review.md`: Academic variant
   - `create-skill.md`: Meta-skill: how to create new skills
   - `integrate-tool.md`: Meta-skill: how to add new providers

4. **Architecture Decision Records** (`docs/adr/`): When we make significant design choices:
   - Why we chose Crawl4AI over other scrapers
   - Why we separate search from scrape
   - Why IDs are sequential and workspace-scoped
   - Why we don't call LLMs from scripts

5. **Provider documentation** (`providers/README.md`): How the provider system works:
   - Interface contracts
   - How to implement a new search provider
   - How to implement a new scrape provider
   - How to register and test new providers

**Script documentation standard:**

```python
"""
search_web.py: Search the web and scrape results into a workspace.

This script composes a search provider (finds URLs) with a scrape provider
(fetches content) to collect web sources for research.

Usage:
    python scripts/search_web.py "query" --workspace ./workspaces/my-research

Architecture:
    - Calls SearchProvider.search() to get URLs
    - Calls ScrapeProvider.scrape() for each URL
    - Saves results as markdown with YAML frontmatter
    - Updates workspace config.json with search history
    - Deduplicates via sources/index.json

Providers:
    - Search: duckduckgo (default), brave, tavily
    - Scrape: crawl4ai (only option currently)

See also:
    - providers/search/base.py: SearchProvider interface
    - providers/scrape/crawl4ai_provider.py: ScrapeProvider implementation
    - skills/integrate-tool.md: How to add new providers
"""
```

**Extension patterns are documented with examples:**

When an agent needs to "add PubMed search," it reads `skills/integrate-tool.md` which says:

1. Create `providers/search/pubmed.py`
2. Implement the `SearchProvider` interface (see `providers/search/base.py`)
3. Here's a minimal example implementation
4. Register it in the provider registry (see `providers/__init__.py`)
5. Test it with this command
6. Update `config.json` schema to include "pubmed" as a valid provider

**The agent can then implement it correctly without:**
- Asking the user to explain the codebase
- Guessing at the interface
- Hallucinating the registration mechanism
- Needing to read every file to understand the architecture

**Upstream contribution workflow:**

1. User asks agent: "Add support for Semantic Scholar search"
2. Agent reads `AGENTS.md` → learns about provider system
3. Agent reads `skills/integrate-tool.md` → learns the pattern
4. Agent reads `providers/search/base.py` → sees the interface
5. Agent reads `providers/search/duckduckgo.py` → sees a reference implementation
6. Agent implements `providers/search/semantic_scholar.py`
7. Agent writes tests
8. Agent updates documentation
9. User submits PR

**Documentation as code:**

Documentation is treated as a first-class artifact:
- Docs are versioned with the code
- Docs are reviewed in PRs
- Outdated docs are bugs (tracked in issues)
- Meta-skills teach agents how to write good docs

**The test:** Clone this repo fresh. Open it in a coding agent. Ask: "Add a new search provider for Google Scholar." Can the agent do it correctly by reading the docs? If not, the docs need improvement.

---

### Principle 2: File-Based State in Practice

**Workspace layout** (created by `init_workspace.py` from `templates/workspace/`):

```
<workspace>/
├── config.json              # Research params + search history
├── sources/
│   ├── index.json           # Deduplication registry
│   ├── web/                 # source_NNN.md files
│   ├── papers/              # arxiv_ID.md files
│   └── code/                # repo/doc files
├── notes/
│   ├── summary.md           # Agent's running synthesis
│   └── gaps.md              # Follow-up questions
└── outputs/
    ├── report.md            # Final deliverable
    └── bibliography.md      # Source list with ratings
```

**File conventions:**
- Source files: YAML frontmatter (metadata) + markdown body (content)
- Config: JSON with `searches` array appended to (not rewritten) on each search
- Index: JSON with `sources` array, one entry per collected source
- Notes and reports: pure markdown, agent writes freely

**No hidden state:**
- No `.cache` directories inside workspaces (cache lives in provider layer, outside workspace)
- No temp files left behind after script completion
- No symlinks or special file types

---

### Principle 3: Modular and Configurable in Practice

**Provider layer** (`providers/`):

```
providers/
├── search/
│   ├── base.py              # Abstract SearchProvider interface
│   ├── duckduckgo.py        # DuckDuckGo implementation
│   ├── brave.py             # Brave implementation
│   └── tavily.py            # Tavily implementation
└── scrape/
    └── crawl4ai_provider.py # Crawl4AI implementation
```

**Interface contracts:**

```python
# Search: query → URLs
class SearchProvider:
    def search(self, query: str, max_results: int) -> list[SearchResult]: ...

# Scrape: URL → markdown
class ScrapeProvider:
    def scrape(self, url: str) -> ScrapeResult: ...
```

**Composition in `search_web.py`:**
```
query → SearchProvider.search() → URLs → ScrapeProvider.scrape() → markdown → save to workspace
```

Each layer is independently testable and replaceable. Adding a new search provider means implementing `SearchProvider` and registering it. No other code changes.

**Config resolution order:**
1. Script defaults (hardcoded in each script)
2. Workspace `config.json` (per-workspace overrides)
3. CLI arguments (per-command overrides)

**Example: search provider:**
```
# Default: DuckDuckGo
python scripts/search_web.py "query" --workspace ./ws

# Workspace override: config.json has "providers": {"search": "brave"}
python scripts/search_web.py "query" --workspace ./ws  # uses Brave

# CLI override: explicit flag wins
python scripts/search_web.py "query" --workspace ./ws --search-provider tavily  # uses Tavily
```

**Adding a new provider** (documented in `skills/integrate-tool.md`):
1. Implement the `SearchProvider` interface in `providers/search/new_provider.py`
2. Register it in the provider registry
3. Reference it by name in config or CLI

No existing code needs to change. The new provider slots into the existing interface.

---

### Principle 4: Honest Complexity in Practice

**Setup script** (`setup.sh` / `setup.ps1`) prints what it's doing:

```
[1/4] Installing uv...
[2/4] Installing Python dependencies...
      - crawl4ai (50MB)
      - ddgs (1MB)
      - arxiv (1MB)
[3/4] Installing Playwright browsers...
      - Chromium (~450MB), this may take a few minutes
[4/4] Verifying installation...
      ✓ crawl4ai ready
      ✓ ddgs ready
      ✓ Chromium ready

Total installed: ~500MB
```

**Dependency justification** (in `pyproject.toml`):
```toml
[project]
dependencies = [
    "crawl4ai",           # Web scraping: no comparable FOSS alternative at this quality
    "ddgs",               # Free web search: 1MB, no API key
    "arxiv",              # arXiv API: 1MB, official client
]

[project.optional-dependencies]
brave = ["brave-search"]   # Better search quality, requires API key
tavily = ["tavily-python"] # AI-optimized search, requires API key
```

**No dependency is added without answering:** What does this unlock, and what does it cost?

---

### Principle 5: Portability in Practice

**A workspace without our repo:**

If someone copies a workspace folder and deletes this repo, they have:
- Markdown files they can read in any editor
- JSON files they can parse with any tool
- A report they can share, print, or publish
- Source files with URLs they can re-visit

They lose:
- The ability to run new searches (they'd need to install our tools or use alternatives)
- The skill instructions (they'd need to improvise their own workflow)

They do NOT lose:
- Any data
- Any structure
- Any metadata
- Any ability to understand what the workspace contains

**Workspace as git repo:**

Every workspace can be `git init`'d independently. Commits track research progress:
```
git log --oneline
a3f2c1d Added 5 more sources on pricing comparison
b1e4a2c Initial report draft
c5d3b1a Collected 12 web sources
d7f2e0b Workspace created: "best gpu under 500"
```

---

### Principle 6: Reproducibility in Practice

**Search caching** (`tests/golden/cache/`):
- First run: search provider is called, results cached as JSON
- Subsequent runs with `--use-cache`: cached results used, no network call
- Cache key: hash of (provider + query + max_results)
- Cache invalidation: manual (delete cache file) or time-based (configurable TTL)

**Config as audit trail:**
```json
{
  "searches": [
    {
      "query": "best GPU under $500 2025",
      "provider": "duckduckgo",
      "timestamp": "2025-01-15T10:30:00Z",
      "results_count": 10,
      "urls_found": ["https://...", "https://..."]
    }
  ]
}
```

Every search is logged. Anyone can see exactly what was searched, when, and how many results were found.

**Golden dataset comparison** (`tests/golden/compare.py`):
- Compares structural properties, not content
- Checks: source count range, section presence, citation coverage, frontmatter validity
- Reports drift: "Run A had 12 sources, Run B had 14 (within tolerance)"

---

### Principle 7: Traceability in Practice

**ID assignment** happens at collection time and persists for the lifetime of the workspace.

**Source IDs**: assigned by `search_web.py` and `search_arxiv.py` when saving to `sources/`:

```yaml
# sources/web/src_001.md
---
id: src_001
url: https://example.com/article
title: "Article Title"
date_crawled: 2025-01-15T10:30:00Z
provider: crawl4ai
search_provider: duckduckgo
query: "best GPU under $500 2025"
---
```

The `sources/index.json` registry tracks all IDs:

```json
{
  "sources": [
    {
      "id": "src_001",
      "url": "https://example.com/article",
      "file": "web/src_001.md",
      "added_at": "2025-01-15T10:30:00Z",
      "query": "best GPU under $500 2025"
    }
  ]
}
```

**Finding IDs**: assigned by the agent when extracting facts from sources. The skill instructs the agent to write findings with IDs and source references:

```markdown
<!-- notes/findings.md -->
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

**Insight IDs**: assigned by the agent when synthesizing findings into higher-level conclusions:

```markdown
<!-- notes/summary.md -->
## ins_001
**Based on:** fnd_001, fnd_002
**Insight:** For users focused on local AI workloads, VRAM should be the primary purchasing criterion, making the RTX 4060 Ti (16GB) the best value despite its higher price.

## ins_002
**Based on:** fnd_003, fnd_004, fnd_007
**Insight:** The GPU market in 2025 is segmented into three clear tiers under $500...
```

**Report citations**: the final report references source IDs inline:

```markdown
<!-- outputs/report.md -->
The RTX 4060 offers the best price-to-performance ratio in the sub-$500 segment [src_003].
However, for AI workloads, VRAM becomes the primary bottleneck [src_001, src_005],
making the RTX 4060 Ti 16GB a better choice despite its higher price.
```

**The full traceability chain:**

```
search query "best GPU under $500"
  → src_003 (tomshardware.com review)
    → fnd_001 (price-performance claim)
      → ins_001 (VRAM-first purchasing advice)
        → report.md paragraph 2
```

**Traceability rules:**
- Every finding MUST reference at least one source ID
- Every insight MUST reference at least one finding ID
- Every report claim MUST reference at least one source ID
- IDs are never reused. If a source is deleted, its ID is retired
- IDs are workspace-scoped. Forking a workspace preserves all IDs

**Scripts enforce traceability at collection:**
- `search_web.py` assigns `src_NNN` IDs sequentially
- `search_arxiv.py` assigns `src_NNN` IDs sequentially (shared counter via `index.json`)
- The agent assigns `fnd_NNN` and `ins_NNN` IDs during extraction and synthesis (guided by skill)

**Traceability audit** (can be checked by the agent or a future script):
- Are all source IDs in findings present in `index.json`?
- Are all finding IDs in insights present in `findings.md`?
- Are all source IDs cited in the report present in `index.json`?
- Are there orphaned sources (collected but never cited)?
