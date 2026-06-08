# Self-Contained Workspace Redesign Plan

## Metadata

- Plan Status: READY FOR APPROVAL
- Created: 2026-06-09
- Last Updated: 2026-06-09
- Owner: Coding agent
- Approval: PENDING

## Status Legend

- Plan Status values: DRAFT, QUESTIONS PENDING, READY FOR APPROVAL, APPROVED, IN PROGRESS, COMPLETED, BLOCKED
- Task/Milestone Status values: TO BE DONE, IN PROGRESS, COMPLETED, BLOCKED, SKIPPED

## Goal

Redesign Calixto so the repository root is the toolkit source and factory, while each newly created workspace is a self-contained research snapshot that can be copied elsewhere and still be usable without depending on the parent repository layout. Root-level updates must affect only future workspaces, not existing ones.

## Scope

- Redefine the root repository as developer/toolkit content only.
- Define the exact runtime asset set that must be copied into each new workspace.
- Change workspace creation so it materializes a standalone runtime snapshot.
- Refactor research-facing scripts and docs to run from inside a copied workspace.
- Simplify installer and update behavior so it manages the toolkit root only.
- Add tests and documentation for standalone workspace creation and copied-workspace execution.

## Non-Goals

- Automatically migrating all existing workspaces to the new standalone format in this change.
- Vendoring a Python virtual environment or binary dependencies into each workspace.
- Implementing container images or remote runners in this change.
- Refactoring unrelated providers, search behavior, or report quality logic.
- Preserving the current “update mixed root + workspace state in place” model.

## Current Status

The current implementation still assumes the root repository owns most runtime assets and that workspaces are template-only data folders under `workspaces/`. Recent installer hardening also optimized the wrong boundary by treating mixed toolkit and user state as an update target. No reset toward standalone workspace snapshots has been implemented yet.

## Assumptions

- “Portable workspace” means filesystem-portable within the same machine or another machine after dependency setup, not shipping a prebuilt virtualenv.
- A standalone workspace should contain only research-facing runtime assets, not developer ADRs, golden tests, or meta-skills for maintaining Calixto itself.
- Existing standalone-incompatible workspaces may remain supported only under the old root-driven model until a separate migration path is approved.
- The preferred user flow remains: install/setup toolkit once at the root, create a workspace snapshot, `cd` into that workspace, and run the agent there.
- The current `scripts/init_workspace.py` entrypoint may remain in place even if additional wrapper commands are introduced later.

## Open Questions

- None.

## Milestones

### Milestone 1: Reset The Product Contract

- Status: TO BE DONE
- Purpose: Re-establish the intended architecture before changing code so implementation follows a stable boundary.
- Exit Criteria: The repository docs clearly define root toolkit content vs. standalone workspace content, and implementation work has a single approved contract to follow.

#### Task 1.1: Write The Root-vs-Workspace Architecture Statement

- Status: TO BE DONE
- Objective: Replace the mixed-state mental model with an explicit “toolkit factory + standalone workspace snapshot” contract.
- Steps:
  1. Update the primary architecture docs to define the root repository as developer/toolkit source only.
  2. Define a workspace as a self-contained research project snapshot with its own runtime-facing docs, skills, scripts, and state files.
  3. State explicitly that root updates affect only future workspaces unless a separate migration command is used.
- Validation: Inspect updated docs and confirm they contain the three explicit statements above without describing in-place updates of existing workspaces.
- Notes: Update at minimum `AGENTS.md`, `PHILOSOPHY.md`, and any user-facing installer/setup docs that currently blur the boundary.

#### Task 1.2: Define The Workspace Runtime Asset Manifest

- Status: TO BE DONE
- Objective: Produce a concrete list of files and directories that every standalone workspace must include.
- Steps:
  1. Audit current root assets and classify each as developer-only, research-runtime, or template-only.
  2. Create a manifest document or machine-readable manifest listing the workspace runtime payload.
  3. Include the research-facing `AGENTS.md`, runtime scripts, providers, skills, workspace seed files, and any bootstrap helpers that must live inside the workspace.
