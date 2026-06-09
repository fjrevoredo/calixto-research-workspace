---
name: literature-review
description: "Toolkit-side handoff for Calixto literature reviews. Use when starting from the toolkit root and the user needs a paper-heavy review workflow. This skill creates a standalone workspace snapshot, switches into it, and then continues with the bundled workspace-local literature-review skill."
license: MIT
compatibility: Requires Python 3.11+, the Calixto toolkit root, and `scripts/init_workspace.py` in this repository.
metadata:
  category: research
  mode: research
  version: "0.1.0"
---

# Literature Review

Use this skill when you are at the toolkit root and need to start a new
literature-review workspace.

## Goal

Create a standalone workspace snapshot, move into it, and continue the review
there using the bundled runtime assets.

## Workflow

### Step 1: Create a workspace

```bash
uv run python scripts/init_workspace.py <slug>
```

### Step 2: Enter the workspace

```bash
cd workspaces/<slug>
```

### Step 3: Prepare the workspace runtime

Run the workspace-local setup helper:

```bash
./setup.sh
```

Or on Windows:

```powershell
.\setup.ps1
```

### Step 4: Switch to the bundled workspace-local skill

Open these files from inside the workspace you just created:

- `AGENTS.md`
- `skills/literature-review/SKILL.md`

Then continue the literature review from the standalone workspace.
