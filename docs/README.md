# Documentation

This directory contains project documentation.

## Contents

| File | Purpose |
|---|---|
| `README.md` | (you are here) |
| `initial-implementation-plan.md` | The original implementation plan that drove the v0.1.0 build (6 milestones, 38 tasks) |
| `initial-implementation-plan-decision-log.md` | Decisions made during implementation that were not in the original plan |
| `philosophy-compliance-remediation-plan.md` | Remediation plan for restoring the streamlined CLI flow to the philosophy contract |
| `philosophy-compliance-remediation-decision-log.md` | Tactical decisions made while executing the philosophy remediation |
| `adr/001-choose-crawl4ai.md` | First Architecture Decision Record: why Crawl4AI is our scrape backend |

## ADRs

Architecture Decision Records (ADRs) capture significant design choices with their context, decision, and consequences. They follow the pattern:

```markdown
# ADR NNN: <Title>

## Status
Accepted / Proposed / Superseded

## Context
What was the situation?

## Decision
What did we decide?

## Consequences
What follows from this decision?

## Alternatives Considered
What else did we look at? Why didn't we pick them?

## References
Links to related code, docs, or external resources.
```

To create a new ADR, copy `docs/adr/001-choose-crawl4ai.md` to `docs/adr/NNN-<short-title>.md` and fill in the sections.

## Decision Log

The decision log captures smaller, tactical implementation choices that don't warrant a full ADR. See `initial-implementation-plan-decision-log.md` and `philosophy-compliance-remediation-decision-log.md` for the format and current examples.

## See Also

- [`../PHILOSOPHY.md`](../PHILOSOPHY.md): guiding principles
- [`../AGENTS.md`](../AGENTS.md): entry point for coding agents
- [`../requirements.md`](../requirements.md): full specification
