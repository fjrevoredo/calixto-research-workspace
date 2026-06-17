# Methylene Blue Retrospective Enhancement Plan

## Metadata

- Plan Status: COMPLETED
- Created: 2026-06-17
- Last Updated: 2026-06-17
- Owner: Coding agent
- Approval: APPROVED

## Status Legend

- Plan Status values: DRAFT, QUESTIONS PENDING, READY FOR APPROVAL, APPROVED, IN PROGRESS, COMPLETED, BLOCKED
- Task/Milestone Status values: TO BE DONE, IN PROGRESS, COMPLETED, BLOCKED, SKIPPED

## Goal

Turn the methylene-blue retrospective into concrete toolkit improvements that reduce citation attribution errors, force report claims through the findings layer when requested, make source quality visible before extraction, and route biomedical research toward better evidence providers without violating the file-based, agent-first architecture.

## Scope

- Add stricter traceability audit modes for report citations that bypass findings.
- Add a lightweight claim-verification workflow that helps agents check cited report claims against source files without calling an LLM from scripts.
- Add deterministic source-quality tier metadata and audit/reporting hooks.
- Add biomedical topic guidance and provider routing so arXiv is not treated as the default scholarly source for medicine.
- Add provider-level or script-level relevance filtering for arXiv result sets.
- Update runtime research skills and tests to encode the improved workflow.

## Non-Goals

- Fully automate semantic citation verification with NLP or LLM calls.
- Hard-block every report with pending sources in the default audit path.
- Replace arXiv globally; it remains useful for CS, physics, math, and related literature reviews.
- Rewrite existing generated workspaces in place.
- Give medical advice or encode domain-specific clinical dosing rules in toolkit code.

## Assumptions

- The current completed reliability and UX follow-up work stays in place: workspace state coordination, `review_status`, `review-source`, `sync-counters`, low-signal metadata, max-source warnings, and filesystem/index audit checks.
- Strict workflow enforcement should be opt-in at first so existing sample workspaces and partial research runs do not become invalid by default.
- Source quality tiers are heuristic metadata for agent triage, not authoritative truth.
- PubMed support should use a non-LLM, file-friendly API path such as NCBI E-utilities, with no required API key for basic usage.
- New runtime scripts must be registered consistently in `runtime/workspace-manifest.json` and, when appropriate, `pyproject.toml` console scripts.

## Open Questions

- None.

## Validated Feedback Summary

- `workspace_info.py show` on `C:\Users\Francisco\Downloads\Junk\calixto2\workspaces\methylene-blue` confirms 7 searches, 64 indexed source files, 35 pending sources, 19 discarded sources, 10 used sources, and a 14-source overrun of `scope.max_sources`.
- `workspace_info.py audit` confirms the workspace is structurally valid after manual fixes but still warns on 50 orphaned sources; this validates that structural audit cannot catch citation-content mismatch.
- Comparing `notes/findings.md` to `outputs/report.md` confirms five report-only source IDs: `src_002`, `src_004`, `src_007`, `src_008`, and `src_016`.
- The arXiv batch added 10 sources and all 10 were later discarded as irrelevant, validating that biomedical topics need better scholarly-provider routing and arXiv relevance checks.
- Existing toolkit plans already addressed concurrency, lost updates, source review state, soft max-source warnings, low-signal metadata, and path-aware citation validation; this plan focuses on remaining gaps.

## Milestones

### Milestone 1: Strict Traceability Modes

- Status: COMPLETED
- Purpose: Make the report-to-findings bypass visible to agents without breaking normal exploratory audits.
- Exit Criteria: `workspace_info.py audit` can report or fail on report-only source citations in a strict mode, and tests prove the methylene-blue failure pattern is detected.

#### Task 1.1: Add Report-Only Citation Detection

- Status: COMPLETED
- Objective: Extend audit output with `report_sources_not_in_findings`.
- Steps:
  1. In `scripts/workspace_info.py`, compute `report_src_refs - findings_src_refs`.
  2. Include the sorted list in the structured audit payload.
  3. Include a concise warning summary and `status: "warning"` when the list is non-empty and no hard failures exist.
  4. Confirm `runtime/workspace-manifest.json` continues to bundle `scripts/workspace_info.py` into generated workspaces.
