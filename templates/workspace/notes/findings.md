# Findings

Extracted facts with finding IDs. Each finding MUST reference at least one source ID.

## Format

```markdown
## fnd_<NNN>
**Source:** src_<NNN>
**Fact:** The fact statement goes here.
**Quote:** "Optional direct quote from the source."
**Confidence:** high|medium|low
```

Replace `<NNN>` with the next three-digit number from the workspace counter.
Use only the canonical underscore form for findings and sources.

Multiple sources can be cited by comma-separating the IDs:

```markdown
## fnd_<NNN>
**Source:** src_<NNN>, src_<NNN>
**Fact:** ...
**Confidence:** medium
```

## Example

```markdown
## fnd_<NNN>
**Source:** src_<NNN>
**Fact:** Python 3.11 added asyncio.TaskGroup for structured concurrency.
**Quote:** "TaskGroup provides a clean way to run tasks as a unit."
**Confidence:** high
```
