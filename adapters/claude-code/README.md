# Claude Code Adapter

Use Claude Code in two different places depending on the task:

- **Toolkit root:** maintain Calixto itself
- **Standalone workspace:** run research

## Research Workflow

1. From the toolkit root, run:

   ```bash
   calixto research "your question" --agent claude
   ```

2. If you create with `--agent none`, reopen later with:

   ```bash
   calixto open my-topic --agent claude
   ```

3. Inside Claude Code, read the workspace-local files:

   - `AGENTS.md`
   - `skills/deep-research/SKILL.md`
   - or `skills/literature-review/SKILL.md`

Do not run the research workflow from the toolkit root.

## Developer Workflow

Open Claude Code at the toolkit root when modifying Calixto itself:

```bash
cd <calixto-toolkit-root>
claude
```

Then follow the root `AGENTS.md`.

## Notes

- Root skills live under `skills/<name>/SKILL.md`.
- Claude Code project skill mirrors are generated under `.claude/skills/` when
  you explicitly prepare the Claude harness.
- Standalone workspaces carry their own bundled copies of the research skills.
- Existing workspaces are not upgraded in place by toolkit updates.
