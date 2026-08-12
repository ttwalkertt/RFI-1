# TASK-075 architectural review — frozen V3 pre-verification checkpoint

## Outcome

**The V3 calibration experiment did not converge on an accurate and repeatable QA gauge.**

The V2-selected `task075.epistemic-root-cause-v3` design was measured unchanged on the fresh,
independently authored V3 calibration partition. Calibration evidence justified one fundamental
replacement methodology, `task075.causal-admission-gauge-v4`; the replacement corrected the
baseline misses but introduced a larger, different set of epistemic and causal-classification
errors. It was rejected on gauge quality, and the unchanged starting design was selected for the
single terminal repeatability assessment.

The terminal V3 calibration failed seven semantic/validity controls and every repeatability
control. The same selected design then materially regressed on the known V2 suite. The complete QA
design is frozen, no MCP/access change was made, and V3 held-out verification remains physically
absent and unattempted. This checkpoint is therefore negative and not an accepted measurement
gate. TASK-075 remains in progress only for the one required frozen held-out run after exact human
restoration.

## Experimental boundary

- Independent benchmark: `rfi-qa-independent-v3.0.0`, authored at
  `8a44d4a13b69db443953d7162b659d4034b1b982` without access to QA implementation or performance.
- Corpus: 60 objective matched pairs / 120 cases, with 40 pairs / 80 cases in calibration and 20
  pairs / 40 cases in physically absent held-out verification.
- Quarantine: six judgment-dependent cases, preserved unchanged and excluded from optimization,
  regression, scoring, and success criteria.
- Split: seed `20260812`, no rerandomization; held-out case identities and content are absent from
  the task controls.
- Contract: the original 16 conjunctive thresholds and three-run terminal repeatability regime are
  unchanged. Only population-dependent integer equivalents and the mechanically necessary
  400-call V3 calibration budget were preregistered before V3 outcomes.
- Optimization boundary: V3 calibration truth was the only optimization signal. V2 was used once
  as a known regression suite after selection and did not motivate tuning.
- Truth boundary: no label, fixture, authority, scoring, threshold, split, or benchmark change was
  made. No suspected reference-truth defect was identified.

## Candidate-selection rationale

Methodology selection was controlled by disposition accuracy, finding recall, class F1,
unsupported findings, pair discrimination, indeterminate handling, evidence grounding, invalid
review behavior, and ultimately repeatability. Runtime, latency, prompt length, and context pressure
were secondary operational characteristics only.

| Gauge-quality property | Unchanged baseline | Causal-admission candidate | Predicted consequence |
|---|---:|---:|---|
| Disposition accuracy | 97.47% | 96.25% | Preserved above threshold; declined |
| Material finding recall | 85.00% | 85.00% | Preserved, not improved |
| Defect-class F1 | 85.00% | 85.00% | Not improved |
| Unsupported finding rate | 15.00% | 15.00% | Not decreased |
| Matched-pair discrimination | 80.00% | 77.50% | Worsened |
| Indeterminate accuracy | 87.50% | 75.00% | Worsened |
| Evidence grounding | 100% | 100% | Preserved |
| Valid evaluation rate | 98.75% | 100% | Operational improvement only |

The candidate corrected all seven baseline semantic misses but introduced nine different misses.
It therefore displaced error rather than producing more accurate causal findings. Its 27% shorter
static prompt, lower transport burden, and 100% one-run validity were useful secondary properties
but received no selection credit and could not rescue inferior semantic behavior. Conversely, no
candidate was rejected merely for being longer or slower within the declared runtime limits.

## Final frozen assessment

