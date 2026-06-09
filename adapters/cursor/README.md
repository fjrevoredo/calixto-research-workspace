# Cursor Adapter

Cursor should be pointed at the directory that matches the job:

- **Toolkit root:** extend or maintain Calixto
- **Standalone workspace:** perform research

## Research Workflow

1. Generate a workspace from the toolkit root:

   ```bash
   uv run python scripts/init_workspace.py my-topic
   ```

2. Enter the workspace and bootstrap it:

   ```bash
   cd workspaces/my-topic
   ./setup.sh
   cursor .
   ```

3. In Cursor, load the workspace-local:

   - `AGENTS.md`
   - `skills/deep-research/SKILL.md`
   - or `skills/literature-review/SKILL.md`

Research commands should run from the workspace root and use `--workspace .`.

## Developer Workflow

Open Cursor at the toolkit root when changing providers, scripts, runtime
bundle sources, tests, or installer logic.

## Notes

- The research runtime is bundled into each generated workspace.
- The toolkit root is the source used to create future workspaces.
- Updating the toolkit does not rewrite existing workspaces.
