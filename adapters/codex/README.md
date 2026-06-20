# Codex Adapter

Use Codex at the directory boundary that matches the task:

- **Toolkit root:** maintain Calixto itself
- **Standalone workspace:** run research

## Research Workflow

1. From the toolkit root, run:

   ```bash
   calixto research "your question" --agent codex
   ```

2. If you create with `--agent none`, reopen later with:

   ```bash
   calixto open my-topic --agent codex
   ```

3. Codex can discover generated project skills from `.agents/skills/`, while
   `skills/` remains the canonical bundled copy in the workspace. If you
   regenerate mirrors later, divergent existing mirrors are preserved by
   default; use the toolkit's force-refresh option only when you explicitly
   want to overwrite them.

## Developer Workflow

Open Codex at the toolkit root when modifying Calixto itself:

```bash
codex --cd .
```

Then follow the root `AGENTS.md`.

## Notes

- Existing workspaces are not rewritten in place by toolkit updates.
- If you copy a workspace away from the toolkit root, run the workspace-local
  setup script there before continuing.
