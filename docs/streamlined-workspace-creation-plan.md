# Streamlined Workspace Creation And Launch Plan

## Metadata

- Plan Status: COMPLETED
- Created: 2026-06-20
- Last Updated: 2026-06-20
- Owner: Coding agent
- Approval: APPROVED

## Status Legend

- Plan Status values: DRAFT, QUESTIONS PENDING, READY FOR APPROVAL, APPROVED, IN PROGRESS, COMPLETED, BLOCKED
- Task/Milestone Status values: TO BE DONE, IN PROGRESS, COMPLETED, BLOCKED, SKIPPED

## Goal

Reduce the normal path from “I have a research question” to “my selected coding agent is open in a ready Calixto workspace” to one memorable command, without weakening standalone workspace portability, snapshot reproducibility, toolkit freshness checks, structured output, or harness-agnostic operation.

The intended primary workflow is:

```text
calixto research "How much quality assurance should an MVP have?" --agent opencode
```

For a newly created workspace under the toolkit-managed `workspaces/` directory, this command must create the standalone snapshot, store the question, add the selected harness integration, use a pre-provisioned shared runtime, and launch the selected coding agent without requiring a manual `cd` or workspace-local setup run.

## Scope

- Add a top-level `calixto` CLI with a `research` command that orchestrates workspace creation and optional agent launch.
- Preserve `scripts/init_workspace.py` and the existing `calixto-init` entry point as lower-level, structured workspace-creation interfaces.
- Reuse the current pre-create toolkit freshness-check behavior, including the conservative print-and-exit update path.
- Create and maintain a toolkit-local, content-addressed managed runtime cache from workspace `pyproject.toml` and `uv.lock` fingerprints, with the current bundled runtime prepared eagerly.
- Use a managed runtime only when the workspace is eligible and its exact runtime key and metadata match.
- Fall back to workspace-local setup when a workspace is moved, is incompatible, or cannot safely use the managed runtime.
- Store the research question in `config.json` during creation.
- Generate harness-native skill mirrors and launch configuration for explicitly supported harnesses.
- Add a reusable `calixto open` command so existing managed workspaces can be reopened with the correct runtime instead of receiving the fast path only on their creation day.
- Optimize root and workspace setup so browser installation is conditional and idempotent rather than invoking Crawl4AI's forced reinstall path every time.
- Add unit, integration, installed-root, generated-workspace, moved-workspace, and manual UX coverage.
- Update root docs, workspace runtime docs, adapter docs, requirements, changelog, and a durable decision log.

## Non-Goals

- Calling an LLM API from Calixto scripts.
- Running research automatically without a user-selected coding-agent harness.
- Adding a server, daemon, background service, GUI, or proprietary workspace format.
- Removing the standalone workspace runtime files, lockfile, setup scripts, or direct script execution path.
- Rewriting or upgrading existing workspaces in place.
- Making one harness mandatory.
- Guaranteeing identical behavior across all coding agents.
- Introducing a machine-global runtime service or cache shared by unrelated toolkit installations. Managed runtimes remain owned by one toolkit root under ignored local state.
- Automatically installing coding-agent harnesses such as OpenCode, Claude Code, Codex, or Cursor.
- Hard-coding research workflow decisions into the launcher; the coding agent remains the research orchestrator.

## Current Status

- Workspace creation is implemented by `scripts/init_workspace.py` and copies the standalone payload defined by `runtime/workspace-manifest.json`.
- The user must currently remember a long `uv run python scripts/init_workspace.py <name>` command, enter the new directory, execute a workspace-local setup script, and launch a coding agent separately.
- Every inspected real workspace under `C:\Users\Francisco\Downloads\Junk\calixto2\workspaces` contains its own `.venv`.
- A warm generated-workspace benchmark on the current machine took approximately:
  - 0.8 seconds to create the workspace snapshot;
  - 5.3 seconds to create and sync a workspace `.venv`;
  - 53 seconds to run `crawl4ai-setup`;
  - 42 seconds to run `crawl4ai-setup` again.
- The locked Crawl4AI installer invokes Playwright and Patchright browser installation with `--force`, making the current setup path repeat expensive work even when browser assets already exist.
- Calixto's current `Crawl4AIProvider` constructs the default `BrowserConfig` and therefore uses standard Playwright, not Crawl4AI's optional undetected/Patchright path. The normal setup path should not install Patchright browser assets unless that provider configuration changes.
- uv hard-links most environment package files to its global cache on Windows, so apparent `.venv` size is not equal to physical duplication; the primary problem is repeated provisioning latency and workflow ceremony.
- Bundled workspace scripts can execute correctly through a compatible external environment when `UV_PROJECT_ENVIRONMENT` points to that environment and syncing is disabled.
- Workspace-local skills currently remain under `skills/<name>/SKILL.md`; harness-native project skill directories are not generated.
- The existing toolkit update check is correctly scoped to workspace creation and must remain conservative: choosing to update prints the supported installer command and exits before creating a workspace.

## Target User Flows

### Primary Managed Flow

```powershell
calixto research "What are the evidence-based benefits and risks of X?" --agent opencode
```

Observable behavior:

1. The toolkit performs the existing pre-create freshness check.
2. A slug is derived or supplied with `--name`.
3. A standalone workspace snapshot is created under `workspaces/<slug>/`.
4. The full question is written to `config.json`.
5. The requested harness integration is generated.
6. The exact managed runtime key is verified.
7. The coding agent launches with the workspace as its working directory and with the compatible managed runtime selected.

### Create Without Launch

```powershell
calixto research "Question text" --agent none
```

Observable behavior:

- The workspace is created and prepared, but no external harness process is started.
- Human-readable output reports the workspace path, selected runtime mode, harness integration, and an exact `calixto open` command.

### Reopen An Existing Workspace

```powershell
calixto open mvp-quality --agent codex
```

Observable behavior:

- A slug resolves under the active toolkit root's `workspaces/` directory; an explicit path is also accepted.
- Calixto selects the exact compatible managed runtime or a valid workspace-local runtime.
- The selected terminal harness launches from the workspace root with the research question and instructions available.

