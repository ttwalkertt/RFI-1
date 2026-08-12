# V3 benchmark review record

## Scope

All authored repository changes are confined to `benchmarks/rfi_qa_candidates_v3/`. No RFI, MCP,
investigator, QA runtime, scoring, test, or optimization code was inspected or changed.

## Independence

Authoring did not inspect QA implementation, QA prompts, runtime outputs, calibration ledgers,
optimization results, observed QA failures/performance, or previous benchmark case contents. New
case IDs, fixture IDs, locators, evidence text, submitted answers, and reference truth were created
for v3.

## Split and isolation

- Seed: `20260812`.
- Unit: complete matched pair.
- Assignment: first 40 shuffled pairs calibration; remaining 20 verification.
- Rerandomization: none.
- Pair co-location and partition disjointness: validator-enforced.
- Fixture duplication across calibration/verification: prohibited and validator-enforced.
- Quarantine participation in objective partitions: prohibited.
- Verification case-level truth in root manifest: prohibited.
- Verification directory: ignored and moved outside the repository after full validation.

## Validation evidence

```bash
python3 benchmarks/rfi_qa_candidates_v3/validate_candidates.py --full
python3 benchmarks/rfi_qa_candidates_v3/validate_candidates.py --visible
```

Authoritative corpus digest:

```text
52962392643587aab0ae6211e7f9dea21a181805fb0e25bf808dc4c877103968
```

The visible validator can replay the seeded assignment and verify aggregate/digest commitments with
verification absent. Full verification requires an authorized custodian to restore the held-out
files whose hashes are recorded in `split-manifest.json`.
