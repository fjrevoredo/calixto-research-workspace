# Research Preparation Skill Implementation Plan

## Metadata

- Plan Status: COMPLETED
- Created: 2026-06-28
- Last Updated: 2026-06-28
- Owner: Coding agent
- Approval: APPROVED BY USER IN CHAT ON 2026-06-28

## Status Legend

- Plan Status values: DRAFT, QUESTIONS PENDING, READY FOR APPROVAL, APPROVED, IN PROGRESS, COMPLETED, BLOCKED
- Task/Milestone Status values: TO BE DONE, IN PROGRESS, COMPLETED, BLOCKED, SKIPPED

## Goal

Introduce a holistic `research-preparation` workflow that always runs before source gathering when a research topic needs normalization. The workflow must triage the raw question, decide whether user clarification is needed, produce a structured `notes/research-brief.md`, and hand off cleanly to `deep-research` or `literature-review` inside a standalone workspace.

## Current Status

Implementation is complete. The runtime, docs, and test surfaces have been updated; skill validation, manifest loading, diff checks, targeted `rg` checks, a generated-workspace smoke inspection, and the targeted unit test suites all passed.

## Scope

- Add a workspace-visible `research-preparation` skill under `runtime/workspace/skills/research-preparation/`.
- Add a toolkit-side `research-preparation` handoff skill under `skills/research-preparation/`.
- Seed every new workspace with a structured `notes/research-brief.md` template.
- Update `deep-research` and `literature-review` so they consume the brief before searching.
- Update workspace and toolkit documentation so agents understand the new question -> triage -> brief -> research flow.
- Update `runtime/workspace-manifest.json` so future standalone workspaces include the new skill and brief artifact.
- Add or update tests proving the new runtime assets are bundled and mirrored consistently.
- Add a changelog entry describing the research preparation workflow.

## Non-Goals

- Do not add an LLM-calling Python script for clarification or brief generation.
- Do not require a new `calixto prepare` CLI command in the first implementation.
- Do not mutate existing generated workspaces in place.
- Do not change the source, finding, or insight ID scheme.
- Do not make research preparation a deterministic validator; it is an agent workflow with a durable markdown output.
- Do not remove the ability to run `deep-research` directly for advanced or already-prepared workspaces.

## Assumptions

- The first implementation should be skill-driven and file-based to preserve Calixto's agent-first design.
- `research-preparation` is a research-mode skill that belongs in standalone workspaces, unlike the host-only `research-retrospective` maintainer skill.
- Clarifying questions are conditional; the brief is mandatory whenever the preparation skill is used.
- `notes/research-brief.md` is the durable operating contract for downstream research.
- `config.json.question` remains the concise refined research question, while the brief records the raw question, assumptions, scope, output shape, evidence plan, uncertainty, and handoff notes.
- Existing workspaces are not rewritten by this change; only future workspaces created from the updated runtime bundle receive the new assets automatically.
- `tests/validate_skills.py` is the repo-local structural validator for both toolkit-side skills and workspace runtime skills.
- `runtime/workspace-manifest.json` copies `templates/workspace/notes` as a directory, so adding `templates/workspace/notes/research-brief.md` should bundle the brief template without a separate file entry; implementation must verify this with a generated workspace.

## Open Questions

- None.

## Milestones

### Milestone 1: Contract And Artifact Design

- Status: COMPLETED
- Purpose: Define the exact preparation workflow and research brief contract before touching runtime behavior.
- Exit Criteria: The brief schema, triage categories, clarification policy, and handoff behavior are explicit enough for a future agent to implement without rereading the original conversation.

#### Task 1.1: Define the Research Brief Template

- Status: COMPLETED
- Objective: Add a durable `notes/research-brief.md` template that future workspaces can use before source gathering.
- Steps:
  1. Create `templates/workspace/notes/research-brief.md`.
  2. Include sections for original question, refined question, triage summary, user intent, intended output, scope, assumptions, clarifications, evidence plan, report plan, expected uncertainty, and handoff notes.
  3. Keep placeholder text concise and executable by an agent.
