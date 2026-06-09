# Research Session Reliability Fix Plan

## Metadata

- Plan Status: COMPLETED
- Created: 2026-06-10
- Last Updated: 2026-06-10
- Owner: Coding agent
- Approval: APPROVED

## Status Legend

- Plan Status values: DRAFT, QUESTIONS PENDING, READY FOR APPROVAL, APPROVED, IN PROGRESS, COMPLETED, BLOCKED
- Task/Milestone Status values: TO BE DONE, IN PROGRESS, COMPLETED, BLOCKED, SKIPPED

## Goal

Fix the reliability, traceability, and workflow failures exposed by the first real research session so that a standalone workspace can safely survive concurrent search invocations, accurately audit what is on disk versus what is indexed, preserve correct source-to-claim provenance across web and paper sources, and guide agents toward the intended research workflow without silent data loss.

## Scope

- Search-state concurrency and crash-consistency for `config.json`, `sources/index.json`, and source markdown files.
- Audit correctness for indexed sources, on-disk source files, path-qualified citations, and metadata counter drift.
- Research workflow guidance in the standalone workspace skill and docs.
- Search output UX improvements for dedup details and failed-result retries.
- Scrape-content quality improvements for noisy pages returned by the Crawl4AI pipeline.
- Regression coverage for the exact failures observed in `C:\Users\Francisco\Downloads\Junk\calixto2\workspaces\my-research`.

## Non-Goals

- Redesign the overall standalone-workspace architecture.
- Introduce a new search provider or replace Crawl4AI entirely.
- Retroactively auto-repair every previously corrupted workspace as part of the first fix pass.
- Redesign the canonical `src_NNN` / `fnd_NNN` / `ins_NNN` traceability model.
- Change the research report format beyond the minimum needed to enforce correct citations.
- Add source freshness ranking or publish-age scoring in this fix pass.

## Current Status

- Real workspace evidence confirms a state-integrity failure:
  - `config.json` records only 2 searches while the session issued 10 searches.
  - `sources/index.json` contains 20 indexed sources while `sources/` contains 30 source files on disk.
  - `sources/papers/src_001.md` through `src_010.md` exist on disk but are absent from `sources/index.json`.
- The search scripts are currently read-modify-write without shared coordination:
  - `search_web.py` loads `config.json` and `index.json` before mutation and writes files, `config.json`, and `index.json` separately.
  - `search_arxiv.py` follows the same pattern and writes paper files before its registry writes complete.
  - `_common.py` provides atomic single-file writes, but not a multi-file transaction or workspace-level lock.
- The audit has a false-positive traceability path:
  - `workspace_info.py audit` validates source references with a bare `src_NNN` regex and does not reconcile cited IDs to actual indexed file paths.
  - In the real workspace, `papers/src_001` is accepted because the regex extracts `src_001`, which is also the ID of an unrelated indexed web source.
- The standalone research skill encourages multiple searches but does not warn about concurrent execution, does not require post-search verification, and does not tell the agent to keep `next_finding_id` and `next_insight_id` aligned with the notes.
- The scrape provider currently accepts Crawl4AI markdown output directly with no readability or boilerplate-reduction step, which explains the poor signal-to-noise ratio on YouTube, Colab, and UI-heavy pages.

## Assumptions

- The canonical citation format remains bare `src_NNN` across all source types; path-qualified citations like `papers/src_001` are treated as malformed and must be surfaced by tooling.
- The logical source namespace remains shared across web and paper sources; the first fix pass will address correctness through serialized state coordination and audit hardening rather than introducing `web_src_NNN` / `paper_src_NNN`.
- The toolkit should become safe under concurrent search invocation in the same workspace; documentation warnings are necessary but are not the primary fix.
- Existing corrupted workspaces need detection and clear diagnostics in the first pass; automated repair can remain a follow-up if not required to land the core safety changes.
- A changelog entry will be added in `CHANGELOG.md`; create the file if it does not already exist.

## Open Questions

- None.

## Milestones

### Milestone 1: Codify The Real Failures

