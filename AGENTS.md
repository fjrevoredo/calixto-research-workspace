# AGENTS.md

This file is the entry point for any coding agent (Claude Code, OpenCode, Cursor, Codex, etc.) working with the Calixto Research Workspace repository. Read this first, then follow the mode-specific instructions below.

## What This Repo Is

Calixto Research Workspace is an agent-first research toolkit. It gives coding agents the skills, scripts, and conventions to perform structured, reproducible deep research, from web search to final report, with full traceability from source to claim.

Every research session is a folder on disk containing markdown and JSON files. No databases, no servers, no daemons. Workspaces are git-friendly and survive without this repo.

Read [`PHILOSOPHY.md`](./PHILOSOPHY.md) for the guiding principles. Read [`requirements.md`](./requirements.md) for the full specification.

## One-Line Installation

Fresh install in a new empty directory:

**Unix (Linux, macOS, WSL):**

```bash
curl -fsSL https://raw.githubusercontent.com/calixto/calixto/main/install.sh | bash
```

**Windows (PowerShell):**

```powershell
irm https://raw.githubusercontent.com/calixto/calixto/main/install.ps1 | iex
```

Update an existing Calixto workspace in the same way. The installer detects whether the directory is already a Calixto workspace and switches to update mode automatically. It preserves user-owned data, keeps a timestamped backup copy, and uses a rollback transaction for toolkit files during updates.

Installer details are documented in [`docs/installer.md`](./docs/installer.md), including:

- branch vs. tag/version selection
- supported custom GitHub repository URLs
- git-to-archive fallback behavior
- managed-entry ownership metadata
- transactional update rollback and interrupted-transaction recovery
- TLS verification and test-only archive overrides

## Two Modes of Operation

Calixto operates in two distinct modes. Load context for the mode you are in. Do not cross-contaminate.

### Research Mode (default)

You are inside a workspace performing research for the user. Load only:

- The active skill (e.g., `skills/deep-research.md`)
- Script usage (CLI help text, argument signatures)
- Workspace structure and conventions (this file, the workspace template)
- The current workspace's `config.json` and `sources/index.json`

Do NOT load in research mode:

- Internal architecture docs
- Provider implementation details
- Meta-skills (`create-skill.md`, `integrate-tool.md`)
- ADRs
- Test infrastructure and golden dataset
- Contribution guidelines

The agent's job in research mode is to search, collect, analyze, and report, not to think about how the tools work internally.

### Developer Mode

You are modifying, extending, or maintaining the toolkit itself. Load the full context:

- `AGENTS.md` (this file)
- `PHILOSOPHY.md`
- `requirements.md`
- Provider interfaces and implementations in `providers/`
- Meta-skills: `skills/create-skill.md`, `skills/integrate-tool.md`
- ADRs in `docs/adr/`
- Test infrastructure in `tests/golden/`
- Sample workspace in `examples/`
- Decision log: `docs/initial-implementation-plan-decision-log.md`
- Inline code documentation

The agent's job in developer mode is to understand the codebase deeply enough to make correct changes.

### Mode Switching

Mode switching is explicit and user-driven. The user says "switch to developer mode" or asks for a development task ("add a new search provider", "create a new skill", "fix this bug"). When the development task is done, return to research mode. Never load developer context during research unless explicitly asked.

## How to Set Up

### Prerequisites

- Python 3.11 or newer
- Git (for the installer and for workspace archival)
- Internet connection (to download dependencies)
- ~500 MB free disk space (Crawl4AI + Playwright + Chromium)

### One-Liner Install (recommended)

See the One-Line Installation section above. The installer creates the workspace, copies all files, and runs `setup.sh` / `setup.ps1` automatically.

### Manual Setup

If you cloned or copied the repo manually:

**Unix:**

```bash
./setup.sh
```

**Windows:**

```powershell
.\setup.ps1
```

The setup script installs `uv`, syncs Python dependencies, installs Playwright browsers, and verifies the installation.

### Verify

```bash
python -c "import crawl4ai, ddgs, arxiv; print('ready')"
```