- Validation: Inspect `templates/workspace/notes/research-brief.md` and confirm every planned section exists exactly once.
- Notes: Do not replace `notes/gaps.md`; keep gaps for research-time unresolved questions.

#### Task 1.2: Define Triage And Clarification Policy

- Status: COMPLETED
- Objective: Specify when the agent proceeds directly, asks clarifying questions, or proceeds with explicit assumptions.
- Steps:
  1. In the new workspace `research-preparation` skill, document three outcomes: proceed directly, ask targeted clarification, or proceed with explicit assumptions.
  2. Define triage dimensions: clarity, scope, intended outcome, domain, stakes, time sensitivity, subjectivity, expected uncertainty, source needs, and report shape.
  3. Add examples for simple medical self-care, broad philosophical questions, and open-ended business strategy questions.
- Validation: Manual inspection confirms the policy gives concrete decision criteria and does not ask questions reflexively.
- Notes: Medical examples must route to authoritative sources and red-flag language without giving personalized medical advice.

### Milestone 2: Skill Implementation

- Status: COMPLETED
- Purpose: Add both workspace and toolkit skill surfaces while keeping the runtime boundary clear.
- Exit Criteria: Both skill files validate structurally, describe the same workflow at the correct boundary, and avoid toolkit-root assumptions inside the workspace skill.

#### Task 2.1: Add Workspace `research-preparation` Skill

- Status: COMPLETED
- Objective: Create the canonical workspace-local skill used before `deep-research`.
- Steps:
  1. Create `runtime/workspace/skills/research-preparation/SKILL.md`.
  2. Add YAML frontmatter with `name: research-preparation`, a trigger-focused description, license, compatibility, and research-mode metadata.
  3. Write the two-phase workflow: initial triage, then research brief creation.
  4. Instruct the agent to update `config.json.question` only when a refined question is approved or safely assumed.
  5. Instruct the agent to save the complete brief to `notes/research-brief.md`.
  6. End with a handoff choice between `deep-research` and `literature-review`.
- Validation: Manual inspection confirms the skill references only workspace-local files and commands; `uv run python tests/validate_skills.py` passes after the skill exists.
- Notes: The skill should mention `scripts/workspace_info.py show .` only as a workspace-state inspection aid, not as a clarification mechanism.

#### Task 2.2: Add Toolkit-Side Handoff Skill

- Status: COMPLETED
- Objective: Create a toolkit-root skill that performs preparation before creating or opening a workspace.
- Steps:
  1. Create `skills/research-preparation/SKILL.md`.
  2. Document that this skill runs from the toolkit root and may create a workspace with `calixto research "<refined question>" --agent none`.
  3. Instruct the agent to write or paste the approved brief into the generated workspace's `notes/research-brief.md`.
  4. Explain that the workspace-local `research-preparation` skill is the source of truth after entering the workspace.
- Validation: Manual inspection confirms the toolkit skill uses toolkit commands only before workspace handoff and does not imply existing workspaces are rewritten; `uv run python tests/validate_skills.py` passes after the skill exists.
- Notes: Keep this as a handoff skill, similar in spirit to toolkit-side `deep-research` and `literature-review`.

#### Task 2.3: Keep Skill Copies Consistent Where Intentional

- Status: COMPLETED
- Objective: Ensure the toolkit and workspace skill variants agree on the core workflow while preserving boundary-specific commands.
- Steps:
  1. Compare the two `research-preparation/SKILL.md` files.
  2. Confirm both describe question triage, conditional clarification, mandatory brief creation, and downstream handoff.
  3. Confirm only the toolkit-side skill references `calixto research` or toolkit-root behavior.
- Validation: Run `rg -n "calixto research|toolkit root|scripts/init_workspace.py" runtime/workspace/skills/research-preparation skills/research-preparation` and verify toolkit-only terms do not appear in the workspace skill.
- Notes: Similar wording is acceptable; identical files are not required because the boundary differs.

### Milestone 3: Runtime Integration

