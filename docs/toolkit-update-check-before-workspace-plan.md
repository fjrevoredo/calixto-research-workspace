# Toolkit Update Check Before Workspace Creation Plan

## Metadata

- Plan Status: COMPLETED
- Created: 2026-06-17
- Last Updated: 2026-06-17
- Owner: Coding agent
- Approval: APPROVED

## Status Legend

- Plan Status values: DRAFT, QUESTIONS PENDING, READY FOR APPROVAL, APPROVED, IN PROGRESS, COMPLETED, BLOCKED
- Task Status values: TO BE DONE, IN PROGRESS, COMPLETED, BLOCKED, SKIPPED

## Goal

Add a lightweight toolkit freshness check to workspace creation so a user creating a new standalone workspace can see when the local toolkit checkout is behind the repository default branch and choose whether to update the toolkit before the workspace snapshot is created.

## Scope

- Add local toolkit build metadata derived from Git history rather than a manually maintained release version.
- Stamp generated workspaces with the toolkit commit and build metadata used to create them.
- Check for newer toolkit commits only during `scripts/init_workspace.py` execution, before the runtime bundle is copied.
- Provide an interactive update-before-create prompt when a newer toolkit is available and the command is running in an interactive terminal.
- Provide explicit non-interactive flags so automation does not hang.
- Keep standalone workspace semantics intact: existing workspaces are not checked or rewritten by this feature.
- Reconcile default-branch documentation so the update check, installer docs, and one-line installer examples agree.
- Add deterministic unit coverage with mocked Git/remote behavior.

## Non-Goals

- Creating a strict semantic release process.
- Adding a workspace-side recurring update checker.
- Automatically mutating existing standalone workspaces after toolkit updates.
- Adding a migration command for legacy or older standalone workspaces.
- Replacing the existing installer transaction and managed-entry ownership model.
- Requiring network access for every workspace creation. Offline creation must remain possible.

## Current Status

- `scripts/init_workspace.py` is currently documented as pure file I/O with no network calls and creates a standalone runtime snapshot from `runtime/workspace-manifest.json`.
- New workspace `config.json` files already record `runtime_bundle_version` and `toolkit_version_created_with`, both currently derived from `pyproject.toml` version `0.1.0`.
- The installer can update a toolkit root while preserving standalone workspaces, but it does not expose build metadata to workspace creation.
- The repository has a default-branch inconsistency: `docs/installer.md` says the default branch is `main`, while `AGENTS.md` and `README.md` one-line installer examples point at `master`.

## Assumptions

- The canonical source for freshness is the repository default branch, not a manually incremented file committed on every change.
- A monotonic build number can be derived as the commit count of the selected default branch using Git history, with the commit SHA kept as the authoritative identity.
- The update check may use `git` when available. If `git` is unavailable, the feature should degrade gracefully and allow workspace creation.
- The existing installer remains the supported way to update a toolkit root. `init_workspace.py` may invoke it only through a narrow, explicit path, or it may print the exact command if automatic self-update proves unsafe during implementation.
- Interactive behavior is acceptable only when stdin/stdout are TTYs. Non-interactive invocations must use deterministic defaults.
- The existing workspace boundary remains authoritative: updating the toolkit affects future workspaces only.

## Open Questions

- None

## Tasks

### Task 1: Define Toolkit Build Metadata Helpers

- Status: COMPLETED
- Objective: The toolkit can report its local commit identity and monotonically increasing build number without introducing a committed build-counter file.
- Steps:
  1. Add helper functions in `scripts/runtime_bundle.py` or a small adjacent helper module for `toolkit_commit`, `toolkit_build_number`, and `toolkit_ref_name`.
  2. Derive `toolkit_commit` from `git rev-parse HEAD`.
  3. Derive `toolkit_build_number` from `git rev-list --count HEAD`.
  4. Return `None` or an explicit unavailable state when Git metadata is missing, the checkout is not a Git repository, or `git` is unavailable.
  5. Avoid failing workspace creation only because build metadata cannot be derived.
- Validation: Add unit tests that monkeypatch subprocess calls and cover successful metadata, missing Git, non-Git checkout, and command failure cases.
- Notes: Keep the project version fields for compatibility. The new build number is freshness metadata, not a semantic version.

### Task 2: Stamp Workspace Config With Build Metadata