- Validation: The manifest names every copied top-level workspace asset and excludes developer-only assets such as ADRs, golden tests, and maintainer meta-skills.
- Notes: Do not leave the runtime bundle implicit in `init_workspace.py`.

#### Task 1.3: Define Workspace Metadata And Compatibility Rules

- Status: TO BE DONE
- Objective: Make each standalone workspace self-describing and versioned.
- Steps:
  1. Add workspace metadata fields such as `workspace_schema_version`, `runtime_bundle_version`, and `toolkit_version_created_with`.
  2. Define which fields are required for new workspaces and which are legacy-compatible.
  3. Document how future code should detect whether a workspace is standalone or legacy.
- Validation: A sample metadata block exists in the docs and a reviewer can determine standalone-vs-legacy format by inspection.
- Notes: Prefer stable, explicit version keys over inferred behavior from file presence alone.

#### Task 1.4: Re-scope Existing Installer Hardening Against The New Boundary

- Status: TO BE DONE
- Objective: Prevent further work from reinforcing the wrong root/workspace update model.
- Steps:
  1. Review current installer/update changes against the new standalone-workspace direction.
  2. Identify which parts remain useful for root toolkit installation and which parts should be simplified or dropped.
  3. Record the keep/drop decisions in the decision log before implementation proceeds.
- Validation: A written keep/drop table or decision-log entry exists and covers managed-entry logic, update rollback, and workspace preservation behavior.
- Notes: This task is a scope correction, not a full installer rewrite by itself.

### Milestone 2: Materialize Standalone Workspace Snapshots

- Status: TO BE DONE
- Purpose: Change workspace creation from “copy a small template” to “create a runnable research snapshot.”
- Exit Criteria: A new workspace contains the defined runtime bundle, can be opened directly by an agent, and does not require parent-repo-relative paths for research execution.

#### Task 2.1: Create A Workspace Runtime Source Tree Or Bundle Builder

- Status: TO BE DONE
- Objective: Introduce a single source of truth for the files copied into a new workspace.
- Steps:
  1. Decide whether the runtime payload is maintained as a dedicated source tree, a generated bundle, or a manifest-driven copy operation.
  2. Create the structure that holds research-facing runtime assets separate from developer-only assets.
  3. Ensure the runtime payload can be copied without also copying unrelated root repository files.
- Validation: A dry inspection of the runtime source tree or bundle builder shows only the intended research-facing assets.
- Notes: Keep this mechanism simple enough that `init_workspace.py` does not need ad hoc include/exclude rules spread across the script.

#### Task 2.2: Replace Template-Only Initialization With Snapshot Initialization

- Status: TO BE DONE
- Objective: Make workspace creation copy the runtime bundle plus seed state files.
- Steps:
  1. Refactor `scripts/init_workspace.py` so it creates a workspace from the runtime bundle instead of only `templates/workspace/`.
  2. Preserve slug validation and refusal to overwrite existing workspaces.
  3. Write the workspace metadata defined in Milestone 1 into the initialized workspace.
- Validation: `python scripts/init_workspace.py test-1` creates a workspace containing runtime assets, seed workspace files, and version metadata.
- Notes: The output contract should remain structured JSON unless an approved CLI redesign changes it.

#### Task 2.3: Add Workspace-Local Bootstrap Helpers

- Status: TO BE DONE
- Objective: Ensure a copied workspace has its own setup/bootstrap entrypoint instead of relying on root setup scripts.
- Steps:
  1. Add workspace-local setup helpers or bootstrap commands that install or verify required Python dependencies for the standalone workspace.
  2. Make the bootstrap logic relative to the workspace root, not the original repository root.
  3. Document how an agent or user should initialize a copied workspace after moving it elsewhere.
- Validation: The plan identifies a concrete workspace-local bootstrap command and its documentation lives inside the standalone workspace payload.
- Notes: This task does not require shipping a virtualenv inside the workspace.

#### Task 2.4: Create Workspace-Local Research Entry Docs

