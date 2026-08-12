# TASK-075 architectural review

## Outcome

**QA improved materially but did not meet the predetermined gauge criteria.**

TASK-075 completed the protected RBF experiment and the single frozen held-out validation. The v3
gauge generalized well on whole-answer disposition, false-accept/false-reject control, evidence
grounding, and repeatability. It did not generalize sufficiently on material-finding recall, exact
class attribution, unsupported findings, indeterminate handling, or matched-pair discrimination.
The combined evidence therefore rejects this design as a trustworthy terminal QA measurement gate.

## Architectural result

The experiment introduced a separate `rfi.qa_gauge` measurement boundary with strict reviewer
contracts, reference-free prompts, matched-pair scoring, repeatability aggregation, protected
partition loading, calibration accounting, immutable raw records, freeze integrity, and one-shot
validation enforcement. It did not change TASK-074 repair behavior, first-pass investigator
prompting, repository truth, or the MCP surface.

The retained design evolved through:

`authority ledger -> claim/obligation ledger -> deterministic verification -> three-state
epistemic decision -> exact-class precedence`

That design was materially more accurate than the inherited baseline and produced complete,
strong held-out repeatability. Its remaining failures were semantic: it substituted nearby defect
classes, omitted secondary material defects, and converted one authority-limited proposition from
indeterminate to defective. These are QA reasoning/prompt failures, not missing access semantics.

## Experimental disposition

- Independent benchmark: 36 objective matched pairs / 72 cases; four judgment-dependent cases
  quarantined unchanged.
- Fixed split: seed `20260811`, 22 calibration pairs / 44 cases and 14 validation pairs / 28 cases;
  no rerandomization.
- Optimization: 220/240 v2 calibration judgments and two total material design changes including
  the retained v1 change.
- Freeze: `task075.epistemic-root-cause-v3`, stopped by the predetermined budget rule.
- Validation: one attempt, three independent runs per case, 84/84 valid judgments.
- Held-out disposition accuracy: 96.43%; false accepts: 0%; supported false rejects: 0%.
- Held-out repeatability: 100% disposition and material-detection full agreement; class Jaccard
  94.05%; evidence-reference Jaccard 92.98%; supported false-positive-count variance 0.
- Failed held-out controls: finding recall 68.75%, class F1 73.33%, unsupported findings 21.43%,
  indeterminate accuracy 75%, and matched-pair discrimination 71.43%.
- MCP/access changes: none; no calibration or validation miss demonstrated a missing general RFI
  repository/access semantic.
- Benchmark defects: none suspected.
- Post-freeze tuning: none.
- Fresh live transfer: prohibited by the failed held-out result and not attempted.

Detailed metrics, degradation, and case attribution are in
[`task075-qa-gauge-evaluation.md`](task075-qa-gauge-evaluation.md). Machine-readable identities and
outcomes are in `experiments/task075/held-out-validation-result.json`; the frozen design inventory
remains in `experiments/task075/frozen-gauge-manifest.json`.

## Architectural Status Summary

- **Independent v2 benchmark — Complete and frozen.** Reference truth, matched pairs, quarantine,
  authority boundaries, split membership, and hashes remained outside RBF control.
- **Scoring and success contract — Complete and frozen.** Sixteen conjunctive accuracy,
  false-result, evidence, pair, indeterminate, and repeatability thresholds were preregistered and
  applied unchanged.
- **Calibration-only RBF harness — Complete for the experiment.** It preserved the v1 provenance,
  every v2 iteration, exact prompts/outputs/events, failure attribution, budget, and freeze.
- **V3 QA gauge — Usable with material limitations.** Whole-answer and evidence behavior are strong,
  but finding completeness and exact semantic classification are below the measurement-gate bar.
- **Repeatability — Established for held-out validation.** All cases had three valid independent
  runs and passed every repeatability threshold. This does not override failed accuracy controls.
- **MCP/access surface — Complete for the supplied evidence contract, unchanged.** No observed miss
  justified a general access capability change.
- **Held-out validation — Complete, negative.** The single attempt used the exact restored files and
  frozen design; five thresholds failed.
- **Fresh live transfer — Not started by design.** It was conditional on held-out success.
- **Product composition — Not accepted.** The gauge remains experimental infrastructure and must
  not gate repair or investigator optimization.

Architectural change: RFI now has a reproducible, independently labeled QA-gauge experiment that
can distinguish measurement accuracy from repeatability and preserve a valid negative result. The
tested design is repeatable but not accurate enough at material defect classification and
matched-pair discrimination. Any future improvement requires a new authorized task and a new
protected evaluation regime; TASK-075 does not resume tuning.
