# Decision Log: Streamlined Workspace Creation And Launch

## Purpose

This log captures implementation decisions made while executing
`docs/streamlined-workspace-creation-plan.md`.

## Entry Format

Each entry uses:

```markdown
## Decision NNN: <Short title>

- **Date:** YYYY-MM-DD
- **Task:** <Task name>
- **Decision:** <What was decided>
- **Rationale:** <Why this approach was chosen>
- **Impact:** <What this changes for code, tests, docs, or behavior>
```

## Current Entries

## Decision 001: Add one-command orchestration without replacing `init_workspace.py`

- **Date:** 2026-06-20
- **Task:** Task 1.1 / Task 1.2
- **Decision:** The new top-level `calixto` CLI will provide `research`, `open`, and runtime-management commands, while `scripts/init_workspace.py` remains the lower-level structured workspace-factory interface and source of truth for pre-create update checks.
- **Rationale:** The new UX needs a memorable entry point, but existing automation and maintainer workflows already depend on `init_workspace.py` and its JSON/error contracts. Reusing it avoids duplicate policy logic and preserves backward compatibility.
- **Impact:** Implementation focuses on refactoring reusable creation operations out of `init_workspace.py` and adding a separate orchestration CLI instead of rewriting the factory command.

## Decision 002: Use toolkit-local content-addressed managed runtimes keyed by workspace dependency bytes plus host identity

- **Date:** 2026-06-20
- **Task:** Task 1.1 / Task 1.3
- **Decision:** Managed runtimes will live under toolkit-local ignored state and will be keyed from the exact `runtime/workspace/pyproject.toml` bytes, the exact `runtime/workspace/uv.lock` bytes, operating system, architecture, and selected Python major/minor identity.
- **Rationale:** The fast path must be reproducible, safe across toolkit updates, and independent from the root developer `.venv`. Fingerprinting the bundled workspace dependency contract and host compatibility dimensions ensures that only exact-compatible runtimes are reused.
- **Impact:** New runtime lifecycle helpers, metadata files, inspection commands, and setup integration will revolve around this key and will preserve older keys for older workspaces.

## Decision 003: Keep canonical workspace skills portable and generate harness mirrors only as discovery helpers

- **Date:** 2026-06-20
- **Task:** Task 1.1 / Task 4.2
- **Decision:** The bundled `skills/` directory inside every workspace remains the canonical research-skill source, while harness-native directories such as `.agents/skills/` and `.claude/skills/` are generated mirrors for supported harness discovery.
- **Rationale:** The workspace contract is portability first. Canonical skills must remain usable after a workspace is copied away from the toolkit or opened without a supported harness. Harness-specific mirrors improve ergonomics without becoming the source of truth.
- **Impact:** Workspace initialization generates deterministic mirrors for selected supported harnesses, but `runtime/workspace-manifest.json` continues to bundle only the canonical workspace assets.

## Decision 004: Preserve standalone fallback through workspace-local setup instead of storing machine-local runtime state in workspace metadata

- **Date:** 2026-06-20
- **Task:** Task 1.1 / Task 1.3 / Task 5.2
- **Decision:** Managed-runtime selection stays derived from bundled workspace dependency files plus toolkit-local runtime metadata. Absolute managed-runtime paths and current machine-availability claims are not written into portable workspace files; moved or incompatible workspaces fall back to workspace-local setup.
- **Rationale:** The workspace must remain a standalone snapshot, not a thin wrapper around a specific toolkit checkout. Persisting machine-local runtime paths would produce stale, misleading state as soon as the workspace is copied or the toolkit root moves.
- **Impact:** `calixto open` and related runtime selection code will compute compatibility at launch time, while workspace-local `setup.sh` and `setup.ps1` remain the supported portable recovery path.

## Decision 005: Install a lightweight launcher shim instead of a second tool-specific environment

- **Date:** 2026-06-20
- **Task:** Task 2.4
- **Decision:** Toolkit setup installs a small user-level `calixto` shim under the user's local bin directory that delegates to `uv run --project <toolkit-root> calixto ...` instead of using `uv tool install` or another packaging path that would create a second heavy research environment.
- **Rationale:** The launcher should be easy to invoke after setup, but creating another Crawl4AI-capable environment just to expose one command would defeat the managed-runtime goal and slow installs unnecessarily.
- **Impact:** `setup.sh` and `setup.ps1` now install or refresh the shim, detect when the shim directory is not on `PATH`, and print the exact fallback command instead of claiming universal command availability.

## Decision 006: Replace forced browser bootstrap with a shared runtime probe

- **Date:** 2026-06-20
- **Task:** Task 2.3 / Task 5.1
- **Decision:** Both toolkit setup and workspace-local setup now verify the actual scraper/browser runtime through `scripts/runtime_probe.py` and run `python -m playwright install chromium` only when the probe reports a missing browser, instead of calling `crawl4ai-setup` on every rerun.
- **Rationale:** The locked `crawl4ai-setup` path forces repeated browser installation work. A direct runtime probe is idempotent, honest about the real browser requirement, and reusable across managed and standalone flows.
- **Impact:** Setup reruns no longer reinstall browser assets on the warm path, tests target the shared probe contract, and runtime probing is bundled into standalone workspaces.

## Decision 007: Keep Cursor launch support gated until the agent CLI contract is verifiable

- **Date:** 2026-06-20
- **Task:** Task 4.1
- **Decision:** Calixto documents Cursor as an editor-opening convenience only and does not expose it as a guaranteed launched harness because the locally observed `cursor` CLI remains the editor launcher surface and did not provide a distinct verified agent-launch contract.
- **Rationale:** The plan required a stable working-directory, prompt, and environment-inheritance contract before claiming Cursor Agent CLI support. The current local observation did not meet that bar, so exposing Cursor as equivalent to the guaranteed terminal agents would overstate support.
- **Impact:** Supported harness generation/launch remains `opencode`, `claude`, `codex`, and `none`, while Cursor adapter docs explicitly describe the limitation and the reason it remains gated.

## Decision 008: Launch resolved harness executables directly and wrap PowerShell-script CLIs on Windows

- **Date:** 2026-06-20
- **Task:** Task 4.1 / Task 7.2
- **Decision:** Calixto now launches the fully resolved harness executable path instead of the bare command name, and when the resolved launcher is a `.ps1` script on Windows it wraps it through `pwsh` or `powershell` with `-File`.
- **Rationale:** The live self-check showed that `shutil.which("opencode")` resolves to `opencode.ps1` on this Windows machine, but `subprocess.Popen(["opencode", ...])` does not execute that PowerShell script directly. Using the resolved path plus an explicit PowerShell host preserves the verified working-directory and prompt contract across Windows launcher surfaces.
- **Impact:** Windows harness launching now works for PowerShell-backed CLIs such as OpenCode, unit coverage explicitly checks `.ps1` launch wrapping, and harness execution no longer depends on shell-specific command resolution quirks.
