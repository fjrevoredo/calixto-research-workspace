# Research Session UX Follow-Up Plan

## Metadata

- Plan Status: COMPLETED
- Created: 2026-06-11
- Last Updated: 2026-06-11
- Owner: Coding agent
- Approval: PENDING

## Status Legend

- Plan Status values: DRAFT, QUESTIONS PENDING, READY FOR APPROVAL, APPROVED, IN PROGRESS, COMPLETED, BLOCKED
- Task/Milestone Status values: TO BE DONE, IN PROGRESS, COMPLETED, BLOCKED, SKIPPED

## Goal

Reduce the remaining agent-facing friction observed in the latest standalone workspace run after the reliability fixes landed. The target outcome is a workflow that still preserves the current file-based, agent-orchestrated architecture while making common research-session mistakes cheaper to detect, easier to correct, and easier to interpret from workspace state alone.

## Scope

- Add a safe counter-synchronization command to the workspace runtime.
- Improve audit and show output so source-limit overruns and orphaned-source intent are easier to interpret.
- Add structured source-review state so the workspace can distinguish pending review from intentional discard.
- Filter clearly invalid web-search URLs before they reach the scraper.
- Update workspace docs and research skills to surface the current best-practice workflow more explicitly.
- Add regression coverage for the new UX and workflow behaviors.

## Non-Goals

- Changing the global Codex or harness skill-loader behavior outside this repository.
- Replacing the current `src_NNN` / `fnd_NNN` / `ins_NNN` identifier model.
- Turning `workspace_info.py audit` into a mutating command.
- Hard-blocking searches once `scope.max_sources` is exceeded.
- Adding subjective finding-count or insight-count heuristics to audit.

## Current Status

- The reliability fixes from `docs/research-session-reliability-fix-plan.md` appear to have solved the underlying state-loss and provenance-integrity issues.
- The latest reflection identified remaining friction in counter maintenance, skill discovery expectations, orphaned-source interpretation, low-signal triage, scope signaling, and invalid DuckDuckGo result URLs.
- Some reflection items are already partially addressed by the current runtime bundle, especially concrete `fnd_001` / `ins_001` examples and the explanation for sequential search discipline. This plan focuses on the gaps that remain in the shipped workflow.

## Assumptions

- The current runtime architecture remains agent-first: scripts expose state and guardrails, but the agent still decides what to search, what to read, and what to write.
- `scope.max_sources` should remain a soft planning limit, not a hard enforcement boundary, unless a later design pass proves that partial-search behavior is acceptable.
- Source-review intent belongs in structured workspace state rather than only in freeform notes, because audit and future agents need machine-readable status.
- The correct place to address workspace-local skill discovery confusion is workspace docs, not the external system skill loader.

## Open Questions

- None

## Milestones

### Milestone 1: Counter Sync And Early Validation

- Status: COMPLETED
- Purpose: Remove the highest-friction manual maintenance step without weakening the current audit contract.
- Exit Criteria: The workspace runtime offers a deterministic counter-sync command, audit stays read-only, and regression tests cover the expected sync behavior.

#### Task 1.1: Add `sync-counters` To `workspace_info.py`

- Status: COMPLETED
- Objective: Provide a dedicated command that scans `notes/findings.md` and `notes/summary.md`, computes the correct next IDs, and writes them back to `config.json`.
- Steps:
  1. Extend the `workspace_info.py` CLI with a `sync-counters` subcommand that resolves a workspace using the same path rules as `show` and `audit`.
  2. Reuse the existing highest-ID parsing logic to compute the expected `next_finding_id` and `next_insight_id`.
  3. Persist the updated counters through `WorkspaceStateCoordinator` so config mutations remain serialized and transactional.
  4. Return structured JSON describing old values, new values, and whether changes were applied.
- Validation: `python -m pytest tests/unit/test_scripts.py -q -k "sync_counters"`
- Notes: Keep source ID counters out of scope for this command; source IDs are owned by search-time persistence.