| Metric | Threshold | V3 terminal calibration | Result |
|---|---:|---:|---|
| Valid evaluation rate | >= 100% | 95.00% | Fail |
| Disposition accuracy | >= 90% | 97.37% | Pass |
| Material false-accept rate | <= 10% | 0% | Pass |
| Supported false-reject rate | <= 10% | 0% | Pass |
| Material finding recall | >= 85% | 77.50% | Fail |
| Defect-class attribution F1 | >= 85% | 81.58% | Fail |
| Evidence grounding | >= 95% | 100% | Pass |
| Unsupported finding rate | <= 10% | 13.89% | Fail |
| Indeterminate accuracy | 100% | 62.50% | Fail |
| Matched-pair discrimination | >= 90% | 72.50% | Fail |
| Disposition full agreement | >= 90% | 0% | Fail |
| Disposition pairwise agreement | >= 95% | 0% | Fail |
| Material-detection full agreement | >= 90% | 0% | Fail |
| Defect-class mean Jaccard | >= 90% | 0% | Fail |
| Evidence-reference mean Jaccard | >= 80% | 0% | Fail |
| Supported false-positive-count variance | <= 0.1 | 1.0 | Fail |

The repeatability result is an independent failure, not an inference from aggregate accuracy. Four
cases lacked one of three required judgments after both permitted transport attempts; the frozen
contract therefore invalidated those cases and failed all repeatability measures closed. The
remaining semantic misses independently demonstrate that runtime invalidity is not the primary
reason for the negative architectural disposition.

## Architectural result

TASK-075 retains a separate experimental `rfi.qa_gauge` boundary with reference-free reviewer
projection, strict output contracts, deterministic rescoring, matched-pair controls, immutable raw
records, budget accounting, protected partitions, freeze integrity, and one-shot validation
enforcement. It did not alter TASK-074 repair behavior, first-pass investigator prompting,
repository authority, or the MCP surface.

The V2-derived architecture remains frozen as the selected candidate:

`authority ledger -> claim/obligation ledger -> deterministic verification -> three-state
epistemic decision -> exact-class precedence`

V3 evidence shows that this abstraction is not converged. The attempted replacement—task-contract
parsing, evidence modeling, proposition verdicts, finding admission, earliest-causal-mechanism
classification, and epistemic aggregation—also failed to stabilize causal findings. A successor
must address structured finding completeness, exact causal classification, indeterminate authority,
and repeatable reviewer completion as general mechanisms rather than add case-specific precedence
rules.

## Architectural Status Summary

- **Independent V3 benchmark — Complete and protected.** Visible provenance, calibration,
  quarantine, split commitments, and hashes validate; the held-out partition remains absent.
- **Scoring and success contract — Complete and frozen.** The original formulas, 16 thresholds,
  invalid-review behavior, and repeatability regime were unchanged.
- **V3 calibration-only RBF harness — Complete for the authorized budget.** It preserves the
  unchanged baseline, material replacement, rejection rationale, terminal assessment, raw prompts
  and outputs, failure attribution, and all 400 judgments.
- **Selected QA methodology — Usable only as experimental infrastructure.** It preserves high
  disposition accuracy, zero false accepts/rejects, and grounded matched findings, but it fails
  finding completeness, exact classing, epistemic handling, pair discrimination, and repeatability.
- **MCP/access surface — Complete for the supplied experiment, unchanged.** All semantic misses had
  the required authority, records, and locators; no general access gap was demonstrated.
- **Known V2 regression — Complete, negative.** The selected design materially regressed in finding
  quality, indeterminate handling, pair discrimination, validity, and repeatability. V2 results did
  not drive tuning.
- **Freeze — Complete.** The gauge inventory, selected prompt, contracts, scorer, controls, and
  runner are hash-locked; post-freeze tuning is prohibited.
- **Repository validation — Usable with one frozen limitation.** Focused QA tests, benchmark and
  freeze controls, experiment rescoring, all functional tests/proofs, lint, typecheck, docs,
  baseline, import, and build checks pass. The repository-wide format check reports two overlong
  lines in the freeze-locked QA benchmark loader. They predate freeze and cannot be reformatted in
  this checkpoint without invalidating the immutable design.
- **V3 held-out verification — Not started; awaiting operator action.** The human must restore the
  exact files and confirm the preregistered hashes before the single permitted run.
- **Fresh live transfer — Not started.** It remains conditional on passing every V3 held-out
  threshold.
- **Product composition — Not accepted.** The frozen gauge must not gate repair or investigator
  optimization.

The next action is administrative rather than optimization: restore only the exact V3 held-out
archive, confirm its two preregistered SHA-256 values, and run the frozen design once. No result from
that run may trigger tuning within TASK-075.