### Machine-Readable Creation

```powershell
calixto research "Question text" --agent none --json
```

Observable behavior:

- `--json` emits one structured result object and never starts an attached interactive TUI.
- Combining `--json` with a launching agent is rejected as an invalid argument.
- The existing lower-level commands retain their current JSON-by-default contracts.

### Explicit Name

```powershell
calixto research "Question text" --name mvp-quality --agent claude
```

Observable behavior:

- `--name` is authoritative and must pass the existing slug validation.
- Automatic slug generation is not used.

### Portable Or Incompatible Workspace Fallback

```powershell
cd <moved-workspace>
.\setup.ps1
```

Observable behavior:

- The workspace-local setup script creates its own `.venv`, verifies the actual scraper/browser runtime, and preserves the existing standalone contract.
- The workspace remains usable without the toolkit root after setup.

## Assumptions

- The CLI command name will be `calixto`, with `research` as the user-facing orchestration subcommand.
- Toolkit setup will expose the `calixto` console entry point without requiring users to activate `.venv`. The registration mechanism must not create another full research-dependency environment; the managed runtime cache remains responsible for research dependencies.
- `scripts/init_workspace.py` remains the source of truth for workspace materialization and update-check policy; orchestration code must call reusable functions rather than duplicate that logic.
- The canonical research skills remain under `skills/` inside every workspace. Harness-native directories are generated mirrors for discovery, not replacement sources.
- The guaranteed first-class launch adapters are terminal harnesses with verified interactive prompt and working-directory contracts: `opencode`, `claude`, `codex`, and `none`.
- Cursor support is conditional on verifying the separate Cursor Agent CLI contract. The installed `cursor` editor command alone only opens an editor window and is not sufficient to claim that the research question was submitted to an agent with the managed runtime environment.
- `--agent` defaults to `none`. Launching an agent is always explicit; Calixto must not guess between multiple installed harnesses.
- Agent command availability is checked before launch. Calixto reports an actionable error but does not install a missing agent.
- The launcher may provide a concise initial prompt when the harness supports a stable non-interactive prompt argument; otherwise the question in `config.json` and generated workspace instructions are the handoff contract.
- Managed-runtime eligibility requires both:
  - an allowed relationship to the creating toolkit root, normally a workspace under that root's managed `workspaces/` directory; and
  - an exact match between the workspace runtime key and one validated managed runtime.
- The runtime fingerprint hashes the exact workspace `pyproject.toml` and `uv.lock` bytes. The runtime key also includes platform, architecture, and selected Python major/minor identity so incompatible environments never share a cache entry.
- Managed environments are separate from the toolkit developer `.venv` so runtime compatibility does not depend on developer extras or root-project lockfile differences.
- Toolkit updates prepare a new current runtime but do not delete older valid runtime keys. Therefore workspaces created from earlier snapshots keep the fast path after toolkit updates.
- Managed runtime pruning is explicit, never automatic during toolkit update, and must not remove a runtime still referenced by a managed workspace unless the user forces it.
- Existing workspaces remain unchanged. They may use the fast path only if the compatibility and ownership checks pass without mutating workspace contents.
- Browser binaries may be machine-level caches, but setup verification must be performed through the selected runtime so version mismatches are detected honestly.
- Performance targets are evaluated with a warm toolkit installation. First toolkit installation may still download Python packages and browser assets.
- The default workspace parent is `<active-toolkit-root>/workspaces`, independent of the shell's current directory. `--path` remains the explicit override.
- Interactive commands use concise human-readable console output. `--json` is the opt-in automation mode and is incompatible with attached harness launch.

## Open Questions

- None.

## Milestones

### Milestone 1: Freeze The UX And Runtime Contracts

- Status: COMPLETED
- Purpose: Record the exact command behavior, runtime boundary, fallback rules, and compatibility policy before changing executable code.
- Exit Criteria: The CLI contract, managed-runtime contract, harness integration contract, and fallback behavior are documented in repository artifacts with no unresolved design questions.

#### Task 1.1: Create And Maintain The Decision Log

- Status: COMPLETED
- Objective: Create a durable implementation record at `docs/streamlined-workspace-creation-decision-log.md`.
- Steps:
  1. Create the decision log before implementation edits begin.
  2. Seed entries for the approved high-level decisions: one-command orchestration, content-addressed toolkit-local runtimes, exact runtime keys, canonical skills plus generated harness mirrors, and local setup fallback.
  3. Record subsequent decisions when they are made, including CLI argument changes, harness command details, browser-probe behavior, and compatibility exceptions.
- Validation: The decision log exists, references this plan, uses the repository's established decision-entry format, and contains the initial approved decisions.
- Notes: Do not defer decision-log reconstruction until the end of implementation.

#### Task 1.2: Define The `calixto research` CLI Contract

- Status: COMPLETED
- Objective: Specify a deterministic user-facing and automation-facing command interface.
- Steps:
  1. Define positional question input and options including `--name`, `--path`, `--agent`, `--json`, and the existing update-check controls.
  2. Define defaults: parent path `<active-toolkit-root>/workspaces`, `--agent none`, and interactive update checking consistent with `init_workspace.py`.
  3. Reuse `scripts._common.slugify`; when its result is not meaningful for non-ASCII or symbol-only input, use a stable `research-<short-question-hash>` fallback.
  4. For automatically derived names, append the lowest available numeric suffix on collision; for explicit `--name`, preserve the current error-on-existing behavior.
  5. Define invalid-question, invalid-name, missing-agent, launch-failure, and create-without-launch behavior.
  6. Define human-readable interactive output separately from `--json` output.
  7. Make `--json` valid only with `--agent none`; reject any combination that would mix a structured result with an attached TUI.
  8. Define JSON result fields for workspace path, workspace name, runtime mode, runtime key, generated integration paths, and exact `calixto open` next command.
  9. Keep prompts and human-facing warnings off stdout in `--json` mode.