- Status: TO BE DONE
- Objective: Make a new workspace understandable in isolation by an agent started inside it.
- Steps:
  1. Add a research-facing `AGENTS.md` or equivalent workspace-local entry document inside the runtime bundle.
  2. Ensure it references workspace-local skills/scripts, not root-only paths.
  3. Remove or rewrite instructions that assume the agent is operating from the toolkit root.
- Validation: A reviewer can open the generated workspace alone and find clear instructions for performing research without consulting the parent repository.
- Notes: Keep developer-mode and maintainer instructions out of the workspace entry docs.

### Milestone 3: Make Runtime Scripts And Skills Truly Workspace-Relative

- Status: TO BE DONE
- Purpose: Remove hidden root-repository assumptions from the research runtime.
- Exit Criteria: Research scripts, skills, and example flows work when executed from a copied standalone workspace without resolving paths back into the toolkit root.

#### Task 3.1: Audit Research Runtime Code For Root-Relative Assumptions

- Status: TO BE DONE
- Objective: Identify every script or skill that assumes the repository root owns the runtime.
- Steps:
  1. Audit `scripts/`, `providers/`, research-facing skills, and supporting docs for `REPO_ROOT`, `Path(__file__).parent.parent`, or equivalent root-relative assumptions.
  2. Classify each assumption as safe, needs refactor, or should stay developer-only.
  3. Record the affected files and required changes in the implementation notes.
- Validation: A tracked list exists of each runtime file that must change for copied-workspace execution.
- Notes: Focus on research runtime only; developer/test tooling can remain root-relative.

#### Task 3.2: Refactor Research Scripts To Resolve From The Workspace Root

- Status: TO BE DONE
- Objective: Make research scripts run correctly from inside a standalone workspace.
- Steps:
  1. Refactor runtime scripts so they locate config, sources, notes, outputs, and bundled providers relative to the workspace root.
  2. Remove dependencies on root-only directories such as `templates/`, `docs/`, or developer-only skills.
  3. Preserve CLI behavior where it remains compatible with the new workspace boundary.
- Validation: Running the primary research scripts from inside a copied standalone workspace succeeds without importing from the parent repository.
- Notes: If a shared helper module is needed, place it inside the runtime bundle.

#### Task 3.3: Refactor Research Skills To Reference Bundled Runtime Assets

- Status: TO BE DONE
- Objective: Make research skills accurate when used from a standalone workspace.
- Steps:
  1. Update research skill compatibility and usage text to point at workspace-local scripts and files.
  2. Remove references to developer-only paths and root-only maintenance assets.
  3. Verify that the research skill can be followed in a copied workspace without reinterpretation.
- Validation: The bundled research skill instructions match the workspace layout and do not mention unavailable root-only paths.
- Notes: Developer meta-skills should remain root-only and must not leak into the runtime bundle.

#### Task 3.4: Add A Standalone Example Workspace Or Fixture

- Status: TO BE DONE
- Objective: Preserve a concrete example of the new standalone runtime model.
- Steps:
  1. Create or regenerate an example workspace snapshot using the new initialization flow.
  2. Ensure the example demonstrates the self-contained runtime structure.
  3. Update example docs to explain what belongs inside a standalone workspace and what remains root-only.
- Validation: The example workspace layout matches the runtime manifest and can be reviewed without consulting the root source tree.
- Notes: Keep the example maintainable; do not manually fork a layout that the initializer can generate.

### Milestone 4: Simplify Toolkit Installation And Update Behavior

- Status: TO BE DONE
- Purpose: Make the installer manage the toolkit root only, now that workspaces are standalone runtime snapshots.
- Exit Criteria: Root installation/update docs and code no longer imply that updating the toolkit should mutate existing workspaces.

#### Task 4.1: Redefine Root Setup And Installer Responsibilities

- Status: TO BE DONE
- Objective: Narrow the installer/setup contract to the toolkit root.
- Steps:
  1. Update setup/install docs so they describe preparing the toolkit environment and creating future workspaces.
  2. Remove language that suggests root updates preserve or mutate active workspace state in place.
  3. Define the supported root workflow: install/setup toolkit, create workspace snapshot, then operate inside the workspace.
