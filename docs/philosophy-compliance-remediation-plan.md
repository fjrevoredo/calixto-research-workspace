# Philosophy Compliance Remediation Plan

## Metadata

- Plan Status: COMPLETED
- Created: 2026-06-20
- Last Updated: 2026-06-20
- Owner: Coding agent
- Approval: APPROVED

## Status Legend

- Plan Status values: DRAFT, QUESTIONS PENDING, READY FOR APPROVAL, APPROVED, IN PROGRESS, COMPLETED, BLOCKED
- Task Status values: TO BE DONE, IN PROGRESS, COMPLETED, BLOCKED, SKIPPED

## Goal

Bring the streamlined workspace creation flow back into compliance with [PHILOSOPHY.md](/D:/Repos/calixto-research-workspace/PHILOSOPHY.md) by removing silent destructive workspace mutations, restoring agent-consumable structured output where the philosophy requires it, and eliminating or constraining hidden machine-global launcher state so the implementation remains infrastructure rather than app-like orchestration magic.

## Scope

- Remediate the three philosophy deviations found in the post-commit self-check:
  - harness mirror regeneration silently deleting workspace file state
  - top-level `calixto` commands not consistently offering structured JSON output
  - the user-global `calixto` shim introducing hidden cross-checkout coupling
- Update code, tests, and docs so the shipped behavior and the documented philosophy match.
- Re-run automated and manual verification, including an explicit philosophy re-review against the finished implementation.

## Non-Goals

- Reversing the entire streamlined workspace flow or removing managed runtimes.
- Rewriting the standalone workspace contract or introducing a new workspace format.
- Expanding supported harnesses beyond the current documented set.
- Relaxing `PHILOSOPHY.md` to accommodate the current deviations unless the user explicitly asks for a philosophy change instead of a code fix.

## Assumptions

- The remediation target is the current `master` branch state at commit `f7a1615`.
- `PHILOSOPHY.md` remains the authoritative contract; code and user-facing docs must be brought into alignment with it.
- The preferred outcome is to preserve the streamlined UX where possible, but not at the cost of violating file ownership, structured output, or hidden-state constraints.
- The repository should keep both human-friendly CLI usage and agent-friendly machine-readable usage, but the latter must be explicit and complete wherever the philosophy requires structured output.

## Open Questions

- None.

## Current Status

- Commit `f7a1615` introduced the streamlined workspace flow and passed its implementation-focused self-check.
- A follow-up philosophy review found three concrete deviations:
  - `scripts/calixto.py` mirror regeneration deletes existing harness mirror directories before copying canonical skills.
  - the top-level `calixto` CLI defaults to human text for key flows and does not expose structured JSON for all runtime-management commands.
  - `scripts/install_calixto_shim.py` overwrites a single user-global launcher that points at one absolute checkout path.
- The worktree is clean at plan creation time.

## Tasks

### Task 1: Preserve Workspace File State During Harness Mirror Management

- Status: COMPLETED
- Objective: Harness mirror preparation no longer silently deletes or overwrites workspace-owned files without an explicit, documented user choice.
- Steps:
  1. Decide on a non-destructive mirror strategy for `.agents/skills/`, `.opencode/skills/`, and `.claude/skills/` that preserves agent or user edits by default.
  2. Update `scripts/calixto.py` mirror-generation logic so existing mirrors are either left intact, refreshed only when byte-identical-safe, or replaced only behind an explicit force-style option.
  3. Ensure the chosen behavior is reflected in any open/create flow that currently calls `_generate_harness_skill_mirrors()`.
  4. Update workspace-facing docs to explain which directory is canonical, when mirrors are created, and what happens if a mirror already contains edits.
- Validation:
  - Add or update unit tests proving that rerunning mirror preparation does not delete a custom marker from an existing harness mirror unless an explicit destructive mode is requested.
  - Run `python -m pytest tests/unit/test_calixto_cli.py tests/unit/test_harnesses.py -q`.
  - Perform one manual local repro equivalent to the current failing scenario and confirm the custom marker survives the default path.
- Notes:
  - Relevant files likely include [scripts/calixto.py](/D:/Repos/calixto-research-workspace/scripts/calixto.py), [runtime/workspace/AGENTS.md](/D:/Repos/calixto-research-workspace/runtime/workspace/AGENTS.md), and adapter docs.

### Task 2: Restore Structured Output As A First-Class Agent Contract