- Status: TO BE DONE
- Purpose: Turn the observed research-session failures into deterministic regression coverage before changing behavior.
- Exit Criteria: The repository contains targeted regression tests for concurrent search loss, orphaned paper files, malformed paper citations, and counter drift; the tests are collected successfully and their pre-fix failure mode is documented so later milestones can turn them green.

#### Task 1.1: Capture The Real Workspace Failure Shape In Test Fixtures

- Status: TO BE DONE
- Objective: Create deterministic fixture data that matches the observed `my-research` corruption pattern closely enough to drive regression tests.
- Steps:
  1. Add fixture builders or fixture files representing:
     - 20 indexed web sources with `next_id = 21`
     - 10 extra paper markdown files on disk not present in `sources/index.json`
     - malformed citations using `papers/src_001`
     - `next_finding_id = 1` and `next_insight_id = 1` despite populated notes
  2. Keep the fixture small enough for unit tests while preserving the failure semantics.
- Validation: `python -m pytest tests/unit/test_scripts.py --collect-only -q` includes the new audit/workspace regression tests and fixture-backed cases.
- Notes: Prefer reusing `tests/unit` helpers over copying the entire real workspace into the repo.

#### Task 1.2: Add Concurrent Search Regression Tests

- Status: TO BE DONE
- Objective: Add subprocess-level tests that reproduce lost updates when multiple search processes target the same workspace.
- Steps:
  1. Add a deterministic concurrent test for multiple `search_web.py` invocations against one temporary workspace.
  2. Add a deterministic mixed concurrent test for `search_web.py` plus `search_arxiv.py`.
  3. Make the tests assert both metadata integrity and on-disk file integrity, not just process exit codes.
- Validation: `python -m pytest tests/unit/test_scripts.py -q -k "concurrent or search"` collects and runs the new cases; before Milestone 2 is complete, at least one targeted case is expected to fail for the known lost-update reason, and that failure mode is recorded in the implementation notes.
- Notes: Use fixture providers, cache replay, or monkeypatched provider implementations so the test does not depend on live network responses.

#### Task 1.3: Add Audit False-Positive Regression Tests

- Status: TO BE DONE
- Objective: Prove that the audit must reject malformed paper citations and detect filesystem-index mismatches.
- Steps:
  1. Add a regression case where `findings.md` or `report.md` cites `papers/src_001` while the index only contains a web `src_001`.
  2. Add a regression case where extra `sources/papers/*.md` files exist but are missing from `sources/index.json`.
  3. Add a regression case where `next_finding_id` / `next_insight_id` drift from the note contents.
- Validation: `python -m pytest tests/unit/test_scripts.py -q -k "audit"` collects and runs the new cases; before Milestone 3 is complete, the malformed-citation and mismatch cases are expected to fail for the known false-positive audit behavior, and that failure mode is recorded in the implementation notes.
- Notes: The expected behavior after the fix is explicit detection, not silent normalization.

### Milestone 2: Make Workspace Search State Safe Under Concurrency

- Status: TO BE DONE
- Purpose: Eliminate silent data loss and cross-file inconsistency when multiple search commands mutate a workspace.
- Exit Criteria: Concurrent web and paper searches preserve every search record, every indexed source, and every saved source file, with no orphaned files, no lost metadata, and no invalid config/index state committed to disk.

#### Task 2.1: Introduce A Workspace State Coordinator

- Status: TO BE DONE
- Objective: Centralize workspace mutation behind a shared lock and mutation API instead of direct read-modify-write logic in the search scripts.
- Steps:
  1. Add a new helper module or extend `_common.py` with a workspace-level state coordinator for `config.json` and `sources/index.json`.
  2. Implement lock acquisition and release under `workspace/.calixto/` with stale-lock handling.
  3. Ensure mutations reload current state after the lock is acquired, not before.
- Validation: `python -m pytest tests/unit/test_common.py -q` passes with new lock/state-coordinator coverage.
- Notes: Single-file atomic writes in `_common.py` are not sufficient; the coordinator must serialize the full mutation window.