- Validation: Add a CLI contract section to the decision log or a dedicated implementation note, and ensure every success/error branch planned here has an expected exit code and human/JSON output shape.
- Notes: Do not remove or silently change the existing `init_workspace.py` CLI contract.

#### Task 1.3: Define Managed Runtime Eligibility And Fallback

- Status: COMPLETED
- Objective: Make fast-path selection explicit, reproducible, and safe.
- Steps:
  1. Define the managed runtime location under ignored toolkit-local state, such as `.calixto/runtimes/<runtime-key>/`.
  2. Define the runtime key from workspace `pyproject.toml`, workspace `uv.lock`, operating system, architecture, and Python major/minor identity.
  3. Define runtime metadata containing the full fingerprint inputs, Python executable identity, preparation timestamp, and toolkit provenance where available.
  4. Require exact key and metadata matching before using a managed runtime.
  5. Preserve older valid runtime keys across toolkit updates.
  6. Define explicit runtime inspection and pruning behavior that scans managed workspaces before deletion and requires `--force` to remove a referenced runtime.
  7. Define allowed workspace locations and reject stale, missing, incomplete, or incompatible managed runtimes.
  8. Define fallback outcomes: use an already-valid local workspace `.venv`, run or recommend workspace setup according to CLI mode, or stop with a structured preparation error.
  9. State explicitly that the launcher never syncs a workspace project into an incompatible shared environment.
- Validation: A compatibility decision table covers new managed workspace, existing compatible workspace, workspace from a previous toolkit runtime, old lockfile with retained cache, old lockfile after explicit prune, moved workspace, missing managed runtime, incomplete managed runtime, local `.venv` present, Python-version change, and offline operation.
- Notes: `UV_NO_SYNC=1` or the equivalent uv argument is mandatory on the managed execution path.

### Milestone 2: Build The Content-Addressed Managed Runtime Cache

- Status: COMPLETED
- Purpose: Provision each distinct workspace dependency/browser runtime once per toolkit root rather than once per generated workspace, while retaining prior runtime keys for older snapshots.
- Exit Criteria: Root setup prepares and verifies the current runtime key, older valid keys survive toolkit updates, runtime inspection/pruning is safe, and unchanged setup reruns without forced browser installation.

#### Task 2.1: Add Managed Runtime Preparation Helpers

- Status: COMPLETED
- Objective: Provide testable Python helpers for locating, preparing, inspecting, and validating the toolkit-managed workspace runtime.
- Steps:
  1. Add a toolkit-only managed-runtime helper under `scripts/` rather than embedding cache lifecycle logic in shell scripts.
  2. Calculate the runtime key from the exact `runtime/workspace/pyproject.toml` and `runtime/workspace/uv.lock` bytes plus platform, architecture, and selected Python major/minor.
  3. Prepare the keyed environment using the bundled workspace project and lockfile.
  4. Serialize first-time preparation of the same runtime key with a cross-process lock or equivalent atomic ownership protocol.
  5. Build incomplete environments in a staging path and publish/mark them atomically only after dependency synchronization and runtime verification succeed.
  6. Detect stale locks, abandoned staging directories, and incomplete environments and return structured diagnostic states.
  7. Keep paths portable between Git checkouts and non-Git installed toolkit roots, and keep Windows path lengths bounded by using a short display key backed by the full hash in metadata.
  8. Add inspection helpers that enumerate runtime keys and determine which managed workspaces reference each key by hashing their bundled dependency files.
- Validation: Add unit tests covering key stability, changed pyproject/lockfile, platform/Python differences, missing files, valid metadata, stale metadata, incomplete environments, concurrent preparation, stale-lock recovery, old-key retention, workspace reference scanning, and atomic publication behavior.
- Notes: Reuse shared subprocess/error helpers where practical, but do not couple workspace research state to toolkit runtime state.

#### Task 2.2: Integrate Managed Runtime Preparation Into Root Setup

- Status: COMPLETED
- Objective: A successful toolkit setup leaves the current workspace runtime ready for immediate workspace creation and launch.
- Steps:
  1. Update `setup.sh` and `setup.ps1` to invoke the managed-runtime preparation helper after required tools are available.
  2. Preserve root developer-environment setup required by tests and maintainer commands.
  3. Ensure the current keyed environment is synchronized from `runtime/workspace/pyproject.toml` and `runtime/workspace/uv.lock`, not the root project lockfile.
  4. Make reruns idempotent and fast when the fingerprint and environment are already valid.
  5. Ensure installer-driven fresh install and update paths still finish with the current runtime prepared unless dependency setup was explicitly skipped or the user declined update-time setup.
  6. Preserve older runtime-key directories during installer updates and never classify them as source-managed toolkit files.
  7. If update-time setup is skipped or declined, make the next `calixto research/open` invocation validate and lazily prepare the required key before launch rather than claiming immediate readiness.
  8. Add the selected toolkit-local state directory, including `.calixto/` if used, to the root `.gitignore`.
- Validation: Extend setup and installer tests to assert that successful root setup creates a valid current runtime, an unchanged rerun avoids reconstruction, an update preserves an old key, and skipped/declined update setup produces honest messaging plus lazy repair on the next command.
- Notes: Update `.gitignore` if the selected managed-runtime path is not already ignored.

#### Task 2.3: Replace Forced Browser Setup With A Runtime Probe

- Status: COMPLETED
- Objective: Install browser assets only when the locked workspace runtime cannot launch the scraper's required browser.
- Steps:
  1. Add a browser/runtime probe executed through the target environment.
  2. Verify the actual default `Crawl4AIProvider` launch path or the exact browser backend selected by the locked Crawl4AI version; do not treat a path lookup alone as proof.
  3. Assert the current configured provider uses standard Playwright Chromium because `Crawl4AIProvider` constructs default `BrowserConfig`; install Patchright assets only if a future provider configuration explicitly enables the undetected path.
  4. When the probe succeeds, skip all browser installation.
  5. When the probe fails because browser assets are absent, run the narrow explicit browser install command required by the provider, without `--force`, then rerun the probe.
  6. Avoid calling `crawl4ai-setup` in the normal idempotent setup path because the locked implementation forces browser reinstall and resets Crawl4AI user cache state.
  7. Return a hard setup failure if the post-install probe still cannot launch the runtime.
