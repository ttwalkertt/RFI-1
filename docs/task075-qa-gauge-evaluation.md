# TASK-075 QA gauge evaluation

## Final disposition

**QA improved materially but did not meet the predetermined gauge criteria.**

The frozen `task075.epistemic-root-cause-v3` design completed its single held-out validation
attempt against the independently restored v2 validation partition. All 28 cases and all 84
preregistered judgments were valid, but five conjunctive thresholds failed. No post-validation
tuning occurred, and the conditional fresh-live-transfer test was not permitted.

The result does not support using this QA design as a trustworthy measurement gate for repair or
investigator-prompt optimization. Its held-out dispositions and repeatability were strong, but its
material-finding completeness, exact defect-class selection, indeterminate handling, and
matched-pair discrimination were insufficient.

## Frozen benchmark and controls

- Benchmark: `rfi-qa-independent-v2.0.0`, independently authored at
  `ac2837034078ec101ea7e2a582916268b88663fb`.
- Corpus digest: `09ec5ab31d4f9683e7ce7f9064fb294f388d4846b5f75a68875f69a6c740c54a`.
- Objective population: 36 matched pairs / 72 cases.
- Calibration: 22 pairs / 44 cases; validation: 14 pairs / 28 cases.
- Quarantine: four judgment-dependent cases, unchanged and excluded from optimization and scoring.
- Split seed: `20260811`; no rerandomization or case movement.
- Scoring-contract digest:
  `79f6e5a5ef445d08880079f2c27a995e80ed16489bb7d823782c28795a197ae6`.
- Optimization-config digest:
  `b0670449fc0f24ff28af98e69f0bfe995a6b9009d81154084ca1ecf3a4d70330`.
- Frozen-gauge digest:
  `ef2a44d43288ee9273c2582d22a07e19cd03d8815ed8909ab1328c0e59231d86`.

The human-restored validation files matched the preregistered SHA-256 identities before the run:

- `validation/cases.jsonl`:
  `22e98803f86c36fc1009ce8c16b153e3e4bc871b31740f2620bab13a16fb899d`.
- `validation/fixtures.json`:
  `9afb3a99090a85574f6c2a5effaf8a56fe93648eb85bbe280e21ccd84fbb0bbf`.

## Optimization trajectory and freeze

The retained calibration-derived architecture was:

`authority ledger -> claim/obligation ledger -> deterministic verification -> three-state
epistemic decision -> exact-class precedence`

V2 used 220 of 240 calibration judgments. Its clean retained-design baseline was followed by one
calibration-attributed material change: truth status became dominant, findings were reduced to
non-overlapping root causes, materiality was tightened, and general precedence was added for
inconsistency, omitted conflict, population qualification, and draft-versus-governing authority.
The resulting v3 diagnostic passed every non-repeatability threshold. The only terminal calibration
assessment failed because one case lacked all three required judgments, forcing repeatability to
fail closed; it also retained two class-selection misses. The design was frozen under the
predetermined budget stopping rule. No MCP/access change was justified or made.

## Single held-out validation result

The one permitted validation attempt ran from `2026-08-12T01:15:21.258567+00:00` through
`2026-08-12T01:22:11.713388+00:00`. It scheduled 84 logical judgments and made 88 transport
invocations. Four judgments used the one allowed transport retry after four timed-out invocations;
all 84 final judgments were valid.

| Metric | Threshold | Frozen calibration terminal | Held-out validation | Validation result |
|---|---:|---:|---:|---|
| Valid evaluation rate | >= 100% | 97.73% | 100% | Pass |
| Disposition accuracy | >= 90% | 100% | 96.43% | Pass |
| Material false-accept rate | <= 10% | 0% | 0% | Pass |
| Supported false-reject rate | <= 10% | 0% | 0% | Pass |
| Material finding recall | >= 85% | 86.36% | 68.75% | **Fail** |
| Defect-class attribution F1 | >= 85% | 88.37% | 73.33% | **Fail** |
| Evidence grounding | >= 95% | 100% | 100% | Pass |
| Unsupported finding rate | <= 10% | 9.52% | 21.43% | **Fail** |
| Indeterminate accuracy | 100% | 100% | 75% | **Fail** |
| Matched-pair discrimination | >= 90% | 86.36% | 71.43% | **Fail** |
| Disposition full agreement | >= 90% | Invalid / 0% | 100% | Pass |
| Disposition pairwise agreement | >= 95% | Invalid / 0% | 100% | Pass |
| Material-detection full agreement | >= 90% | Invalid / 0% | 100% | Pass |
| Defect-class mean Jaccard | >= 90% | Invalid / 0% | 94.05% | Pass |
| Evidence-reference mean Jaccard | >= 80% | Invalid / 0% | 92.98% | Pass |
| Supported false-positive-count variance | <= 0.1 | Invalid / 1.0 | 0.0 | Pass |

Every threshold is conjunctive, so the observed result is a failure. The complete held-out
repeatability scores are genuine and materially better than the invalid terminal calibration
measurement, but they do not compensate for the failed accuracy and pair controls.

## Failure attribution

The score contained 16 expected material findings, 14 predicted findings, 11 exact class matches,
11 grounded matches, and three unsupported predicted classes. Four of 14 matched pairs failed:
`R2P-003`, `R2P-008`, `R2P-009`, and `R2P-015`.

- `R2C-005`: correct `indeterminate` disposition, but
  `ambiguous_reference_overresolved` replaced `attribution_unsupported`.
- `R2C-007`: `qualification_omitted` was detected, but the second material class
  `claim_strength_overstatement` was omitted.
- `R2C-015`: a reference-indeterminate corpus-completeness assertion was promoted to `defective`.
- `R2C-018`: correct `indeterminate` disposition, but `insufficiency_miscalibrated` replaced
  `causal_overstatement`.
- `R2C-029`: `provenance_authority_error` replaced `status_mischaracterized`.
- `R2C-072`: `denominator_error` was detected, but the second material class
  `qualification_omitted` was omitted.

All six misses are attributed to frozen QA reasoning/prompt behavior: exact-class selection,
multi-finding completeness, or application of the three-state epistemic decision. The required
authority declarations, records, and locators were supplied. There was no invalid consensus or
aggregation failure, no demonstrated MCP/access gap, no repository-authority limitation that
prevented the correct reference outcome, and no suspected benchmark/reference-truth defect.

## Calibration-to-validation change

Relative to the frozen terminal calibration score, validation disposition accuracy changed by
`-0.035714`, material finding recall by `-0.176136`, class F1 by `-0.150388`, unsupported finding
rate by `+0.119048` (worse), indeterminate accuracy by `-0.25`, and matched-pair discrimination by
`-0.149351`. False accepts, false rejects, and evidence grounding did not change. Calibration
repeatability was fail-closed because of an incomplete case, so its numeric repeatability deltas
must not be treated as a comparable performance improvement.

## Evidence and stopping decision

The raw validation manifest digest is
`c8dcd099ee756e453c084a660fb67078cda357c3ba20a6cdc282358f8f227bcd`; the score digest is
`31d77a019536a59828c715bebd5c8893094ecb047b38ba64305ea50482a4b49b`. The committed result record
is `experiments/task075/held-out-validation-result.json`. The final review package includes the
restored benchmark, exact prompts and schemas, all model outputs, event streams, stderr, attempts,
the deterministic rescore, state markers, calibration provenance, and validation transcripts.

Because held-out validation did not pass every threshold, fresh live transfer was prohibited and
not attempted. TASK-075 ends with the negative result unchanged; no further QA, prompt,
orchestration, MCP, scoring, threshold, or benchmark change was made after observing validation.
