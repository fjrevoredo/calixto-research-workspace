# Cursor Adapter for Calixto Research Workspace

This document explains how to use Calixto Research Workspace skills with [Cursor](https://cursor.com).

## Quick Start

1. **Install Calixto**:

   ```bash
   curl -fsSL https://raw.githubusercontent.com/calixto/calixto/main/install.sh | bash
   ```

2. **Open the directory in Cursor**:

   ```bash
   cd <calixto-workspace> && cursor .
   ```

3. **Cursor reads `AGENTS.md`** at the repo root (and also looks for `.cursorrules`).

## How Cursor Loads Skills

Cursor has its own convention for project-level rules and skills:

- `.cursor/rules/*.md`: rule files (auto-loaded if matched)
- `.cursorrules`: legacy single-file rules (auto-loaded)
- Any markdown file in the workspace can be loaded by reference

Calixto skills live in `skills/`. To make them available to Cursor:

### Option A: Symlink into `.cursor/rules/`

```bash
mkdir -p .cursor/rules
ln -s ../../skills/deep-research.md .cursor/rules/deep-research.md
ln -s ../../skills/literature-review.md .cursor/rules/literature-review.md
```

Now Cursor's "Rules" system sees them.

### Option B: Create a thin `.cursorrules` that points to the skills

```markdown
# Calixto Research Workspace

This project uses Calixto. Skills are in `skills/`. To use one, read the file first.

## Research mode

- General research: `skills/deep-research.md`
- Academic review: `skills/literature-review.md`

## Developer mode (only when working on Calixto itself)

- Provider interfaces: `providers/search/base.py`, `providers/scrape/base.py`
- Meta-skills: `skills/create-skill.md`, `skills/integrate-tool.md`
- ADRs: `docs/adr/`
```

### Option C: Reference directly in prompts

Just say "follow skills/deep-research.md" in your Cursor prompt and the agent will read the file.

## Example Workflow

```
> Research the best open-source LLMs for local deployment in 2025.
> Follow skills/deep-research.md.

Cursor agent: [reads the skill, then follows the 7-step workflow]

> First step: create a workspace called best-llm-2025.

Cursor agent: [runs python scripts/init_workspace.py best-llm-2025 in the integrated terminal]
```

## Mode Switching

Cursor does not have explicit modes. You simulate them by context:

- **Research mode** (default): keep the agent focused on the active skill and the workspace files.
- **Developer mode**: when working on Calixto itself, ask the agent to read the architecture docs, the provider interfaces, and the relevant ADRs.

## Using Cursor's Built-in Tools

Cursor has built-in tools for terminal access, file editing, and web access. All of these work with Calixto:

- Use the integrated terminal to run the Calixto scripts
- Use the file editor to update `notes/findings.md`, `notes/summary.md`, `outputs/report.md`
- Use Composer (Cmd+I) for multi-file edits

## Known Limitations

- Cursor's context window is finite. Don't load all skills at once; reference only what you need.
- Cursor's "agent" mode (Composer) is good for complex multi-step tasks like running a research session, but the underlying LLM is the same.
- The `.cursorrules` file is global to the project, not per-skill. Use the directory structure approach (Option A) for finer control.

## See Also

- [`AGENTS.md`](../../AGENTS.md): universal entry point
- `skills/deep-research.md`: the main research workflow
- [Cursor docs](https://docs.cursor.com)