- Validation: `python -m pytest tests/unit/test_scripts.py -q -k "report_sources_not_in_findings"`
- Notes: Keep default status as `warning`, not `error`, unless strict mode is enabled.

#### Task 1.2: Add `--strict-traceability` Audit Mode

- Status: COMPLETED
- Objective: Let agents make report-only citations, unresolved pending sources, and used-but-uncited sources fail the audit deliberately.
- Steps:
  1. Add `--strict-traceability` to the `audit` subcommand.
  2. In strict mode, set status to `error` when any report source is absent from findings.
  3. In strict mode, set status to `error` when any uncited source remains in the `pending` orphan bucket.
  4. In strict mode, set status to `error` when any source marked `used` is not cited in findings or report.
  5. Leave discarded and low-signal orphan handling as warnings unless malformed references or index mismatches exist.
- Validation: `python -m pytest tests/unit/test_scripts.py -q -k "strict_traceability"`
- Notes: This directly addresses the five source IDs that bypassed findings in the methylene-blue report.

#### Task 1.3: Add Fixture Coverage For The Methylene-Blue Failure Shape

- Status: COMPLETED
- Objective: Preserve the regression as a compact deterministic unit test.
- Steps:
  1. Build a temporary workspace with findings citing `src_001` and a report citing `src_001` plus `src_002`.
  2. Assert default audit returns a warning with `report_sources_not_in_findings: ["src_002"]`.
  3. Assert `audit --strict-traceability` returns `status: "error"`.
- Validation: `python -m pytest tests/unit/test_scripts.py -q -k "report_sources_not_in_findings or strict_traceability"`
- Notes: Do not copy the real methylene-blue workspace into the repository.

### Milestone 2: Claim Verification Workflow

- Status: COMPLETED
- Purpose: Reduce wrong-source attribution by giving agents a deterministic pre-handoff checklist and source excerpts to verify manually.
- Exit Criteria: The runtime exposes a non-LLM `verify-citations` or equivalent command that extracts cited report lines, maps them to source files, and produces a review checklist artifact.

#### Task 2.1: Design A Citation Verification Artifact

- Status: COMPLETED
- Objective: Define a plain Markdown/JSON artifact for manual citation verification.
- Steps:
  1. Add a proposed output format under `docs/` or in `requirements.md` for `outputs/citation-check.md`.
  2. Include report line number, cited source IDs, source file paths, source review status, and blank verification fields.
  3. Document that verification is semantic and must be completed by the agent or human, not by the script.
- Validation: Manual inspection confirms every field is file-based and no LLM call is required.
- Notes: This keeps the project aligned with the no-LLM-scripts rule.

#### Task 2.2: Add A `verify-citations` Command

- Status: COMPLETED
- Objective: Generate the citation verification checklist from `outputs/report.md`.
- Steps:
  1. Add a `workspace_info.py verify-citations <workspace>` subcommand, or a narrow standalone `scripts/verify_citations.py` if that keeps responsibilities cleaner.
  2. Parse report paragraphs or lines containing `src_NNN`.
  3. For each citation, resolve source metadata from `sources/index.json`.
  4. Write `outputs/citation-check.md` by default, with an option to print JSON only.
  5. Include warnings for snippet-only, errored, discarded, pending, or report-only citations.
  6. If a standalone script is chosen, register it in `runtime/workspace-manifest.json` and `pyproject.toml`.
- Validation: `python -m pytest tests/unit/test_scripts.py -q -k "verify_citations"`
- Notes: The command must not claim a citation is semantically correct; it only prepares the verification pass.

#### Task 2.3: Add Source Excerpt Support

- Status: COMPLETED
- Objective: Make the verification artifact practical by showing nearby source text candidates.
- Steps:
  1. Extract key terms from the report sentence or paragraph using deterministic token filtering.
  2. Find the top few matching lines or paragraphs in each cited source file using simple lexical overlap.
  3. Include short excerpts and file references in `citation-check.md`.
  4. Mark citations with no lexical match as `needs_manual_review`.
- Validation: Unit tests with fixture source files confirm relevant excerpts are surfaced and no-match cases are flagged.
- Notes: This is a triage aid, not a semantic proof.

### Milestone 3: Source Quality Tiers