- Validation: User-facing installer/setup docs describe only toolkit-root responsibilities and standalone workspace creation.
- Notes: This is a product-contract change, not just wording cleanup.

#### Task 4.2: Simplify Root Update Logic To Ignore Existing Workspaces

- Status: TO BE DONE
- Objective: Stop treating existing workspaces as updater-managed content.
- Steps:
  1. Remove or simplify update logic that exists only to preserve in-place workspace state under the toolkit root.
  2. Ensure root updates never rewrite the contents of existing standalone workspaces.
  3. Keep only the root-level safety logic still required for updating the toolkit itself.
- Validation: Code inspection and tests show that root updates touch toolkit files only and leave existing workspaces unchanged.
- Notes: If preserving `workspaces/` as plain user data remains necessary at the root, keep that rule simple and explicit.

#### Task 4.3: Drop Or Downgrade No-Longer-Needed Mixed-State Mechanisms

- Status: TO BE DONE
- Objective: Remove maintenance burden created solely by the old mixed-state model.
- Steps:
  1. Review managed-entry metadata, rollback logic, and installer conflict handling against the new scope.
  2. Remove mechanisms that exist only because the updater was previously responsible for mixed toolkit + workspace state.
  3. Retain only the pieces still justified for safe toolkit-root replacement.
- Validation: The remaining installer complexity maps directly to toolkit-root concerns and no longer references standalone workspace internals.
- Notes: Do not leave dead compatibility code behind without an explicit reason.

#### Task 4.4: Define Legacy Workspace Behavior Explicitly

- Status: TO BE DONE
- Objective: Avoid ambiguity for users who already created workspaces under the old model.
- Steps:
  1. Document whether legacy workspaces remain supported only when used under the original root layout.
  2. Decide whether to add a placeholder `migrate_workspace` command later or leave migration out of scope for now.
  3. Record the legacy policy in docs and the decision log.
- Validation: A user can tell from the docs what happens to old workspaces and whether migration is available.
- Notes: This task is documentation/policy unless a migration command is explicitly approved.

### Milestone 5: Add Tests, Fixtures, And Validation Around The New Boundary

- Status: TO BE DONE
- Purpose: Lock in the standalone workspace contract with executable checks.
- Exit Criteria: Tests cover snapshot creation, copied-workspace execution, and the new toolkit-root-only update behavior.

#### Task 5.1: Add Unit And Integration Tests For Snapshot Initialization

- Status: TO BE DONE
- Objective: Prove that a new workspace contains the correct runtime payload and metadata.
- Steps:
  1. Add tests for `init_workspace.py` that verify the new runtime bundle contents.
  2. Verify required runtime files, skills, scripts, and metadata fields are present.
  3. Verify developer-only assets are absent from the standalone workspace.
- Validation: `python -m pytest -q` includes passing tests that assert the runtime bundle contents and exclusions.
- Notes: Prefer deterministic file-list assertions over broad smoke tests alone.

#### Task 5.2: Add Copied-Workspace Execution Tests

- Status: TO BE DONE
- Objective: Prove that a workspace still works after being moved outside the repository.
- Steps:
  1. Create an integration test that initializes a workspace, copies it to a directory outside the repository tree, and runs its bootstrap/runtime commands there.
  2. Exercise at least one primary research workflow command from the copied workspace.
  3. Verify the copied workspace does not import from or resolve paths back into the original repository.
- Validation: A dedicated copied-workspace test passes from a temp directory that is not inside the toolkit root.
- Notes: This is the core test for the user’s original product vision.

#### Task 5.3: Add Toolkit-Root Update Tests That Ignore Existing Workspaces

- Status: TO BE DONE
- Objective: Prove that root updates do not mutate existing standalone workspaces.
- Steps:
  1. Add installer/update tests where one or more existing workspaces are present under the root.
  2. Run the toolkit update flow.
  3. Verify toolkit files may change while existing workspace contents remain byte-identical.
