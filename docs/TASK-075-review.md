# TASK-075 architectural review — frozen calibration checkpoint

## Outcome

TASK-075 now has a frozen QA gauge and a complete calibration-only RBF trajectory against the
fresh independent v2 benchmark. The current evidence supports the provisional disposition
**QA improved materially but did not meet the predetermined gauge criteria**. This is not yet the
ticket's final architectural disposition because the human-protected held-out partition is still
absent and validation has not been attempted.

The v3 gauge materially improved one-run calibration quality, including perfect disposition and
indeterminate handling with no false accepts or false rejects. Its single terminal repeatability
assessment failed the fixed contract after two reviewer contexts for one case exhausted the
allowed retry. Repeatability is therefore failed, not inferred from aggregate accuracy.

## Implemented boundary

The `rfi.qa_gauge` package provides strict reviewer contracts, reference-free prompt designs,
matched-pair scoring, repeatability aggregation, and protected benchmark projection. The experiment
runner enforces visible calibration-only access, call accounting, isolated ephemeral contexts,
transport retries, immutable result records, freeze integrity, and a one-shot validation marker.

Reference truth, fixtures, authority declarations, taxonomy, quarantine, split assignment,
scoring formulas, thresholds, and held-out content remain outside the optimization surface. The
reviewer receives only the question, requirements, declared authority, evidence records, and
submitted answer. Repair and first-pass investigator prompting are absent.

No MCP capability changed. The fixture contract already provided the general authority,
provenance, exact-record, completeness, and locator semantics that an MCP change could legitimately
address. Calibration misses were reviewer reasoning/class selection or reviewer-runtime failures.

## Experimental status

- Visible benchmark validation passes for 44 calibration cases and four quarantined cases.
- Twenty-eight held-out cases remain physically absent.
- V1 calibration provenance is retained; no v1 held-out validation was run.
- V2 baseline and feedback iteration used one run per case; terminal used three independent runs.
- V2 consumed 220/240 logical judgments and two of three allowed material design changes in total.
- V3 passed every one-run non-repeatability threshold.
- Terminal v3 failed valid-evaluation, pair-discrimination, and all repeatability thresholds.
- The gauge is frozen with no post-freeze tuning permitted.
- Held-out validation and fresh-live transfer have not run.

Detailed metrics and failure attribution are in
[`task075-qa-gauge-evaluation.md`](task075-qa-gauge-evaluation.md). The machine-readable trajectory
is in `experiments/task075/calibration-history.json` and the immutable file inventory is in
`experiments/task075/frozen-gauge-manifest.json`.

## Architectural Status Summary

- **Independent v2 reference benchmark — Complete and frozen.** Thirty-six objective matched pairs
  are split once with seed `20260811`; four judgment-dependent cases remain quarantined. Held-out
  payload bytes are intentionally outside the repository.
- **Scoring and success contract — Complete and frozen.** Accuracy, false accepts/rejects, finding
  quality, evidence grounding, matched-pair discrimination, indeterminate handling, and independent
  repeatability have fixed formulas and thresholds.
- **Calibration-only RBF harness — Complete for the experiment.** It protects hidden truth,
  captures exact prompts/schemas/outputs/events, accounts for the fixed budget, and fails closed on
  incomplete terminal repeats.
- **V3 QA gauge — Usable with material limitations.** It is highly accurate in one-run calibration
  but did not produce a valid complete terminal repeatability measurement and retained two
  class-selection misses.
- **Repeatability claim — Not established.** One incomplete case invalidated terminal repeatability;
  good consensus accuracy on other cases cannot replace the preregistered measure.
- **MCP/access surface — Complete for the supplied benchmark inputs, unchanged.** No observed miss
  demonstrated a missing general repository/access semantic.
- **Held-out validation — Blocked by intentional human custody.** The exact 28-case archive must be
  restored and hash-verified before the one allowed run.
- **Fresh live transfer — Not started.** It remains conditional on all held-out thresholds passing.
- **Product composition — Deferred.** The gauge and harness remain experimental infrastructure,
  outside the stable CLI, Pull Workflow, repository authority, and QA/repair product flow.

Architectural change: RFI now has a protected, independently scored QA-gauge experiment with a
frozen negative calibration result and explicit repeatability failure. It is not yet a trustworthy
measurement gate. The next bounded action is human restoration of the exact held-out archive,
followed by one frozen validation run and the final TASK-075 disposition; no optimization resumes.