- Status: COMPLETED
- Purpose: Make low-quality, commercial, affiliate, and authoritative sources visible before the agent writes findings or reports.
- Exit Criteria: New web and paper sources carry deterministic quality-tier metadata, audit/show summarize tiers, and skills tell agents how to use tiers.

#### Task 3.1: Define The Source Quality Schema

- Status: COMPLETED
- Objective: Add a small stable metadata model for source quality.
- Steps:
  1. Define `quality_tier`, `quality_reasons`, and `quality_requires_corroboration` fields for source index entries.
  2. Use tiers such as `authoritative`, `scholarly`, `established_media`, `commercial`, `affiliate_or_vendor`, `low_signal`, and `unknown`.
  3. Document that tiers are heuristic and editable through source review notes.
- Validation: Schema notes are present in `requirements.md` and accepted by `_common.py` validation.
- Notes: Use ASCII spelling for field names; avoid domain-specific hardcoding beyond general categories.

#### Task 3.2: Implement Deterministic Tier Assignment

- Status: COMPLETED
- Objective: Assign initial tiers when sources are collected.
- Steps:
  1. Add a helper that classifies URL/domain and existing metadata.
  2. Treat `.gov`, `nih.gov`, `ncbi.nlm.nih.gov`, `pmc.ncbi.nlm.nih.gov`, and PubMed records as high-authority biomedical signals.
  3. Treat commercial sales, supplement, affiliate, and vendor patterns as corroboration-required signals.
  4. Preserve low-signal/error metadata as a tier input.
  5. Apply the helper in `search_web.py` and paper-source scripts.
- Validation: `python -m pytest tests/unit/test_scripts.py -q -k "quality_tier"` and `python -m pytest tests/unit/test_common.py -q -k "index"`
- Notes: The tier should be visible in both frontmatter and `sources/index.json` when feasible.

#### Task 3.3: Surface Quality Tiers In `show`, `audit`, And Bibliography Guidance

- Status: COMPLETED
- Objective: Make quality distribution obvious to agents before report writing.
- Steps:
  1. Add tier counts to `workspace_info.py show`.
  2. Add audit warnings when all report-cited sources are commercial, affiliate, vendor, or unknown tiers and no report-cited source is authoritative or scholarly.
  3. Update bibliography template guidance to include quality tier and conflict notes.
- Validation: `python -m pytest tests/unit/test_scripts.py -q -k "quality_tier or show or audit"` and `python tests/validate_skills.py`
- Notes: Avoid overfitting to medical claims; phrase warnings as evidence-quality prompts.

### Milestone 4: Biomedical Scholarly Provider Routing

- Status: COMPLETED
- Purpose: Stop sending biomedical literature questions to arXiv by default when PubMed/MEDLINE is the better source.
- Exit Criteria: The toolkit supports PubMed search for biomedical topics, documents when to use it, and warns when arXiv is likely a poor fit.

#### Task 4.1: Add PubMed Search Support

- Status: COMPLETED
- Objective: Provide a first-class biomedical paper search command or provider.
- Steps:
  1. Implement `scripts/search_pubmed.py` using NCBI E-utilities or another no-key-required official path.
  2. Save records to `sources/papers/src_NNN.md` with shared `src_NNN` IDs, PubMed ID, title, abstract, authors, journal, publication date, DOI when available, and URL.
  3. Commit config/index/source files through `WorkspaceStateCoordinator`.
  4. Add cache support using the existing cache-key conventions.
  5. Add the script to `runtime/workspace-manifest.json` and standalone workspace bundles.
  6. Add a `calixto-search-pubmed` console script entry in `pyproject.toml` if the new command is intended to be installed with the toolkit.
  7. Document NCBI rate-limit behavior and any optional `--email` or API-key parameter without making it required for basic use.
- Validation: `python -m pytest tests/unit/test_scripts.py -q -k "pubmed"` with cached fixtures; no live network required.
- Notes: Keep API-key support optional; basic use must remain account-free.

#### Task 4.2: Add Biomedical Topic Warnings For arXiv

- Status: COMPLETED
- Objective: Warn agents when `search_arxiv.py` is being used for a likely biomedical query without an appropriate arXiv category.
- Steps:
  1. Add a deterministic biomedical keyword detector for a small documented term list such as clinical, dosage, safety, drug, medication, PubMed, human trial, contraindication, pharmacology, adverse effect, and randomized trial.
  2. If detected and no fitting arXiv category is provided, include a warning in stdout/config search metadata.
  3. Mention `search_pubmed.py` as the recommended next command when available.
