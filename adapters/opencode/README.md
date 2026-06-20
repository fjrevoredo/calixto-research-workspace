# OpenCode Adapter

Use OpenCode at the correct boundary:

- **Toolkit root:** development and maintenance
- **Standalone workspace:** research execution

## Research Workflow

1. Run the streamlined flow from the toolkit root:

   ```bash
   calixto research "your question" --agent opencode
   ```

2. If you create with `--agent none`, reopen later with:

   ```bash
   calixto open my-topic --agent opencode
   ```

3. OpenCode can discover generated project skills from `.agents/skills/` and
   `.opencode/skills/`, while `skills/` remains the canonical copy bundled into
   the standalone workspace. Regenerating mirrors later preserves divergent
   existing mirror content by default; use the toolkit's force-refresh option
   only when you explicitly want to overwrite a mirror.

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
- If you copy a workspace away from the toolkit root, run the workspace-local
  `setup.sh` or `setup.ps1` there before continuing.
