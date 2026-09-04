# TASK-076 — Author an RFI-native Seagate transcript QA benchmark

**Status:** Complete; benchmark is validated and review-ready, with human label acceptance required before operational use

## Objective

Create an independently labeled QA benchmark grounded only in the immutable Seagate transcript corpus retained by RFI. Replace synthetic QA corpora as the proposed primary calibration/evaluation truth without inspecting QA behavior or changing retained truth, MCP, investigation, QA, RBF, or prior benchmarks.

## Boundaries and invariants

- Freeze corpus membership from repository authority and canonical transcript semantics, never filenames or filesystem time.
- Use no public web, external data, background facts, synthetic evidence, QA outputs, QA metrics, miss lists, optimization history, or gauge behavior.
- Keep proposition state independent from answer quality.
- Preserve overlapping defensible defect classes.
- Keep matched variants on identical questions and exact evidence universes.
- Split and isolate by independent scenario; quarantine unstable judgments.
- Make every locator and digest reproducible against the frozen retained state.

## Acceptance and evidence

- Dedicated README, contract, corpus manifest, schemas, taxonomy, calibration, held-out, quarantine, split/digests, validator, analyses, human packet, and review summary.
- Approximately 40–60 independent scenarios unless retained evidence responsibly supports fewer.
- Deterministic validation of schema, IDs, corpus, locators, pairs, labels, partitions, split replay, digests, and isolation.
- Aggregate diversity, evidence/date coverage, pair symmetry, and evidence-withheld leakage controls.
- Required Architectural Status Summary and known limitations.

## Result

The benchmark at `benchmarks/rfi_native_seagate_transcripts_v1/` contains 40 independent scenarios, 80 paired answer cases, and 4 quarantined cases. Calibration contains 48 cases; held-out verification contains 32. All 21 frozen transcripts contribute selected evidence. Full validation passes against `sqlite-revision-8237`. QA and RBF were not run.
