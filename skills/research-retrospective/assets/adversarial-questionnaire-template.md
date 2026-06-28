# Adversarial Self-Assessment Questionnaire: `<workspace>`

## Instructions to Agent A

You performed the original research in this workspace. Re-examine your original
question, session transcript, sources, intermediate artifacts, final output,
warnings, and workarounds.

Write your answers to:

```text
<slug>-adversarial-questionnaire-answers.md
```

inside this research workspace.

Do not modify this questionnaire or other research artifacts.

For every answer:

- distinguish what you believed or knew during the original session from what
  you conclude now;
- cite exact workspace files, IDs, transcript events, or command output;
- state confidence;
- identify missing evidence;
- say whether you would preserve or change the original decision.

Use:

```markdown
### Q-NNN — <question title>

**Original-session reasoning**

...

**Evidence**

- `<workspace evidence>`

**Current self-assessment**

...

**Would you preserve or change the original decision?**

...

**Confidence:** High | Medium | Low

**Remaining uncertainty**

...

**Suggested Calixto improvement**

...
```

## Questions

### Q-001 — `<write a report-derived but non-leading question>`

`<Question text written specifically for this workspace and adversarial report.>`

<!-- Add all report-derived questions and remove every placeholder/comment. -->

## Final Self-Assessment

After answering all questions, summarize:

- decisions you would preserve;
- decisions you would change;
- evidence you used correctly;
- evidence you misused or did not collect;
- process or tooling behavior that helped;
- process or tooling behavior that hindered;
- the five Calixto improvements that would have helped you most.
