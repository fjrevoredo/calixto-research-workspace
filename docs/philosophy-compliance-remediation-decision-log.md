# Decision Log: Philosophy Compliance Remediation

## Purpose

This log captures implementation decisions made while executing
`docs/philosophy-compliance-remediation-plan.md`.

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

## Decision 001: Make harness mirror refresh additive by default and destructive only behind an explicit force flag

- **Date:** 2026-06-20
- **Task:** Task 1
- **Decision:** Harness mirror preparation will create missing mirror directories, leave byte-identical mirrors untouched, and preserve divergent mirrors by default. Replacing an existing divergent mirror requires an explicit force-style CLI option.
- **Rationale:** The canonical `skills/` directory is the workspace contract, while harness-native mirrors are discovery helpers. Defaulting to destructive replacement violates file ownership and breaks the philosophy's file-based, auditable model.
- **Impact:** `scripts/calixto.py` mirror generation will return explicit sync outcomes, tests will cover preserved custom edits and forced replacement, and workspace-facing docs will explain when users need an explicit refresh.

## Decision 002: Promote JSON mode to a stable top-level CLI contract instead of a research-only special case

- **Date:** 2026-06-20
- **Task:** Task 2
- **Decision:** `calixto research`, `calixto open`, `calixto runtime list`, and `calixto runtime prune` will all support an explicit `--json` mode with consistent success and error envelopes. Interactive harness launch remains incompatible with JSON mode.
- **Rationale:** The philosophy's no-silent-failures and agent-first requirements need a direct machine-readable interface. Agents should not depend on parsing prose from top-level orchestration commands.
- **Impact:** CLI handlers, parser definitions, and tests will be updated to emit one JSON object on stdout in JSON mode and keep human-readable output as a separate interactive path.

## Decision 003: Replace the checkout-bound shim with a context-discovering launcher

- **Date:** 2026-06-20
- **Task:** Task 3
- **Decision:** The installed `calixto` launcher will stop embedding one absolute toolkit-root path. Instead it will resolve the active toolkit root from the current working directory hierarchy or an explicit environment override, then delegate to `uv run --project <resolved-root> calixto ...`.
- **Rationale:** A single absolute-path shim lets one checkout silently steal command ownership from another. A context-discovering launcher preserves the documented `calixto research ...` entry point without hidden cross-checkout coupling.
- **Impact:** `scripts/install_calixto_shim.py`, setup docs, and tests will move from "install or refresh a root-bound shim" to "install a generic launcher that explains its scope and fallback behavior."
