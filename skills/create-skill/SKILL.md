---
name: create-skill
description: Teaches an agent how to create a new Calixto skill (a research workflow packaged as a directory of markdown with a SKILL.md file). Use when the user wants to add a new research skill, formalize a recurring pattern, or build a domain-specific variant of an existing skill (e.g., competitive analysis, bug triage, codebase archaeology). Covers the Agent Skills spec, skill file structure, ID conventions, validation, and examples.
license: MIT
compatibility: Requires Python 3.11+, Calixto Research Workspace installed. Reads from and writes to the skills/ directory in the Calixto repo.
metadata:
  category: meta
  mode: developer
  version: "0.1.0"
---

# Create a Skill (Meta-Skill)

Teaches an agent how to write a new research skill for Calixto. Skills are directories under `skills/` with a `SKILL.md` file at the root, following the [Agent Skills spec](https://agentskills.io/specification).

## When to Use

- The user asks for a new research skill (e.g., "create a competitive analysis skill")
- The user wants to formalize a recurring pattern into a reusable workflow
- A new domain needs a specialized variant of `deep-research` or `literature-review`

Do NOT use this skill for one-off research tasks, fixing an existing skill (edit in place), or for adding new tool providers (use `integrate-tool` instead).

## Goal

Produce a new skill directory at `skills/<skill-name>/SKILL.md` that:

1. Has a valid `name` and `description` in the YAML frontmatter
2. The `name` matches the directory name
3. Has clear, scoped workflow instructions in the body
4. Passes `skills-ref validate` (when available)
5. Is documented in `AGENTS.md` and (if appropriate) `requirements.md`

## Directory Structure (per the spec)

```
skills/<skill-name>/
|-- SKILL.md        # Required: frontmatter + body
|-- scripts/        # Optional: executable code bundled with the skill
|-- references/     # Optional: detailed reference docs loaded on demand
`-- assets/         # Optional: templates, images, lookup tables
```

For Calixto, skill context depends on where the skill lives. Toolkit-side skills
at the repo root can reference toolkit scripts such as `scripts/init_workspace.py`.
Workspace runtime skills should reference the bundled workspace-local scripts and
must not assume the parent toolkit checkout exists. Reserve a skill-local
`scripts/` directory for logic that is specific to one skill and reused across
many tasks.

## SKILL.md Format

Required YAML frontmatter:

| Field | Required | Notes |
|---|---|---|
| `name` | Yes | 1-64 chars, lowercase, alphanum + hyphens, no leading/trailing `--` |
| `description` | Yes | 1-1024 chars. Describes what the skill does AND when to use it. Include keywords that trigger the skill. |
| `license` | No | e.g., `MIT` |
| `compatibility` | No | 1-500 chars. Environment requirements. |
| `metadata` | No | Arbitrary key-value pairs. |
| `allowed-tools` | No | Space-separated tool allowlist (experimental). |

Body content has no format restrictions. Recommended sections: step-by-step instructions, examples, common edge cases.

### Minimal example

```markdown
---
name: my-skill
description: One-sentence summary of what the skill does and when to use it.
---

# My Skill

Step-by-step instructions here.
```

### Full example

```markdown
---
name: competitive-analysis
description: Produces a competitive landscape report identifying main competitors and comparing their offerings. Use when the user asks "who competes with X?" or wants a market scan for a product category.
license: MIT
compatibility: Requires Python 3.11+ and the Calixto search scripts.
metadata:
  category: research
  mode: research
  version: "0.1.0"
---

# Competitive Analysis
...
```

## Steps to Create a New Skill

1. **Identify the workflow.** What does the agent need to do that the existing skills do not cover? Avoid duplicating `deep-research` or `literature-review`.

2. **Sketch the 5-10 main steps.** The skill should be a coherent unit of work. If you need more than 10 steps, the skill is probably too broad. If fewer than 3, it is too narrow.

3. **Decide the mode.** Research mode (default) or developer mode only. The metadata block should reflect this.

4. **Choose a slug.** Kebab-case, lowercase, alphanum + hyphens. The slug must match the directory name and the `name` field in frontmatter.

5. **Write the description carefully.** This is the only field the agent sees at startup for all skills. The description must be specific enough to trigger on the right prompts and short enough to fit in 1024 characters. Include concrete keywords (e.g., "competitor", "market scan", "battlecard") that match what users will type.

6. **Write the body.** Structure it for progressive disclosure:
   - Lead with the goal and when to use
   - Then the workflow steps
   - Then decision criteria, quality guidelines, common pitfalls
   - Keep total length under 500 lines and under 5,000 tokens
   - Move detailed reference material to `references/` if it would otherwise push the file over 500 lines

7. **Reference the correct runtime boundary explicitly.** Toolkit-side skills may
   reference repo-root commands such as `uv run python scripts/init_workspace.py <slug>`.
   Workspace runtime skills should reference bundled commands such as
   `uv run python scripts/search_web.py "query" --workspace . --max-results 10`.

8. **Define ID conventions if needed.** If the skill introduces new traceable items (e.g., `comp_NNN` for a competitor), document the prefix and the format in the skill.

9. **Update `AGENTS.md`.** Add the new skill to the Skills Reference table.

10. **Validate.** If `skills-ref` is available, run `skills-ref validate ./skills/<skill-name>`. If not, manually check: name matches directory, no `--` in name, description is non-empty, frontmatter parses as YAML.

## Best Practices (from the spec)

- **Aim for moderate detail.** Concise, stepwise guidance with a working example tends to outperform exhaustive documentation.
- **Match specificity to fragility.** Be prescriptive for fragile, sequenced operations; give the agent freedom where multiple approaches are valid.
- **Provide defaults, not menus.** Pick a default approach and mention alternatives briefly.
- **Favor procedures over declarations.** The skill should teach the agent how to approach a class of problems, not what to produce for a specific instance.
- **Use gotchas sections.** The highest-value content is often a list of non-obvious corrections.
- **Use templates for output format.** Show concrete templates for report structure, finding format, etc. rather than describing the format in prose.
- **Checklists for multi-step workflows.** An explicit progress checklist helps the agent track state.

## ID Conventions

If your skill introduces new types of traceable items, document them. Stick to the established format `<prefix>_NNN` (zero-padded 3 digits).

Existing ID types:

- `src_NNN`: a collected source (assigned by search scripts)
- `fnd_NNN`: a finding (assigned by the agent)
- `ins_NNN`: an insight (assigned by the agent)

A new skill could introduce:

- `comp_NNN`: a competitor in competitive analysis
- `hyp_NNN`: a hypothesis in a research project
- `q_NNN`: a question in a Q&A skill

Each new ID type must:

- Have a unique prefix that does not collide
- Be assigned sequentially within a workspace
- Be saved in a structured place (markdown file with a clear format)
- Be referenced by higher-level IDs

## Examples

### Competitive Analysis Skill

```markdown
---
name: competitive-analysis
description: Produces a competitive landscape report identifying main competitors and comparing their offerings. Use when the user asks "who competes with X?" or wants a market scan for a product category.
---

# Competitive Analysis

## Workflow

1. Initialize: create workspace with the company or category as the slug
2. Search: 3-5 queries like "<category> competitors", "<category> comparison 2025"
3. Filter: keep sources from vendor sites, review sites, and analysts; skip forum noise
4. Extract: for each competitor, write `comp_NNN` with name, URL, source ID, one-line description
5. Build a comparison table: rows are competitors, columns are key features
6. Write a "battlecard" report: strengths, weaknesses, pricing, target audience
7. Audit and iterate
```

## Validation Checklist

Before declaring a new skill done, verify:

- The skill is in the right location (`skills/<name>/SKILL.md`)
- The directory name matches the `name` field
- The filename is exactly `SKILL.md` (case-sensitive)
- The `name` is 1-64 chars, lowercase, alphanum + hyphens, no `--`, no leading/trailing hyphen
- The `description` is 1-1024 chars, non-empty, and describes both what and when
- The skill is referenced in `AGENTS.md` Skills Reference table
- An end-to-end test of the skill on a small input succeeds

## Updating Documentation

When you add a new skill:

1. Add an entry to the "Skills Reference" table in `AGENTS.md`
2. If the skill introduces new ID types, document them in `requirements.md` section 7
3. If the skill requires a new script, see `integrate-tool/SKILL.md` for how to add it
4. Add an entry to the decision log if you made non-obvious choices

## See Also

- `skills/deep-research/SKILL.md`: the canonical research workflow
- `skills/literature-review/SKILL.md`: the academic variant
- `skills/integrate-tool/SKILL.md`: how to add new scripts and providers
- `PHILOSOPHY.md` Principle 1: Agent-First (skills are for agents to follow)
- `requirements.md` section 6: Skills
- [Agent Skills specification](https://agentskills.io/specification)
- [Best practices for skill creators](https://agentskills.io/skill-creation/best-practices)
