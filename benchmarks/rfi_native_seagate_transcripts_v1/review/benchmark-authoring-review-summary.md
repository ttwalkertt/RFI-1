# RFI-native Seagate benchmark authoring review

## Outcome

The authoring milestone produced a separate, independently labeled benchmark over the actual retained Seagate transcript corpus. It contains 40 independent question/evidence scenarios and 80 same-evidence matched answer cases, plus 4 quarantined cases. The fixed-seed scenario split is 24 calibration scenarios / 48 cases and 16 held-out scenarios / 32 cases.

The frozen truth boundary is Seagate firm authority, canonical `earnings_transcript` artifacts, repository `repository-3cc74b7b56983605e27858afc34cd599`, snapshot `sqlite-revision-8237`, 21 documents, 2,268 deterministic segments, and trustworthy source-effective dates from 2024-09-04 through 2026-07-28. No transcript lacks a retained trusted event date.

## Coverage and reference distribution

- Proposition states: 30 supported, 21 contradicted, 18 indeterminate, 11 mixed.
- Answer quality: 40 acceptable, 40 defective.
- Primary failures: 15 classes, led by incorrect quantitative synthesis (9), contradicted claim (8), overgeneralization (4), incorrect chronology (3), and unsupported certainty (3).
- Defensible failure overlap covers all 16 taxonomy classes.
- Estimated independent semantic templates: 40; 39 question families, 37 reasoning structures, and 39 named failure mechanisms.
- Selected decisive/qualifying evidence covers all 21 transcripts and the complete frozen date range. Per scenario, exact evidence ranges from 1 to 4 passages (mean 2.5).

## Artifact and leakage audit

All 40 pairs have identical question/requirements and evidence universes. Mean acceptable-minus-defective length difference is 0.55 words; locator distributions are identical. Evidence-withheld controls pass: longest-answer heuristic 0.538, locator heuristic 0.500, uncertainty-term heuristic 0.538, leave-one-scenario-out bag-of-words answer-quality accuracy 0.688, and defect-family text-only accuracy 0.225. The threshold is deliberately recorded; passing reduces obvious shortcut signal but does not prove that every leakage channel is absent.

The held-out boundary is the complete `withheld/` directory. Removing it leaves aggregate provenance and digests without held-out case IDs, text, labels, selected evidence, or defect assignments. The restorable archive is `withheld/rfi-native-seagate-held-out-v1.tar.gz`, SHA-256 `c6e839f0d60afe09640901a78c127764f8043355921cb17d99b3d4e4a7274ff5`. The payload tree SHA-256 is `9a689088e8cecfeee5e40678fa022ad9331d545b3c28f70eac732fbe88af4aa0`.

## Known limitations

- Historical repository classification includes conference/investor-event titles under `earnings_transcript`; event-kind diagnostics are absent. The benchmark reports rather than repairs this authority state.
- Deterministic speaker labels are absent. Only explicit textual introductions safely support named attribution.
- Corpus coverage is retained-inventory coverage, not proof that every real-world Seagate call or event was acquired.
- Reference judgments are authored and validated but still require human acceptance before being treated as operational reference truth. The withheld human packet includes all quarantined, difficult, compound, insufficiency, and fixed-seed control cases.
- Exact selected evidence is intentionally bounded to at most four decisive/qualifying passages per scenario while the full 21-document governed corpus remains case scope.
- The simple evidence-withheld controls are not an exhaustive adversarial leakage study.

## Independence declaration

Authoring used only RFI repository authority and retained Seagate transcript bytes. It did not use the public web, external financial databases, investor-relations pages outside RFI, model background facts, synthetic evidence fixtures, fabricated passages or authority, QA implementation/prompts, QA outputs, calibration/validation results, miss lists, RBF history, performance metrics, or known gauge failure cases. QA and RBF were not run.

## Verification

- The benchmark validator passes in full mode against `.artifacts/task071-live-eval`, including
  exact locator resolution, fixed-seed split replay, physical held-out isolation, member and
  archive digests, and evidence-withheld leakage controls.
- The validator also passes in visible-only mode after removing the complete `withheld/`
  directory.
- `tests.test_foundation` and `tests.test_task076` pass together (5 tests).
- The complete repository unit suite passes (749 tests). The subsequent repository format gate
  remains red only for two pre-existing overlength lines in `src/rfi/qa_gauge/benchmark.py`; the
  TASK-076 additions introduce no format findings. That QA implementation was deliberately left
  unchanged under this task's independence boundary.

## Architectural Status Summary

| Subsystem | Responsibility | Status |
|---|---|---|
| Frozen corpus authority | Defines firm, canonical artifact membership, dates, revision, provenance, and limitations | Complete |
| Benchmark case/reference model | Separates submitted answers from proposition state, answer quality, failures, and exact evidence | Complete |
| Matched-pair corpus | Supplies realistic acceptable/defective answers over identical retained evidence | Complete |
| Partition and isolation | Keeps scenario families together and makes held-out payload physically removable/restorable | Complete |
| Deterministic validator | Checks authority, locators, labels, taxonomy, pairs, split, digests, archive, and leakage | Complete |
| Authoring analyses | Measures diversity, transcript/date coverage, evidence volume, symmetry, labels, failures, and leakage | Complete |
| Human adjudication | Accepts labels and resolves or retains quarantine before operational benchmark use | Usable with limitations; pending human review |
| QA gauge calibration | Consumes only calibration after held-out removal | Not started; explicitly outside TASK-076 |

Architectural change: the repository now has a real-evidence benchmark layer that remains separate from retained truth and QA implementation. It introduces no new evidence authority, retrieval contract, MCP behavior, investigator behavior, or QA behavior.

Next architectural milestone: human acceptance of the review packet and benchmark contract, followed by a separately authorized calibration experiment with the entire `withheld/` directory removed.