- Status: COMPLETED
- Objective: Every newly generated standalone workspace records the exact local toolkit build that created it.
- Steps:
  1. Extend `standalone_workspace_metadata()` to include `toolkit_commit_created_with`, `toolkit_build_number_created_with`, and, if useful, `toolkit_ref_created_with`.
  2. Preserve existing fields: `workspace_schema_version`, `workspace_layout`, `runtime_manifest_version`, `runtime_bundle_version`, and `toolkit_version_created_with`.
  3. Update `scripts/init_workspace.py` success output to include the new metadata when available.
  4. Ensure unavailable Git metadata is represented consistently in `config.json` without breaking JSON consumers.
- Validation: Extend `TestInitWorkspace.test_config_has_required_keys` and related assertions in `tests/unit/test_scripts.py` to verify the new fields and preserve existing metadata.
- Notes: Do not change the workspace schema version unless implementation determines these metadata fields require a formal schema bump; if bumped, update `runtime/workspace-manifest.json` and tests together.

### Task 3: Implement Default-Branch Freshness Check

- Status: COMPLETED
- Objective: Workspace creation can determine whether the local toolkit is behind the repository default branch before copying the runtime snapshot.
- Steps:
  1. Add a small update-check helper that discovers the configured repository URL and default branch consistently with the installer contract.
  2. Prefer `git ls-remote <repo> HEAD` or equivalent remote metadata to find the latest default-branch commit without fetching the full repository.
  3. Compare the remote default-branch commit to the local commit.
  4. When the local commit is an ancestor of the remote commit, report the number of commits behind when that can be computed locally or after a lightweight fetch.
  5. Classify ambiguous cases, such as detached HEAD, local unpushed commits, unrelated history, missing network, missing Git, or private repository access failure, without blocking workspace creation by default.
- Validation: Unit tests cover up-to-date, behind, local-ahead/diverged, remote unavailable, missing Git, and non-Git checkout cases using mocked subprocess results.
- Notes: Network failures should produce a warning or structured skipped status, not an `init_workspace` failure unless the user explicitly requested a required update check.

### Task 4: Add `init_workspace.py` CLI Flags And Prompt Flow

- Status: COMPLETED
- Objective: Users can choose to update before workspace creation when a newer toolkit is available, while automation remains deterministic.
- Steps:
  1. Add CLI flags for update-check behavior, such as `--check-updates`, `--skip-update-check`, `--require-update-check`, and `--update-before-create`.
  2. Define defaults: interactive terminals perform a check and prompt when a newer toolkit is available; non-interactive runs skip the check unless explicitly requested.
  3. Run the freshness check before validating or copying the target workspace, so the user can update without leaving a partially created workspace.
  4. Print a concise prompt that includes current commit/build, latest commit/build when available, and the consequence of continuing.
  5. If the user declines or the check is skipped, create the workspace normally and stamp the local toolkit metadata.
  6. If `--require-update-check` is set and the check cannot be completed, exit with a structured error before creating the workspace.
- Validation: CLI tests in `tests/unit/test_scripts.py` verify interactive prompt decisions through stdin mocks or subprocess input, non-interactive default behavior, explicit skip, required-check failure, and normal workspace creation after declining an update.
- Notes: Keep JSON stdout clean for successful creation. Warnings and prompts should go to stderr or the console stream used elsewhere for user-facing prompts.

### Task 5: Wire Update-On-Demand To The Existing Installer Contract

- Status: COMPLETED
- Objective: When a user chooses to update first, `init_workspace.py` either invokes the supported toolkit update path safely or prints an exact command and exits before workspace creation.
- Steps:
  1. Evaluate whether self-updating from inside the running Python process is safe on Windows and Unix, especially when files under `scripts/` may be replaced.
  2. If direct invocation is safe, call the repository installer with the same branch/repository selection contract and wait for completion before creating the workspace.
  3. If direct invocation is unsafe, print the exact platform-appropriate installer command and exit with a structured status that tells the user no workspace was created.
  4. Ensure update mode still preserves `workspaces/`, `.git/`, user data, and managed-entry ownership semantics.
  5. Ensure `--update-before-create` never creates a workspace from the stale toolkit if the update fails.
- Validation: Unit tests cover accepted update, declined update, update command failure, and no-workspace-created-on-failed-update cases. Installer integration tests should be reused or extended only if direct installer invocation is implemented.
- Notes: Prefer the conservative command-print-and-exit behavior if in-process self-update introduces platform-specific risk.

