# TASK-074 — Independent QA and Single Bounded Repair Loop for MCP Investigations

**Status:** Implemented and evaluated; QA useful but did not materially close quality gap
**Type:** Bounded implementation and evaluation experiment
**Depends on:** TASK-073
**Scope:** Independent quality review and one bounded repair cycle over the preserved TASK-073 Codex Work investigation outputs

## Objective

Implement and evaluate an independent quality-assurance and single bounded-repair loop for investigations produced by a general-purpose runtime over the RFI MCP surface.

Use the five preserved TASK-073 Codex Work outputs as the fixed proving set. Do not rerun the original first-pass investigations and do not modify the TASK-073 MCP surface merely to improve review or repair results.

The proving lifecycle is exactly:

`TASK-073 first-pass answer → Independent QA #1 → Structured findings → Bounded Repair #1 → Independent QA #2 → STOP`

There is no repair escalation, recursive repair, second repair cycle, reviewer/repairer negotiation, or recovery of original investigative context in this task. Any defects remaining after QA #2 are experimental evidence.

## Architectural Question

Determine:

> Does one independent QA pass followed by one bounded repair and one independent re-review materially improve the preserved TASK-073 investigation outputs while preserving the separation between RFI's epistemic substrate and runtime-owned analytical judgment?

This task tests a simple quality-feedback loop before designing more elaborate repair, escalation, or recursive-review machinery.

## Fixed Proving Set

Use the preserved TASK-073 outputs for:

1. management sentiment/confidence over time;
2. cloud/nearline demand and constraints;
3. HAMR/Mozaic progress;
4. first/latest discussion of 40-TB-class capacity;
5. named-executive employee attrition by geography / retained-corpus insufficiency.

Do not regenerate them before QA.

Known TASK-073 defects are evaluation targets, not reviewer hints: incorrect chronology boundaries; weak/missing stable evidence mapping in demand and technology; incomplete scope/metadata qualification in sentiment; and incomplete insufficiency calibration in the attrition control.

## Governing Boundary

RFI/MCP owns retained evidence, immutable identity, exact evidence verification, canonical repository identity, provenance, retained metadata, deterministic access metadata and basis, source-effective chronology, dictionary semantics, access generation/health, query semantics, bounds, diagnostics, and empty-versus-failure semantics.

The investigator owns investigation strategy, query formulation, hypotheses, evidence selection, stopping, synthesis, and report construction.

Independent QA owns evaluation of claim support, chronology, evidence mapping, material qualifications, insufficiency calibration, unsupported/overstated conclusions, defect classification/severity, bounded repair findings, and final review disposition.

QA findings do not become retained repository truth.

## Independence Requirement

Initialize each reviewer without the original investigator's hidden reasoning, planning context, search strategy, tool history as guidance, TASK-071 answer/protocol, external benchmark analysis, or case-specific defect hints.

The reviewer may receive the original question, submitted TASK-073 answer, evidence references contained in that answer, declared repository/corpus limitations needed to interpret it, and independent read-only access to the same RFI MCP surface.

The reviewer may independently search and inspect RFI evidence. Preserved TASK-073 traces may be used afterward for diagnostic evaluation but are not reviewer guidance.

## QA Objective

The reviewer evaluates the submitted answer rather than writing a replacement report.

Where applicable, determine whether material claims are supported by exact retained evidence; citations support their claims; evidence identity is stable; chronology boundaries are correct; contrary/qualifying evidence changes conclusions; scope statements match the retained corpus; metadata limitations are carried into the answer; insufficiency is calibrated; absence claims exceed query/coverage semantics; or conclusions overstate the evidence.

## QA Finding Contract

Each structured finding includes:

- stable finding ID and case ID;
- severity;
- defect class;
- affected claim/location;
- concise defect statement;
- supporting RFI evidence/repository fact;
- conflicting or missing evidence where applicable;
- why the defect matters;
- bounded repair instruction;
- review confidence;
- whether additional investigation is required.

Suggested classes: `unsupported_claim`, `incorrect_chronology`, `evidence_mapping_missing`, `evidence_mapping_incorrect`, `scope_overstatement`, `qualification_missing`, `insufficiency_miscalibrated`, `absence_overstatement`, `repository_limitation_omitted`, `internal_inconsistency`, `material_ambiguity`.

Severity is `material`, `significant`, or `minor`.

Per-case QA disposition is `pass`, `repair_required`, or `insufficient_for_review`.

## Bounded Repair

When QA #1 returns `repair_required`, invoke exactly one bounded repair.

The repair agent receives:

- original research question;
- submitted TASK-073 answer;
- structured QA findings;
- stable evidence references contained in the answer or findings;
- the same unchanged RFI MCP access.

