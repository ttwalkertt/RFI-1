# Independent RFI QA benchmark v3

`rfi-qa-independent-v3.0.0` is a fresh synthetic reference-truth corpus for independent review of
evidence-grounded RFI investigation answers. It is benchmark data and validation infrastructure
only; it does not change RFI, MCP, investigator, QA runtime, scoring, or optimization behavior.

## Independence

V3 was authored without inspecting QA implementation, QA prompts, QA runtime outputs, calibration
or optimization ledgers, observed QA failures, QA performance, or prior benchmark case contents.
Only repository operating guidance and permitted benchmark schema, taxonomy, validator, authority,
and locator conventions informed the contract. `authoring-metadata.json` records this boundary.

## Layout

```text
benchmarks/rfi_qa_candidates_v3/
    calibration/cases.jsonl
    calibration/fixtures.json
    verification/               # held back and ignored after full validation
        cases.jsonl
        fixtures.json
    quarantine/cases.jsonl
    quarantine/fixtures.json
    case.schema.json
    fixture.schema.json
    taxonomy.json
    authoring-metadata.json
    split-manifest.json
    coverage-analysis.md
    review.md
    validate_candidates.py
```

Fixture storage is partition-local. Removing `verification/` removes verification questions,
answers, evidence, locators, labels, and expected findings. The root manifest retains only aggregate
verification provenance, coverage counts, pair-set digest, and file/corpus digests; it contains no
case-level verification truth.

## Composition

- 60 objective matched pairs / 120 objective cases;
- 60 supported, 46 defective, and 14 indeterminate objective cases;
- 40 calibration pairs / 80 cases;
- 20 held-out verification pairs / 40 cases;
- 6 separately quarantined judgment-dependent cases; and
- 30 objective defect classes, each instantiated twice before random partitioning.

Every objective pair shares one question, answer requirement, fixture, and authority boundary. One
member is supported and the other is defective or indeterminate. This tests both false acceptance
and invented defects while keeping the evidence problem fixed.

## Authoritative split

The matched pair is the indivisible unit. With seed `20260812`:

1. sort `R3P-001` through `R3P-060` lexicographically;
2. shuffle with Python `random.Random(20260812).shuffle` (MT19937);
3. assign the first 40 pairs to calibration; and
4. assign the remaining 20 pairs to verification.

The first split retained all three dispositions and broad class coverage in both partitions, so no
rerandomization or case movement occurred. The split is exactly two-thirds calibration and
one-third verification.

## Evidence contract

Each fixture has a stable `R3F-*` identity, an authority statement with its own
`rfiqa-v3://.../@authority` locator, and immutable evidence records with exact locators. Authority
modes are:

- `complete`: supplied records exhaust the declared evidence universe;
- `partial`: supplied records/search coverage are unenumerated, so corpus-wide absence and
  completeness claims are prohibited; and
- `dimension_complete`: a named metadata dimension is complete while a broader proposition remains
  unresolved.

For QA execution, provide only the question, answer requirements, resolved fixture authority and
records, and submitted answer. Withhold `reference_qa`, adjudicability, pair metadata, titles,
taxonomy labels, split metadata, and coverage analysis.

Disposition semantics:

- `supported`: material claims, qualifications, and explicit locator obligations are satisfied;
- `defective`: a material defect is demonstrable from the declared authority and evidence; and
- `indeterminate`: the submitted proposition cannot be established or refuted from available
  evidence. The reference finding identifies improper certainty without inventing the opposite.

## Quarantine

Six cases involving undefined terms such as material, frequent, substantial, adequate, prompt, and
near term are physically separate. They are not matched pairs and must not enter calibration,
verification, scoring, thresholds, or optimization feedback.

## Validation

With verification restored locally:

```bash
python3 benchmarks/rfi_qa_candidates_v3/validate_candidates.py --full
```

After verification is physically removed:

```bash
python3 benchmarks/rfi_qa_candidates_v3/validate_candidates.py --visible
```

Full mode checks schemas, IDs, fixture/locator resolution, finding references, taxonomy membership,
disposition invariants, pair symmetry and co-location, split replay, partition disjointness,
quarantine exclusion, manifest consistency, and partition/corpus digests. Visible mode validates
committed calibration/quarantine content and independently verifies the held-out assignment and
aggregate/digest commitments without requiring verification bytes.

This corpus defines no QA scoring thresholds and performs no QA or RBF execution.
