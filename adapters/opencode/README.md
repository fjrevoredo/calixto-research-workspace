# OpenCode Adapter for Calixto Research Workspace

This document explains how to use Calixto Research Workspace skills with [OpenCode](https://opencode.ai).

## Quick Start

1. **Install Calixto**:

   ```bash
   curl -fsSL https://raw.githubusercontent.com/calixto/calixto/main/install.sh | bash
   ```

2. **Open the directory in OpenCode**:

   ```bash
   cd <calixto-workspace> && opencode
   ```

3. **OpenCode automatically reads `AGENTS.md`** at the repo root, which is the universal entry point for any coding agent.

## How OpenCode Loads Skills

OpenCode reads `AGENTS.md` for the project overview and convention. Skills in `skills/*.md` are loaded explicitly when you reference them.

### Loading a skill

Reference the skill by name in your prompt:

```
Follow skills/deep-research.md to research the best open-source LLMs for local deployment.
```

OpenCode reads the file and follows its instructions.

## Example Workflow

```
$ cd my-calixto-workspace
$ opencode

> Research the best open-source LLMs for local deployment in 2025 using the deep-research skill.

OpenCode: [reads AGENTS.md, then skills/deep-research.md, then follows the 7-step workflow]

> First step: create a workspace.

OpenCode: [runs python scripts/init_workspace.py best-llm-2025]
```

## Mode Switching

OpenCode does not have explicit modes. You simulate them by context:

- **Research mode** (default): reference the active skill and the workspace files. Do not load `providers/`, `docs/adr/`, or meta-skills unless needed.
- **Developer mode**: when working on the toolkit itself, ask OpenCode to read `AGENTS.md`, the provider interfaces, and the relevant ADRs.

## Using OpenCode's Built-in Tools

OpenCode has built-in tools (file read/write, bash, web fetch) that work well with Calixto's scripts:

- Use `bash` to run the Calixto scripts (`python scripts/init_workspace.py ...`)
- Use `read` to read source files before extracting findings
- Use `write` to update `notes/findings.md`, `notes/summary.md`, `outputs/report.md`
- Use `webfetch` for direct web access when needed (the Calixto scripts do this for you, but a fallback is fine)

## Known Limitations

- OpenCode's context window is finite. Loading all skills at once wastes context. Reference only the skill you need.
- No built-in subagent system. The agent orchestrates everything itself.

## See Also

- [`AGENTS.md`](../../AGENTS.md): universal entry point
- `skills/deep-research.md`: the main research workflow
- [OpenCode docs](https://opencode.ai/docs)
