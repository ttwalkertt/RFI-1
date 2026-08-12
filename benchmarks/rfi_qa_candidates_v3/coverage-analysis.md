# V3 coverage analysis

## Partition composition

| Partition | Pairs | Cases | Supported | Defective | Indeterminate | Fixtures |
|---|---:|---:|---:|---:|---:|---:|
| Calibration | 40 | 80 | 40 | 32 | 8 | 40 |
| Verification | 20 | 40 | 20 | 14 | 6 | 20 |
| Objective total | 60 | 120 | 60 | 46 | 14 | 60 |
| Quarantine | 0 | 6 | 0 | 0 | 6 | 6 |

The split uses the whole matched pair, meets the requested minimum exactly, and was accepted on the
first seeded draw. Calibration contains 33 complete, five dimension-complete, and two partial
fixtures. Verification contains 14 complete, four dimension-complete, and two partial fixtures.

## Taxonomy coverage

The objective corpus instantiates 30 defect classes twice in distinct evidence settings. The seeded
split yields:

- 28 distinct classes in calibration;
- 18 distinct classes in verification;
- 16 classes shared across both partitions;
- 12 calibration-only classes; and
- 2 verification-only classes.

Verification-only classes are a natural consequence of pair-level randomization, not hand-selected
challenge placement. They create limited zero-shot generalization pressure. Both partitions retain
all three reference dispositions, multiple authority modes, and atomic, multi-record, and
authority-boundary cases. No rerandomization was performed.

Aggregate class counts by partition are recorded in `split-manifest.json`; case-level verification
assignments are deliberately absent.

## Behaviors exercised

The corpus requires evidence discrimination across:

- exact numeric values, units, denominators, and additive totals;
- governed identity versus document/revision count;
- earliest/latest boundaries, event versus repository chronology, missing dates, time zones,
  inclusive/exclusive endpoints, and requested temporal scope;
- final/completed status, record eligibility, explicit correction, and source hierarchy;
- stable entity joins, anonymous attribution, ambiguous pronouns, and redacted identity;
- exact claim-to-locator mapping and explicit missing-mapping obligations;
- population/configuration qualifications and strength of inference;
- association versus causation and genuinely unresolved mechanisms;
- partial-corpus completeness and bounded-search absence;
- overlooked present evidence, whole-answer contradiction, contrary evidence, and altered quotation
  meaning; and
- supported controls for every non-supported submission.

Indeterminate reference truth is limited to cases where the fixture expressly lacks authority to
resolve the proposition: missing dates or identities, unresolved referents/causes, partial corpus
coverage, or bounded negative search. References do not assume an opposite fact.

## Why 60 pairs is reasonable

Thirty defect classes appear in two materially different evidence settings rather than through
simple name/date perturbation. The second instances change evidence shape or reasoning operation—for
example, denominator eligibility versus pure arithmetic, UTC conversion across opposite date
directions, stable identity across revisions versus amendments, and partial OCR versus date-bounded
body search.

The size permits a 40/20 pair split while keeping supported controls balanced and retaining
indeterminate cases in both partitions. It is an authored benchmark version, not a recommendation
for a universal final benchmark size.

## Quarantine and limitations

Six undefined evaluative terms are quarantined because their measurements are objective but their
category boundaries are not. They must not influence scored outcomes.

Still difficult to test objectively are material omissions in long open-ended narratives, adequacy
of open-ended counterevidence search, authority conflicts without an explicit hierarchy, severity
aggregation, and semantic equivalence of compressed or indirect paraphrase. Those require governed
criteria or separate human adjudication.