## How to Use (Research Mode)

### 1. Create a workspace

```bash
python scripts/init_workspace.py my-research-topic
```

This creates `workspaces/my-research-topic/` with the full template structure. The script prints a JSON status object to stdout.

### 2. Load the active skill

Read `skills/deep-research.md` (or `skills/literature-review.md` for academic work). The skill contains the full 7-step workflow: Initialize, Search, Evaluate, Extract, Synthesize, Report, Iterate.

### 3. Search and collect

```bash
# Web search + scrape
python scripts/search_web.py "python asyncio best practices" \
    --workspace workspaces/my-research-topic \
    --max-results 10

# arXiv search
python scripts/search_arxiv.py "transformer architecture" \
    --workspace workspaces/my-research-topic \
    --max-results 10
```

Each command assigns sequential `src_NNN` IDs and saves results as markdown with YAML frontmatter.

### 4. Extract findings

Read the saved sources. For each relevant fact, append to `notes/findings.md` using the format from the skill:

```markdown
## fnd_001
**Source:** src_003
**Fact:** ...
**Quote:** "..."
**Confidence:** high
```

### 5. Synthesize insights

Append to `notes/summary.md`:

```markdown
## ins_001
**Based on:** fnd_001, fnd_002
**Insight:** ...
```

### 6. Generate the report

Write `outputs/report.md` citing sources inline as `[src_NNN]`. The full provenance chain is: `search -> source -> finding -> insight -> report`.

### 7. Inspect and audit

```bash
python scripts/workspace_info.py list
python scripts/workspace_info.py show my-research-topic
python scripts/workspace_info.py audit my-research-topic
```

## How to Develop (Developer Mode)

### Repository Structure

```
research-workspace/
|-- README.md
|-- PHILOSOPHY.md
|-- AGENTS.md                      # This file
|-- requirements.md
|-- setup.sh                       # Unix setup
|-- setup.ps1                      # Windows setup
|-- install.sh                     # Unix one-liner installer
|-- install.ps1                    # Windows one-liner installer
|-- pyproject.toml
|
|-- skills/                        # Workflow instructions for agents
|   |-- deep-research.md
|   |-- literature-review.md
|   |-- create-skill.md            # Meta-skill
|   `-- integrate-tool.md          # Meta-skill
|
|-- adapters/                      # Agent-specific setup docs
|   |-- claude-code/README.md
|   |-- opencode/README.md
|   `-- cursor/README.md
|
|-- templates/workspace/           # Starter workspace structure
|   |-- config.json
|   |-- sources/
|   |   |-- index.json
|   |   |-- web/
|   |   |-- papers/
|   |   `-- code/
|   |-- notes/
|   |   |-- findings.md
|   |   |-- summary.md
|   |   `-- gaps.md
|   `-- outputs/
|       |-- report.md
|       `-- bibliography.md
|
|-- docs/adr/                      # Architecture Decision Records
|-- docs/initial-implementation-plan.md
|-- docs/initial-implementation-plan-decision-log.md
|
|-- scripts/                       # CLI helpers
|   |-- init_workspace.py
|   |-- search_web.py
|   |-- search_arxiv.py
|   `-- workspace_info.py
|
|-- providers/                     # Pluggable backends
|   |-- search/
|   |   |-- base.py                # SearchProvider interface
|   |   |-- duckduckgo.py
|   |   `-- brave.py
|   `-- scrape/
|       |-- base.py                # ScrapeProvider interface
|       `-- crawl4ai_provider.py
|
|-- tests/golden/                  # Reproducible benchmark
|   |-- README.md
|   |-- config.json
|   |-- cache/
|   |-- expected/
|   |-- run.py
|   `-- compare.py
|
`-- examples/                      # Reference implementations
    `-- sample-workspace/