### Task 6: Reconcile Default Branch And Documentation

- Status: COMPLETED
- Objective: The repository has one documented default-branch story for installers and update checks.
- Steps:
  1. Decide from repository truth whether the canonical default branch is `master`, `main`, or remote `HEAD`.
  2. Update `AGENTS.md`, `README.md`, `docs/installer.md`, and installer help text where needed so examples and behavior agree.
  3. Document the new workspace-creation update check in user-facing setup/create-workspace docs.
  4. Document the new metadata fields and their meaning in `requirements.md` or the most appropriate maintainer/runtime metadata section.
  5. Add or update a decision-log entry explaining why build numbers are derived from Git history instead of stored in a manually incremented file.
- Validation: `rg -n "master|main|default branch|raw.githubusercontent.com" AGENTS.md README.md docs install.sh install.ps1 tests` shows intentional, consistent references only; manual inspection confirms docs distinguish project version, runtime bundle version, build number, and commit SHA.
- Notes: If a durable architectural rationale is needed beyond a tactical decision log entry, create an ADR instead of only updating the decision log.

### Task 7: Add End-To-End And Regression Coverage

- Status: COMPLETED
- Objective: The complete workspace-creation flow is covered without relying on live network access.
- Steps:
  1. Extend unit tests for `runtime_bundle.py` metadata helpers.
  2. Extend `tests/unit/test_scripts.py` for the new `init_workspace.py` flags and prompt paths.
  3. Add fixture-backed fake Git command behavior or dependency-injected subprocess helpers so tests do not call the network.
  4. Add a copied-workspace or generated-workspace assertion proving existing standalone workspaces do not contain `scripts/init_workspace.py` and do not gain workspace-side update-check behavior.
  5. Update skill validation or generated-workspace smoke tests only if runtime-facing instructions changed.
- Validation: `python -m pytest tests/unit/test_scripts.py -q -k "init or update or metadata"` and any new targeted unit test file pass without network access.
- Notes: Live GitHub availability should not be required for CI.

### Task 8: Cleanup Intermediate Artifacts And Changelog

- Status: COMPLETED
- Objective: Keep the final repository state focused and document the user-visible behavior change.
- Steps:
  1. Inspect the worktree for temporary workspaces, scratch scripts, captured command output, debug logs, and obsolete test fixtures.
  2. Remove only artifacts that are not part of the intended final repository state.
  3. Add a `CHANGELOG.md` entry describing the update-before-workspace-create check and new toolkit build metadata.
  4. Verify no unrelated user changes were reverted or reformatted.
- Validation: `git status --short` shows only intended final changes, and `CHANGELOG.md` contains a concise entry for the feature.
- Notes: Preserve this plan and any decision log or ADR created as maintainable documentation.

## Final Verification

- `python -m pytest tests/unit/test_scripts.py -q -k "init or update or metadata"`
- `python -m pytest tests/unit/test_install.py tests/unit/test_install_windows.py -q -k "update or branch or version"` when the host has the required platform prerequisites, or document skipped platform-specific coverage.
- `python tests/validate_skills.py`
- Manual smoke test: create a temporary workspace with update checks skipped, inspect `config.json` for build metadata, and run `scripts/workspace_info.py audit <workspace>`.
- Manual docs check: verify `AGENTS.md`, `README.md`, and `docs/installer.md` agree on the default branch and update contract.

## Plan Self-Check

- [x] Plan location follows the default location rule.
- [x] Plan status is `READY FOR APPROVAL`.
- [x] Scope, non-goals, assumptions, and open questions are explicit.
- [x] Zero unanswered open questions remain.
- [x] Every task has concrete steps and validation.
- [x] More than 10 tasks are not present, so milestones are omitted.
- [x] Cleanup and final verification are included.
- [x] The plan avoids vague actions without concrete targets.
- [x] The plan can be executed by a coding agent without reading the original conversation.

## Approval Gate

Implementation must not start until the user approves this plan.

## Execution Notes

- Update this plan to `APPROVED` after user approval and `IN PROGRESS` before implementation starts.
- Update task status to `IN PROGRESS` before starting each task.
- Update task status to `COMPLETED` immediately after its validation passes.
- Mark tasks `BLOCKED` with a short reason when progress cannot continue.
- Record meaningful implementation decisions in the decision log as they are made, not after the fact.
