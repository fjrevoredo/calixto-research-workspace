# Improvement Synthesis

## Contents

1. Inputs and evidence hierarchy
2. Triangulation
3. Root-cause analysis
4. Recommendation design
5. Prioritization
6. Final-report requirements
7. Self-check

## 1. Inputs and Evidence Hierarchy

Require:

- independent adversarial review;
- report-derived questionnaire;
- Agent A's questionnaire answers from the original research session;
- original workspace evidence;
- current toolkit code and documentation.

Evidence priority:

1. preserved files, command output, and transcript events;
2. current code, tests, CLI help, and primary documentation;
3. reproducible current checks;
4. reviewer inference;
5. Agent A self-assessment.

Do not promote self-report above preserved evidence.

## 2. Triangulation

Build a matrix:

| Issue | Agent B evidence | Agent A answer | Agreement/conflict | Independent verification | Confidence |
| --- | --- | --- | --- | --- | --- |

Classify:

- **Confirmed:** multiple independent evidence paths agree.
- **Probable:** strong evidence with one unresolved detail.
- **Possible:** one credible signal requiring validation.
- **Rejected:** contradicted or based on contamination.

Record useful disagreements. They often reveal unclear contracts or misleading
tool output even when one factual interpretation is correct.

## 3. Root-Cause Analysis

Group symptoms under systemic causes. Example layers:

- hard constraints not represented in structured state;
- skill instructions depend on agent discipline;
- audit verifies references but not semantic support;
- quality metadata is non-actionable;
- runtime metadata and execution environment diverge;
- generated artifacts are too large to review;
- search defaults optimize source count rather than decision value.

For each root cause identify:

- affected workflows;
- recurrence likelihood;
- blast radius;
- current workaround;
- why existing tests did not catch it.

## 4. Recommendation Design

Consider additions, fixes, removals, and simplifications.

Recommendation categories:

- fix broken feature;
- add missing guardrail or capability;
- remove or demote harmful/low-value behavior;
- change process or stopping criteria;
- change skill or workspace instructions;
- change scaffold, schema, or artifact format;
- change source collection or quality classification;
- change audit or semantic verification;
- change CLI or structured output;
- change runtime, setup, installer, or harness behavior;
- change tests, fixtures, golden evaluation, or docs.

Each recommendation must provide:

```text
ID:
Priority:
Confidence:
Affected layer:
Problem:
Evidence:
Root cause:
Proposed change:
Likely files:
Expected benefit:
Risks/trade-offs:
Acceptance criteria:
Validation:
Effort:
Dependencies:
```

Include removal recommendations when a feature:

- creates false confidence;
- consumes substantial context without changing decisions;
- produces warnings users routinely dismiss;
- duplicates stronger evidence;
- encourages compliance theater rather than semantic review.

## 5. Prioritization

Use:

- **P0:** prevents materially incorrect, unsafe, destructive, or
  constraint-violating output.
- **P1:** materially improves research quality, reliability, traceability, or
  speed.
- **P2:** improves clarity, ergonomics, maintainability, or lower-frequency
  behavior.

Also rate:

- impact;
- recurrence likelihood;
- evidence confidence;
- implementation effort;
- compatibility risk;
- philosophy alignment.

Do not rank by ease alone.

## 6. Final-Report Requirements

The report must include:

- executive verdict;
- evidence and method;
- agreements and conflicts between Agent B's report and Agent A's answers;
- confirmed root causes;
- prioritized recommendations;
- features to remove or simplify;
- decisions requiring user policy;
- recommended sequencing;
- validation matrix;
- non-actions and rejected suggestions;
- residual uncertainty.

For policy choices, present two or three options with rationale and a recommended
default. Do not implement the policy in the report.

## 7. Self-Check

Verify:

- every P0/P1 item traces to evidence;
- no recommendation relies only on contaminated self-report;
- symptoms are not duplicated as separate root causes;
- proposed files exist or are clearly labeled as new;
- acceptance criteria are observable;
- validation covers Windows and standalone boundaries when relevant;
- recommendations preserve file-based state and workspace portability;
- host-only changes are not accidentally added to runtime bundling;
- current CLI and code assumptions were checked;
- the report distinguishes immediate fixes from longer-term redesign.