#### Task 1.2: Expose Sync Guidance In Audit Output

- Status: COMPLETED
- Objective: Make audit output point directly at the non-mutating fix path when counter drift is detected.
- Steps:
  1. Extend the audit payload to include a machine-readable remediation hint when `next_finding_id` or `next_insight_id` is invalid.
  2. Keep `audit` read-only and CI-safe; do not add `--fix`.
  3. Update the summary text so counter drift failures mention the availability of `sync-counters` without hiding the error status.
- Validation: `python -m pytest tests/unit/test_scripts.py -q -k "audit and counter"`
- Notes: This preserves a clean split between detection and mutation.

#### Task 1.3: Add Mid-Workflow Validation Coverage

- Status: COMPLETED
- Objective: Lock in the intended workflow by testing the new command and the current ID-format expectations together.
- Steps:
  1. Add script tests for `sync-counters` on empty notes, populated notes, and already-correct counters.
  2. Add a regression case showing that malformed findings still fail audit until the content is corrected, even if counters are synchronized.
  3. Ensure JSON outputs remain stable enough for agents to consume mechanically.
- Validation: `python -m pytest tests/unit/test_scripts.py -q -k "sync_counters or citation or counter"`
- Notes: Reuse existing temp-workspace fixtures where possible.

### Milestone 2: Structured Source Review And Orphan Interpretation

- Status: COMPLETED
- Purpose: Let the workspace distinguish pending review from intentional discard so orphan warnings become actionable instead of ambiguous.
- Exit Criteria: New sources carry explicit review state, agents can update that state with a supported command, and audit classifies orphaned sources using both review state and existing low-signal metadata.

#### Task 2.1: Extend Source Index Entries With Review State

- Status: COMPLETED
- Objective: Add a minimal structured review schema to `sources/index.json`.
- Steps:
  1. Define optional index-entry fields such as `review_status`, `review_note`, and `reviewed_at`.
  2. Accept only a small explicit state set: `pending`, `discarded`, and `used`.
  3. Update shared validation in `scripts/_common.py` so the new fields are accepted and validated consistently.
  4. Ensure existing workspaces without these fields remain readable and valid.
- Validation: `python -m pytest tests/unit/test_common.py -q -k "index or coordinator or validation"`
- Notes: `used` should remain optional because citations can still be derived from notes and reports.

#### Task 2.2: Seed New Search Results As `pending`

- Status: COMPLETED
- Objective: Ensure every newly added source starts with explicit review intent rather than implicit ambiguity.
- Steps:
  1. Update `search_web.py` and `search_arxiv.py` so new index entries include `review_status: "pending"`.
  2. Preserve existing metadata such as `snippet_only`, `error`, `low_signal`, and `content_quality`.
  3. Avoid changing dedup or update semantics for already-indexed sources unless the new metadata is absent.
- Validation: `python -m pytest tests/unit/test_scripts.py -q -k "search_web or search_arxiv"`
- Notes: Do not auto-set `used`; that should come from citations or an explicit review action.

#### Task 2.3: Add A Source-Review Mutation Command

- Status: COMPLETED
- Objective: Provide a supported runtime command to mark sources as discarded or reviewed without hand-editing `sources/index.json`.
- Steps:
  1. Add a `workspace_info.py review-source` subcommand that accepts a workspace, source ID, status, and optional note.
  2. Apply the mutation through `WorkspaceStateCoordinator` so it is serialized and transactional.
  3. Return structured JSON describing the updated entry.
  4. Reject unknown source IDs and invalid statuses with structured errors.
- Validation: `python -m pytest tests/unit/test_scripts.py -q -k "review_source"`
- Notes: Keep the command narrow; it should update source-review metadata only.

#### Task 2.4: Reclassify Orphaned Sources In Audit

