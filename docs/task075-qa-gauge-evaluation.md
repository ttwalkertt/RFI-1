# TASK-075 QA gauge evaluation — V3 frozen pre-verification evidence

## Disposition

**V3 calibration did not converge, and the frozen design is not an accepted QA gauge.**

The fresh V3 experiment exhausted its mechanically preregistered 400-judgment calibration budget.
One V3-evidenced methodology replacement was measured and rejected because it displaced errors
instead of improving causal finding quality. The selected unchanged design failed the terminal V3
calibration criteria and materially regressed on the known V2 suite. It is frozen solely so the
required one-shot V3 held-out measurement can be run after human restoration; no held-out truth has
been observed in this V3 experiment.

## Frozen benchmark and controls

- Benchmark: `rfi-qa-independent-v3.0.0`.
- Independent authoring commit: `8a44d4a13b69db443953d7162b659d4034b1b982`.
- Corpus digest:
  `52962392643587aab0ae6211e7f9dea21a181805fb0e25bf808dc4c877103968`.
- Objective population: 60 matched pairs / 120 cases.
- Calibration: 40 pairs / 80 cases; held-out verification: 20 pairs / 40 cases.
- Quarantine: six judgment-dependent cases, unchanged and excluded.
- Split seed: `20260812`; no rerandomization.
- Scoring-contract digest:
  `79f6e5a5ef445d08880079f2c27a995e80ed16489bb7d823782c28795a197ae6`.
- V3 optimization-config digest:
  `389ad1dd32530b30252686440e7dcf26a0cdeb53d283e9c1c966d651856408ea`.
- Frozen-gauge digest:
  `b165ff2966f7ba2ba741c346b8b72fd2d7d00a1921f0d030025cf8f9267781b4`.

The held-out files are physically absent. Their preregistered commitments are:

- `verification/cases.jsonl`:
  `8184454d4cfbec057b41fc2d460fc8cf1eb9a1174200be8ca9cc3f10d166a257`.
- `verification/fixtures.json`:
  `a637f1dd86aebee72d435acf112f9a0014573ba99bcfc0fffa5d0703c8fd0b94`.

The scoring formulas, success thresholds, invalid-review rules, three-run terminal repeatability
regime, and stopping rules are unchanged from the original preregistration. Before V3 outcomes,
only benchmark-size-dependent integer equivalents and the calibration call count were updated. The
400-call maximum preserves one 80-case baseline, one 80-case feedback iteration, and one 240-call
terminal assessment; it adds no outcome-driven iteration.

## Calibration trajectory

| Assessment | Design | Runs/case | Valid | Disposition | Recall | Class F1 | Unsupported | Indeterminate | Pair discrimination |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| V3 baseline | Epistemic root cause v3 | 1 | 98.75% | 97.47% | 85.00% | 85.00% | 15.00% | 87.50% | 80.00% |
| V3 candidate | Causal admission v4 | 1 | 100% | 96.25% | 85.00% | 85.00% | 15.00% | 75.00% | 77.50% |
| V3 terminal | Epistemic root cause v3 | 3 | 95.00% | 97.37% | 77.50% | 81.58% | 13.89% | 62.50% | 72.50% |

All three runs had 0% material false accepts and 100% evidence grounding. The baseline had a 2.5%
supported false-reject rate; the candidate and terminal had 0%.

### Unchanged V2-selected baseline

The inherited methodology was:

`authority ledger -> claim/obligation ledger -> deterministic verification -> three-state
epistemic decision -> exact-class precedence`

The baseline produced high disposition accuracy, no false accepts, and perfectly grounded matched
findings, but six expected classes were missed and six predicted classes were unsupported. The
misses clustered in finding admission, adjacent causal classes, and epistemic aggregation. Two
provenance/version errors recurred despite V2's explicit precedence rule, supporting a challenge to
the abstraction rather than another case-specific patch. One review exhausted both transport
attempts. Every semantic miss had the governing evidence and stable locators; no MCP/access gap was
present.

### Causal-admission replacement

V3 calibration justified a fundamental replacement:

`task contract -> evidence model -> proposition verdict -> finding admission -> earliest causal
mechanism -> epistemic aggregation`

