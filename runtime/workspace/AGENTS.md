# AGENTS.md

This workspace is a standalone Calixto research snapshot. Treat this directory
as the active research runtime. Do not depend on a parent toolkit checkout.

## What Is In This Workspace

- `config.json`: workspace metadata, question, provider choices, and ID counters
- `skills/`: research workflows to follow
- `scripts/`: workspace-local CLI helpers
- `providers/`: bundled search and scrape backends used by the scripts
- `sources/`, `notes/`, `outputs/`: research state and deliverables

This workspace is portable. You can copy it elsewhere and keep working after
running the workspace-local setup script there.

## First Run

Run one setup command from the workspace root:

**Unix**

```bash
./setup.sh
```

**Windows**

```powershell
.\setup.ps1
```

That creates or updates the local `.venv/`, installs Python dependencies, and
installs Playwright Chromium for live web scraping.

## How To Work

1. Read `skills/deep-research/SKILL.md` for general research or
   `skills/literature-review/SKILL.md` for paper-heavy work.
2. Set or refine the question in `config.json`.
3. Run workspace-local scripts from this directory.

Recommended command style:

```bash
uv run python scripts/search_web.py "your query" --workspace . --max-results 10
uv run python scripts/search_arxiv.py "your query" --workspace . --max-results 10
uv run python scripts/workspace_info.py audit .
```

## Boundaries

- This directory is for research execution, not toolkit maintenance.
- Developer ADRs, golden tests, and maintainer meta-skills are intentionally
  not bundled here.
- Root toolkit updates do not mutate this workspace. Create a new workspace
  from a newer toolkit version if you want a newer runtime snapshot.
