# TASK-075 — Establish QA Gauge Capability Through RBF Optimization

**Status:** Draft  
**Type:** Bounded capability-development and evaluation experiment  
**Depends on:** TASK-074 and the independent RFI QA candidate corpus  
**Scope:** Determine whether Codex RBF can evolve the RFI investigation-QA capability into an accurate and repeatable measurement gauge against independently labeled reference truth

## Objective

Determine whether Codex RBF can evolve the current RFI investigation-QA capability into an accurate and repeatable QA gauge.

TASK-074 established that independent QA can add useful signal, but the existing QA behavior is not sufficiently trustworthy as a terminal measurement system. TASK-075 therefore treats QA itself as the object under development and evaluation.

Use the independently created labeled QA candidate corpus as reference truth, establish a controlled calibration and held-out validation regime, define scoring and success criteria before optimization, and allow Codex RBF substantial autonomy to improve the QA capability within explicit architectural and experimental boundaries.

The central question is:

> Can the QA capability become accurate and repeatable enough to serve as a trustworthy quality gauge for RFI investigations?

Repair effectiveness and first-pass investigator optimization are not evaluated in this task.

## Gauge Properties

### Accuracy

The gauge should correctly distinguish supported, defective, and genuinely indeterminate cases; identify material defect classes; ground findings in valid evidence; and avoid false findings against supported answers.

### Repeatability

Repeated evaluations of the same case under controlled conditions should produce materially consistent dispositions and defect detection.

A sophisticated reviewer that is not repeatable is not yet a trustworthy gauge.

## Reference-Truth Corpus

Use `benchmarks/rfi_qa_candidates/`.

The starting pool contains:

- 66 candidate cases;
- 62 objectively adjudicable cases;
- 4 judgment-dependent borderline cases;
- 31 objective matched supported/non-supported pairs;
- 31 supported objective cases;
- 25 defective objective cases;
- 6 indeterminate objective cases;
- 32 defect classes;
- 35 synthetic evidence fixtures with explicit authority boundaries.

The corpus, fixtures, schemas, taxonomy, and validator are reference inputs. Do not alter labels to improve QA scores.

## Borderline-Case Quarantine

Quarantine the four judgment-dependent borderline cases for TASK-075.

They are excluded from:

- calibration;
- held-out validation;
- primary scoring;
- RBF optimization feedback;
- success/failure criteria.

Do not human-adjudicate or relabel them in this task. Preserve them unchanged as a future evaluation/adjudication set.

TASK-075 therefore uses the 62 objectively adjudicable cases as its benchmark population.

## Benchmark Freeze

Freeze stable case/fixture IDs, authority boundaries, expected dispositions/findings, adjudicability, matched-pair relationships, taxonomy version, and corpus digest/revision.

## Scoring Design Before Partitioning

Define scoring before choosing calibration and held-out validation partitions.

At minimum score:

- supported/defective/indeterminate disposition accuracy;
- false-accept rate for defective cases;
- false-reject rate for supported cases;
- material/significant defect detection;
- defect-class attribution;
- evidence/locator correctness;
- unsupported QA findings / false positives;
- indeterminate handling;
- matched-pair discrimination;
- whole-answer disposition;
- repeatability across repeated runs.

Do not reduce gauge quality to one aggregate accuracy number. False accepts of materially defective answers require explicit attention.

Specify primary/secondary metrics, severity weighting if used, treatment of partial findings, indeterminate and judgment-dependent cases, repeatability measurement, predetermined success thresholds, and invalid-evaluation conditions.

Do not change scoring or thresholds after observing held-out validation.

## Calibration and Held-Out Validation

Only after scoring is fixed, partition the 62 objective cases approximately 2:1 between calibration and held-out validation.

Use the 31 objective matched supported/non-supported pairs as the unit of randomization:

- both members of every matched pair must remain in the same partition;
- randomly assign approximately 20 pairs to calibration and 11 pairs to held-out validation;
- use a fixed, recorded random seed so the split is reproducible;
- do not select or move individual cases independently of their pair.

### Calibration/development partition

Visible to RBF and usable for repeated execution, error analysis, QA prompt/implementation/orchestration changes, justified MCP/access improvements, and scoring feedback.

### Held-out validation partition

Hidden from RBF until the QA design is frozen.

RBF must not inspect validation cases/labels/outcomes, move cases after seeing performance, or tune thresholds from validation.

After the seeded split, verify that both partitions retain reasonable disposition and defect-class coverage. Rerandomization is permitted only if a partition lacks meaningful coverage of a required class or disposition. Any rerandomization must occur before RBF sees calibration outcomes, use another recorded seed, and preserve the reason and rejected split manifest.

Do not hand-optimize the partition for expected QA performance.

