# AGENTS.md

This file is the entry point for any coding agent working with the Calixto
toolkit repository.

Read this file first. Then choose the correct mode.

## What This Repo Is

Calixto Research Workspace is an agent-first research toolkit. The repository
root is the **toolkit source and factory**. It is not the primary research
runtime.

The toolkit generates **standalone workspaces** under `workspaces/<name>/`.
Each generated workspace contains its own research-facing `AGENTS.md`,
research skills, bundled scripts, providers, setup helpers, and state files.

That boundary is the core product contract:

- **Toolkit root:** source, maintainer docs, tests, templates, installers
- **Workspace snapshot:** portable research runtime
- **Toolkit updates:** affect future workspaces only
- **Existing workspaces:** are not rewritten in place by toolkit updates

Read [PHILOSOPHY.md](./PHILOSOPHY.md) for principles and
[requirements.md](./requirements.md) for the formal specification.

## Modes

### Research Mode

Use research mode when the task is to answer a research question.

The correct place for research mode is a generated standalone workspace, not
this toolkit root.

From the toolkit root:

```bash
calixto research "your question" --agent none
```

Or on Windows:

```powershell
calixto research "your question" --agent none
```

If the `calixto` launcher is not on `PATH`, use the fallback form:

```bash
uv run --project . calixto research "your question" --agent none
```

Once inside the workspace, stop using this root `AGENTS.md` and read the
workspace-local `AGENTS.md` instead.

In a standalone workspace, load only:

- the active research skill under `skills/`
- the bundled `scripts/` help text and arguments
- the current workspace `config.json`
- the workspace `sources/index.json` and other research state files

Do not load toolkit-maintainer docs during research unless the user explicitly
switches to development work.

### Developer Mode

Use developer mode when modifying, extending, or maintaining the toolkit.

Load the full toolkit context:

- this file
- `PHILOSOPHY.md`
- `requirements.md`
- provider implementations in `providers/`
- toolkit-side skills, especially `skills/research-preparation/`,
  `skills/create-skill/`, `skills/integrate-tool/`, and
  `skills/research-retrospective/`
- ADRs in `docs/adr/`
- tests and golden dataset tooling under `tests/`
- runtime bundle sources under `runtime/`
- examples and decision logs

Developer mode happens in the toolkit root.

## Toolkit Setup

### One-Line Install

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
branch name. When the installer runs locally without `--branch`, it follows the
repository default branch.

Running the same installer command in an existing toolkit checkout updates the
toolkit root. Existing workspaces under `workspaces/` are left untouched.

### Manual Setup

If you cloned or copied the toolkit manually:

**Unix**

```bash
./setup.sh
```

**Windows**

```powershell
.\setup.ps1
```

This prepares the toolkit environment so you can generate and maintain
workspaces. It also prepares the current managed workspace runtime under
toolkit-local `.calixto/` state and installs a context-aware `calixto`
launcher that resolves the active toolkit root from the current directory.
If you invoke Calixto outside a toolkit root, use the explicit fallback form
or set `CALIXTO_TOOLKIT_ROOT`.

## Creating A Workspace

The default user-facing command is:

```bash
calixto research "my research question" --agent none
```

This creates a standalone workspace snapshot under the toolkit root's
`workspaces/` directory, stores the exact question in `config.json`, and reuses
the managed runtime when the workspace stays under that toolkit root.

The lower-level structured factory remains:

```bash
uv run python scripts/init_workspace.py my-research-topic
```

By default in an interactive terminal, `init_workspace.py` checks whether the
toolkit root is behind the repository default branch before copying the runtime
bundle. Use `--skip-update-check` to suppress that prompt, `--check-updates`
to force the check in automation, `--require-update-check` to fail when the
check cannot complete, or `--update-before-create` to print the exact installer
update command and exit before any workspace is created.

This creates `workspaces/my-research-topic/` with:

- workspace-local `AGENTS.md`
- bundled research `skills/`
- bundled `scripts/` and `providers/`
- workspace-local `setup.sh` / `setup.ps1`
- workspace state files: `config.json`, `sources/`, `notes/`, `outputs/`

