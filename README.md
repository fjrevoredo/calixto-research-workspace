# Calixto Research Workspace

Calixto is an agent-first research toolkit that generates standalone research
workspaces.

The repository root is the toolkit source and factory. Each workspace created
from it is a self-contained runtime snapshot with its own scripts, providers,
skills, setup helpers, and research state.

## Architecture

- **Toolkit root:** developer docs, maintainer skills, tests, templates, setup,
  installers, and the source used to generate new workspaces.
- **Workspace snapshot:** a portable research project under `workspaces/<name>/`
  that can be copied elsewhere and still run after local dependency setup.
- **Updates:** updating the toolkit root affects future workspaces only. Existing
  workspaces are not rewritten in place.

## Install The Toolkit

Fresh install into a new empty directory:

**Unix**

```bash
curl -fsSL https://raw.githubusercontent.com/calixto/calixto/main/install.sh | bash
```

**Windows**

```powershell
irm https://raw.githubusercontent.com/calixto/calixto/main/install.ps1 | iex
```

If you cloned the repo manually, run the root setup script instead:

**Unix**

```bash
./setup.sh
```

**Windows**

```powershell
.\setup.ps1
```

## Create A Workspace

From the toolkit root:

```bash
uv run python scripts/init_workspace.py mosquito-research
```

That creates `workspaces/mosquito-research/` as a standalone snapshot.

## Work Inside The Workspace

Move into the generated workspace and prepare its local runtime:

**Unix**

```bash
cd workspaces/mosquito-research
./setup.sh
```

**Windows**

```powershell
cd workspaces\mosquito-research
.\setup.ps1
```

Then run research commands from the workspace root:

```bash
uv run python scripts/search_web.py "best methods to combat mosquitoes" --workspace . --max-results 10
uv run python scripts/search_arxiv.py "mosquito control methods" --workspace . --max-results 10
uv run python scripts/workspace_info.py audit .
```

Read the bundled workspace `AGENTS.md` and `skills/` directory for the full
research workflow.

## Portability

A generated workspace contains the runtime assets it needs:

- research-facing `AGENTS.md`
- bundled `scripts/`, `providers/`, and research `skills/`
- workspace-local `setup.sh` / `setup.ps1`
- its own `pyproject.toml`
- research state in `sources/`, `notes/`, and `outputs/`

You can copy a workspace to another folder or machine and continue after
running the workspace-local setup script there.

## Developing The Toolkit

This repository also contains the maintainer-side source:

- root `AGENTS.md`
- `PHILOSOPHY.md`
- `requirements.md`
- provider implementations in `providers/`
- templates and runtime bundle sources
- tests and golden dataset tooling

Use the toolkit root for development work. Use generated workspaces for
research execution.