- Status: COMPLETED
- Purpose: Make future standalone workspaces receive and use the preparation workflow by default.
- Exit Criteria: Generated workspace snapshots include `notes/research-brief.md` and `skills/research-preparation/SKILL.md`, and downstream skills know to consume the brief before search.

#### Task 3.1: Update Runtime Manifest

- Status: COMPLETED
- Objective: Bundle the new workspace skill and brief template into future workspaces.
- Steps:
  1. Add `runtime/workspace/skills/research-preparation` to `runtime/workspace-manifest.json`.
  2. Confirm `templates/workspace/notes` still copies the new brief template through the existing notes directory entry.
  3. Do not add toolkit-only `skills/research-preparation` to the runtime manifest.
- Validation: Inspect `runtime/workspace-manifest.json` and confirm exactly one workspace `research-preparation` skill entry exists; run `uv run python -c "import sys; sys.path.insert(0, 'scripts'); from runtime_bundle import load_runtime_manifest; load_runtime_manifest(); print('ok')"` from the repo root.
- Notes: Because `templates/workspace/notes` is already bundled as a directory, the brief template may not require a separate manifest entry.

#### Task 3.2: Update Workspace AGENTS Guidance

- Status: COMPLETED
- Objective: Teach workspace agents the new default flow.
- Steps:
  1. Update `runtime/workspace/AGENTS.md` to list `research-preparation` as the first skill for underspecified or new research topics.
  2. Document the flow as question -> triage -> brief -> deep research or literature review.
  3. Mention that `notes/research-brief.md` is the operating contract for source gathering and final report shape.
- Validation: Manual inspection confirms workspace AGENTS still preserves the research/developer boundary and does not reference toolkit maintainer docs.
- Notes: Keep the guidance short so workspace AGENTS remains a practical entry point.

#### Task 3.3: Update Deep Research Skill To Consume Briefs

- Status: COMPLETED
- Objective: Make `deep-research` use the preparation artifact before searching.
- Steps:
  1. Update `runtime/workspace/skills/deep-research/SKILL.md` Step 1.
  2. Tell the agent to read `notes/research-brief.md` when present and populated.
  3. Tell the agent to run `research-preparation` first when the question is raw, ambiguous, or no brief exists.
  4. Keep traceability, source review, and final audit instructions unchanged.
- Validation: Manual inspection confirms source gathering still starts after question and brief confirmation.
- Notes: Avoid making brief absence a hard failure for advanced users.

#### Task 3.4: Update Literature Review Skill To Consume Briefs

- Status: COMPLETED
- Objective: Make `literature-review` use the preparation artifact before scholarly search.
- Steps:
  1. Update `runtime/workspace/skills/literature-review/SKILL.md` Step 1.
  2. Tell the agent to read the brief for scope, evidence standard, scholarly-provider choice, and report structure.
  3. Tell the agent to run `research-preparation` first when academic scope, corpus type, or review shape is unclear.
  4. Keep PubMed/arXiv routing guidance intact.
- Validation: Manual inspection confirms provider routing remains domain-aware and consistent with ADR 002.
- Notes: The brief should improve provider choice, not replace the literature-review workflow.

### Milestone 4: Toolkit Documentation And Product Contract

- Status: COMPLETED
- Purpose: Keep root documentation, formal requirements, and user-facing docs aligned with the new default workflow.
- Exit Criteria: Repo docs consistently describe research preparation as a research-mode skill and the workspace brief as the pre-search contract.

#### Task 4.1: Update Root AGENTS

- Status: COMPLETED
- Objective: Document the new skill in the agent entry point.
- Steps:
  1. Update `AGENTS.md` Developer Mode context or script/skill reference as needed.
  2. Add `research-preparation` to the skill description area.
  3. Clarify that it is bundled into standalone workspaces and is not a maintainer-only skill.
- Validation: `rg -n "research-preparation|research brief|research-retrospective" AGENTS.md` shows distinct descriptions for research and maintainer skills.
- Notes: Preserve the toolkit-root versus workspace-root boundary language.

#### Task 4.2: Update Requirements

