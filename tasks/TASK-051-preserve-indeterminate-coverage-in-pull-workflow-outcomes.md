# TASK-051 — Preserve Indeterminate Coverage in Pull Workflow Outcomes

## Status

Done

## Objective

Correct the Pull Workflow outcome aggregation so that bounded discovery exhaustion is not presented or persisted as a conclusive `no_change` result.

A failure-free, zero-result acquisition run may still be inconclusive. When discovery stops because configured policy bounds were exhausted and coverage remains indeterminate, the workflow must preserve that indeterminate state through the domain result, API representation, and operator presentation.

## Problem Statement

The earnings-call transcript adapter can complete without retrieval or validation failures while reporting:

- `candidate_ids: []`
- `document_ids: []`
- `bounds_exhausted: true`
- a non-empty `exhausted_budget`
- `coverage: indeterminate`

The Pull Workflow currently maps a failure-free, zero-result engine run to `no_change` and emits the explanation:

> Source checkpoint indicates no new artifact.

That conclusion is incorrect when no checkpoint decision occurred and configured discovery bounds prevented complete coverage.

`no_change` is a conclusive outcome. Policy exhaustion with indeterminate coverage is not.

## Required Outcome Semantics

The implementation must preserve these distinctions:

### No change

Use `no_change` only when the system has conclusive evidence that no new artifact exists, including a genuine source-checkpoint decision or another explicitly supported complete-discovery result.

### Indeterminate

Use the repository's canonical domain representation for an inconclusive acquisition result when configured discovery bounds prevent a complete determination.

Signals requiring indeterminate treatment include, as applicable to the existing contracts:

- `bounds_exhausted: true`
- a non-empty `exhausted_budget`
- `coverage: indeterminate`

Do not introduce a UI-only status or an adapter-specific exception. The state must originate at the workflow/domain aggregation boundary and propagate consistently.

### Failure

Reserve failure outcomes for actual retrieval, parsing, validation, adapter, persistence, or workflow failures.

Policy exhaustion alone is not a retrieval failure.

## Scope

### In scope

- Review and correct Pull Workflow aggregation of failure-free, zero-result engine results.
- Identify and use the canonical existing domain outcome for indeterminate or incomplete coverage.
- Add or revise the domain outcome only if the repository has no suitable representation, with all affected contracts updated consistently.
- Ensure persisted run/result state retains the distinction between conclusive `no_change` and indeterminate coverage.
- Ensure API serialization exposes the correct outcome.
- Ensure operator summary and detail presentation describe the actual cause.
- Prevent checkpoint-specific text unless a checkpoint decision actually occurred.
- Add focused regression coverage for the outcome matrix defined below.
- Update narrowly affected operator help or contract documentation where necessary.

### Out of scope

- Increasing or removing discovery budgets.
- Changing `max_links_per_page` or other acquisition policy defaults.
- Altering transcript discovery strategy, ranking, parsing, or candidate validation.
- Treating policy exhaustion as a retrieval failure.
- Broad redesign of Pull Workflow status taxonomy unrelated to this defect.
- General operator-console visual redesign.
- Changes to source-registry, artifact-retention, provenance, or checkpoint semantics beyond the incorrect aggregation and presentation.

## Required Invariants

The task must preserve:

- TASK-048A's requirement that policy exhaustion remains indeterminate.
- Existing successful artifact acquisition behavior.
- Existing genuine checkpoint-based `no_change` behavior.
- Existing retrieval, parsing, validation, and persistence failure behavior.
- Adapter diagnostics, including exhausted-bound and coverage evidence.
- Immutable artifact and provenance contracts.
- Source checkpoint behavior and persistence.
- Outcome consistency across the domain model, persistence, API, and operator UI.

## Outcome Precedence

The implementation must define and test deterministic precedence when multiple signals are present.

At minimum:

1. A genuine operational failure remains a failure.
2. A successful artifact acquisition remains an acquisition success.
3. A zero-result run with indeterminate coverage or exhausted discovery bounds must not become `no_change`.
4. `no_change` requires affirmative conclusive evidence.
5. A generic absence of failures is not, by itself, evidence of complete coverage.

If existing repository contracts require a different ordering, document the reason and demonstrate that policy exhaustion cannot be collapsed into `no_change`.

## Operator Presentation Requirements

For an indeterminate result, the operator-facing summary must make clear that:

- no new artifact was acquired;
- discovery did not establish that no artifact exists;
- configured discovery bounds were exhausted or coverage remained indeterminate.

The presentation must not state or imply:

- that a source checkpoint determined there was no new artifact;
- that discovery completed comprehensively;
- that the source definitively contained no new artifact;
- that policy exhaustion was a transport or retrieval failure.

The detailed diagnostic payload may remain available, but the human-readable summary must be accurate without requiring the operator to inspect raw JSON.

## Required Tests

Add focused regression tests covering at least:

1. **Checkpoint-based no change**
   - zero candidates;
   - a genuine checkpoint decision;
   - conclusive `no_change`;
   - checkpoint-specific explanation is present.

2. **Bound-exhausted indeterminate result**
   - zero candidates;
   - `bounds_exhausted: true`;
   - non-empty `exhausted_budget`;
   - `coverage: indeterminate`;
   - outcome is not `no_change`;
   - checkpoint-specific explanation is absent.

3. **Complete discovery with no artifact**
   - zero candidates;
   - complete or otherwise conclusive coverage;
   - no operational failure;
   - expected conclusive outcome is preserved.

4. **Operational failure**
   - genuine retrieval, parsing, validation, adapter, persistence, or workflow failure;
   - failure outcome remains unchanged;
   - policy exhaustion is not substituted for that failure.

5. **Mixed diagnostic precedence**
   - zero candidates with both failure-free execution and an indeterminate coverage signal;
   - indeterminate state takes precedence over generic zero-result mapping.

6. **Cross-layer representation**
   - persisted result, API payload, and operator presentation agree on the outcome;
   - no layer reclassifies indeterminate coverage as `no_change`.

7. **Regression protection**
   - successful artifact acquisition remains unchanged;
   - genuine checkpoint-based `no_change` remains unchanged.

## Review Actions

The implementation review must explicitly inspect:

- the Pull Workflow branch that currently maps failure-free, zero-result engine runs;
- the canonical domain outcome/status definitions;
- persistence and serialization of pull-source outcomes;
- operator summary and detail composition;
- all consumers that assume `no_change` is the only non-failure zero-result outcome;
- whether tests assert semantics rather than only display strings.

The review must confirm that the correction is implemented at the appropriate aggregation boundary and is not limited to the earnings-call transcript adapter or a UI text substitution.

## Verification Package

Provide a complete verification report containing:

- root-cause summary;
- files changed and why;
- final outcome matrix;
- canonical indeterminate representation selected;
- evidence that TASK-048A's policy-exhaustion invariant is preserved;
- focused test commands and results;
- full repository validation command and result;
- API or serialization proof;
- operator presentation proof for both checkpoint-based `no_change` and bound-exhausted indeterminate results;
- confirmation that successful acquisition and genuine failure paths remain unchanged.

## Acceptance Criteria

TASK-051 is complete when:

- the reported earnings-call transcript scenario is no longer classified as `no_change`;
- policy-bound exhaustion remains explicitly indeterminate;
- checkpoint-specific language appears only when a checkpoint decision occurred;
- domain, persistence, API, and operator presentation agree;
- all required focused regressions pass;
- the full validation suite passes;
- the completed task is committed on the task branch with the verification evidence reported.