- Validation: Tests use fake commands to cover already-ready, missing-browser-then-installed, installer failure, and post-install launch failure; a real Windows smoke test confirms a second setup does not reinstall browser assets.
- Notes: Update provider/setup error text so recovery guidance names the supported explicit command.

#### Task 2.4: Register The Lightweight Global CLI Entry Point

- Status: COMPLETED
- Objective: Make the documented `calixto` command available after toolkit setup without requiring users to activate `.venv` or remember `uv run`.
- Steps:
  1. Run a bounded implementation spike comparing an editable uv tool, platform-native launcher shims in a user bin directory, and any uv-supported entry-point mechanism available in the repository's supported uv versions.
  2. Reject any mechanism that creates another full Crawl4AI research environment merely to expose the launcher command.
  3. Select and document one cross-platform registration contract that resolves the active toolkit root explicitly and can be refreshed safely.
  4. Register or repair the command during toolkit update and manual setup.
  5. Detect when the selected executable directory is not available on `PATH` and print an exact recovery command or restart-shell instruction.
  6. Preserve a documented fallback command, such as `uv run --project <toolkit-root> calixto ...`, for environments where global command registration is intentionally skipped.
  7. Ensure uninstalling or moving one toolkit root cannot silently redirect a different toolkit installation's command.
- Validation: Fresh-install, update, and manual-setup tests verify `calixto --help` resolves to the intended toolkit root; a `--skip-deps` installation reports that command/runtime preparation was skipped or incomplete without claiming readiness.
- Notes: Record the rejected alternatives and final registration mechanism in the decision log. Current uv `tool install` behavior must be verified carefully because installing the root project normally also installs its declared heavy dependencies.

#### Task 2.5: Add Runtime Inspection And Safe Pruning

- Status: COMPLETED
- Objective: Prevent unmanaged runtime accumulation without silently breaking older workspaces.
- Steps:
  1. Add `calixto runtime list` to report runtime keys, size/apparent size where practical, validity, current-key status, and managed workspace references.
  2. Add `calixto runtime prune` with a dry-run default or explicit confirmation.
  3. Keep the current key and all referenced keys by default.
  4. Require `--force` plus explicit key selection to delete a runtime still referenced by a managed workspace.
  5. Make deletion failures non-destructive and report partial cleanup clearly.
- Validation: Unit and integration tests cover empty cache, invalid entries, unreferenced old keys, referenced old keys, current key protection, dry run, confirmation, forced deletion, and interrupted/failed deletion.
- Notes: Runtime pruning is toolkit-local maintenance and must not modify workspace files.

### Milestone 3: Implement One-Command Workspace Creation And Reopening

- Status: COMPLETED
- Purpose: Add memorable creation and reopening commands while preserving `init_workspace.py` as the low-level workspace factory.
- Exit Criteria: `calixto research "<question>" --agent none` creates a complete prepared workspace, and `calixto open <workspace> --agent <terminal-harness>` reopens it through the exact compatible runtime without requiring manual `cd` or local setup.

#### Task 3.1: Refactor Workspace Creation Into Reusable Operations

- Status: COMPLETED
- Objective: Allow the new command to reuse creation and update-check behavior without parsing subprocess JSON or duplicating policies.
- Steps:
  1. Separate argument parsing, update-check policy, workspace materialization, and result emission in `scripts/init_workspace.py`.
  2. Expose reusable functions that return typed dictionaries or small data objects and raise controlled exceptions.
  3. Preserve current `init_workspace.py` stdout, stderr, exit-code, prompting, update flags, and no-overwrite behavior.
  4. Keep the update-before-create print-and-exit contract unchanged.
  5. Add regression tests proving the existing CLI remains backward compatible.
- Validation: Existing init/update/metadata tests pass, plus new direct-function tests prove orchestration can call the creation path without subprocess output parsing.
- Notes: Do not move update checks into generated workspaces.

#### Task 3.2: Add The Top-Level `calixto` Command

- Status: COMPLETED
- Objective: Install a `calixto` console command with a `research` subcommand.
- Steps:
  1. Add a focused CLI module, for example `scripts/calixto.py`, and register `calixto = "scripts.calixto:main"` in `pyproject.toml`.
  2. Parse the question and options defined in Task 1.2.
  3. Default workspace creation to the active toolkit root's `workspaces/` directory rather than the caller's current directory.
  4. Derive the workspace name with the existing `slugify` helper, stable hash fallback, and collision policy from Task 1.2.
  5. Call the reusable update-check and workspace-creation operations.
  6. Write the exact question to `config.json` through existing config helpers.
  7. Prepare harness integration and runtime selection before optional launch.
  8. Emit concise human output by default and one JSON object only in valid `--json` mode.
- Validation: Add CLI tests for toolkit-root default paths from unrelated working directories, automatic slugging, explicit naming, non-ASCII/symbol-only questions, automatic collisions, explicit-name collisions, empty questions, alternate paths, update flags, `--agent none`, `--json`, and rejection of `--json` plus an attached agent.
- Notes: The question must not be lost or reduced to the generated slug.

#### Task 3.3: Add `calixto open`

- Status: COMPLETED
- Objective: Reopen an existing workspace through the same runtime-selection and harness-launch path used immediately after creation.
- Steps:
  1. Accept either a managed workspace slug or an explicit workspace path.
  2. Resolve slugs only under the active toolkit root's `workspaces/` directory and reject ambiguous/nonexistent values.
  3. Validate standalone workspace metadata and dependency files before runtime selection.
  4. Select the exact keyed managed runtime or a valid local `.venv`; invoke the defined fallback when neither is available.
  5. Generate missing harness integration only with explicit authorization for an existing workspace.
  6. Launch the selected terminal harness from the workspace root and provide an exact manual command if launch fails.
