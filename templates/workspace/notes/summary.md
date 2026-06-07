# Summary

Synthesized insights with insight IDs. Each insight MUST reference at least one finding ID.

## Format

```markdown
## INS_ID
**Based on:** FND_ID, FND_ID
**Insight:** The synthesized conclusion goes here.
```

Replace INS_ID with the next insight number, padded to 3 digits (e.g. `ins001`). Replace FND_ID with a finding ID like `fnd001`.

Insights connect findings into higher-level claims. They are the bridge between raw extracted facts and the final report.

## Example

```markdown
## ins001
**Based on:** fnd001, fnd002
**Insight:** Structured concurrency simplifies error handling across many concurrent operations.
```