- Status: COMPLETED
- Objective: Add the formal specification for the preparation skill and brief artifact.
- Steps:
  1. Update repository and workspace structure examples in `requirements.md` to include `research-preparation` and `notes/research-brief.md`.
  2. Add a new skills subsection for `research-preparation`.
  3. Update the deep-research workflow description to include triage and brief creation before search.
  4. Update config or notes sections to explain the relationship between `config.json.question` and `notes/research-brief.md`.
  5. Update the implementation checklist if it still lists the old skill set without `research-preparation`.
- Validation: `rg -n "research-preparation|research-brief|question -> triage|brief" requirements.md` finds the new contract in structure, skills, and state sections.
- Notes: Do not imply the brief is a source or traceability ID artifact.

#### Task 4.3: Update README Or User-Facing Docs

- Status: COMPLETED
- Objective: Surface the workflow change to users without bloating setup docs.
- Steps:
  1. Update `README.md` to mention the preparation step in the user-facing research workflow.
  2. Keep the existing `calixto research "question" --agent none` command valid.
  3. Explain that the agent may clarify the question and will write a brief before source gathering.
- Validation: Manual inspection confirms README still presents a concise getting-started path.
- Notes: Avoid adding a new command unless implementation later explicitly adds one.

#### Task 4.4: Consider ADR Need And Record Decision If Needed

- Status: COMPLETED
- Objective: Decide whether this workflow change deserves an ADR.
- Steps:
  1. Review the final scope after implementation.
  2. If the change materially alters the product contract, create `docs/adr/003-research-preparation-brief.md`.
  3. If an ADR is not warranted, record the rationale in the plan execution notes.
- Validation: Either an ADR exists with status/date/context/decision/consequences, or the plan notes explain why docs and requirements were sufficient.
- Notes: This is a judgment gate, not a default paperwork requirement.

#### Task 4.5: Check Packaging And Adapter Implications

- Status: COMPLETED
- Objective: Verify no package, adapter, or harness documentation needs a separate update beyond the canonical runtime and root docs.
- Steps:
  1. Inspect `pyproject.toml` to confirm root `skills/`, `runtime/`, and `templates/` are already included in packaged artifacts.
  2. Inspect `adapters/` docs for any hard-coded list of bundled skills.
  3. Update adapter docs only if they would otherwise mislead harness users about available skills.
- Validation: `rg -n "deep-research|literature-review|research-preparation|skills/" adapters pyproject.toml` shows either no stale hard-coded list or an intentional update.
- Notes: Harness mirrors are generated from canonical workspace `skills/`; do not document mirror directories as the source of truth.

### Milestone 5: Tests And Verification

- Status: COMPLETED
- Purpose: Prove the new assets are bundled, mirrored, and discoverable in future workspaces.
- Exit Criteria: Unit tests and an optional generated workspace inspection show the new skill and brief are present in standalone workspaces and harness mirrors.

#### Task 5.1: Update Runtime Bundle Tests

- Status: COMPLETED
- Objective: Extend existing tests so workspace creation includes the preparation skill and brief.
- Steps:
  1. Update tests that assert bundled skills, likely in `tests/unit/test_scripts.py`.
  2. Add assertions that a generated workspace contains `skills/research-preparation/SKILL.md`.
  3. Add assertions that a generated workspace contains `notes/research-brief.md`.
- Validation: Run `uv run pytest tests/unit/test_scripts.py`.
- Notes: If the repo's local environment lacks pytest dependencies, record the exact failure and run the closest available Python command.

#### Task 5.2: Update Harness Mirror Tests

- Status: COMPLETED
- Objective: Confirm harness-native mirrors include the new skill when mirrors are prepared.
- Steps:
  1. Update tests that inspect `.agents/skills` or `.claude/skills`, likely in `tests/unit/test_calixto_cli.py`.
  2. Assert `research-preparation` is mirrored alongside `deep-research` and `literature-review`.
  3. Confirm force-preserve behavior still applies to all mirrored canonical skills.
- Validation: Run `uv run pytest tests/unit/test_calixto_cli.py`.
- Notes: The canonical skill directory remains `skills/`; mirrors are generated integration artifacts.