- Validation: Installer/update integration tests assert unchanged workspace hashes before and after the root update.
- Notes: Keep these tests focused on the new boundary, not the old mixed-state model.

#### Task 5.4: Update Skill, Example, And Validation Tooling

- Status: TO BE DONE
- Objective: Keep repository validation aligned with the redesigned runtime boundary.
- Steps:
  1. Update any skill validators, examples, and golden/fixture assumptions affected by the new workspace shape.
  2. Add checks that the standalone workspace entry docs and bundled skills remain internally consistent.
  3. Ensure CI covers the new snapshot and copied-workspace tests.
- Validation: Validation tooling passes with the new workspace shape, and CI includes the standalone workspace boundary tests.
- Notes: Do not let examples or validators silently preserve the old contract.

### Milestone 6: Cleanup And Final Verification

- Status: TO BE DONE
- Purpose: Ensure the repository contains only intentional final artifacts and the complete change is verified.
- Exit Criteria: Intermediate artifacts are removed, all final verification passes, and the plan status is COMPLETED.

#### Task 6.1: Cleanup Intermediate Artifacts

- Status: TO BE DONE
- Objective: Remove artifacts created only to support implementation.
- Steps:
  1. Inspect the worktree for temporary documentation, one-off scripts, scratch tests, generated data, logs, and obsolete plan fragments.
  2. Remove only artifacts that are not part of the intended final repository state.
  3. Keep maintainable tests, fixtures, docs, and generated files that are part of the repository contract.
  4. Update the project changelog or release notes entry if the repository maintains one for user-visible architectural changes.
- Validation: Worktree diff contains only intended final changes.
- Notes: Do not remove user-provided files or unrelated worktree changes.

#### Task 6.2: Final Verification

- Status: TO BE DONE
- Objective: Validate the integrated change after cleanup.
- Steps:
  1. Run the final verification commands or inspections listed below.
  2. Fix failures and rerun until verification passes, or record the blocker.
  3. Confirm one final time that a generated workspace can be copied elsewhere and used without parent-repo-relative runtime dependencies.
- Validation: All commands and manual checks in the Final Verification section pass.
- Notes: Record any intentionally deferred migration work as an explicit limitation, not an implicit omission.

## Final Verification

Run from a clean checkout after implementation:

```text
python -m pytest -q
python tests/validate_skills.py
python scripts/init_workspace.py standalone-smoke --path <temp-dir>/calixto-smoke
copy the generated workspace to a second directory outside the repo tree
run the workspace-local bootstrap command there
run at least one primary research command from inside the copied workspace
```

Manual verification checklist:

- Root docs describe the toolkit as a factory and source repo, not the active research runtime.
- A new workspace contains the runtime assets defined by the manifest and excludes developer-only assets.
- The copied workspace does not resolve runtime paths back into the original repository.
- Updating the toolkit root does not mutate existing workspaces.
- Legacy-workspace behavior is documented explicitly.

## Approval Gate

Implementation must not start until the user approves this plan.

## Plan Self-Check

- [x] Plan location follows the default location rule.
- [x] Scope, non-goals, assumptions, and open questions are explicit.
- [x] Any unresolved open questions have been surfaced to the user.
- [x] Tasks are grouped into milestones because the plan has more than 10 tasks.
- [x] Every task has concrete steps and validation.
- [x] Every milestone has exit criteria.
- [x] Cleanup and final verification are included.
- [x] The plan avoids vague actions without concrete targets.
- [x] The plan can be executed by a coding agent without reading the original conversation.

## Execution Notes

- Update plan status to `APPROVED` after user approval and to `IN PROGRESS` before code changes start.
- Update milestone and task status before starting and after validation.
- Update each task to `COMPLETED` immediately after its validation passes.
- Mark tasks or milestones `BLOCKED` with a short reason when progress cannot continue.
- If implementation reveals a better runtime bundle boundary than expected, update this plan before continuing.
