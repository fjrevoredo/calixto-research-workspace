# Report-Derived Questionnaire Design

## Objective

Agent B creates a workspace-specific questionnaire from its completed
adversarial report. The questionnaire is given by the user to Agent A in the
same session that performed the original research.

The report determines what must be questioned. The questionnaire must not
disclose Agent B's verdicts, evidence interpretation, or preferred fixes.

## Required Process

### 1. Build a Private Finding Inventory

Extract from the adversarial report:

- every material adverse finding;
- every favorable finding worth preserving;
- every uncertain or contested point;
- every observed tooling/process incident;
- every root-cause hypothesis;
- every premise supporting a P0/P1 improvement.

For each item record privately:

```text
Finding:
Report evidence:
Confidence:
What Agent A can clarify:
Neutral question IDs:
```

This inventory is a coverage mechanism for Agent B. Do not copy the finding,
verdict, or report evidence into the questionnaire.

### 2. Convert Findings Into Neutral Questions

Each question must target the underlying decision or evidence without revealing
the conclusion Agent B reached.

Good:

> Re-read the original price requirement and the final recommendation. How did
> you classify the price requirement during the session? Did each primary
> recommendation satisfy it using evidence available at the time? Would you
> preserve or change that decision now?

Bad:

> The review found that you violated the hard budget. Confirm or deny this.

Good:

> Inspect every source marked `used`. Which were directly opened during your
> session, and what evidence did each uniquely contribute?

Bad:

> Why did you mark two unread sources as used?

Questions should ask Agent A to:

- reconstruct original interpretation and decisions;
- cite transcript and workspace evidence;
- distinguish original reasoning from current self-assessment;
- state whether the decision was correct;
- identify missing evidence and alternative explanations;
- suggest improvements from the acting agent's perspective.

### 3. Tailor the Questionnaire

Do not use a fixed bank of generic questions as the final artifact. Use the
template only for headings and answer format.

Question areas should exist only when supported by the report. Examples:

- hard constraint handling;
- candidate or scope completeness;
- source review behavior;
- numerical or time-sensitive claims;
- intermediate artifact use;
- traceability versus semantic verification;
- warnings, failures, and workarounds;
- stopping criteria and context pressure;
- skill, scaffold, script, runtime, or setup friction;
- favorable behavior that should be retained.

### 4. Preserve Non-Bias

Do not include:

- “the adversarial report found...”;
- report verdicts such as failed, unsupported, or contradicted;
- report evidence that tells Agent A what conclusion to reach;
- proposed fixes framed as assumptions;
- loaded or accusatory wording;
- an answer scale designed around Agent B's classifications.

It is acceptable to point to exact artifacts, claims, commands, or transcript
events. Specificity is required; disclosure of Agent B's conclusion is not.

### 5. Require Structured Answers

For each question require:

- answer;
- evidence;
- what Agent A believed or knew during the original session;
- current self-assessment;
- confidence;
- remaining uncertainty;
- suggested correction or Calixto improvement where applicable.

Agent A must write the answers in a separate Markdown file inside the research
workspace. The original questionnaire remains unchanged.

## User-Mediated Handoff

Agent B does not execute the questionnaire.

After creating it:

1. Agent B stops.
2. User transfers it to the research workspace.
3. User resumes Agent A's original session.
4. Agent A writes the answers file.
5. User transfers the answers to Agent B's `docs/`.
6. Agent B resumes synthesis.

If Agent A's original session is unavailable, the workflow is blocked unless
the user explicitly approves a reconstruction by another agent. Such a
reconstruction must be labeled and is not equivalent to Agent A self-assessment.

## Coverage Self-Check

Before handoff, Agent B verifies privately:

- every material report finding maps to at least one question;
- favorable findings are represented;
- no question reveals the expected answer;
- no generic question lacks a report-derived reason;
- Agent A can answer using the workspace and original session context;
- the output path is clear;
- the questionnaire contains no link or path to the adversarial report.