- Validation: Tests cover slug/path resolution, invocation from unrelated current directories, old runtime keys, local-runtime fallback, moved workspaces, invalid/legacy layouts, missing harness integration, and launch failure preserving workspace state.
- Notes: This command is also the supported next step printed by `calixto research --agent none`.

#### Task 3.4: Keep Machine-Local Runtime State Out Of Portable Workspace Metadata

- Status: COMPLETED
- Objective: Make the selected execution mode inspectable without turning machine-local paths into portable workspace truth.
- Steps:
  1. Keep runtime mode, runtime path, and cache-key selection in command output and toolkit-local state.
  2. Do not write an absolute toolkit runtime path or a claim of current managed-runtime availability into `config.json`.
  3. Compute compatibility from the workspace's bundled `pyproject.toml` and `uv.lock`; do not add a redundant portable fingerprint field unless implementation proves it is required and the workspace schema is deliberately bumped.
  4. Ensure copying the workspace does not leave instructions that falsely claim the original managed runtime is still available.
- Validation: Inspect a generated workspace, copy it to another directory, and confirm its files contain no required absolute path back to the toolkit root.
- Notes: Files remain the research database; machine-specific launch state must remain derived or explicitly non-portable.

### Milestone 4: Add Harness-Aware Workspace Integration And Launch

- Status: COMPLETED
- Purpose: Let the selected coding agent discover the correct research workflow automatically and start at the workspace boundary.
- Exit Criteria: Every guaranteed harness can be prepared through one shared adapter interface, generated skill mirrors match canonical skills, and launch tests verify the correct executable, working directory, environment, and handoff.

#### Task 4.1: Implement Harness Adapter Definitions

- Status: COMPLETED
- Objective: Centralize harness-specific paths, executable checks, launch arguments, and prompt capabilities.
- Steps:
  1. Define guaranteed adapter metadata for `opencode`, `claude`, `codex`, and `none`.
  2. For each harness, define executable discovery, workspace working-directory behavior, project skill location, instruction-file expectations, and whether a stable initial-prompt argument is supported.
  3. Use the verified interactive contracts as of plan review: OpenCode TUI supports project path plus `--prompt`; Claude Code accepts an initial positional prompt; Codex accepts `--cd`/working directory plus an optional positional prompt.
  4. Run a bounded Cursor Agent CLI verification. Add a Cursor Agent adapter only if the separately installed agent CLI exposes a stable working-directory, interactive prompt, and inherited-environment contract. Do not treat the `cursor` editor launcher as equivalent.
  5. If useful, keep `cursor` as a separate editor-opening convenience that reports it did not submit the research question or guarantee managed-runtime inheritance.
  6. Keep adapter logic data-driven where possible and isolate unavoidable platform-specific command construction.
  7. Return clear human or JSON errors, according to output mode, when the selected executable is unavailable.
  8. Do not execute shell-composed strings when an argument array is sufficient.
- Validation: Unit tests mock executable discovery and process launch for every guaranteed adapter on Windows and Unix command shapes; Cursor tests are required only if the official verification gate passes.
- Notes: Re-verify command details against current official harness behavior during implementation and record source URLs, accessed date, and locally observed `--help` command in the decision log because harness CLIs can change.

#### Task 4.2: Generate Harness-Native Skill Mirrors

- Status: COMPLETED
- Objective: Make bundled research skills discoverable by the explicitly selected harness while retaining canonical workspace skills.
- Steps:
  1. Keep `skills/deep-research` and `skills/literature-review` as canonical portable copies.
  2. Generate `.agents/skills/` for Codex and OpenCode, since both officially discover that repository-local location; generate `.claude/skills/` for Claude Code.
  3. If Cursor Agent support passes its verification gate, use only the project skill location confirmed by current official Cursor documentation.
  4. Generate only the integrations required by the selected harness unless a documented compatibility reason justifies an additional common mirror.
  5. Add a generated-file marker or deterministic comparison rule so drift can be detected.
  6. Update `runtime/workspace-manifest.json` only for new canonical runtime assets; harness-specific generated mirrors should be produced by initialization logic.
  7. Ensure copied workspaces retain the generated integration.
- Validation: Generated-workspace tests compare each mirror byte-for-byte with canonical skill sources and verify unsupported/developer-only skills are absent.
- Notes: If a harness does not support project skill discovery, generate only the instruction/config files it actually uses and rely on `AGENTS.md`.

#### Task 4.3: Launch The Agent In The Prepared Workspace

- Status: COMPLETED
- Objective: Start the selected coding agent at the workspace root with the correct runtime environment and research handoff.
- Steps:
  1. Set the child process working directory to the created workspace.
  2. On the managed path, set the managed environment override and disable uv synchronization for the child process.
  3. Preserve unrelated user environment variables.
  4. Pass a short initial handoff that tells the agent to read workspace `AGENTS.md`, use the applicable research skill, and answer the exact question in `config.json`; do not duplicate the whole research workflow in the command line.
  5. Define whether the launcher waits for the agent process or replaces/attaches to it, and make exit-code behavior explicit.
  6. On launch failure, preserve the successfully created workspace and return its path plus an actionable `calixto open` retry command.
- Validation: Process-launch tests assert executable, arguments, environment, and working directory; a manual smoke test launches at least OpenCode and one second available harness from a generated workspace.
- Notes: Use hidden windows only for non-interactive helpers. The coding agent itself is interactive and must remain visible/attached as appropriate for the harness.

### Milestone 5: Preserve And Improve Standalone Fallback

- Status: COMPLETED
- Purpose: Ensure speed improvements do not turn managed workspaces into toolkit-dependent projects.
- Exit Criteria: A moved workspace can still create its own runtime and execute research commands without the original toolkit, and setup reruns do not repeat browser installation unnecessarily.

#### Task 5.1: Update Workspace-Local Setup For Conditional Provisioning