- Status: COMPLETED
- Objective: Make orphan output explain whether a source is pending, intentionally discarded, or likely low-value based on existing metadata.
- Steps:
  1. Extend `cmd_audit` to partition uncited indexed sources into at least `pending`, `discarded`, and `low_signal_or_error` buckets.
  2. Preserve the existing hard/soft failure boundary: malformed references and index mismatches stay errors, uncited sources remain warnings.
  3. Update the audit summary text and JSON payload so agents can tell whether a warning reflects oversight or deliberate triage.
- Validation: `python -m pytest tests/unit/test_scripts.py -q -k "orphaned or audit"`
- Notes: Derived low-signal grouping should use persisted metadata such as `low_signal`, `content_quality`, `snippet_only`, and `error`.

### Milestone 3: Search Quality And Scope Signaling

- Status: COMPLETED
- Purpose: Reduce wasted source slots and make scope overruns visible without creating brittle hard limits.
- Exit Criteria: Invalid redirect-like URLs are filtered before scraping, and `show`/`audit` expose `max_sources` overruns as explicit warnings.

#### Task 3.1: Filter Invalid DuckDuckGo Result URLs Before Scrape

- Status: COMPLETED
- Objective: Stop clearly unusable DuckDuckGo / Startpage redirect URLs from becoming persisted snippet-only sources.
- Steps:
  1. Add URL validation in `providers/search/duckduckgo.py` so only `http://` and `https://` results survive provider normalization.
  2. Detect and drop known internal redirect shapes such as bare `/clev?...` Startpage-style targets.
  3. Record filtered-result counts or details in provider metadata or search results only if that can be done without destabilizing the interface.
  4. Add targeted tests using representative cached result payloads or direct fixtures.
- Validation: `python -m pytest tests/unit/test_providers.py -q -k "duckduckgo or search"`
- Notes: Keep the filtering provider-local so the rest of the pipeline receives only scrapeable URLs.

#### Task 3.2: Surface `max_sources` As A Soft Warning

- Status: COMPLETED
- Objective: Make scope overruns visible in runtime inspection without blocking the search pipeline.
- Steps:
  1. Extend `workspace_info.py show` to compare indexed source count against `config.json.scope.max_sources`.
  2. Extend `workspace_info.py audit` to report when the collected source count exceeds the configured soft limit.
  3. Add concise summary text so an agent can see immediately whether the workspace is within or beyond scope.
- Validation: `python -m pytest tests/unit/test_scripts.py -q -k "max_sources or show or audit"`
- Notes: Do not hard-fail audit for this condition; it is workflow guidance, not data corruption.

#### Task 3.3: Preserve Existing Search Retry Behavior

- Status: COMPLETED
- Objective: Ensure the new filtering and scope signaling does not regress `--retry-failed`, duplicate handling, or partial-result persistence.
- Steps:
  1. Add or update regression tests that combine filtered URLs, scrape failures, and retryable failures in one search record.
  2. Verify that filtered invalid URLs do not appear as persisted failed sources.
  3. Verify that genuine scrape failures still produce retryable failure metadata and `snippet_only` content when appropriate.
- Validation: `python -m pytest tests/unit/test_scripts.py -q -k "retry_failed or duplicate or partial"`
- Notes: This milestone must not re-open the reliability work completed in the previous pass.

### Milestone 4: Runtime Guidance And Research Workflow Docs

- Status: COMPLETED
- Purpose: Align the bundled runtime instructions with the actual supported workflow and with the new source-review and counter-sync capabilities.
- Exit Criteria: Workspace docs explain direct skill loading, counter sync, source triage, gaps/bibliography expectations, and the intended audit cadence; skill validation still passes.

#### Task 4.1: Clarify Workspace-Local Skill Loading

- Status: COMPLETED
- Objective: Prevent agents from assuming the generic skill loader can discover workspace-local skills.
- Steps:
  1. Update `runtime/workspace/AGENTS.md` to state explicitly that agents should read `skills/<name>/SKILL.md` directly inside the workspace.
  2. Note that workspace-local skills are bundled runtime files, not globally installed harness skills.
  3. Keep the wording agent-agnostic and compatible with the current standalone-workspace contract.