It does **not** receive TASK-071's answer, an external reference answer, reviewer hidden reasoning, a reviewer-authored replacement answer, the original TASK-073 investigation trace, prior hidden reasoning/planning/search history/intermediate hypotheses, or a prescribed tool sequence.

The repair agent receives durable work products, not the original investigation context. It may perform new MCP investigation as needed and should repair identified defects and consequentially affected claims rather than restart the investigation by default.

## No Repair Escalation

TASK-074 provides no escalation mechanism.

The repair agent may not request or receive the original trace, selected prior searches, intermediate reasoning, additional original-investigation context, another reviewer consultation, or a replacement answer.

If a finding cannot be fully resolved from the supplied repair context and current RFI/MCP access, the repair agent must:

1. identify the unresolved finding;
2. state what remains uncertain or blocked;
3. distinguish an evidence/access limitation from its own inability where possible;
4. complete all other feasible repairs;
5. preserve the unresolved issue in the repaired submission;
6. hand the result to QA #2.

An unresolved repair item is experimental evidence, not a trigger for additional machinery.

## Independent QA #2

After Repair #1, run a fresh independent review with a fresh reviewer context.

QA #2 receives the original question, repaired answer, its evidence references, explicitly unresolved repair items if any, and independent access to the unchanged MCP surface.

For each QA #1 finding record `resolved`, `partially_resolved`, `unresolved`, or `superseded`. Also record newly introduced material/significant defects and whether unresolved repair items are justified limitations or investigator-repair failures.

QA #2 is terminal. No second repair occurs regardless of disposition.

## Hard One-Cycle Bound

The lifecycle is exactly:

**Investigation → QA #1 → Repair #1 → QA #2 → stop**

There is no QA #3, Repair #2, recursive review, escalation, human correction during the proving run, or automatic workflow expansion.

Further repair cycles, escalation paths, specialist reviewers, reviewer ensembles, or other recovery mechanisms are deferred until multiple investigation/QA experiments provide evidence about recurring failure modes.

## MCP Surface Freeze

Use the TASK-073 MCP surface unchanged.

Do not add QA-specific tools such as `validate_claim`, `check_chronology`, `find_counterevidence`, `review_answer`, or `repair_answer`; MCP reviewer prompts; semantic/vector retrieval; or additional evidence types.

If QA exposes a genuine access defect, classify it rather than repairing MCP during the proving experiment.

## TASK-071 Separation

TASK-071 QA/adjudication/recovery is prior art, not the target runtime. Inspect it for lessons but do not mechanically reuse its evidence-admission policy, adjudication state machine, closed-record model, recovery work orders, fixed investigation protocol, tool budgets, final-turn rules, or reporting assumptions.

Reuse only genuinely architecture-neutral contracts and document why.

## Reviewer Prompting

TASK-074 may define the minimum reviewer prompt needed to express the review role and quality criteria.

Do not optimize the first-pass investigator prompt. TASK-073 outputs remain fixed.

Reviewer prompting states quality obligations rather than a search algorithm. Preserve exact reviewer and repair prompts.

First-pass Codex Work prompting strategy is a separate future experiment.

## Known Defects as Evaluation Targets

The reviewer must be capable of independently detecting, without case-specific hints:

- **Chronology:** false first/latest 40-TB boundaries despite correct ordered candidates being available.
- **Demand:** useful analysis with materially weak stable evidence mapping.
- **Technology:** human-locatable references rather than stable RFI locators.
- **Sentiment:** selected title-derived subset overstated as the retained earnings-call universe and incomplete corpus/event-kind qualification.
- **Attrition:** directionally correct insufficiency with incomplete speaker/coverage qualification and lexical absence not equivalent to real-world absence.

## QA False-Positive Control

QA is not rewarded merely for finding faults.

Measure supported material/significant findings, unsupported findings, overcorrections, forced certainty, and attempts to convert repository limitations into invented conclusions.

Supported claims should be preserved.

## Diagnostic Attribution

Classify failures where possible as:

- **QA/reviewer failure:** missed demonstrable defect, invented defect, evidence misread, or unsupported repair demand.
- **MCP/access failure:** required retained evidence/semantics unavailable through frozen MCP.
- **Investigator repair failure:** sound finding not corrected despite adequate access.
- **Repair-induced regression:** repair introduces a new material/significant defect.
- **Repository-authority limitation:** retained authority is ambiguous/unavailable.
- **Unresolved bounded repair:** repair explicitly cannot resolve a finding within supplied context/access.

QA #2 determines whether an unresolved repair is justified or an investigator-repair failure.

## Experimental Metrics

For each case record:

- QA #1 disposition and material/significant/minor findings;
- validated true findings and false positives;
- known TASK-073 defects detected/missed;
- QA #1 MCP/search/exact-read counts;
- Repair #1 MCP operation count and repair extent;
- explicitly unresolved repair items;
- QA #2 MCP operation count;
- findings resolved/partial/unresolved/superseded;
- new defects introduced;
- final QA #2 disposition;
- elapsed time where available.