- Status: COMPLETED
- Objective: Make `runtime/workspace/setup.sh` and `runtime/workspace/setup.ps1` reliable portable fallbacks with fast idempotent reruns.
- Steps:
  1. Preserve Python and uv prerequisite checks.
  2. Sync the workspace-local environment from the bundled lockfile.
  3. Create a small workspace-safe browser/runtime probe separate from the toolkit cache-lifecycle helper, and bundle it through `runtime/workspace-manifest.json`.
  4. Install only missing required browser assets and verify a real launch.
  5. Print clear guidance distinguishing managed fast-path use from moved-workspace local setup.
  6. Preserve recovery for incomplete `.venv` directories.
- Validation: Setup unit tests pass for both root and runtime scripts; a copied-workspace smoke test runs setup twice and confirms the second run performs no browser reinstall.
- Notes: New workspace-visible helper files must be registered in `runtime/workspace-manifest.json`.

#### Task 5.2: Add Managed-To-Standalone Fallback Behavior

- Status: COMPLETED
- Objective: Handle incompatible or moved workspaces without hidden dependency on the creating toolkit.
- Steps:
  1. Detect runtime-key mismatch, missing runtime metadata, moved workspace, unavailable toolkit runtime, and Python/platform incompatibility before launching.
  2. Prefer a workspace-local environment only after a locked/check-only uv validation plus required import/browser probes succeed; directory existence alone is insufficient.
  3. In interactive mode, offer or perform the supported workspace-local setup according to the CLI contract.
  4. In non-interactive mode, fail deterministically unless an explicit setup flag authorizes provisioning.
  5. Return structured runtime-selection reasons and next actions.
- Validation: Integration tests cover each eligibility/fallback branch without network access by using prepared fake environments and command stubs.
- Notes: No fallback branch may silently use a mismatched environment.

#### Task 5.3: Verify Existing Workspace Compatibility

- Status: COMPLETED
- Objective: Ensure existing standalone workspaces remain valid and are not rewritten merely because the new launcher exists.
- Steps:
  1. Add tests using a pre-feature standalone workspace fixture.
  2. Verify direct workspace-local setup and script commands continue to work.
  3. Verify `calixto open` does not add harness mirrors or metadata to an existing workspace unless the user explicitly invokes a preparation path that authorizes those additions.
  4. Verify an older post-feature workspace continues using its retained runtime key after the toolkit prepares a newer current key.
  5. Verify toolkit installation/update still leaves existing workspace contents unchanged.
- Validation: Byte-level workspace preservation assertions pass across toolkit update tests, and legacy standalone fixture commands remain functional.
- Notes: This task does not add an old-workspace migration command.

### Milestone 6: Documentation, Packaging, And User-Facing Consistency

- Status: COMPLETED
- Purpose: Make the streamlined flow the obvious default while retaining accurate advanced and portability instructions.
- Exit Criteria: All root, runtime, adapter, packaging, and changelog surfaces describe the same command, runtime modes, update policy, and fallback behavior.

#### Task 6.1: Update Root Product And Quick-Start Documentation

- Status: COMPLETED
- Objective: Replace the multi-command normal workflow with the one-command flow in primary documentation.
- Steps:
  1. Update `README.md`, `AGENTS.md`, and the relevant `PHILOSOPHY.md` implementation guidance with `calixto research` and the managed-runtime boundary.
  2. Explain `--agent`, `--name`, `--path`, `--agent none`, `--json`, `calixto open`, runtime inspection/pruning, update-check controls, and missing-agent behavior.
  3. Explain that root setup prepares the managed runtime once.
  4. Preserve the lower-level `init_workspace.py` documentation for automation and maintenance use.
  5. State clearly that existing workspaces are not updated in place.
- Validation: Manual inspection and `rg` confirm the primary quick start no longer requires manual create, `cd`, workspace setup, and launch steps for the managed case.
- Notes: Keep platform examples for Windows and Unix where command syntax differs.

#### Task 6.2: Update Runtime And Adapter Documentation

- Status: COMPLETED
- Objective: Make workspace-local and harness-specific guidance match generated behavior.
- Steps:
  1. Update `runtime/workspace/AGENTS.md` to explain managed and standalone runtime modes without requiring toolkit context during research.
  2. Update `adapters/opencode` and `adapters/claude-code`, add a Codex adapter, and update the existing Cursor adapter to distinguish verified Cursor Agent CLI support from editor-only `cursor` folder opening.
  3. Document canonical skills versus generated harness-native mirrors.
  4. Ensure generated workspace instructions still work after the workspace is copied away.
  5. Remove stale wording that says generic skill loaders cannot discover the skills when the selected harness mirror now enables discovery, while retaining direct canonical-skill guidance for `--agent none` and unsupported harnesses.
- Validation: Generate one workspace per guaranteed harness and inspect all referenced files and paths; run `python tests/validate_skills.py`. If Cursor Agent support passes its gate, include its generated workspace too.
- Notes: Harness-specific claims must be verified against current official documentation during implementation.

#### Task 6.3: Update Requirements, Installer Documentation, And Changelog

- Status: COMPLETED
- Objective: Reconcile formal requirements and installation behavior with the new startup target.
- Steps:
  1. Update `requirements.md` workspace lifecycle, agent adapters, setup-time target, and portability sections.
  2. Update `docs/installer.md` to explain managed-runtime preparation and `--skip-deps` consequences.
  3. Update installer completion messages to show the one-command research flow.
  4. Add a `CHANGELOG.md` entry covering the CLI, managed runtime, harness discovery, and conditional browser setup.
  5. Update package entry-point tests or build metadata so the `calixto` command ships in installed and archive-based toolkit roots.
- Validation: Build/install smoke tests confirm the installed toolkit exposes `calixto`, and docs contain no contradictory normal-flow instructions.
- Notes: Preserve the repository-default-branch and installer-provenance behavior already implemented.

### Milestone 7: Integrated Validation, Cleanup, And UX Acceptance

