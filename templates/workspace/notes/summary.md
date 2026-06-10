# Summary

Synthesized insights with insight IDs. Each insight MUST reference at least one finding ID.

## Format

```markdown
## ins_<NNN>
**Based on:** fnd_<NNN>, fnd_<NNN>
**Insight:** The synthesized conclusion goes here.
```

Replace `<NNN>` with the next three-digit number from the workspace counter.
Use only the canonical underscore form for insight and finding IDs.

Insights connect findings into higher-level claims. They are the bridge between raw extracted facts and the final report.

## Example

```markdown
## ins_<NNN>
**Based on:** fnd_<NNN>, fnd_<NNN>
**Insight:** Structured concurrency simplifies error handling across many concurrent operations.
```
