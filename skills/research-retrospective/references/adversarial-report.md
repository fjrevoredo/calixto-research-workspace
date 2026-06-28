# Adversarial Workspace Report

## Contents

1. Evidence boundary
2. Review sequence
3. Required analyses
4. Claim and source classification
5. Tooling and process diagnosis
6. Actionability standard
7. Final self-check

## 1. Evidence Boundary

Review the completed workspace as preserved evidence. Load:

- original question and scope from `config.json`;
- workspace-local `AGENTS.md` and active skill;
- full session transcript;
- `sources/index.json` and relevant source files;
- findings, gaps, summary, report, bibliography, citation-check, and other
  outputs;
- current toolkit code for commands or behavior observed in the transcript;
- current primary external sources only when a decisive claim is time-sensitive.

Do not use later reviews as evidence. Do not silently repair or rerun the
research before judging what the original process produced.

## 2. Review Sequence

### A. Reconstruct the Session

Build a factual timeline:

- start and end time;
- instruction and skill loading;
- each search query and result count;
- each source-read action;
- triage and review-state changes;
- findings, insights, and report writes;
- audits, failures, warnings, retries, and workarounds;
- final response and claims.

Distinguish actions shown in the transcript from inferred work.

### B. Reconstruct the Decision

Extract:

- hard constraints;
- preferences;
- unknown variables;
- candidate set;
- eligibility rules;
- evidence used for each finalist;
- stopping criteria;
- final decision rule.

Check whether the final answer solved the literal question or a modified one.

### C. Verify the Evidence Chain

For each material report claim:

```text
report claim
  -> cited src_NNN
  -> finding fnd_NNN
  -> source passage and metadata
  -> semantic support status
```

Mechanical validity is necessary but insufficient.

## 3. Required Analyses

### Answer Quality

Determine:

- whether the original question was answered directly;
- whether hard constraints were met;
- whether assumptions were explicit;
- whether the conclusion was proportional to evidence;
- whether caveats invalidate or materially qualify the recommendation.

### Process Compliance

Compare actual session behavior with:

- workspace `AGENTS.md`;
- active skill;
- script help and output contracts;
- documented audit and review-state rules.

Use a compliance matrix with `followed`, `partial`, `not followed`, or
`not applicable`.

### Intermediate Artifacts

For every artifact assess:

- created;
- structurally valid;
- actually used;
- semantically useful;
- consistent with upstream and downstream artifacts;
- completed rather than generated and abandoned.

### Source Quantity, Quality, and Coverage

Measure:

- total, used, discarded, pending, failed, and duplicate sources;
- unique decision-relevant evidence;
- source-type and domain diversity;
- current versus stale evidence;
- primary versus secondary evidence;
- coverage of credible alternatives;
- discard rate and search efficiency.

Do not equate source count with research depth.

### Claim Accuracy

Audit:

- recommendation claims;
- prices and availability;
- product or version identity;
- numerical benchmarks;
- regulatory and technical measurements;
- superlatives and market-wide claims;
- reliability and consensus claims;
- all conclusions dependent on unresolved gaps.

### Problems and Workarounds

List:

- tool errors;
- warnings;
- degraded modes;
- environment mismatches;
- scrape/search failures;
- missing capabilities;
- manual workarounds;
- alternative tools or commands used;
- silent or misleading output.

## 4. Claim and Source Classification

Classify claims as:

- **Supported:** the cited evidence supports the complete claim.
- **Supported with caveat:** core claim is supported but scope, currency,
  methodology, or applicability is limited.
- **Partially supported:** only some clauses are supported.
- **Unsupported:** no cited evidence supports the claim.
- **Contradicted:** preserved or authoritative evidence conflicts with it.
- **Not verifiable:** required evidence is absent.

Classify sources as:

- primary or official;
- independent controlled evidence;
- commercial or retailer;
- reseller or affiliate;
- community, forum, or anecdotal;
- low-signal or failed;
- unclear provenance.

Do not label an incorrect agent claim as deliberate fabrication unless evidence
supports intent. Separately report:

- invented source records;
- nonexistent citations;
- false source claims;
- unsupported agent synthesis;
- unreliable third-party assertions.

## 5. Tooling and Process Diagnosis

Map each problem to one or more layers:

- agent reasoning;
- research skill;
- workspace instructions;
- scaffold or artifact schema;
- source collection and quality classification;
- audit or verification tooling;
- CLI or structured output;
- managed runtime and dependency setup;
- installer or update behavior;
- harness integration;
- documentation and tests.

Separate:

- symptom;
- immediate cause;
- systemic root cause;
- workaround;
- proposed prevention.

Do not recommend a product-wide change from one isolated symptom unless the
mechanism is general or additional evidence supports recurrence.

## 6. Actionability Standard

Every finding must state:

- evidence;
- impact;
- affected layer;
- concrete correction;
- validation method;
- confidence.

When multiple product behaviors are reasonable, present options and request a
user decision.

## 7. Final Self-Check

Before finalizing:

- verify all counts and quoted statuses;
- verify transcript line or event references;
- inspect all sources supporting decisive claims;
- date live verification;
- distinguish evidence available then from evidence found now;
- check external links;
- ensure recommendations do not exceed evidence;
- run Markdown and diff checks;
- reread the executive verdict after the detailed analysis and reconcile any
  mismatch.