- Status: COMPLETED
- Purpose: Verify the complete user journey, preserve only intentional artifacts, and measure the practical startup improvement.
- Exit Criteria: Automated tests pass, real managed and portable flows work, warm startup performs no dependency/browser installation, docs match behavior, and the plan is reconciled to `COMPLETED`.

#### Task 7.1: Add End-To-End Creation And Launch Tests

- Status: COMPLETED
- Objective: Cover the complete orchestration path without requiring live harnesses or network access in CI.
- Steps:
  1. Install or invoke the built console entry point in a temporary toolkit root.
  2. Stub toolkit freshness, runtime preparation, browser probe, and harness process launch deterministically.
  3. Execute `calixto research` and verify workspace contents, question, harness mirrors, runtime-key selection, child environment, and human/JSON output contracts.
  4. Execute `calixto open` against the created workspace and an older retained runtime key.
  5. Add failure-path coverage for stale toolkit update request, runtime mismatch, setup failure, missing harness, invalid JSON-plus-launch combination, launch failure, and existing workspace collision.
  6. Verify no partial workspace is created for pre-create failures and that post-create launch failures preserve the workspace.
- Validation: Targeted CLI/integration test modules pass on Windows and Unix-compatible CI paths.
- Notes: Live GitHub, browser downloads, and installed coding agents must not be required for deterministic CI.

#### Task 7.2: Run Real Managed And Portable Smoke Tests

- Status: COMPLETED
- Objective: Confirm the feature works outside mocks on representative Windows flows and, where available, Unix.
- Steps:
  1. Prepare the toolkit managed runtime from a clean or temporary installed root.
  2. Create a new workspace with `--agent none` and verify it has no workspace-local `.venv`.
  3. Run representative workspace commands through the managed environment, including `workspace_info.py show` and one deterministic cached search path.
  4. Reopen the workspace with `calixto open`.
  5. Launch OpenCode or another installed guaranteed harness and verify it opens at the workspace root with discoverable research skills.
  6. Copy the workspace outside the toolkit tree, run workspace-local setup, and execute the same representative commands.
  7. Rerun root and workspace setup and verify browser installation is skipped when the probe succeeds.
  8. Prepare a newer synthetic/current runtime key and verify the older workspace still selects its retained key.
- Validation: Record command outputs and timings in the decision log or implementation notes, then remove transient smoke-test artifacts.
- Notes: If Unix is unavailable locally, retain shell parser/unit coverage and document the unexecuted live platform check.

#### Task 7.3: Verify Startup Performance And No-Reinstall Behavior

- Status: COMPLETED
- Objective: Demonstrate that the warm normal path no longer performs per-workspace dependency or browser provisioning.
- Steps:
  1. Time workspace creation and preparation separately from external coding-agent startup.
  2. Confirm the managed path does not create `<workspace>/.venv`.
  3. Capture invoked subprocesses or logs proving no `uv sync` for the workspace and no browser install command on the warm path.
  4. Compare the result with the recorded pre-change benchmark.
  5. Treat timing as observational rather than a brittle CI threshold; the functional acceptance requirement is absence of repeated provisioning.
- Validation: Warm reference-machine results show workspace creation/preparation in seconds and logs show no workspace dependency sync or browser reinstall.
- Notes: External harness startup time is reported separately because Calixto does not control it.

#### Task 7.4: Cleanup Intermediate Artifacts

- Status: COMPLETED
- Objective: Remove implementation-only artifacts while retaining maintainable tests and documentation.
- Steps:
  1. Inspect the worktree for temporary workspaces, benchmark outputs, scratch scripts, captured logs, fake harness executables, one-off fixtures, and obsolete documentation fragments.
  2. Remove artifacts not required by the final implementation or regression suite.
  3. Preserve this plan, the decision log, durable tests, required fixtures, and user-facing docs.
  4. Verify unrelated user changes were not modified.
- Validation: `git status --short` and full diff inspection show only intentional final changes.
- Notes: The changelog update is required and must remain.

#### Task 7.5: Final Verification And Plan Reconciliation

- Status: COMPLETED
- Objective: Validate the integrated change and close the execution ledger accurately.
- Steps:
  1. Run the final verification commands below.
  2. Fix failures and rerun until all required checks pass or mark an explicit blocker.
  3. Review every task and milestone against its validation and exit criteria.
  4. Reconcile `README.md`, `AGENTS.md`, `PHILOSOPHY.md`, `requirements.md`, runtime docs, adapters, installer docs, changelog, and decision log with shipped behavior.
  5. Set completed tasks/milestones and the plan status to `COMPLETED` only after verification succeeds.
- Validation: All automated commands and manual checks in Final Verification pass, and the plan contains no stale status claims.
- Notes: Do not mark completion based only on unit tests; real generated-workspace and installed-root checks are required.

## Final Verification

Run the applicable commands from the toolkit root:

```text
python -m compileall scripts providers
python -m pytest tests/unit/test_setup.py -q
python -m pytest tests/unit/test_scripts.py -q
python -m pytest tests/unit/test_install.py tests/unit/test_install_windows.py -q
python -m pytest tests/unit/test_providers.py -q
python tests/validate_skills.py
python -m pytest -q
```

Add and run targeted test files introduced for:

- top-level CLI parsing and structured output;
- managed-runtime keying, locking, metadata, and lifecycle;
- runtime listing, reference scanning, and safe pruning;
- harness adapters and launch environment;
- harness-native skill generation;
- managed/local runtime selection;
- browser probe and conditional installation;
- installed-root command exposure;
- end-to-end create-and-launch orchestration.
- existing-workspace reopening through `calixto open`.

Required real smoke checks:

1. Run toolkit setup from a clean or temporary installed root and confirm the managed workspace runtime is prepared.
2. Rerun toolkit setup and confirm no browser reinstall occurs when the runtime probe succeeds.
3. Run:

   ```text
   calixto research "Smoke-test research question" --name streamlined-smoke --agent none
   ```

