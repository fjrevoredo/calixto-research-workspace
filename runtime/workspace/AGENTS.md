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
   Read the file directly from this workspace. Do not rely on a generic skill
   loader to discover workspace-local skills.
2. Set or refine the question in `config.json`.
3. Run workspace-local scripts from this directory.

Search discipline matters:

- Run search commands sequentially, not as parallel tool calls in one agent message.
- After each search batch, inspect `config.json` search count via `workspace_info.py show .`
  and run `workspace_info.py audit .`.
- Use only bare `src_NNN` citations in findings and reports, never file paths such as
  `papers/src_001`.
- After writing findings or insights, run `workspace_info.py audit .`.
  If the audit reports counter drift, run `workspace_info.py sync-counters .`.
- When you intentionally discard or finish reviewing a source, record that state with
  `workspace_info.py review-source . <src_NNN> <pending|discarded|used>`.
- Record open questions in `notes/gaps.md` and populate `outputs/bibliography.md`
  before handoff.

Recommended command style:

```bash
uv run python scripts/search_web.py "your query" --workspace . --max-results 10
uv run python scripts/search_arxiv.py "your query" --workspace . --max-results 10
uv run python scripts/search_pubmed.py "your biomedical query" --workspace . --max-results 10
uv run python scripts/workspace_info.py review-source . src_007 discarded --note "Low-signal landing page"
uv run python scripts/workspace_info.py sync-counters .
uv run python scripts/workspace_info.py audit . --strict-traceability
uv run python scripts/workspace_info.py verify-citations .
```

Final-report discipline:

- Before handoff, either cite each still-pending source in a finding, discard it with a reason, or record the deferral explicitly in `notes/gaps.md`.
- Run `workspace_info.py audit . --strict-traceability` before final delivery.
- Generate `outputs/citation-check.md` with `workspace_info.py verify-citations .` and complete the manual review fields.
- For biomedical or clinical questions, prefer `search_pubmed.py` over `search_arxiv.py`.

## Boundaries

- This directory is for research execution, not toolkit maintenance.
- Developer ADRs, golden tests, and maintainer meta-skills are intentionally
  not bundled here.
- Root toolkit updates do not mutate this workspace. Create a new workspace
  from a newer toolkit version if you want a newer runtime snapshot.