```

### Common Development Tasks

| Task | Where to start |
|---|---|
| Add a new search provider | `skills/integrate-tool.md`, then `providers/search/base.py` |
| Add a new scrape backend | `skills/integrate-tool.md`, then `providers/scrape/base.py` |
| Create a new skill | `skills/create-skill.md` |
| Modify workspace structure | `templates/workspace/` (keep `init_workspace.py` in sync) |
| Add a new script | Existing scripts in `scripts/` as reference |
| Change error output format | All scripts in `scripts/` (consistency required) |
| Add a new ADR | `docs/adr/NNN-short-title.md` |

## Scripts Reference

| Script | Purpose |
|---|---|
| `scripts/init_workspace.py <name> [--path DIR]` | Create a new workspace from the template |
| `scripts/search_web.py <query> --workspace PATH [--max-results N] [--search-provider NAME] [--no-scrape] [--truncate N]` | Search the web and scrape results into a workspace |
| `scripts/search_arxiv.py <query> --workspace PATH [--max-results N] [--category CAT]` | Search arXiv and save paper metadata |
| `scripts/workspace_info.py list|show|delete|audit <name>` | Manage existing workspaces |
| `tests/golden/run.py [--use-cache] [--clear-cache]` | Execute the full golden dataset workflow |
| `tests/golden/compare.py <run1> <run2>` | Compare two golden runs structurally |

All scripts print structured JSON to stdout on success and to stderr on failure. Exit code 0 on success, 1 on error.

## Skills Reference

| Skill | Mode | Purpose |
|---|---|---|
| `skills/deep-research/SKILL.md` | Research | 7-step general research workflow |
| `skills/literature-review/SKILL.md` | Research | Academic literature review variant |
| `skills/create-skill/SKILL.md` | Developer | Meta-skill for writing new skills |
| `skills/integrate-tool/SKILL.md` | Developer | Meta-skill for adding new providers and tools |

Skills follow the [Agent Skills specification](https://agentskills.io/specification): each is a directory under `skills/` with a `SKILL.md` file that has YAML frontmatter (name, description, license, compatibility, metadata) plus the workflow body. The frontmatter `name` must match the directory name. See `skills/create-skill/SKILL.md` for how to add a new skill.

## Workspace Conventions

### File Format

- **Markdown** for human-readable content (sources, notes, reports)
- **JSON** for structured data (config, source index)
- **YAML frontmatter** in source files for metadata (URL, date, provider)

### ID System

- Sources: `src_NNN` (assigned by `search_web.py`, `search_arxiv.py`)
- Findings: `fnd_NNN` (assigned by agent in `notes/findings.md`)
- Insights: `ins_NNN` (assigned by agent in `notes/summary.md`)

IDs are sequential, never reused, and workspace-scoped.

### Traceability Rules

- Every finding MUST reference at least one source ID
- Every insight MUST reference at least one finding ID
- Every report claim MUST reference at least one source ID
- The full chain: `search -> source -> finding -> insight -> report`

### Dedup

`search_web.py` normalizes URLs (strips protocol, `www.`, trailing slashes, tracking params) and skips URLs already in `sources/index.json`. `search_arxiv.py` deduplicates by arXiv ID.

## Running the Golden Dataset

```bash
# Fresh run (calls live search providers)
python tests/golden/run.py --clear-cache

# Reproducible run (uses cached search results)
python tests/golden/run.py --use-cache

# Compare two runs
python tests/golden/compare.py tests/golden/runs/run-A tests/golden/runs/run-B
```

The golden dataset validates the full pipeline and benchmarks changes to providers, models, or prompts.

## Adapter Docs

Each adapter explains how to wire Calixto skills into a specific coding agent:

- `adapters/claude-code/README.md`
- `adapters/opencode/README.md`
- `adapters/cursor/README.md`

`AGENTS.md` (this file) is the universal entry point. Adapters add agent-specific setup steps on top of it.

## Contributing

1. Read `PHILOSOPHY.md` and `requirements.md`.
2. Follow the Agent-First principle: write code that an agent can understand by reading the docs.
3. Add tests where the plan requires them.
4. Update relevant skills, ADRs, and the decision log.
5. Run `./setup.sh` and the golden dataset locally to validate changes.

For non-trivial implementation decisions, add an entry to `docs/initial-implementation-plan-decision-log.md` describing what was decided and why.