Efficiency is secondary to correctness.

## Success Criteria

Strong evidence of success includes detection of false chronology boundaries, weak evidence mapping, scope/coverage/metadata defects; preservation of supported claims; low material false positives; bounded repair instructions rather than replacement answers; successful repair over unchanged MCP; and independent confirmation without material regressions.

Not every QA #2 result must pass. Remaining defects inform later design of prompting, escalation, additional repair cycles, or reviewer specialization.

## Required Tests

Add focused coverage for:

- QA finding/severity/disposition schemas;
- stable finding IDs and evidence references;
- repair instruction serialization;
- QA #1 → Repair #1 → QA #2 lifecycle;
- hard one-cycle termination;
- prohibition of repair escalation;
- unresolved-repair representation;
- finding resolution states;
- preservation of original/repaired outputs;
- immutable association among question, answer, findings, repair, and QA #2;
- RFI read-only behavior;
- absence of QA-specific MCP mutation/convenience tools;
- preservation of exact prompts and traces.

Where model judgment is nondeterministic, test the surrounding contracts, provenance, lifecycle, and evidence capture.

## Required Deliverables

1. independent QA/review contract;
2. bounded single-repair contract;
3. independent QA #2 contract;
4. minimal orchestration for those stages;
5. focused automated tests;
6. preserved reviewer/repair prompts and runtime identity;
7. QA #1 outputs/traces for all five preserved TASK-073 cases;
8. Repair #1 outputs/traces for all cases requiring repair;
9. QA #2 outputs/traces;
10. finding-resolution matrix;
11. unresolved repair-item record;
12. false-positive/false-negative analysis against known TASK-073 defects;
13. pre-QA versus post-repair quality comparison;
14. architectural evaluation;
15. normal commit-aware review package.

## Out of Scope

Do not rerun TASK-073 first-pass investigations; change/optimize their prompt; modify MCP to improve QA; add semantic/vector retrieval or evidence types; expose QA/repair through MCP; retain QA findings as repository truth; provide TASK-071/external benchmark answers; provide reviewer-authored replacement reports; provide original investigation context to repair; implement escalation, a second repair cycle, recursive QA/repair, TASK-071's full adjudication/recovery machinery, or a general workflow engine.

## Acceptance Criteria

TASK-074 is complete when:

1. the five preserved TASK-073 outputs are the fixed proving set;
2. QA #1 independently reviews each with fresh context and unchanged MCP access;
3. reviewers receive no TASK-071/external answers, defect hints, or investigator hidden context;
4. QA #1 emits structured evidence-grounded findings and bounded repair instructions;
5. chronology, evidence mapping, scope/qualification, and insufficiency defects are independently tested;
6. false positives and misses are evaluated;
7. repair receives only the bounded repair context and unchanged MCP;
8. repair has no escalation path and explicitly records unresolved findings;
9. all feasible repairs are completed before handoff;
10. QA #2 independently re-reviews repaired answers and unresolved items;
11. QA #2 records finding resolution and repair regressions;
12. QA #2 terminates the proving lifecycle with no second repair;
13. RFI/MCP remains read-only and unchanged;
14. QA, MCP/access, repair, authority, and unresolved-repair failures remain distinguishable;
15. focused/full repository validation pass;
16. completed work is committed/pushed and a commit-aware review package is generated.

## Final Architectural Disposition

End with one of:

**Independent QA + one bounded repair materially closes the TASK-073 quality gap**

**QA is useful but additional runtime-side quality controls require a future experiment**

**QA/repair does not reliably improve general-runtime investigation**

**Experiment is inconclusive because of a named access or repository-authority limitation**

State first-pass defects, QA detection performance/false positives, repair effectiveness, QA #2 results, unresolved defects, runtime/access cost, whether anything justifies changing RFI/MCP, and whether the next experiment should address first-pass investigator prompting.

Do not design additional repair cycles or escalation inside TASK-074. Preserve unresolved evidence so those mechanisms can be designed later from observed investigations rather than speculation.

## Completion Record

Implemented on `codex/task-074-independent-qa-repair`. The five preserved TASK-073 answers were
reviewed without rerunning their investigations through exactly one fresh QA #1, one bounded repair,
and one fresh terminal QA #2 per case. RFI/MCP and retained authority remained unchanged.

The experiment produced eight supported QA #1 findings with no unsupported substantive findings,
detected five of eight known targets, missed three, and yielded only one diagnostically sound pass
among four QA #2 pass dispositions. One repair-induced significant regression and one justified
unresolved bounded-repair item were preserved. The final disposition is **QA is useful but
additional runtime-side quality controls require a future experiment**. See
`docs/task074-qa-repair-evaluation.md` and `docs/TASK-074-review.md`.
