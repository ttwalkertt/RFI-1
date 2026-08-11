# RFI QA independent v2 coverage analysis

## Composition and split

| Partition | Pairs | Cases | Supported | Defective | Indeterminate | Fixtures |
|---|---:|---:|---:|---:|---:|---:|
| Calibration | 22 | 44 | 22 | 19 | 3 | 22 |
| Held-out validation | 14 | 28 | 14 | 10 | 4 | 14 |
| Objective total | 36 | 72 | 36 | 29 | 7 | 36 |
| Quarantine | 0 | 4 | 0 | 1 | 3 | 4 |

The split uses 22/36 = 61.1% of pairs for calibration and 14/36 = 38.9% for held-out validation.
All pair members and their one fixture are co-located. No fixture crosses a partition boundary.

The first fixed-seed split retained all three objective dispositions in each partition:

- calibration: 22 supported, 19 defective, 3 indeterminate;
- validation: 14 supported, 10 defective, 4 indeterminate.

No rerandomization or class-driven case movement occurred.

## Defect-class coverage

The 72 objective cases exercise 31 distinct defect classes through 38 material findings. The only
taxonomy class absent from objective scoring is `undefined_evaluation_criterion`, which is confined
to quarantine by design.

Calibration contains 22 classes. Held-out validation contains 15 classes. Six classes occur in both
partitions:

- `chronology_boundary_incorrect`;
- `claim_strength_overstatement`;
- `denominator_error`;
- `evidence_mapping_incorrect`;
- `provenance_authority_error`; and
- `qualification_omitted`.

Validation also retains nine classes not instantiated in calibration, providing genuine
generalization pressure without selection based on QA behavior. Calibration retains 16 classes not
present in validation. The aggregate per-partition class counts are authoritative in
`split-manifest.json`; no case-level validation mapping is exposed there.

## Capability coverage

The objective corpus covers the following evidence-discrimination behaviors:

- exact source fidelity: numbers, units, denominators, additive totals, and stable field values;
- chronology: first/latest boundaries, effective versus repository dates, fiscal periods,
  half-open intervals, missing dates, and time-zone conversion;
- record governance: stable entity identity, duplicate versions, eligibility status, current versus
  superseded versions, proposed versus final actions, and source hierarchy;
- evidence mapping: true claims with wrong locators and true claims missing explicitly required
  locators;
- whole-answer synthesis: internal contradiction, omitted contrary outcomes, distorted conditional
  speech, and present evidence falsely reported absent;
- scope and qualification: tested configuration, claims population, sample population, and limits
  on diagnostic exclusion;
- authority boundaries: partial archives, incomplete OCR coverage, anonymized speakers, redacted
  recipients, unresolved pronouns, and observational evidence incapable of establishing cause; and
- false-positive restraint through one supported control for every non-supported submission.

The cases use 29 complete, five dimension-complete, and two partial objective fixtures. This keeps
open-world limitations explicit rather than forcing every absence or boundary question into the
same closed-corpus model.

## Why the reference truth is low-disagreement

Every objective case is resolvable through one or more of:

- an exact governing source field;
- an explicit arithmetic operation;
- a complete eligible set with a named chronology or identity key;
- express correction, status, population, or source-authority language;
- an explicit answer mapping requirement; or
- a declared missing/partial evidence boundary that forbids imputation or universal absence.

Indeterminate cases do not assert the opposite of the submitted answer. They identify that the
submitted proposition could be true or false in the world but cannot be decided from the available
authority.

## Quarantine rationale

The four quarantined cases test terms or standards that lack an objective governing boundary:

- whether a 12-day delay is “material”;
- whether three alarms in 90 days is “frequent”;
- whether 98% field completion is sufficient for operational use; and
- whether upgrading a layered perception note to direct speech is necessarily material under an
  unstated attribution policy.

They remain useful authoring candidates but must not influence optimization or held-out scoring.

## Remaining hard-to-objectify behaviors

Important behaviors not made primary scoring cases include:

- material omissions in long narrative answers where no exhaustive claim obligation exists;
- stopping adequacy for open-ended counterevidence search;
- real corpus completeness inferred from acquisition operations rather than declared by a fixture;
- conflicts between sources with overlapping mandates and no explicit hierarchy;
- severity aggregation across several individually minor defects;
- domain-dependent terms such as likely, effective, sufficient, or material without governed
  thresholds; and
- semantic equivalence of indirect speech, technical shorthand, or highly compressed paraphrase.

Those behaviors require either additional governing rules or separate human adjudication. Treating
them as objective here would weaken the benchmark rather than broaden it.