#### Task 2.2: Make Web Search Use Coordinated, Transactional Writes

- Status: TO BE DONE
- Objective: Refactor `search_web.py` so saved markdown files, `sources/index.json`, and `config.json` are committed as one coordinated unit.
- Steps:
  1. Keep search-provider and scrape-provider network work outside the critical section where feasible.
  2. Re-load and re-deduplicate against the latest locked state before reserving source IDs.
  3. Reserve source IDs only while holding the workspace lock.
  4. Stage newly scraped source files before final publication.
  5. Commit source files plus registry/config updates through the shared coordinator and clean up incomplete staged artifacts on failure.
- Validation: `python -m pytest tests/unit/test_scripts.py -q -k "search_web"` passes.
- Notes: The implementation must prevent both lost updates and orphaned source files.

#### Task 2.3: Make arXiv Search Use The Same Coordinator And Source Contract

- Status: TO BE DONE
- Objective: Refactor `search_arxiv.py` to follow the same coordinated mutation path as `search_web.py`.
- Steps:
  1. Route paper-source ID allocation through the shared coordinator.
  2. Stage paper markdown writes before final commit.
  3. Keep `config.json` search history and `sources/index.json` in sync with the file commit path.
- Validation: `python -m pytest tests/unit/test_scripts.py -q -k "search_arxiv"` passes.
- Notes: Do not leave paper search on a separate, less strict persistence path.

#### Task 2.4: Add Recovery Behavior For Interrupted Search Transactions

- Status: TO BE DONE
- Objective: Ensure the next search or audit can detect and resolve incomplete staged mutations safely.
- Steps:
  1. Define the on-disk representation for an incomplete search transaction or staging area.
  2. Implement deterministic recovery on the next search/audit start.
  3. Add tests for interrupted writes after source-file staging and after registry write attempts.
- Validation: `python -m pytest tests/unit/test_scripts.py -q -k "transaction or recovery"` passes.
- Notes: Recovery may roll forward or roll back, but the behavior must be explicit and testable.

#### Task 2.5: Validate Workspace State Before Commit

- Status: TO BE DONE
- Objective: Reject invalid or internally inconsistent workspace state before it is written to disk.
- Steps:
  1. Define invariants for persisted search state, including unique source IDs, required source fields, valid `next_source_id`, and coherent `config.json` search records.
  2. Validate staged `config.json` and `sources/index.json` payloads immediately before commit.
  3. Fail the mutation cleanly if invariants are violated, preserving recoverable staging data or diagnostics as designed in Task 2.4.
- Validation: `python -m pytest tests/unit/test_common.py -q -k "state or validation"` passes.
- Notes: This addresses the current gap where partial overwrites can still look syntactically valid and therefore slip through silently.

### Milestone 3: Harden Audit And Traceability Validation

- Status: TO BE DONE
- Purpose: Make the audit authoritative for the actual workspace state instead of a regex-only approximation.
- Exit Criteria: Audit output detects unindexed files, missing indexed files, malformed citations, duplicate IDs across directories, and finding/insight counter drift without false-validating broken provenance.

#### Task 3.1: Add Filesystem-Index Consistency Checks

- Status: TO BE DONE
- Objective: Extend `workspace_info.py audit` to compare `sources/index.json` against the actual `sources/web/`, `sources/papers/`, and `sources/code/` directories.
- Steps:
  1. Scan source directories and build the on-disk source set.
  2. Report unindexed files, index entries whose target file is missing, and duplicate IDs across source directories.
  3. Surface these mismatches in both structured JSON and the human-readable summary.
- Validation: `python -m pytest tests/unit/test_scripts.py -q -k "filesystem or index"` passes.
- Notes: This fixes the current blind spot where `workspace_info list` can show `file_count > source_count` but `audit` still reports `status: ok`.

#### Task 3.2: Make Citation Validation Path-Aware And Canonical

- Status: TO BE DONE
- Objective: Stop accepting malformed paper citations as valid source references.
- Steps:
  1. Define the canonical accepted source reference form as bare `src_NNN`.
  2. Update audit parsing so path-qualified references such as `papers/src_001` are flagged explicitly.
  3. Validate cited IDs against actual indexed entries and their file metadata rather than a bare ID set alone.