4. Confirm:
   - the workspace exists under the selected path;
   - `config.json.question` contains the exact question;
   - the standalone runtime bundle is complete;
   - the reported managed-runtime key matches the workspace dependency files and host/Python identity;
   - no workspace-local `.venv` was created;
   - `workspace_info.py show` runs through the managed environment.
5. Run `calixto open streamlined-smoke --agent opencode` or another installed guaranteed harness.
6. Generate and inspect one workspace for each guaranteed harness adapter.
7. Launch at least OpenCode and one other installed guaranteed harness from a generated workspace.
8. Copy a generated workspace outside the toolkit root, run its local setup, and execute `workspace_info.py show` plus a deterministic cached research command.
9. Simulate or perform a toolkit runtime change and confirm the old workspace still selects its retained runtime key.
10. Run `calixto runtime list` and a dry-run prune, confirming referenced/current keys are protected.
11. Confirm toolkit update/install tests leave existing workspace contents byte-identical.

Manual consistency checks:

- The primary docs present `calixto research` as the default workflow.
- Lower-level and automation docs retain `init_workspace.py`.
- The toolkit freshness check remains pre-create only.
- No generated workspace requires an absolute path back to the toolkit.
- A managed runtime is never used on a runtime-key or metadata mismatch.
- Older managed workspaces keep a usable retained runtime after toolkit updates.
- Harness-native skills match canonical workspace skills.
- Setup scripts no longer invoke forced browser installation on every run.
- Existing standalone workspaces remain usable and are not rewritten in place.

## Self-Check Evidence

The 2026-06-20 plan review verified these implementation assumptions against current repository and official tool behavior:

- Repository:
  - `scripts/init_workspace.py` remains the workspace factory and update-check entry point.
  - `runtime/workspace-manifest.json` drives generated workspace contents.
  - Root and workspace setup currently call `crawl4ai-setup`.
  - The locked Crawl4AI default path used by `Crawl4AIProvider` selects standard Playwright unless undetected mode is explicitly enabled.
  - `scripts._common.slugify` needs a non-ASCII/symbol-only fallback because its current short-result fallback can produce an invalid slug.
  - The current root `.gitignore` does not ignore a toolkit-root `.calixto/` directory.
  - Installer updates preserve `workspaces/` and unknown toolkit-local state, while setup may be skipped or declined during update.
- OpenCode:
  - Interactive TUI supports a project path and `--prompt`.
  - Project skills are discovered from `.agents/skills`, `.opencode/skills`, or `.claude/skills`.
  - Official references: `https://opencode.ai/docs/cli/` and `https://opencode.ai/docs/skills/`.
- Claude Code:
  - `claude "query"` starts an interactive session with an initial prompt.
  - Project skills use `.claude/skills/<name>/SKILL.md`.
  - Official references: `https://code.claude.com/docs/en/cli-reference` and `https://docs.anthropic.com/en/docs/claude-code/skills`.
- Codex:
  - Interactive CLI accepts `--cd <path>` and an optional positional prompt.
  - Repository skills use `.agents/skills/<name>/SKILL.md`.
  - Official references: `https://developers.openai.com/codex/cli/reference` and `https://developers.openai.com/codex/skills`.
- Cursor:
  - The locally installed `cursor` command is the editor launcher, not proof of Cursor Agent CLI availability.
  - Cursor Agent CLI support remains gated on verification of the separate current CLI contract.
  - Official references: `https://cursor.com/docs/cli/overview` and `https://cursor.com/docs/skills`.
- uv:
  - `UV_PROJECT_ENVIRONMENT` and `UV_NO_SYNC` are available in the installed uv command.
  - `uv tool install` normally installs a package's dependencies and therefore cannot be assumed to provide a lightweight launcher for the current root package.
  - The final global command-registration mechanism remains a bounded implementation decision with explicit tests and decision-log recording.

## Approval Gate

Implementation must not start until the user approves this plan.

After approval:

1. Set `Plan Status` to `APPROVED`.
2. Create `docs/streamlined-workspace-creation-decision-log.md`.
3. Set `Plan Status` to `IN PROGRESS` before the first implementation edit.
4. Keep task and milestone statuses current throughout execution.

## Plan Self-Check

- [x] Plan location follows the default location rule.
- [x] Plan status followed the required approval lifecycle before implementation.
- [x] Scope, non-goals, assumptions, and open questions are explicit.
- [x] Zero unanswered open questions remain.
- [x] Tasks are grouped into milestones because the plan has more than 10 tasks.
- [x] Every task has concrete steps and validation.
- [x] Every milestone has exit criteria.
- [x] Cleanup and final verification are included.
- [x] The plan includes a required changelog update.
- [x] The plan preserves the existing standalone workspace and update-check contracts.
- [x] The plan preserves fast reopening for older workspace snapshots after toolkit updates through retained content-addressed runtime keys.
- [x] Interactive TUI output and machine-readable JSON output are separated.
- [x] Guaranteed harness claims were checked against current official documentation; Cursor remains correctly gated.
- [x] Toolkit-root default path behavior is explicit and independent of caller working directory.
- [x] Concurrent runtime preparation, cache lifecycle, and safe pruning are covered.
- [x] The plan distinguishes deterministic CI coverage from live harness/browser smoke checks.
- [x] The plan avoids vague actions without concrete targets.
- [x] The plan can be executed by a coding agent without reading the original conversation.

## Execution Notes

- Read this plan completely before implementation.
- Preserve unrelated user changes in a dirty worktree.
- Use `runtime/workspace-manifest.json` for every new workspace-visible runtime helper.
- Keep the managed runtime outside generated workspaces and outside version-controlled files.
- Never point uv at the shared environment without disabling synchronization on the workspace execution path.
- In `--json` mode, keep stdout to one result object and send prompts/progress to stderr or the controlling terminal. In interactive launch mode, use human console output and allow the attached harness to own the terminal streams.
- Verify harness CLI details against current official documentation at implementation time because these interfaces are externally maintained and may change.
- Update the decision log when implementation changes a contract, not only after code is complete.