- Validation: `python -m pytest tests/unit/test_scripts.py -q -k "arxiv and biomedical"`
- Notes: Warn only; do not block, because some biomedical-adjacent computational topics legitimately belong on arXiv.

#### Task 4.3: Add arXiv Relevance Filtering

- Status: COMPLETED
- Objective: Prevent obviously irrelevant arXiv records from consuming source slots silently.
- Steps:
  1. Add an optional `--must-contain TERM` argument that requires title or abstract lexical matches.
  2. Add a `--min-query-token-overlap N` option or internal low-relevance marker for broad queries, using stopword-filtered query tokens.
  3. Persist filtered/skipped counts in the search record.
  4. Mark low-overlap saved results with `content_quality` or `quality_tier` metadata rather than discarding by default.
- Validation: `python -m pytest tests/unit/test_scripts.py -q -k "arxiv and relevance"`
- Notes: For the methylene-blue query, `--must-contain "methylene blue"` would have prevented the 10 irrelevant arXiv saves.

### Milestone 5: Runtime Workflow Updates

- Status: COMPLETED
- Purpose: Ensure agents apply the new strict traceability, source-tier, citation-check, and provider-routing workflow during real research.
- Exit Criteria: Workspace-local skills and docs describe the new workflow concisely, and skill validation passes.

#### Task 5.1: Update Deep Research Skill

- Status: COMPLETED
- Objective: Add the missing pre-report and post-report guardrails to `runtime/workspace/skills/deep-research/SKILL.md`.
- Steps:
  1. Require a close-pending decision before report writing: cite in a finding, discard with reason, or explicitly leave pending in `notes/gaps.md`.
  2. Require `audit --strict-traceability` before handoff for final reports.
  3. Require the citation verification artifact before final delivery.
  4. Add guidance that medical/biomedical topics should prefer PubMed over arXiv.
  5. Explain that strict traceability treats unresolved pending sources as errors, so intentionally deferred sources need an explicit review decision before final handoff.
- Validation: `python tests/validate_skills.py`
- Notes: Keep the skill concise; avoid turning it into a medical-domain skill.

#### Task 5.2: Update Literature Review Skill

- Status: COMPLETED
- Objective: Make scholarly-provider choice domain-aware.
- Steps:
  1. Keep arXiv primary for CS, math, physics, and computational topics.
  2. Add PubMed-first guidance for biomedical, pharmacology, clinical, and health questions.
  3. Document arXiv relevance filters for broad multi-word queries.
  4. Require source quality tier notes in bibliography entries.
- Validation: `python tests/validate_skills.py`
- Notes: The skill description should no longer imply arXiv is always the primary academic source.

#### Task 5.3: Update Workspace Docs And Templates

- Status: COMPLETED
- Objective: Make the new commands discoverable in generated workspaces.
- Steps:
  1. Update `runtime/workspace/AGENTS.md` script references.
  2. Update `templates/workspace/outputs/bibliography.md` to mention quality tiers and conflicts.
  3. Update `templates/workspace/outputs/report.md` to mention strict audit and citation-check expectations.
  4. Update `requirements.md` script interface sections for any new commands.
  5. Add or update an ADR/decision-log entry for PubMed routing, source quality tiers, and strict final-report traceability.
- Validation: `python tests/validate_skills.py` and manual inspection of generated workspace contents from `python scripts/init_workspace.py plan-check --path <tmp>`
- Notes: Existing workspaces remain unchanged unless regenerated.

### Milestone 6: Golden And Example Coverage

- Status: COMPLETED
- Purpose: Validate the new behavior in repeatable examples rather than relying only on unit tests.
- Exit Criteria: Golden or fixture-backed tests cover strict citation routing, quality tiers, and PubMed/arXiv provider selection.

#### Task 6.1: Add A Biomedical Fixture Scenario

- Status: COMPLETED
- Objective: Create a cached, offline biomedical search scenario that reproduces provider routing concerns.
- Steps:
  1. Add fixture cache data for PubMed with one relevant biomedical abstract.
  2. Add fixture arXiv data with irrelevant lexical matches similar to the methylene-blue batch.
  3. Assert PubMed results persist as paper sources and arXiv warnings/filtering behave as designed.
