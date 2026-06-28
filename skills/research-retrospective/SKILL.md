---
name: research-retrospective
description: Performs a user-mediated two-agent retrospective of a completed Calixto research workspace. Use when Agent B must independently audit Agent A's research, derive a case-specific but non-leading questionnaire from that adversarial report, pause while the user gives it to Agent A in the original research session, then synthesize the report, questionnaire, and returned answers into prioritized improvements for Calixto tooling, setup, runtime, skills, scaffold, audits, documentation, or product behavior.
---

# Research Retrospective

Run this developer-mode workflow from the Calixto toolkit root. This is a
maintainer meta-skill. Never bundle it into generated standalone workspaces.

## Roles and Handoffs

- **Agent A:** performs the original research in a workspace and remains
  available in that same research session.
- **Agent B:** starts from a separate clean session, performs the adversarial
  review, creates the questionnaire, and later writes the improvement proposal.
- **User:** transfers the questionnaire to Agent A's workspace/session and
  transfers Agent A's answers back to Agent B.

Do not collapse these roles. Agent B must not answer on behalf of Agent A, and a
fresh proxy agent is not an equivalent replacement for Agent A's original
session.

## Goal

Produce four durable artifacts:

1. `docs/<slug>-adversarial-report.md` - Agent B
2. `docs/<slug>-adversarial-questionnaire.md` - Agent B
3. `docs/<slug>-adversarial-questionnaire-answers.md` - Agent A, transferred by
   the user
4. `docs/calixto-research-workspace-improvement-proposal.md` - Agent B

The skill ends after artifact 4. Do not create an implementation plan or modify
Calixto based on the proposal unless the user asks in a later task.

## Read Before Starting

Read:

- root `AGENTS.md`;
- `PHILOSOPHY.md`;
- `requirements.md`;
- target workspace `AGENTS.md`;
- active workspace research skill;
- workspace transcript, configuration, sources, notes, and outputs;
- current toolkit code relevant to observed host-side behavior.

Load the stage reference only when entering that stage:

- Stage 1: `references/adversarial-report.md`
- Stage 2: `references/questionnaire-design.md`
- Stage 3: `references/improvement-synthesis.md`

Use the files under `assets/` only as structural starting points. Copy and
customize them; never overwrite the templates.

## Evidence and Mutation Boundary

Treat the research workspace as preserved evidence. Agent B must not mutate its
configuration, sources, notes, outputs, local skills, or transcript.

Write Agent B artifacts under `docs/`. Agent A may write the questionnaire
answers inside the research workspace after the user transfers the
questionnaire there. The user then transfers the answers back to `docs/`.

Preserve unrelated worktree changes. Do not clean, reset, or rewrite evidence.

## Workflow

### Stage 1 - Agent B Creates the Adversarial Report

Read `references/adversarial-report.md` completely.

Copy `assets/adversarial-report-template.md` to:

```text
docs/<slug>-adversarial-report.md
```

Perform a deep independent review of:

- whether the literal original question was answered;
- constraint handling and assumptions;
- process compliance;
- intermediate artifact creation and actual use;
- source integrity, quantity, quality, relevance, currency, and coverage;
- claim support, contradiction, fabrication, and missing citations;
- conclusion quality;
- failures, warnings, workarounds, and alternative execution paths;
- likely agent, skill, scaffold, script, runtime, setup, installer, harness,
  documentation, and test weaknesses;
- favorable behavior worth preserving.

Distinguish:

- mechanical traceability from semantic correctness;
- unsupported claims from deliberate fabrication;
- source existence from source reliability;
- evidence available during the research from later verification;
- symptoms from root-cause hypotheses.

Verify unstable decisive claims against dated primary or authoritative sources.
Inspect current code when the transcript indicates a tooling behavior. Do not
implement fixes.

Before completing Stage 1:

- verify all quantitative claims;
- inspect sources supporting material conclusions;
- reconstruct the transcript sequence;
- compare documented contracts with code;
- run a factual self-check and `git diff --check`.

### Stage 2 - Agent B Creates a Purpose-Built Questionnaire

Read `references/questionnaire-design.md` completely.

The questionnaire is derived from the completed adversarial report but must not
reveal that report's verdicts. The goal is to ask Agent A targeted questions
that independently surface evidence confirming, qualifying, or denying Agent
B's findings.

#### Build a Private Coverage Inventory

Agent B privately inventories every material:

- adverse finding;
- favorable finding;
- uncertainty or disputed conclusion;
- tooling/process incident;
- root-cause hypothesis;
- P0/P1 recommendation premise.

Map each inventory item to at least one questionnaire question. This mapping is
an Agent B self-check; do not expose the report verdict or expected answer in
the questionnaire.

#### Write Questions From Scratch

Copy `assets/adversarial-questionnaire-template.md` to:

```text
docs/<slug>-adversarial-questionnaire.md
```

Use only the template structure. Write all substantive questions from scratch
for this workspace and report.

Questions must:

- point Agent A to the exact decision, claim, artifact, warning, or session
  behavior that needs self-assessment;