If the workspace is copied elsewhere later, run the workspace-local setup
script in its new location.

## Working In A Workspace

After creating a managed workspace:

```bash
calixto open my-research-topic --agent codex
```

If the workspace is copied elsewhere later, run the workspace-local setup
script in its new location and continue there:

```bash
cd workspaces/my-research-topic
./setup.sh
uv run python scripts/search_web.py "your query" --workspace .
uv run python scripts/workspace_info.py audit .
```

The workspace root remains the execution boundary. Research commands should
resolve paths inside that workspace, not back into the toolkit repository.

## Repository Structure

```text
research-workspace/
├── README.md
├── AGENTS.md
├── PHILOSOPHY.md
├── requirements.md
├── install.sh / install.ps1
├── setup.sh / setup.ps1
├── pyproject.toml
├── runtime/                  # workspace runtime manifest + workspace-only docs
├── templates/                # seed workspace state files
├── scripts/                  # toolkit-side CLI helpers
├── providers/                # search and scrape backends
├── skills/                   # toolkit-side skills and maintainer meta-skills
├── adapters/                 # agent-specific integration docs
├── docs/                     # architecture and maintainer docs
├── examples/                 # reference workspace data
├── tests/                    # unit tests and golden dataset tooling
└── workspaces/               # generated standalone workspaces
```

## Script Reference

Toolkit-side scripts:

- `scripts/calixto.py research|open|runtime ...`
- `scripts/init_workspace.py <name> [--path DIR]`
- `scripts/search_web.py <query> --workspace PATH [--max-results N] ...`
- `scripts/search_arxiv.py <query> --workspace PATH [--max-results N] ...`
- `scripts/search_pubmed.py <query> --workspace PATH [--max-results N] ...`
- `scripts/workspace_info.py list|show|delete|audit|verify-citations|sync-counters|review-source ...`

Notes:

- `calixto research` is the default managed workflow.
- `calixto open` reopens a managed workspace through the exact compatible
  runtime or falls back to workspace-local setup when needed.
- `calixto research --agent none --json`, `calixto open --agent none --json`,
  `calixto runtime list --json`, and `calixto runtime prune --json` are the
  supported top-level machine-readable entry points.
- `init_workspace.py` is a toolkit-root command. It creates new standalone
  workspaces.
- The research scripts are also bundled into every standalone workspace.
- In research mode inside a workspace, prefer `--workspace .`.

## Workspace Metadata

New standalone workspaces record explicit metadata in `config.json`:

- `workspace_schema_version`
- `workspace_layout`
- `runtime_manifest_version`
- `runtime_bundle_version`
- `toolkit_version_created_with`
- `toolkit_commit_created_with`
- `toolkit_build_number_created_with`
- `toolkit_ref_created_with`

Use these fields to distinguish standalone workspaces from older layouts. Do
not infer the layout only from directory names.

## Legacy Workspace Policy

Older root-dependent workspaces are not automatically migrated by the toolkit
installer or updater.

- Existing legacy workspaces may still be usable under their original toolkit
  layout.
- New work should use standalone workspaces.
- A dedicated migration command is not part of the current implementation.

## Golden Dataset

The golden dataset remains a toolkit-maintainer feature under `tests/golden/`.
It uses the committed cache under `tests/golden/cache/` for reproducible
developer validation. That cache is not part of standalone workspaces.

Common commands:

```bash
python tests/golden/run.py --clear-cache
python tests/golden/run.py --use-cache
python tests/golden/compare.py tests/golden/runs/run-A tests/golden/runs/run-B
```

## Contributing

When making non-trivial toolkit changes:

1. Update the root docs that define the product boundary.
2. Update the runtime bundle manifest or runtime sources if the standalone
   workspace contract changes.
3. Add or update tests for snapshot creation and copied-workspace execution.
4. Update relevant skills, examples, and installer/setup docs.
5. Record durable implementation decisions in the decision log.