- Validation: `python -m pytest tests/unit/test_scripts.py -q -k "citation"` passes.
- Notes: The real workspace currently has `fnd_012` and report references that are falsely treated as valid because the audit extracts only `src_001`.

#### Task 3.3: Add Metadata Drift Checks And Better Severity Reporting

- Status: TO BE DONE
- Objective: Make audit and show outputs reflect counter drift and serious warning states more clearly.
- Steps:
  1. Compare `next_finding_id` and `next_insight_id` in `config.json` to the actual highest IDs in `notes/findings.md` and `notes/summary.md`.
  2. Update `workspace_info.py show` to expose file-count versus indexed-count mismatches or equivalent consistency fields.
  3. Revise the audit summary/severity logic so major warning states are not summarized as a generic “OK with warnings”.
- Validation: `python -m pytest tests/unit/test_scripts.py -q -k "show or counters or summary"` passes.
- Notes: Keep the JSON machine-readable while improving the human-facing severity line.

### Milestone 4: Add Workflow Guardrails For Research Agents

- Status: TO BE DONE
- Purpose: Reduce the chance that an agent reproduces the same workspace mistakes even after the core state bug is fixed.
- Exit Criteria: The workspace-local skill and docs explicitly instruct agents on sequential search discipline, post-search verification, canonical citation format, and counter maintenance.

#### Task 4.1: Update The Deep-Research Skill And Workspace Docs

- Status: TO BE DONE
- Objective: Add the missing operational guardrails to the research-facing instructions.
- Steps:
  1. Update `runtime/workspace/skills/deep-research/SKILL.md` to explain that multiple search commands in one agent message may execute in parallel.
  2. Add a required post-search verification step that checks `config.json` search count and runs `workspace_info.py audit .`.
  3. Clarify that source citations must use bare `src_NNN`, never file paths such as `papers/src_001`.
  4. Add instructions to keep `next_finding_id` and `next_insight_id` aligned with the notes after writing findings and insights.
  5. Update the workspace-facing companion docs, at minimum `runtime/workspace/AGENTS.md`, so the same guardrails are visible outside the skill file.
- Validation: `python tests/validate_skills.py` passes.
- Notes: The skill update is necessary even after the locking fix because it makes the intended workflow explicit.

#### Task 4.2: Enrich Search Output Metadata For Dedup And Failures

- Status: TO BE DONE
- Objective: Make search results easier for agents to interpret and recover from.
- Steps:
  1. Include which URLs were skipped as duplicates and, when possible, which existing source IDs they matched.
  2. Preserve enough structured failure data in `config.json` for retry tooling to consume.
  3. Keep stdout JSON stable enough for agents to parse programmatically.
- Validation: `python -m pytest tests/unit/test_scripts.py -q -k "dedup or failures"` passes.
- Notes: This is a UX improvement, not a substitute for state safety.

#### Task 4.3: Add A Retry Path For Failed Scrapes

- Status: TO BE DONE
- Objective: Let an agent rerun only failed URLs from a previous web search instead of repeating the whole query.
- Steps:
  1. Design a `--retry-failed` or equivalent flag for `search_web.py`.
  2. Make it read the structured failure metadata from the workspace.
  3. Ensure retried successes update source/index/config state through the shared coordinator.
- Validation: `python -m pytest tests/unit/test_scripts.py -q -k "retry_failed"` passes.
- Notes: Keep the retry contract deterministic and scoped to one workspace.

### Milestone 5: Improve Scrape Signal Quality

- Status: TO BE DONE
- Purpose: Reduce the amount of UI chrome and unusable content that agents must manually filter out during research.
- Exit Criteria: Crawl output includes a readability or extraction pass, low-signal pages are marked clearly, and regression tests cover the expected behavior on representative fixtures.

#### Task 5.1: Add A Readability / Content-Extraction Pass To Crawl4AI Output

