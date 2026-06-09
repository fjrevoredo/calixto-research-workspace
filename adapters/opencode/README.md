# OpenCode Adapter

Use OpenCode at the correct boundary:

- **Toolkit root:** development and maintenance
- **Standalone workspace:** research execution

## Research Workflow

1. Create a workspace from the toolkit root:

   ```bash
   uv run python scripts/init_workspace.py my-topic
   ```

2. Enter the generated workspace and bootstrap it:

   ```bash
   cd workspaces/my-topic
   ./setup.sh
   opencode
   ```

3. In OpenCode, read the workspace-local `AGENTS.md` and the bundled research
   skill you want to follow.

Use commands from the workspace root, for example:

```bash
uv run python scripts/search_web.py "your query" --workspace .
```

## Developer Workflow

Open OpenCode at the toolkit root when working on Calixto itself and follow the
root `AGENTS.md`.

## Notes

- Skills are directories with `SKILL.md`, not flat `skills/*.md` files.
- Research workspaces are standalone snapshots. Treat them as the execution
  boundary for research tasks.