- Validation: `python -m pytest tests/unit/test_scripts.py -q -k "pubmed or biomedical"`
- Notes: Do not depend on live NCBI or arXiv access in tests.

#### Task 6.2: Add Strict Traceability Golden Checks

- Status: COMPLETED
- Objective: Make citation routing part of structural quality evaluation.
- Steps:
  1. Extend `tests/golden/compare.py` or expected quality checks with a report-sources-through-findings metric.
  2. Keep the default threshold compatible with source-collection-only golden runs.
  3. Add a stricter mode for synthesized-report validation.
- Validation: `python -m pytest tests/unit/test_compare.py -q` and `python tests/golden/compare.py <fixture-a> <fixture-b>` if fixtures exist.
- Notes: The golden runner should still support collection-only runs.

### Milestone 7: Cleanup And Final Verification

- Status: COMPLETED
- Purpose: Ensure the repository contains only intentional final artifacts and the complete change is verified.
- Exit Criteria: Intermediate artifacts are removed, docs/changelog are updated, generated workspaces contain the expected runtime files, and final verification passes.

#### Task 7.1: Cleanup Intermediate Artifacts And Add Changelog Entry

- Status: COMPLETED
- Objective: Leave a clean maintainable diff.
- Steps:
  1. Inspect the worktree for temporary files, scratch fixtures, debug logs, and generated workspaces.
  2. Remove only artifacts that are not part of the intended final repository state.
  3. Update `CHANGELOG.md` with strict traceability, citation verification, source tiers, PubMed support, and arXiv relevance changes.
- Validation: `git status --short` shows only intended tracked changes.
- Notes: Preserve maintainable tests and fixtures.

#### Task 7.2: Final Verification

- Status: COMPLETED
- Objective: Validate the integrated change after cleanup.
- Steps:
  1. Run targeted script and provider tests.
  2. Run skill validation.
  3. Generate a temporary workspace and confirm new runtime commands/docs are bundled.
  4. Run a strict-audit fixture and citation-check generation fixture.
- Validation:
  - `python -m pytest tests/unit/test_common.py -q`
  - `python -m pytest tests/unit/test_scripts.py -q`
  - `python -m pytest tests/unit/test_providers.py -q`
  - `python -m pytest tests/unit/test_compare.py -q`
  - `python tests/validate_skills.py`
- Notes: If full tests are blocked by environment locks, rerun with direct `python` and record the exact blocker.

## Approval Gate

Implementation must not start until the user approves this plan.

## Plan Self-Check

- [x] Plan location follows the default location rule.
- [x] Scope, non-goals, and assumptions are explicit.
- [x] Open questions are resolved.
- [x] Tasks are grouped into milestones because the plan has more than 10 tasks.
- [x] Every task has concrete steps and validation.
- [x] Every milestone has exit criteria.
- [x] Cleanup and final verification are included.
- [x] The plan avoids vague actions without concrete targets.
- [x] The plan can be executed by a coding agent without reading the original conversation.

Self-check result: PASS. The plan is ready for approval.

## Full Self-Check Addendum

- Checked against current runtime bundling: new standalone scripts must be added to `runtime/workspace-manifest.json`; existing bundled scripts are copied from `scripts/`.
- Checked against current state validation: `_common.py` validates core source fields and review metadata but permits additional metadata today; adding explicit quality-field validation is a plan task, not existing behavior.
- Checked against current `workspace_info.py audit`: the plan correctly targets a real missing check because current audit counts valid source IDs but does not report source IDs cited in the report that bypass findings.
- Checked against the methylene-blue workspace evidence: the numbers in the validated feedback summary match direct `show`/`audit` output and the report/findings citation diff.
- Checked against project non-negotiables: citation verification remains deterministic and file-based; semantic judgment stays with the agent or human, not an LLM-calling script.
- Checked for implementation completeness: new commands now include runtime/package registration, docs, deterministic tests, changelog, and final verification coverage.

## Execution Notes

- Update milestone and task status before starting and after validation.
- Keep default audit behavior backward-compatible; use strict flags for stronger final-report gates.
- Do not add LLM calls to scripts. Any semantic judgment stays with the agent or user.
- Use cached fixtures for PubMed/arXiv tests so CI remains deterministic.

