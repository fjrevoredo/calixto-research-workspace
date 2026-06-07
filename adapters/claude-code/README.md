# Claude Code Adapter for Calixto Research Workspace

This document explains how to use Calixto Research Workspace skills with [Claude Code](https://docs.anthropic.com/en/docs/claude-code).

## Quick Start

1. **Clone or install Calixto** in a directory:

   ```bash
   curl -fsSL https://raw.githubusercontent.com/calixto/calixto/main/install.sh | bash
   ```

2. **Open the directory in Claude Code**:

   ```bash
   cd <calixto-workspace> && claude
   ```

3. **Tell Claude Code which skill to load**:

   Use the slash command or mention the skill by name:

   ```
   /skills deep-research
   ```

   Or just say "follow the deep-research skill" and Claude Code will read the file.

## How Claude Code Loads Skills

Claude Code looks for instruction files in two places:

- `.claude/skills/<skill-name>.md` (project-level)
- `CLAUDE.md` at the project root (global context)

Calixto skills live in `skills/` (e.g., `skills/deep-research.md`). You have two options for using them with Claude Code:

### Option A: Symlink (recommended)

```bash
mkdir -p .claude/skills
ln -s ../../skills/deep-research.md .claude/skills/deep-research.md
ln -s ../../skills/literature-review.md .claude/skills/literature-review.md
# ... repeat for each skill you want to use
```

Now Claude Code sees them in its standard location.

### Option B: Reference directly

In your project's `CLAUDE.md`, reference the skills:

```markdown
# Calixto Research Workspace

Skills are in `../skills/`. To use one, read the file first:

- Research: `../skills/deep-research.md`
- Academic: `../skills/literature-review.md`
- Meta (developer mode only): `../skills/create-skill.md`, `../skills/integrate-tool.md`
```

## Example Workflow

A typical session with Claude Code:

```
$ cd my-calixto-workspace
$ claude

> I want to research the best open-source LLMs for local deployment in 2025.

> Please follow the deep-research skill.

Claude Code: [reads skills/deep-research.md, then follows the 7-step workflow]

> Create a workspace called "best-llm-2025" and start the workflow.

Claude Code: [runs python scripts/init_workspace.py best-llm-2025, then proceeds through the steps]
```

## Mode Switching

Tell Claude Code explicitly when to switch modes:

- "Use research mode" -> only load the active skill, scripts, and workspace conventions
- "Switch to developer mode" -> load architecture docs, meta-skills, and ADRs too

You can also use the natural language:

```
> Show me the provider interface in providers/search/base.py
```

This implies developer mode (you are reading internal code). Claude Code will load relevant context.

## Known Limitations

- Claude Code's context window is finite. Loading the full skill plus all workspace files plus all source code can be heavy. Prefer to load just the skill you are using.
- Claude Code does not have a built-in "mode" concept. You simulate modes by what you ask the agent to load.
- Subagents (Task tool) are useful for parallel work (e.g., one subagent extracts findings while another does the report) but each subagent has its own context.

## See Also

- [`AGENTS.md`](../../AGENTS.md): universal entry point
- `skills/deep-research.md`: the main research workflow
- `skills/literature-review.md`: the academic variant
- [Claude Code docs](https://docs.anthropic.com/en/docs/claude-code)
