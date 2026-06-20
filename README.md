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
curl -fsSL https://raw.githubusercontent.com/fjrevoredo/calixto-research-workspace/master/install.sh | bash
```

**Windows**

```powershell
irm https://raw.githubusercontent.com/fjrevoredo/calixto-research-workspace/master/install.ps1 | iex
```

These one-line examples pin `master` because GitHub raw URLs require a concrete
branch name. When you run the installer locally without `--branch`, it follows
the repository default branch.

If you cloned the repo manually, run the root setup script instead:

**Unix**

```bash
./setup.sh
```

**Windows**

```powershell
.\setup.ps1
```

## Default Flow

Run toolkit setup once:

```bash
./setup.sh
```

On Windows:

```powershell
.\setup.ps1
```

That prepares the toolkit developer environment, prepares the current managed
workspace runtime under toolkit-local state, and installs a lightweight
`calixto` launcher shim.

Then start new research with one command:

```bash
calixto research "best methods to combat mosquitoes" --agent none
```

On Windows, if the launcher shim is not on `PATH`, use the documented fallback:

```powershell
uv run --project . calixto research "best methods to combat mosquitoes" --agent none
```

For supported terminal harnesses, replace `--agent none` with `--agent opencode`,
`--agent claude`, or `--agent codex`.

The default managed path creates `workspaces/<derived-name>/` as a standalone
snapshot, stores the exact question in `config.json`, prepares harness-native
skill mirrors when requested, and reuses the pre-provisioned managed runtime
instead of creating a per-workspace `.venv`.

## Lower-Level Creation

`scripts/init_workspace.py` remains the lower-level structured workspace factory
for automation and maintainer workflows:

```bash
uv run python scripts/init_workspace.py mosquito-research
```

It still owns the pre-create toolkit freshness check. Use
`--skip-update-check`, `--check-updates`, `--require-update-check`, or
`--update-before-create` there or through `calixto research`.

## Reopen A Workspace

Managed workspaces can be reopened without a manual `cd`:

```bash
calixto open mosquito-research --agent codex
```

`calixto open` selects the exact compatible managed runtime when available. If
the workspace was copied elsewhere or is otherwise incompatible with the
managed path, use the workspace-local setup script to create its own `.venv`.

## Workspace-Local Fallback

If you copy a workspace away from the creating toolkit root, bootstrap it
locally:

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

That local setup path remains the supported portability contract. After local
setup, run research commands from the workspace root:

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