- Status: TO BE DONE
- Objective: Stop treating raw Crawl4AI markdown as the final research payload for every domain.
- Steps:
  1. Evaluate the extraction options already available in Crawl4AI or add a lightweight post-processing step.
  2. Apply extraction before the final markdown is persisted to workspace source files.
  3. Preserve enough metadata to debug extraction failures when the content becomes too sparse.
- Validation: `python -m pytest tests/unit/test_providers.py -q -k "crawl4ai"` passes.
- Notes: The first goal is a measurable reduction in boilerplate, not perfect per-domain extraction.

#### Task 5.2: Add Low-Signal Detection For Thin Or UI-Heavy Pages

- Status: TO BE DONE
- Objective: Mark sources like Colab auth walls, YouTube chrome pages, and near-empty wrappers as low quality instead of presenting them as normal research artifacts.
- Steps:
  1. Define heuristics for low-signal pages using word count, heading presence, known wall patterns, or provider error metadata.
  2. Record the quality signal in frontmatter and/or index metadata.
  3. Make the skill/docs tell agents how to treat low-signal sources during extraction.
- Validation: `python -m pytest tests/unit/test_providers.py -q -k "quality or low_signal"` passes.
- Notes: This should not discard content blindly; it should make bad sources obvious.

#### Task 5.3: Add Scrape-Quality Regression Fixtures

- Status: TO BE DONE
- Objective: Ensure the content-quality improvements remain stable across future changes.
- Steps:
  1. Add representative HTML or mocked Crawl4AI-result fixtures for GitHub README pages, YouTube-like pages, and thin wrapper pages.
  2. Assert expected extraction behavior and low-signal marking.
  3. Keep the tests deterministic and offline.
- Validation: `python -m pytest tests/unit/test_providers.py -q` passes.
- Notes: Prefer fixtures over live site fetches to keep CI stable.

### Milestone 6: Cleanup And Final Verification

- Status: TO BE DONE
- Purpose: Ensure the repository contains only intentional final artifacts and the complete change is verified.
- Exit Criteria: Intermediate artifacts are removed, all final verification passes, a changelog entry exists, and the plan status is COMPLETED.

#### Task 6.1: Cleanup Intermediate Artifacts And Add Changelog Entry

- Status: TO BE DONE
- Objective: Remove implementation-only artifacts and leave a durable summary of the user-facing fixes.
- Steps:
  1. Inspect the worktree for temporary fixtures, scratch scripts, debug outputs, one-off notes, and obsolete plan fragments created during implementation.
  2. Remove only artifacts that are not part of the intended final repository state.
  3. Create or update `CHANGELOG.md` with an entry summarizing the research-workspace reliability, audit, and scrape-quality fixes.
- Validation: Worktree diff contains only intended final files, including the changelog update.
- Notes: Do not remove maintainable regression fixtures or user-provided files.

#### Task 6.2: Final Verification

- Status: TO BE DONE
- Objective: Validate the integrated fix set after cleanup.
- Steps:
  1. Run the full repository test suite relevant to scripts, providers, installers, and skills.
  2. Run the new concurrent-search and audit regression tests explicitly.
  3. Perform one deterministic end-to-end workspace replay using fixture providers or cached responses, then confirm:
     - expected search count in `config.json`
     - expected indexed source count
     - zero unexpected filesystem/index mismatches
     - audit correctly flags malformed citations when intentionally injected
  4. Fix failures and rerun until verification passes, or record the blocker.
- Validation:
  - `python -m pytest tests/unit -q`
  - `python tests/validate_skills.py`
  - Deterministic manual or scripted replay of the concurrent-search scenario with `python scripts/workspace_info.py show <workspace>` and `python scripts/workspace_info.py audit <workspace>`
- Notes: Keep final verification offline or fixture-driven where possible.

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

Self-check result: PASS. The plan is ready for approval.

## Execution Notes

- Update milestone and task status before starting and after validation.
- Update each task to COMPLETED immediately after its validation passes.
- Mark tasks or milestones BLOCKED with a short reason when progress cannot continue.
