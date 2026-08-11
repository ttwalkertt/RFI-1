# Independent RFI QA benchmark v2

`rfi-qa-independent-v2.0.0` is a freshly authored synthetic reference-truth corpus for evaluating
whether an independent QA reviewer can distinguish supported, defective, and genuinely
indeterminate RFI investigation answers.

This directory is benchmark infrastructure only. It does not change RFI, MCP, investigator, QA,
TASK-075 optimization, scoring, or runtime behavior.

## Independence boundary

The v2 cases and fixtures were authored without inspecting or using:

- `src/rfi/investigation_qa/`;
- TASK-074 or TASK-075 QA implementation;
- TASK-075 calibration ledgers or optimization results;
- QA runtime outputs;
- observed QA failures or performance; or
- the contents of the previous candidate cases as examples.

Repository inspection was limited to the operating model, the normative benchmark portions of the
active task ticket, and permitted benchmark schemas, taxonomy, validator, README, and design
conventions. The machine-readable attestation is in `authoring-metadata.json`.

## Committed and held-back structure

```text
benchmarks/rfi_qa_candidates_v2/
    README.md
    calibration/
        cases.jsonl
        fixtures.json
    validation/                 # held back; ignored and not committed
        cases.jsonl
        fixtures.json
    quarantine/
        cases.jsonl
        fixtures.json
    case.schema.json
    fixture.schema.json
    taxonomy.json
    authoring-metadata.json
    split-manifest.json
    coverage-analysis.md
    review.md
    validate_candidates.py
```

The calibration, validation, and quarantine partitions have disjoint fixture stores. No validation
fixture is duplicated into calibration. Removing `validation/` removes the held-out questions,
answers, labels, findings, evidence text, and locators needed to reconstruct those cases.

The repository `.gitignore` for this benchmark excludes `validation/`; held-out content must be
restored by an authorized benchmark custodian only for terminal validation. It must not be staged or
provided to the optimizing Codex.

## Corpus composition

- 36 objective matched pairs / 72 objective cases;
- 36 supported, 29 defective, and 7 indeterminate objective cases;
- 4 separate judgment-dependent quarantine cases;
- 40 synthetic fixtures total: 36 objective and 4 quarantined;
- 31 objective defect classes and one quarantine-only evaluative class; and
- 38 objective material finding expectations.

Every objective pair contains exactly one supported case and one defective or indeterminate case.
Both members share the same question, answer requirements, evidence fixture, and authority. Their
submitted answer payloads differ, allowing the pair to test both false acceptance and invented
defects without changing the evidentiary problem.

## Authoritative split

The matched pair is the indivisible randomization unit. The split was generated once with seed
`20260811`:

1. sort pair IDs `R2P-001` through `R2P-036` lexicographically;
2. shuffle using `random.Random(20260811).shuffle` (Python MT19937);
3. assign the first 22 pairs to calibration; and
4. assign the remaining 14 pairs to held-out validation.

This yields 61.1% calibration and 38.9% validation by pair. Both partitions contain supported,
defective, and indeterminate cases and retain broad defect-class coverage. The first split was
accepted; no rerandomization or case movement occurred.

`split-manifest.json` records aggregate counts, coverage, assignment-set digests, file digests, and
the corpus digest. It intentionally contains no validation case IDs, pair-ID list, case-level labels,
expected findings, questions, answers, evidence, or locators.

## Evidence and authority contract

Each partition's `fixtures.json` contains partition-local synthetic fixtures. A fixture supplies:

- a stable `fixture_id`;
- an authority object with its own stable `rfiqa-v2://.../@authority` locator;
- an authority mode;
- an explicit evidence scope and absence semantic; and
- one or more immutable evidence records with stable locators.

Authority modes are:

- `complete` — records are the complete evidence universe for the declared scope;
- `partial` — records or search coverage are an unenumerated subset, so universal absence and
  completeness claims are not permitted; and
- `dimension_complete` — a named metadata or evidence dimension is complete, while a broader
  real-world proposition remains unresolved.

The authority locator may appear in reference findings when the governing boundary, rather than a
record's substantive text, is the decisive evidence.

## Case and reference contract

For execution, resolve `case.fixture_id` in the same partition and provide the QA reviewer only:

1. `investigation_question`;
2. `answer_requirements`;
3. the fixture `authority` and `records`; and
4. `submitted_answer`.

Do not expose `reference_qa`, `adjudicability`, pair metadata, case title, split manifest, taxonomy
labels, or coverage analysis to the reviewer.

Reference dispositions mean:

- `supported` — material claims, qualifications, and explicit mapping obligations are satisfied;
- `defective` — a material factual, mapping, calculation, scope, provenance, or synthesis defect is
  demonstrable from the supplied authority and evidence; and
- `indeterminate` — the material proposition cannot be established or refuted from the governed
  evidence. The finding identifies improper certainty without manufacturing a contrary fact.

Each non-supported case includes stable material finding IDs, defect classes, affected claims,
exact evidence/authority locators, a concise rationale, and adjudication evidence. Supported cases
have no expected findings.

## Quarantine

`quarantine/` contains four judgment-dependent cases involving undefined materiality/frequency/use
thresholds or a context-dependent direct-attribution standard. They are not matched pairs and must
not participate in calibration, validation, primary scoring, thresholds, or optimization feedback.

## Validation

With the authorized held-out files restored locally:

```bash
python3 benchmarks/rfi_qa_candidates_v2/validate_candidates.py --full
```

After held-out files are physically absent, the calibration-visible repository remains verifiable:

```bash
python3 benchmarks/rfi_qa_candidates_v2/validate_candidates.py --visible
```

Full mode checks schemas, IDs, locator resolution, finding references, pair symmetry, pair
co-location, split replay, partition disjointness, fixture closure, disposition invariants,
taxonomy membership, quarantine exclusion, manifest aggregates, and all partition/corpus digests.
Visible mode validates committed calibration/quarantine content, replays the seeded assignment,
checks held-out aggregate arithmetic and pair-set digest, and verifies the internally committed
corpus digest without requiring held-out bytes.

The corpus does not define QA scoring thresholds, modify TASK-075's scoring contract, run QA, or
perform RBF optimization.