#### Task 5.3: Add Manual Generated Workspace Inspection

- Status: COMPLETED
- Objective: Verify the runtime manifest, templates, and docs work together in a real generated workspace.
- Steps:
  1. Create a temporary workspace with `uv run python scripts/init_workspace.py research-prep-smoke --path <temporary parent> --skip-update-check`.
  2. Inspect the generated workspace for `skills/research-preparation/SKILL.md`, `notes/research-brief.md`, `skills/deep-research/SKILL.md`, and `AGENTS.md`.
  3. Delete the temporary workspace after inspection.
- Validation: The generated workspace contains the new skill and brief before deletion.
- Notes: Use a temp parent outside tracked `workspaces/` if possible to avoid accidental repo noise.

#### Task 5.4: Run Documentation And Diff Checks

- Status: COMPLETED
- Objective: Catch broken references, formatting drift, and unintended changes.
- Steps:
  1. Run `uv run python tests/validate_skills.py`.
  2. Run `git diff --check`.
  3. Run targeted `rg` checks for `research-preparation` and `research-brief`.
  4. Review `git diff` manually for boundary violations, especially host-only versus workspace-visible skill placement.
- Validation: Skill validation and `git diff --check` pass, and manual diff review finds only intended changes.
- Notes: This task does not replace unit tests.

### Milestone 6: Cleanup And Final Verification

- Status: COMPLETED
- Purpose: Ensure the repository contains only intentional final artifacts and the complete change is verified.
- Exit Criteria: Intermediate artifacts are removed, changelog is updated, all final verification passes or blockers are recorded, and the plan status can be moved to COMPLETED.

#### Task 6.1: Update Changelog

- Status: COMPLETED
- Objective: Record the user-facing workflow change.
- Steps:
  1. Add a concise `CHANGELOG.md` entry for the research preparation skill, research brief template, and downstream skill integration.
  2. Mention that existing workspaces are not rewritten.
- Validation: Manual inspection confirms `CHANGELOG.md` contains a clear entry for this change.
- Notes: Keep the changelog factual and avoid implementation minutiae.

#### Task 6.2: Cleanup Intermediate Artifacts

- Status: COMPLETED
- Objective: Remove artifacts created only to support implementation.
- Steps:
  1. Inspect the worktree for temporary documentation, one-off scripts, scratch tests, generated data, logs, and obsolete plan fragments.
  2. Remove only artifacts that are not part of the intended final repository state.
  3. Keep maintainable tests, fixtures, docs, and generated files that are part of the repository contract.
- Validation: `git status --short` and manual diff review show only intended final changes.
- Notes: Do not remove user-provided files or unrelated worktree changes.

#### Task 6.3: Final Verification

- Status: COMPLETED
- Objective: Validate the integrated change after cleanup.
- Steps:
  1. Run `uv run pytest tests/unit/test_scripts.py tests/unit/test_calixto_cli.py`.
  2. Run `uv run python tests/validate_skills.py`.
  3. Run `uv run python -c "import sys; sys.path.insert(0, 'scripts'); from runtime_bundle import load_runtime_manifest; load_runtime_manifest(); print('ok')"` from the repo root.
  4. Run `git diff --check`.
  5. Run `rg -n "research-preparation|research-brief|research brief" AGENTS.md README.md requirements.md runtime templates skills tests CHANGELOG.md`.
  6. Review the final diff against this plan's scope and non-goals.
  7. Update plan statuses to COMPLETED only after validation passes or record blockers.
- Validation: The listed commands pass, the final diff matches the approved scope, and any skipped validation has an explicit reason.
- Notes: If local tooling is unavailable, record exact command output and perform deterministic file inspections as fallback.

## Approval Gate

Implementation must not start until the user approves this plan.

## Plan Self-Check

- [x] Plan location follows the default location rule.
- [x] Plan status is `READY FOR APPROVAL`.
- [x] Scope, non-goals, assumptions, and open questions are explicit.
- [x] Any unresolved open questions have been surfaced to the user.
- [x] Tasks are grouped into milestones because the plan has more than 10 tasks.
- [x] Every task has concrete steps and validation.
- [x] Every milestone has exit criteria.
- [x] Cleanup and final verification are included.
- [x] The plan avoids vague actions without concrete targets.
- [x] The plan can be executed by a coding agent without reading the original conversation.