- Status: COMPLETED
- Objective: Every relevant top-level Calixto command has a complete structured JSON success/error mode consistent with the philosophy’s “no silent failures” requirement.
- Steps:
  1. Define a stable JSON contract for `calixto research`, `calixto open`, `calixto runtime list`, and `calixto runtime prune`, including success, partial, and error shapes where applicable.
  2. Add an explicit `--json` mode to commands that currently only emit human-readable text, or otherwise make the structured contract available without breaking interactive usage.
  3. Ensure all failure branches return structured error payloads in JSON mode and avoid mixing human chatter into stdout.
  4. Reconcile helper scripts and setup guidance so agents can discover the JSON path directly from docs.
- Validation:
  - Add or update unit tests covering JSON success and JSON error output for `research`, `open`, `runtime list`, and `runtime prune`.
  - Run `python -m pytest tests/unit/test_calixto_cli.py tests/unit/test_managed_runtime.py -q`.
  - Run a manual CLI smoke check for each command in JSON mode and inspect the payload structure.
- Notes:
  - Keep a human-readable interactive mode if useful, but do not leave agent automation dependent on parsing prose.

### Task 3: Remove Or Constrain Hidden Machine-Global Launcher State

- Status: COMPLETED
- Objective: Toolkit setup no longer silently repoints a single machine-global `calixto` launcher across unrelated checkouts without an explicit, understandable contract.
- Steps:
  1. Choose a remediation strategy that aligns with `PHILOSOPHY.md`: either eliminate the global shim, make shim installation explicitly opt-in, or redesign the installed command so multiple checkouts cannot silently steal it from each other.
  2. Preserve the philosophy’s documented primary entry point of `calixto research "your question" --agent none` if that can be done without hidden cross-checkout coupling; if it cannot, stop implementation and surface the product/philosophy conflict to the user before changing the primary invocation contract.
  3. Update `scripts/install_calixto_shim.py`, [setup.sh](/D:/Repos/calixto-research-workspace/setup.sh), and [setup.ps1](/D:/Repos/calixto-research-workspace/setup.ps1) to implement the chosen strategy.
  4. Ensure the resulting setup flow makes launcher state visible and understandable, including the fallback command when no stable global launcher is installed.
  5. Update installer/setup docs so they accurately describe checkout coexistence, launcher ownership, and any explicit opt-in or fallback behavior.
- Validation:
  - Add or update tests that simulate two distinct toolkit roots and verify the final behavior is explicit and non-silent.
  - Run targeted setup/install tests for both shell paths.
  - Perform one manual multi-checkout repro or an equivalent deterministic fixture-based check and confirm there is no hidden repointing behavior.
  - Verify the final setup UX still matches the primary invocation documented in [PHILOSOPHY.md](/D:/Repos/calixto-research-workspace/PHILOSOPHY.md), or explicitly stop and request user direction before any change that would invalidate that contract.
- Notes:
  - Relevant files likely include [scripts/install_calixto_shim.py](/D:/Repos/calixto-research-workspace/scripts/install_calixto_shim.py), [docs/installer.md](/D:/Repos/calixto-research-workspace/docs/installer.md), [README.md](/D:/Repos/calixto-research-workspace/README.md), and setup scripts.

### Task 4: Reconcile Documentation With The Remediated Contracts

- Status: COMPLETED
- Objective: Product docs, agent entry points, and workspace docs describe the remediated behavior without contradicting the philosophy or the code.
- Steps:
  1. Update [README.md](/D:/Repos/calixto-research-workspace/README.md), [AGENTS.md](/D:/Repos/calixto-research-workspace/AGENTS.md), [docs/installer.md](/D:/Repos/calixto-research-workspace/docs/installer.md), and relevant adapter docs to reflect the final launcher, mirror, and JSON contracts.
  2. Update workspace-facing docs under [runtime/workspace/AGENTS.md](/D:/Repos/calixto-research-workspace/runtime/workspace/AGENTS.md) if mirror behavior or reopen guidance changes.
  3. Add or update decision-log entries for any contract changes made during remediation.
  4. Update [CHANGELOG.md](/D:/Repos/calixto-research-workspace/CHANGELOG.md) with the remediation summary once behavior is finalized.
- Validation:
  - Manually inspect the updated docs for contradictions.
  - Use `rg` to confirm stale launcher or mirror claims are removed.
  - Re-run `python tests/validate_skills.py` if any skill-facing guidance changes.