- Validation: `python tests/validate_skills.py`
- Notes: This is a runtime-doc fix, not a system-tool integration change.

#### Task 4.2: Update Deep-Research Workflow Steps

- Status: COMPLETED
- Objective: Reduce late-stage fix cycles by tightening the documented research loop.
- Steps:
  1. Update `runtime/workspace/skills/deep-research/SKILL.md` to require an audit after findings and after insights, not only at the end.
  2. Add the new `sync-counters` command to the documented remediation path after findings and insights.
  3. Add an explicit Step 3a triage pass that tells agents to inspect `sources/index.json` metadata and deprioritize `low_signal`, `snippet_only`, or errored sources first.
  4. Add a concrete expectation to record open questions in `notes/gaps.md` and to populate `outputs/bibliography.md` before handoff.
- Validation: `python tests/validate_skills.py`
- Notes: Keep the workflow concise; the goal is lower friction, not procedural bloat.

#### Task 4.3: Mirror Relevant Guidance In Literature Review

- Status: COMPLETED
- Objective: Keep the paper-heavy skill aligned where the same runtime pitfalls apply.
- Steps:
  1. Update `runtime/workspace/skills/literature-review/SKILL.md` for direct skill loading expectations, counter sync guidance, and audit cadence where applicable.
  2. Reuse the same citation and counter-maintenance language as the deep-research skill where possible.
  3. Avoid forcing source-triage language that only makes sense for web-heavy workflows unless it fits the paper workflow too.
- Validation: `python tests/validate_skills.py`
- Notes: Keep both skills consistent on bare `src_NNN` citations and counter maintenance.

#### Task 4.4: Add A User-Facing Changelog Entry

- Status: COMPLETED
- Objective: Record the workflow and UX improvements in the maintained changelog.
- Steps:
  1. Update `CHANGELOG.md` with a concise entry covering counter sync, source review state, scope warnings, DuckDuckGo filtering, and runtime-doc improvements.
  2. Keep the changelog focused on user-visible behavior rather than internal refactors.
- Validation: Manual inspection of `CHANGELOG.md`
- Notes: Required by the cleanup-phase contract for a user-facing behavior change.

### Milestone 5: Cleanup And Final Verification

- Status: COMPLETED
- Purpose: Ensure the repository contains only intentional final artifacts and the complete change is verified.
- Exit Criteria: Intermediate artifacts are removed, all final verification passes, and the plan status is COMPLETED.

#### Task 5.1: Cleanup Intermediate Artifacts

- Status: COMPLETED
- Objective: Remove artifacts created only to support implementation.
- Steps:
  1. Inspect the worktree for temporary documentation, one-off scripts, scratch tests, generated data, logs, and obsolete plan fragments.
  2. Remove only artifacts that are not part of the intended final repository state.
  3. Keep maintainable tests, fixtures, docs, and generated files that are part of the repository contract.
- Validation: Worktree diff contains only intended final changes.
- Notes: Do not remove user-provided files or unrelated worktree changes.

#### Task 5.2: Final Verification

- Status: COMPLETED
- Objective: Validate the integrated change after cleanup.
- Steps:
  1. Run the final verification commands listed below.
  2. Fix failures and rerun until verification passes, or record the blocker.
  3. Verify one representative workspace scenario manually if the automated coverage leaves a UX ambiguity.
- Validation: `python -m pytest tests/unit/test_common.py -q && python -m pytest tests/unit/test_scripts.py -q && python -m pytest tests/unit/test_providers.py -q && python tests/validate_skills.py`
- Notes: If command runtime becomes excessive, record the equivalent targeted subsets executed during implementation and rerun the full set before completion.

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

- Keep `workspace_info.py audit` read-only; add mutation through dedicated commands only.
- Preserve backward compatibility for older workspaces that lack new source-review fields.
- Prefer using existing persisted metadata before adding new heuristic layers.
- If implementation reveals that structured source-review state is too invasive for one pass, downgrade Milestone 2 only with an explicit decision note and a narrower replacement plan.