The predicted consequences were tested directly:

- unsupported findings should decrease: **did not occur** (15% to 15%);
- material-finding recall should be preserved or improve: **preserved only** (85% to 85%);
- class attribution should improve: **did not occur** (85% to 85%);
- unresolved propositions should remain indeterminate: **worsened** (87.5% to 75%);
- matched pairs should be discriminated for the right cause: **worsened** (80% to 77.5%);
- high disposition accuracy should be preserved: **occurred above threshold, but declined**
  (97.47% to 96.25%);
- evidence grounding should be preserved: **occurred** (100% to 100%).

The candidate corrected the seven prior semantic misses but introduced nine different ones across
epistemic status, boundary/temporal routing, insufficiency/attribution routing, and whole-answer
inconsistency. Diagnostic utility declined from `0.921187` to `0.912500`, and no failed semantic
threshold became a pass. The result is error displacement, not superior causal measurement.

Candidate selection deliberately gave no credit to the 27% shorter static prompt, lower transport
burden, or 100% valid one-run output. Those are useful implementation characteristics, but runtime,
latency, prompt length, and context pressure are not key boundary conditions for gauge selection.
They cannot rescue a methodology that fails the predicted semantic consequences, just as a slower
or longer methodology would not be rejected if it materially improved gauge quality within the
declared runtime limits.

### Terminal selected-design assessment

The unchanged V2-selected design was restored byte-for-byte and assessed three times per case. The
terminal score was:

| Metric | Threshold | Observed | Result |
|---|---:|---:|---|
| Valid evaluation rate | >= 100% | 95.00% | **Fail** |
| Disposition accuracy | >= 90% | 97.37% | Pass |
| Material false-accept rate | <= 10% | 0% | Pass |
| Supported false-reject rate | <= 10% | 0% | Pass |
| Material finding recall | >= 85% | 77.50% | **Fail** |
| Defect-class attribution F1 | >= 85% | 81.58% | **Fail** |
| Evidence grounding | >= 95% | 100% | Pass |
| Unsupported finding rate | <= 10% | 13.89% | **Fail** |
| Indeterminate accuracy | 100% | 62.50% | **Fail** |
| Matched-pair discrimination | >= 90% | 72.50% | **Fail** |
| Disposition full agreement | >= 90% | 0% | **Fail** |
| Disposition pairwise agreement | >= 95% | 0% | **Fail** |
| Material-detection full agreement | >= 90% | 0% | **Fail** |
| Defect-class mean Jaccard | >= 90% | 0% | **Fail** |
| Evidence-reference mean Jaccard | >= 80% | 0% | **Fail** |
| Supported false-positive-count variance | <= 0.1 | 1.0 | **Fail** |

There were 31 exact matches among 40 expected findings and five unsupported predicted findings.
Semantic misses remained on `R3C-030`, `R3C-043`, `R3C-049`, `R3C-063`, `R3C-069`, `R3C-072`,
and `R3C-103`. They reflect incorrect indeterminate aggregation or selection of a nearby symptom
instead of the reference causal class. Four cases—`R3C-055`, `R3C-099`, `R3C-108`, and
`R3C-120`—lacked one required judgment after both permitted transport attempts.

Repeatability is reported independently and failed closed exactly as preregistered. The zeros do
not mean that aggregate accuracy was used as a proxy for disagreement; incomplete three-run
consensus invalidated the cases and forced every agreement/Jaccard statistic to its failure value
and false-positive variance to `1.0`. Even excluding runtime invalidity as the primary architectural
reason, the valid semantic evidence still fails recall, classing, unsupported-finding,
indeterminate, and pair-quality controls.

## Known V2 regression

After terminal selection and before freeze, the exact selected design ran once against the known V2
held-out suite with three runs per case. V2 was not optimization truth and no change followed it.