The four quarantined borderline cases remain outside both partitions.

## RBF Optimization Objective

Give Codex RBF this objective:

> Improve the RFI investigation-QA capability until it meets the predetermined calibration success criteria while preserving reference truth, architectural authority boundaries, and benchmark integrity.

RBF may discover the QA design rather than merely tune a predefined prompt.

## Permitted RBF Optimization Surface

RBF may modify, replace, or introduce:

- reviewer prompts and decomposition;
- number/roles of QA agents or passes;
- reviewer specialization;
- evidence-retrieval strategy;
- deterministic verification;
- claim decomposition;
- chronology/evidence-mapping checks;
- voting/consensus;
- retry policy;
- context partitioning;
- intermediate structured representations;
- QA orchestration/contracts/code;
- model-facing schemas;
- use of existing RFI/MCP capabilities.

RBF need not preserve the TASK-074 QA architecture. TASK-074 is prior evidence, not a mandated design.

## MCP / Access Changes Are Permitted When Justified

The MCP/access surface is not absolutely frozen during calibration.

RBF may implement bounded MCP/access improvements when calibration evidence demonstrates that QA cannot reliably close a defect because required evidence, authority, chronology, provenance, completeness, metadata, or verification semantics are not adequately accessible.

Potential legitimate general capabilities include stable-locator verification, source/authority validation, ordered earliest/latest evidence access, provenance inspection, absence/completeness semantics, coverage metadata, authoritative metadata introspection, exact evidence verification, and reusable relationship/history access.

Every MCP/access change must:

1. address a demonstrated QA access/verification gap;
2. belong legitimately to RFI's repository/access layer;
3. be general and useful independent of the exposing benchmark case;
4. not encode the expected answer or QA judgment;
5. not redefine retained truth;
6. record the motivating failure and improvement.

Benchmark-specific answer helpers are prohibited.

## Failure Attribution During Optimization

Classify material failures where practical:

- **QA reasoning/prompt failure:** evidence is available but QA reasons/uses it poorly.
- **QA orchestration failure:** decomposition, context, aggregation, voting, retry, or deterministic checks cause failure.
- **MCP/access gap:** a legitimate stable repository/access semantic is unavailable or materially ambiguous.
- **Repository-authority limitation:** RFI lacks authoritative evidence; correct result may be indeterminate.
- **Reference-truth defect:** benchmark label/fixture/locator/authority boundary appears wrong; stop the case and route for independent human adjudication. RBF may not relabel it.

## Hard Truth Boundary

RBF may optimize how QA obtains, reasons about, and verifies evidence. It may not modify what counts as truth.

RBF must not rewrite expected labels/findings, weaken authority boundaries, alter fixtures to ease cases, inspect hidden validation truth, move cases after outcomes, change thresholds to obtain a pass, or convert indeterminate truth without independent human adjudication.

## Matched-Pair Requirement

The 31 supported/non-supported pairs are a core anti-gaming control.

Measure whether QA accepts the supported member, detects the defective member, identifies the relevant distinction, and grounds it in the changed evidence/authority condition. Report pair-level accuracy separately.

## Repeatability Experiment

Run repeated independent QA evaluations on a predetermined subset or all cases. Define repeat count before final validation.

Measure disposition agreement, material defect-detection agreement, defect-class agreement, evidence-reference consistency where applicable, and false-positive variance.

Similar aggregate accuracy alone is not repeatability.

## Calibration Exit Criteria

Before optimization, define criteria including overall objective-case disposition accuracy, maximum material false-accept rate, supported-case false-positive rate, material defect recall, matched-pair discrimination, indeterminate calibration, evidence-grounding quality, and repeatability.

RBF iterates until criteria are met, a predetermined optimization budget is exhausted, or progress stalls under a predetermined stopping rule. Record the optimization trajectory.

## Freeze Point

At optimization termination, freeze QA code/prompts/roles/orchestration/model configuration/deterministic checks/contracts, permitted MCP/access surface, scoring implementation, calibration results, and relevant dependency/configuration versions.

No tuning is permitted before held-out validation.

## Held-Out Validation

Run the frozen gauge against untouched validation using the predetermined scoring contract.

Do not repair or retune from validation within TASK-075.

Report accuracy, false accepts/rejects, material defect recall, defect-class performance, evidence-grounding errors, matched-pair behavior under the split policy, indeterminate handling, repeatability, calibration-to-validation degradation, and poorly generalizing defect classes.

Validation failure is a valid result.

## Fresh Live Test

Only if the frozen gauge meets held-out criteria, run a small fresh live test on newly produced RFI investigation outputs unused in calibration/validation. Human-adjudicate them independently.

Do not resume tuning from the live test within TASK-075.

