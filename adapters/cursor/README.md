# Cursor Adapter

Cursor should be pointed at the directory that matches the job:

- **Toolkit root:** extend or maintain Calixto
- **Standalone workspace:** perform research

## Research Workflow

1. Generate a workspace from the toolkit root:

   ```bash
   calixto research "your question" --agent none
   ```

2. Open the workspace in Cursor:

   ```bash
   cursor workspaces/my-topic
   ```

3. In Cursor, load the workspace-local:

   - `AGENTS.md`
   - `skills/research-preparation/SKILL.md` for new or underspecified topics
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
- The observed `cursor` CLI remains the editor launcher surface. Calixto does
  not currently claim a verified Cursor Agent CLI launch contract, so Cursor is
  documented as an editor-opening convenience rather than a guaranteed launched
  agent target.