- ask Agent A to reconstruct what it understood and knew at the time;
- require exact workspace or transcript evidence;
- ask Agent A whether the decision was correct and whether it would make the
  same decision now;
- ask for missing evidence, alternative explanations, and suggested Calixto
  improvements where relevant;
- include favorable areas so the process also identifies behavior to preserve.

Questions must not:

- state "the review found X";
- quote Agent B's verdict;
- disclose Agent B's supporting analysis;
- presume fault through loaded "why did you fail/ignore" wording;
- encode Agent B's proposed fix as the expected response;
- use a generic questionnaire unrelated to the adversarial report.

Example transformation:

```text
Private Agent B finding:
The primary recommendation appears to violate the hard budget.

Question shown to Agent A:
Re-read the original price wording and the final recommendation. How did you
classify the price requirement during the session? Using only evidence
available then, did every primary recommendation satisfy it? Explain whether
you would preserve or change that decision now.
```

The questionnaire must instruct Agent A to write:

```text
<slug>-adversarial-questionnaire-answers.md
```

inside the research workspace.

#### Stop for User Handoff

After writing the questionnaire, stop and report:

```text
Awaiting Agent A questionnaire answers
```

The user then:

1. copies/moves the questionnaire into the research workspace;
2. resumes Agent A's original research session;
3. asks Agent A to answer the questionnaire;
4. copies/moves the answers to
   `docs/<slug>-adversarial-questionnaire-answers.md`;
5. resumes Agent B.

Agent B must not spawn a substitute respondent, answer the questions itself, or
continue to Stage 3 without the returned Agent A answers.

### Stage 3 - Agent B Validates and Synthesizes

Read `references/improvement-synthesis.md` completely.

Require:

- `docs/<slug>-adversarial-report.md`;
- `docs/<slug>-adversarial-questionnaire.md`;
- `docs/<slug>-adversarial-questionnaire-answers.md`;
- original workspace evidence;
- current toolkit code and documentation.

First verify:

- Agent A answered in the original research session;
- Agent A did not receive the adversarial report;
- the questionnaire did not disclose Agent B's conclusions;
- every required question is answered or records a limitation;
- the answers file is preserved unchanged after transfer;
- original reasoning, preserved evidence, and current self-assessment are
  distinguishable.

If integrity is uncertain, record it and ask the user whether to rerun the
handoff. Do not silently substitute another agent's response.

Copy `assets/improvement-proposal-template.md` to:

```text
docs/calixto-research-workspace-improvement-proposal.md
```

Triangulate:

- Agent B report evidence;
- Agent B questionnaire intent;
- Agent A answers and self-assessment;
- original workspace evidence;
- current code, tests, CLI help, and primary documentation.

Agent A's answer is evidence, not authority. Resolve disagreements against
preserved evidence.

Consider:

- broken features to fix;
- missing features or guardrails to add;
- useless, harmful, or false-confidence features to remove or demote;
- process and stopping-rule changes;
- skill and workspace-instruction changes;
- scaffold, schema, and artifact changes;
- source collection, quality, and semantic-verification changes;
- CLI, audit, structured-output, runtime, setup, installer, and harness changes;
- documentation, test, fixture, and golden-evaluation changes.

Every recommendation must include:

- concrete problem and evidence from the three artifacts;
- affected component and likely files;
- root cause;
- proposed behavior;
- expected speed, quality, reliability, or transparency benefit;
- downside and compatibility risk;
- acceptance criteria and tests;
- P0/P1/P2 priority;
- confidence and implementation effort.

When product policy is required, present two or three options and request a
user decision.

## Final Self-Check

Before handoff:

1. Confirm Agent B's report predates and is independent of Agent A's answers.
2. Confirm the questionnaire derives from the report but does not reveal its
   conclusions.
3. Confirm Agent A answered in the original research session.
4. Confirm the transferred answers are unchanged.
5. Trace every P0/P1 recommendation to evidence.
6. Separate root causes from symptoms and remove duplicates.
7. Identify recommendations based on one weak signal.
8. Check all `PHILOSOPHY.md` principles.
9. Verify this host-only skill is absent from
   `runtime/workspace-manifest.json` and generated workspaces.
10. Run:

```bash
python tests/validate_skills.py
python -m pytest tests/unit/test_scripts.py -q
git diff --check
```

Run broader tests if code changes accompany the skill.

## Quality Rules

- Lead with verified outcomes, not effort.
- Prefer exact paths, IDs, command output, and dates.
- Do not infer intent from incorrect claims.
- Do not treat artifact existence as proof of artifact use.
- Do not let caveats neutralize logically invalid recommendations.
- Do not automate semantic judgment merely to produce a green check.
- Do not generalize one symptom without a general mechanism or recurrence
  evidence.
- Keep current facts explicitly dated.
- Keep the questionnaire targeted but non-leading.

## Completion States

- **Awaiting Agent A answers:** report and questionnaire exist; answers have not
  been returned by the user.
- **Complete:** all four artifacts exist and the improvement proposal passed
  final self-check.
- **Blocked:** required evidence or handoff integrity is missing and prevents a
  defensible synthesis.

Do not mark the workflow complete after only the adversarial report or
questionnaire.
