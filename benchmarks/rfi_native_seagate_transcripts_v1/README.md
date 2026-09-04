# RFI-native Seagate transcript QA benchmark v1

This independently authored benchmark evaluates investigative answers against actual immutable Seagate transcript evidence retained by RFI. It is separate from, and replaces synthetic V2/V3 data as the proposed primary QA calibration/evaluation corpus. It does not change retained truth, retrieval/MCP behavior, investigator behavior, QA code, or any prior benchmark.

## Frozen authority

- Firm: Seagate Technology Holdings plc (`seagate`)
- Repository: `repository-3cc74b7b56983605e27858afc34cd599`
- Snapshot: `sqlite-revision-8237`
- Canonical artifact scope: `earnings_transcript`
- Source-effective range: 2024-09-04 through 2026-07-28
- Documents: 21; deterministic exact-span segments: 2,268
- Trustworthy date gaps: none; every document uses retained `trusted_event_date`
- Coverage: indeterminate; retained inventory does not prove acquisition completeness

The historical corpus includes conference- and investor-event-titled documents whose repository authority still says `earnings_transcript`. `event_kind` and deterministic speaker labels are absent. The benchmark records those limitations and never silently reclassifies artifacts or invents speakers.

## Population and split

- 40 independent question/evidence scenarios
- 80 matched answer cases: one acceptable and one materially defective answer per scenario
- Calibration: 24 scenarios / 48 cases
- Held-out verification: 16 scenarios / 32 cases
- Quarantine: 4 unresolved cases outside both partitions
- Split seed: `20260813`; split unit is the scenario, never an answer member

Cases and labels are physically separated. `calibration/cases.jsonl` contains submitted payloads and `calibration/reference.jsonl` contains reference truth. The same structure exists under `withheld/payload/` for held-out verification.

Before calibration or optimization, remove the entire `withheld/` directory. It contains the held-out payload, private split assignments, human review packet, and restorable archive. The remaining tree exposes only aggregate split provenance and the held-out payload digest—not held-out IDs, questions, answers, labels, exact evidence, or defect assignments.

Relocate and later restore the boundary as one directory (the destination must be outside every
calibration-visible tree):

```bash
mv benchmarks/rfi_native_seagate_transcripts_v1/withheld /secure/offline/rfi-native-seagate-heldout
PYTHONPATH=src .venv/bin/python benchmarks/rfi_native_seagate_transcripts_v1/validate_benchmark.py \
  --state .artifacts/task071-live-eval --visible-only

# Only after calibration has ended:
mv /secure/offline/rfi-native-seagate-heldout benchmarks/rfi_native_seagate_transcripts_v1/withheld
```

If directory relocation is unavailable, first copy
`withheld/rfi-native-seagate-held-out-v1.tar.gz` to access-controlled storage and verify its SHA-256
against `withheld/archive-digest.json`; then remove `withheld/`. Restore by creating `withheld/` and
extracting the archive into it. The archive contains `payload/`, `payload-digest.json`, and the human
review packet; `archive-digest.json` is deliberately kept outside the archive.

## Validation

From repository root:

```bash
PYTHONPATH=src .venv/bin/python benchmarks/rfi_native_seagate_transcripts_v1/validate_benchmark.py \
  --state .artifacts/task071-live-eval
```

After removing `withheld/`, run `--visible-only`. Full validation checks schemas, stable IDs, exact locator bytes and hashes, pair integrity, independent labels, taxonomy membership, split replay, disjointness, quarantine exclusion, digests, archive contents, visible-tree isolation, and aggregate leakage controls.

`analyze_benchmark.py` regenerates the aggregate diversity, evidence-volume/date-span, pair-symmetry, class-distribution, and evidence-withheld artifact analyses. It does not run QA.

## Source and independence declaration

Authoring used only repository-retained Seagate transcript artifacts and repository-owned deterministic access. No public web, external financial data, model background facts, synthetic evidence fixtures, QA outputs, QA performance, miss lists, RBF optimization history, or known gauge failure cases were used. Defective answers mutate answers while preserving the exact evidence universe; no transcript passage was manufactured.