## Repair Is Out of Scope

Do not evaluate repair effectiveness. TASK-075 isolates the gauge:

`case → QA gauge → structured judgment → scorer`

Once gauge capability is established, a later task may reintroduce repair.

## First-Pass Investigator Prompting Is Out of Scope

Do not optimize Codex Work's investigation prompt. Once QA can become trustworthy, a later experiment may use the gauge to compare investigator prompting strategies.

## Benchmark Execution Harness

Implement the minimum deterministic harness to load frozen cases/fixtures, invoke QA under controlled conditions, preserve prompts/config/runtime identity, capture/validate structured output, score reference truth, run repeats, aggregate metrics, preserve per-case evidence, prevent validation leakage, and record optimization iterations.

The harness is measurement infrastructure, not a general agent platform.

## Required Experimental Records

Preserve accepted/frozen corpus revision; the four-case quarantine manifest; scoring/thresholds; random seed and partition manifest; any rejected split and rerandomization rationale; calibration visibility; validation protection; every RBF iteration; code/prompt/MCP changes; failure attribution; calibration scores; freeze manifest; validation/repeatability/live-test results; and suspected benchmark defects routed for independent human adjudication.

## Required Tests

Cover benchmark/schema validation, frozen digest, partition disjointness, validation leakage prevention, matched-pair split policy, scoring, severity/disposition and indeterminate handling, evidence/locator scoring, repeatability aggregation, optimization provenance, freeze integrity, prevention of post-freeze mutation, benchmark-label immutability from RBF, MCP-change provenance, and reproducible evaluation outputs.

## Required Deliverables

1. objective benchmark corpus with the four borderline cases explicitly quarantined;
2. corpus freeze manifest/digest and quarantine manifest;
3. scoring specification;
4. predetermined success thresholds;
5. calibration/validation partition manifest;
6. benchmark execution/scoring harness;
7. RBF optimization configuration/instructions;
8. complete calibration optimization history;
9. QA/MCP change log with failure attribution;
10. frozen QA-gauge manifest;
11. held-out validation results;
12. repeatability evaluation;
13. defect-class and matched-pair analysis;
14. fresh live-test evaluation if validation permits;
15. architectural evaluation and next-step recommendation;
16. normal commit-aware review package.

## Out of Scope

Do not optimize investigator behavior/prompting; evaluate repair; build recursive QA/repair; use validation during optimization; let RBF alter reference truth; tune thresholds after validation; add benchmark-specific MCP helpers; manufacture missing authority; broaden into a general benchmark/workflow platform; declare QA trustworthy from calibration alone; or treat one run as repeatability evidence.

## Acceptance Criteria

TASK-075 is complete when:

1. the four judgment-dependent cases are quarantined unchanged and excluded from optimization/scoring;
2. the 62 objective cases are frozen as the TASK-075 benchmark population before optimization;
3. scoring/success criteria are defined before partition selection/results;
4. calibration and held-out validation partitions are created by fixed-seed random assignment of whole matched pairs, approximately 2:1, checked for reasonable coverage, and then fixed/protected;
5. RBF has substantial QA-design autonomy within the truth boundary;
6. justified general MCP/access improvements are permitted for demonstrated QA access gaps;
7. every material QA/MCP change is attributable to calibration evidence;
8. reference truth and held-out validation remain outside RBF control;
9. matched pairs are explicitly evaluated;
10. repeatability is measured through repeated independent evaluations;
11. optimization terminates under predetermined criteria/budget/stopping rules;
12. QA/MCP design is frozen before validation;
13. held-out validation uses exactly the frozen design;
14. no post-validation tuning occurs within the task;
15. results establish whether QA **can become** an accurate and repeatable gauge under the tested regime;
16. repair and investigator-prompt optimization remain separate;
17. focused/full repository validation pass;
18. completed work is committed/pushed and a commit-aware review package is generated.

## Final Architectural Disposition

End with one of:

**QA became an accurate and repeatable gauge under the tested RBF regime**

**QA improved materially but did not meet the predetermined gauge criteria**

**QA gauge capability remains inadequate under the tested design space**

**Experiment is inconclusive because of a named benchmark, MCP/access, or repository-authority limitation**

State benchmark composition and four-case quarantine, split seed/policy, thresholds, optimization trajectory, QA architecture changes, MCP/access changes and justification, calibration/validation performance, repeatability, false accepts, matched-pair discrimination, indeterminate handling, evidence grounding, benchmark defects, live-test result if reached, and whether the resulting gauge is trustworthy enough for future repair and investigator-optimization experiments.

Do not declare success merely because RBF improves the current QA implementation. The question is whether QA can become sufficiently accurate and repeatable to function as a trustworthy measurement gauge.
