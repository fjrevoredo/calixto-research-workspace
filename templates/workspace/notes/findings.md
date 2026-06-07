# Findings

Extracted facts with finding IDs. Each finding MUST reference at least one source ID.

## Format

```markdown
## FND_ID
**Source:** SRC_ID
**Fact:** The fact statement goes here.
**Quote:** "Optional direct quote from the source."
**Confidence:** high|medium|low
```

Replace FND_ID with the next finding number, padded to 3 digits (e.g. `fnd001`). Replace SRC_ID with a source ID like `src001`.

Multiple sources can be cited by comma-separating the IDs:

```markdown
## FND_ID
**Source:** SRC_ID, SRC_ID
**Fact:** ...
**Confidence:** medium
```

## Example

```markdown
## fnd001
**Source:** src001
**Fact:** Python 3.11 added asyncio.TaskGroup for structured concurrency.
**Quote:** "TaskGroup provides a clean way to run tasks as a unit."
**Confidence:** high
```