| Metric | Prior frozen V2 result | V3-final-design regression | Change |
|---|---:|---:|---:|
| Valid evaluation rate | 100% | 89.29% | -10.71 points |
| Disposition accuracy | 96.43% | 100% | +3.57 points |
| Material finding recall | 68.75% | 43.75% | -25.00 points |
| Defect-class F1 | 73.33% | 51.85% | -21.48 points |
| Unsupported finding rate | 21.43% | 36.36% | +14.94 points |
| Indeterminate accuracy | 75.00% | 50.00% | -25.00 points |
| Matched-pair discrimination | 71.43% | 50.00% | -21.43 points |

All previously passing repeatability thresholds became failures because three V2 cases lacked
complete consensus. Correct aggregate dispositions, zero false accepts/rejects, and perfect
grounding of matched findings do not offset incomplete or unsupported findings, poor epistemic and
pair behavior, or the repeatability failure. This is a material regression under the preregistered
rule and a separate negative result from the future V3 held-out measurement.

## Failure attribution and access disposition

- **QA reasoning/prompt failure:** finding admission, exact causal classification, multi-finding
  completeness, and three-state epistemic aggregation remain unstable across independent corpora.
- **QA orchestration failure:** isolated reviews exhausted the bounded transport attempts, causing
  invalid consensus and repeatability failure.
- **MCP/access gap:** none. Every semantic miss had the required general evidence, authority, and
  exact locators.
- **Repository-authority limitation:** several fixtures intentionally leave propositions
  unresolved; the correct action is `indeterminate`, not expanded retrieval outside the declared
  authority.
- **Suspected benchmark/reference-truth defect:** none.

No MCP/access change was made. Adding retrieval to override intentionally partial benchmark
authority would violate rather than improve the evidence contract.

## Freeze and evidence identities

- Baseline manifest:
  `a0205a182f9eaf9cf1bf93b12bb0acc3b39b3c8c926f83aefdf81d3a22e6de1f`.
- Baseline score:
  `fe9eb71dac0a29d7c6572f30e128c58c75685706958e526c8f8e100671ab4357`.
- Candidate manifest:
  `b7a35b5e8c31fbd9a7142bb174ce28eb60bed57236041db177238c911a63e503`.
- Candidate score:
  `ec2a3589e9dbb0ed0aac83964d3edd9610c7932eebd2a795be7cd46f81385ef1`.
- Terminal manifest:
  `bdca76d785b8867bf9efc4ef2320cde16495f7990e96f82d1a8cde1909d28f31`.
- Terminal score:
  `b9eb59a22a841416306e7ccb2e2aee452e386e80893bfe1f4536900fa6679b2a`.
- V2 regression manifest:
  `307ab9ba9ee4bb7052a70ba4102e0e52b92f927589e9616ecb6ad56be494de8f`.
- V2 regression score:
  `71f69b654de11549d0825a29c392bf3eb70c4308b6e17d7c223d33c98f8f505e`.

The freeze includes the complete selected QA implementation, prompt, contracts, deterministic
scorer, experiment harness, controls, calibration history, runtime identity, and dependency
versions. The rejected candidate source is preserved from commit `52040de`; the selected prompt was
restored to SHA-256
`5702ee399de511d188cb11edb3d9275ac96d8b5e48002c9ad6dd8ea10c0fd486`.

Focused QA tests, visible benchmark validation, frozen-control verification, deterministic
rescoring, and all repository functional tests/proofs pass. The full repository validation has one
preserved limitation: its format stage reports pre-freeze line-length violations at
`src/rfi/qa_gauge/benchmark.py:45` and `:617`. That file is part of the immutable freeze inventory;
post-freeze reformatting would invalidate the experimental boundary. Lint, typecheck, import,
documentation, baseline, and build checks pass, and the review package preserves both the failed
full-validation transcript and the successful remaining checks.

## Stopping decision

The one permitted terminal assessment and all 400 V3 calibration judgments are consumed. No
post-terminal, post-regression, or post-freeze tuning occurred. The held-out partition remains
absent, the one-shot marker does not exist, and fresh live transfer has not run.

The human operator must now restore exactly the two V3 verification files and independently confirm
their preregistered hashes. Only then may the frozen design run once under the unchanged scoring
contract. Whatever that result, TASK-075 permits no further QA, prompt, methodology, orchestration,
MCP, scoring, threshold, or benchmark change.