- Notes:
  - Do not change `PHILOSOPHY.md` as part of this remediation unless the user explicitly redirects the effort toward a philosophy update.

### Task 5: Expand Regression Coverage Around Philosophy Contracts

- Status: COMPLETED
- Objective: The repository has durable tests that catch regressions in the three remediated philosophy areas.
- Steps:
  1. Add tests for non-destructive mirror preparation and any explicit overwrite mode.
  2. Add tests for JSON output coverage across top-level CLI flows.
  3. Add tests for launcher installation semantics across repeated setup or multiple toolkit roots.
  4. Add or refine assertions that workspace-local fallback and managed-runtime flows still work after the remediation.
- Validation:
  - Run targeted pytest modules covering the changed surfaces.
  - Ensure full-suite `python -m pytest -q` still passes after the fixes.
- Notes:
  - Prefer deterministic tests over shell-output snapshots when possible.

### Task 6: Re-Run Full Verification And Philosophy Review

- Status: COMPLETED
- Objective: Confirm the final remediated implementation passes both technical verification and an explicit philosophy compliance audit.
- Steps:
  1. Re-run the automated verification suite that exercises setup, CLI, managed-runtime, and installer behavior.
  2. Re-run the relevant real smoke checks for managed workspace creation, workspace reopening, and portable fallback.
  3. Review the final code and docs directly against [PHILOSOPHY.md](/D:/Repos/calixto-research-workspace/PHILOSOPHY.md), especially the sections on file-based state, modular/configurable tooling, easy in/easy out, and no silent failures.
  4. Record any remaining deviations explicitly; if none remain, mark the remediation complete.
- Validation:
  - `python -m compileall scripts providers`
  - `python tests/validate_skills.py`
  - `python -m pytest -q`
  - Manual philosophy review with findings ordered by severity, or an explicit “no findings” outcome.
- Notes:
  - Do not mark the remediation complete based only on unit tests; the final review must include observable runtime and documentation checks.

### Task 7: Cleanup Intermediate Artifacts

- Status: COMPLETED
- Objective: Remove artifacts created only to support remediation and keep the final diff focused on intentional shipped changes.
- Steps:
  1. Inspect the worktree for temporary documentation, one-off scripts, scratch tests, generated data, logs, and obsolete plan fragments.
  2. Remove only artifacts that are not part of the intended final repository state.
  3. Keep maintainable tests, fixtures, docs, and generated files that are part of the repository contract.
  4. Ensure the final changelog entry remains in place.
- Validation: Worktree diff contains only intended final changes.
- Notes: Do not remove user-provided files or unrelated worktree changes.

## Final Verification

- `python -m compileall scripts providers`
- `python tests/validate_skills.py`
- `python -m pytest tests/unit/test_calixto_cli.py tests/unit/test_harnesses.py tests/unit/test_managed_runtime.py tests/unit/test_setup.py tests/unit/test_install.py tests/unit/test_install_windows.py -q`
- `python -m pytest -q`
- Manual smoke checks for:
  - non-destructive mirror regeneration on an existing workspace
  - JSON output for `calixto research`, `calixto open`, `calixto runtime list`, and `calixto runtime prune`
  - launcher/setup behavior across repeated setup runs and, if still applicable, multiple toolkit roots
  - managed workspace create/open and copied-workspace local setup
- Final philosophy review against [PHILOSOPHY.md](/D:/Repos/calixto-research-workspace/PHILOSOPHY.md) with explicit confirmation that the three original deviations were resolved

## Plan Self-Check

- [x] Plan location follows the default location rule.
- [x] Scope, non-goals, assumptions, and open questions are explicit.
- [x] Any unresolved open questions have been surfaced to the user.
- [x] Every task has concrete steps and validation.
- [x] The launcher remediation does not silently assume the philosophy’s primary command can be changed without an explicit user decision.
- [x] Cleanup and final verification are included.
- [x] The plan avoids vague actions without concrete targets.
- [x] The plan can be executed by a coding agent without reading the original conversation.

## Approval Gate

Implementation must not start until the user approves this plan.

## Execution Notes

- Update task status to IN PROGRESS before starting each task.
- Update task status to COMPLETED immediately after its validation passes.
- Set `Plan Status` to `APPROVED` once the user approves execution.
- Set `Plan Status` to `IN PROGRESS` before the first remediation edit.
- Mark tasks BLOCKED with a short reason when progress cannot continue.
