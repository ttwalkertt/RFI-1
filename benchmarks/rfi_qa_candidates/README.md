# Candidate benchmark cases for independent RFI QA

This directory contains an **oversized candidate pool**, not a selected benchmark. It models the
smallest repeatable version of an evidence-grounded RFI workflow: a question, governed evidence,
an investigator's submitted answer, and an independently defensible QA reference result.

The pool is intentionally synthetic. It does not contain, inspect, imitate, or optimize the current
RFI QA implementation, prompts, traces, or outputs. It must not be divided into calibration and
validation sets here.

## Files

- `candidate_cases.jsonl` — one candidate case per JSON line.
- `fixtures.json` — compact synthetic evidence fixtures referenced by the cases.
- `case.schema.json` and `fixture.schema.json` — machine-readable JSON Schemas.
- `validate_candidates.py` — standard-library structural and cross-reference validation.
- `coverage-analysis.md` — capability, disposition, difficulty, and gap analysis.
- `borderline-review.md` — four quarantined candidates requiring explicit human acceptance or
  rejection.

Run validation from the repository root:

```bash
python3 benchmarks/rfi_qa_candidates/validate_candidates.py
```

## Execution model

An executor resolves `case.fixture_id` against `fixtures.json` and gives the QA reviewer only:

1. `investigation_question`;
2. `answer_requirements`;
3. the resolved fixture's `authority` and `records`; and
4. `submitted_answer`.

The executor withholds `reference_qa`, `adjudicability`, pair metadata, case titles, and this README
from the reviewer. After review, the harness may compare the reviewer's disposition and material
findings with `reference_qa`.

Every `fixture://...` locator is synthetic but stable inside this candidate version. A locator used
by a submitted answer or reference result must resolve to a record in that case's fixture.

## Disposition semantics

The reference dispositions apply to the investigator submission as reviewed against the stated
evidence authority:

- `supported` — the answer's material claims, qualifications, and required evidence mappings are
  supported. A properly calibrated answer that says a proposition cannot be determined is
  `supported` when that is what the evidence establishes.
- `defective` — one or more material answer defects can be demonstrated from the available
  evidence or from an explicit answer requirement. This includes directly contradicted facts,
  wrong calculations, status or identity errors, invalid source mappings, and express
  qualifications that were removed.
- `indeterminate` — the evidence cannot establish the answer's relevant proposition either way.
  The reference finding still identifies the investigator's improper certainty, attribution,
  imputation, completeness claim, or absence claim. It does not invent a contrary fact.

This distinction is deliberate. For example, a complete register can support a bounded negative
answer, while a zero-result search over a partial index cannot support archive-wide absence.

## Evidence authority

Each fixture declares one authority mode and an explicit absence policy:

- `complete` — the supplied records are the complete universe for the fixture's stated scope.
  Bounded presence, absence, earliest/latest, and exhaustive aggregation claims may be adjudicated.
- `partial` — the records are a sample or bounded search over an unenumerated universe. Failure to
  find a record cannot establish corpus-wide absence or completeness.
- `dimension_complete` — a named field or metadata dimension is completely represented, while a
  broader real-world proposition remains outside the fixture. For example, speaker-name metadata
  can be completely absent even though the real speaker has an identity.

The authority statement is part of the evidence available to QA. It must not be weakened or
silently expanded by the executor.

## Case schema

Top-level case fields are:

| Field | Meaning |
|---|---|
| `schema_version` | Candidate contract version; currently `1.0`. |
| `case_id` | Stable candidate ID in the form `RFIQA-NNN`. |
| `pair_id` | Shared ID for a matched non-supported case and clean control, or `null`. |
| `title` | Human catalog label; not reviewer input. |
| `fixture_id` | Foreign key to one fixture in `fixtures.json`. |
| `difficulty` | `atomic`, `cross_evidence`, `evidence_limits`, or `judgment_dependent`. |
| `adjudicability` | Whether the reference truth is objective or quarantined as borderline. |
| `investigation_question` | The question originally given to the investigator. |
| `answer_requirements` | Explicit output/evidence obligations that QA may enforce. |
| `submitted_answer` | Investigator text plus the evidence locators actually attached to it. |
| `reference_qa` | Hidden expected disposition, material findings, rationale, and exact evidence. |

`reference_qa.material_findings` is empty for supported controls. For each non-supported case, a
finding contains a stable `finding_id`, one defect class, the affected claim, a concise finding,
and exact locators. `reference_qa.adjudication_evidence` states the role and decisive fact of each
record needed to reproduce the reference result.

