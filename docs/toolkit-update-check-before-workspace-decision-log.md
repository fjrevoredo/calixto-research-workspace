# Decision Log: Toolkit Update Check Before Workspace Creation

## Purpose

This log captures implementation decisions made while executing
`docs/toolkit-update-check-before-workspace-plan.md`.

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

## Decision 001: Use print-and-exit update guidance instead of in-process self-update

- **Date:** 2026-06-17
- **Task:** Task 5: Wire Update-On-Demand To The Existing Installer Contract
- **Decision:** When `init_workspace.py` determines the toolkit should be updated before creating a workspace, it prints the exact installer command for the current platform and exits without creating a workspace instead of attempting to update the running checkout in-process.
- **Rationale:** The running Python process depends on files under `scripts/` that the installer may replace. Avoiding in-process mutation keeps behavior predictable on both Windows and Unix, preserves the existing installer contract, and satisfies the plan's conservative fallback path.
- **Impact:** No direct installer invocation is added to `init_workspace.py`. Tests and docs focus on the structured "update first" exit flow and exact command generation.

## Decision 002: Use `git ls-remote --symref origin HEAD` plus local ancestry only

- **Date:** 2026-06-17
- **Task:** Task 3: Implement Default-Branch Freshness Check
- **Decision:** The freshness check discovers the remote default branch with `git ls-remote --symref origin HEAD` and compares commit ancestry only when the remote commit object is already present locally. It does not fetch additional history.
- **Rationale:** `git ls-remote` is enough to learn the latest default-branch commit without mutating the checkout. Avoiding a fetch keeps the check lightweight and side-effect free, which matches the plan's "before create" safety goal and preserves offline/non-network behavior as a warning path instead of a repository mutation.
- **Impact:** Behind counts and remote build numbers are reported when local history already contains the remote commit object; otherwise the check emits an explicit inconclusive state and continues unless stricter flags were requested.