## Full Self-Check Record

- Date: 2026-06-28
- Result: Corrected and ready for approval.
- Evidence reviewed:
  - `docs/research-preparation-skill-plan.md`
  - `runtime/workspace-manifest.json`
  - `scripts/runtime_bundle.py`
  - `runtime/workspace/AGENTS.md`
  - `runtime/workspace/skills/deep-research/SKILL.md`
  - `runtime/workspace/skills/literature-review/SKILL.md`
  - `templates/workspace/config.json`
  - `templates/workspace/notes/`
  - `tests/unit/test_scripts.py`
  - `tests/unit/test_calixto_cli.py`
  - `tests/validate_skills.py`
  - `pyproject.toml`
  - `PHILOSOPHY.md`
- Corrections made:
  - Added a dedicated Current Status section required by the manual-planning format.
  - Added explicit `tests/validate_skills.py` validation for the new toolkit and workspace skills.
  - Added runtime manifest loading validation in the manifest and final verification tasks, using the same `scripts/` import-path setup the repo tests use.
  - Added requirements coverage for implementation checklist drift.
  - Added packaging and adapter inspection to catch stale hard-coded skill lists.
  - Clarified that `templates/workspace/notes` already bundles the brief template directory, subject to generated-workspace verification.
- Residual risks:
  - Whether to create an ADR remains a deliberate implementation-time decision because the final scope may stay fully covered by requirements and skill docs.
  - Existing generated workspaces remain unchanged by design; users must create a new workspace or manually copy the skill/template if they want the workflow in an old workspace.

## Execution Notes

- Update milestone and task status before starting and after validation.
- Update each task to COMPLETED immediately after its validation passes.
- Mark tasks or milestones BLOCKED with a short reason when progress cannot continue.
- During implementation, keep `docs/research-preparation-skill-plan.md` as the execution ledger.
- 2026-06-28: Completed the brief template, workspace skill, toolkit handoff skill, and the boundary validation (`uv run python tests/validate_skills.py` plus targeted `rg` checks). Runtime integration is now in progress.
- 2026-06-28: Completed runtime integration, root documentation updates, adapter checks, changelog entry, and targeted test updates.
- 2026-06-28: `uv run python tests/validate_skills.py` passed.
- 2026-06-28: `uv run python -c "import sys; sys.path.insert(0, 'scripts'); from runtime_bundle import load_runtime_manifest; load_runtime_manifest(); print('ok')"` passed.
- 2026-06-28: `git diff --check` passed.
- 2026-06-28: Targeted `rg -n "research-preparation|research-brief|research brief" AGENTS.md README.md requirements.md runtime templates skills tests CHANGELOG.md adapters` confirmed the expected contract surfaces.
- 2026-06-28: Temporary generated-workspace smoke inspection passed and was cleaned up. The generated workspace contained `AGENTS.md`, `skills/deep-research/SKILL.md`, `skills/research-preparation/SKILL.md`, and `notes/research-brief.md`.
- 2026-06-28: Initial parallel attempts to run pytest through `uv run` were inconclusive because the repo environment did not yet have the dev-test dependencies available and concurrent installation attempts hit Windows file-locking errors.
- 2026-06-28: Serialized retries with `UV_LINK_MODE=copy` and `uv run --extra dev python -m pytest tests/unit/test_scripts.py` passed (`67 passed`).
- 2026-06-28: Serialized retries with `UV_LINK_MODE=copy` and `uv run --extra dev python -m pytest tests/unit/test_calixto_cli.py` passed (`12 passed`).
- 2026-06-28: ADR decision: no new ADR was added. This change introduces a new research-mode skill and durable brief artifact, but it does not alter the toolkit/workspace boundary, runtime architecture, hidden-state model, or provider contract beyond what the updated requirements and runtime docs already cover.