## Defect taxonomy

The taxonomy describes the material error mechanism rather than the topic of the synthetic record.
It is intentionally multi-label: a single submission can remove a population qualification and
also make an unsupported causal claim.

### Source value and computation

| Defect class | Definition |
|---|---|
| `numeric_mismatch` | Reported number differs from the authoritative source field. |
| `denominator_error` | Rate or share uses or calculates the denominator incorrectly. |
| `unit_mismatch` | Currency, scale, measurement, or magnitude unit changes the source value. |
| `aggregation_error` | Eligible, non-overlapping source values are rolled up incorrectly. |
| `duplicate_counting` | Multiple versions or observations of one governed identity are counted as distinct items. |

### Time, boundaries, status, and eligibility

| Defect class | Definition |
|---|---|
| `chronology_boundary_incorrect` | Wrong earliest or latest record is selected from a complete eligible set. |
| `chronology_basis_mismatch` | Repository, publication, ingestion, or other date is substituted for the requested event chronology. |
| `date_imputation` | A missing date is invented or interpolated from surrounding evidence. |
| `timezone_conversion_error` | A timestamp is assigned to the wrong required local calendar date or time. |
| `boundary_inclusion_error` | Explicit inclusive or exclusive interval endpoints are handled incorrectly. |
| `temporal_scope_mismatch` | A record outside the requested time period is included or an in-period record is excluded. |
| `status_mischaracterized` | Planned, proposed, draft, scheduled, or incomplete activity is reported as completed/final. |
| `record_eligibility_error` | A stated record inclusion rule is not applied to numerator, denominator, boundary, or synthesis. |
| `version_supersession_ignored` | A stale record is treated as current despite explicit correction or supersession. |

### Identity, attribution, provenance, and mapping

| Defect class | Definition |
|---|---|
| `entity_conflation` | Similar names or nearby records are substituted despite stable identity evidence. |
| `attribution_unsupported` | A statement is assigned to a person or role the retained evidence does not identify. |
| `ambiguous_reference_overresolved` | An unresolved pronoun, referent, or identity is selected as fact. |
| `provenance_authority_error` | Lower-authority, indirect, preliminary, or stale evidence is upgraded over the governing source. |
| `evidence_mapping_incorrect` | An attached locator does not support the material claim associated with it. |
| `evidence_mapping_missing` | An explicit requirement for a material claim locator is unmet. |

### Scope, qualifications, and epistemic calibration

| Defect class | Definition |
|---|---|
| `qualification_omitted` | A source's material population, condition, exception, or limitation is removed. |
| `claim_strength_overstatement` | Possibility, consistency, or limited evidence is restated as proof or exclusivity. |
| `causal_overstatement` | Association or before/after evidence is converted into a causal conclusion. |
| `insufficiency_miscalibrated` | Genuinely insufficient evidence is converted into a determinate conclusion. |
| `corpus_completeness_overstatement` | A partial or unenumerated evidence sample is declared complete. |
| `absence_overstatement` | A bounded or incomplete negative search is treated as proof of universal absence. |
| `false_absence` | Matching evidence is actually present, but the answer says it is absent. |
| `undefined_evaluation_criterion` | An evaluative category such as “substantial” or “near term” lacks a supplied boundary. |

### Whole-answer integrity

| Defect class | Definition |
|---|---|
| `internal_inconsistency` | Material claims within the submitted answer cannot all be true together. |
| `conflicting_evidence_omitted` | Available contrary evidence that changes the conclusion is excluded from the synthesis. |
| `quote_context_distortion` | Truncation, negation loss, or context removal changes a source statement's meaning. |
| `unsupported_claim` | A material proposition lacks support and is directly contradicted by governed evidence, without a more specific class. |

## Pairing and false-positive controls

The 62 objective candidates form 31 matched pairs. Each pair uses the same question, answer
requirements, and evidence fixture. One submission is a supported control; its mate is defective or
indeterminate. Pairing isolates the answer difference and helps measure both false acceptance and
invented-defect behavior. Pairs are catalog metadata only and must never be exposed to the reviewer.

The four `borderline` cases have no pair and set `human_review_required: true`. They are outside the
objective core unless separately accepted under the criteria in `borderline-review.md`.

## Versioning and selection boundary

These cases are candidates. Acceptance, rejection, deduplication, benchmark size, success
thresholds, and calibration/validation partitioning belong to a later independent process. If a
fixture, answer, or reference truth changes, assign a new benchmark version before comparing run
results across versions.
