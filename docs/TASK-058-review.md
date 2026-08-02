# TASK-058 Verification Report

## Result

TASK-058 is Complete. Transcript acquisition now has an explicit orchestration contract and an
independently attributable deterministic trial contract. Learned retained-anchor URL forms are
planned in their existing repository order, executed one at a time, and stopped after the first
trial that produces a validated acquisition. The existing configured-hint and bounded-search
fallback remains one unchanged pipeline after learned trials are exhausted.

No temporary operator seeds, LLM calls, selection criteria, HTTP changes, backfill behavior, or
new discovery/validation rules were introduced.

## Architectural Summary

`TranscriptAcquisitionOrchestrator` owns the ordered seed plan. It reads the retained anchor view,
preserves the existing resolved-then-requested form order for each retained entry, deduplicates
exact repeated URLs, and appends the existing configured discovery fallback. It does not traverse,
retrieve, rank, validate, persist, learn, or advance checkpoints.

`AdapterAcquisitionTrial` is the provider-neutral engine contract for one attributable trial. It
contains one trial identity, one starting seed, and one seed classification. The acquisition
engine recognizes this optional contract without changing adapters that continue to use ordinary
discovery pages.

`EarningsTranscriptPullAdapter.discover_trial()` executes one orchestrator-selected trial through
the existing `BoundedTranscriptDiscovery` traversal/ranking code and the existing deferred
`EarningsCallTranscriptAcquisition` retrieval/validation path. The trial never selects its
successor and never declares acquisition completion.

`AcquisitionEngine` remains the acquisition lifecycle orchestrator. It requests trials in planned
order, aggregates candidate and page evidence, continues after an unsuccessful learned trial,
stops after the first trial with validated retrieval, persists the validated result, and performs
the existing checkpoint finalization. Persistence through `record_success()` retains the existing
transactional anchor-learning behavior. Consequently, failed trials cannot teach and checkpoint,
artifact, observation, and learned-anchor state still commit or roll back together.

Every executed trial page now carries `trial_id`, redacted `starting_seed`, `seed_kind`,
`trial_outcome`, and `acquisition_termination_reason`. Existing traversal diagnostics are retained
unchanged inside that attributable page record. Acquisition-level counters, outcomes, lifecycle
status, Pull Workflow summaries, and REST/operator projections retain their existing contracts.

## Deterministic Trial Responsibilities

A transcript trial owns only execution from its supplied starting seed:

1. bounded graph traversal and transport accounting;
2. candidate generation and deterministic ranking;
3. deferred candidate retrieval through the existing transcript retriever;
4. date, media, transcript-structure, speaker, firm, and reporting-period validation; and
5. complete structured trial diagnostics.

It does not read the next seed, mutate the seed plan, decide acquisition completion, finalize a
checkpoint, or directly implement learning.

## Orchestration Responsibilities

The orchestration boundary owns:

1. retained learned-seed ordering and URL-form ordering;
2. invocation of exactly one deterministic trial for each selected learned starting seed;
3. aggregation of trial diagnostics and candidate outcomes;
4. continuation after an unsuccessful learned trial;
5. termination after the first trial with a validated acquisition;
6. durable success publication and retained-anchor learning through the established repository
   transaction; and
7. checkpoint finalization and overall run status.

## Observable Compatibility Evidence

`make task058-proof` compares the legacy aggregate configured-discovery entry point with the new
configured fallback trial using two redirect aliases. It proves:

- identical request order;
- identical candidate canonical projection;
- identical traversal diagnostics after excluding only the new trial-attribution fields;
- preservation of all requested and resolved aliases; and
- an overall `observable_behavior_unchanged: true` result.

The focused regression also preserves the existing mixed-success warning result, deferred
retrieval boundary, redirect convergence, configured hint fallthrough, expected-period fallback,
checkpoint-backed no-change behavior, Pull Workflow outcome mapping, and REST result contract.

## Verification Results

### Focused orchestration and transcript regression

Command: `make task058-test`

Result: PASS, 107 tests. This includes TASK-058, TASK-057, TASK-056, TASK-053, TASK-052,
TASK-048/TASK-048A, Pull Workflow, REST, and capability-selection coverage.

The TASK-058 cases specifically prove:

- retained learned seed forms preserve their existing order;
- each learned starting seed receives its own trial identity and outcome;
- a failed trial alone does not advance checkpoint or anchor learning;
- the next learned seed executes only through orchestration;
- the first validated-success trial prevents remaining learned and configured trials from running;
- successful retained-anchor learning uses the same validated requested URL;
- checkpoint position remains the validated reporting-period ordinal; and
- fully exhausted failures produce no checkpoint and no learned anchor.

### Manual deterministic compatibility proof

Command: `make task058-proof`

Result: PASS. The generated JSON reports identical candidate projection, traversal diagnostics,
and request ordering, with all redirect aliases retained.

### Full repository validation

Command: `make validate`

Result: PASS. The suite ran 556 tests, followed by all required acquisition/engine demos, offline
proofs, lint, formatting, type checking, import verification, documentation checks, architectural
baseline checks, and source archive build/integrity verification.

## Files Changed

- `src/rfi/acquisition/engine.py`: trial contract and acquisition-level trial execution,
  aggregation, completion, persistence, and checkpoint lifecycle.
- `src/rfi/acquisition/__init__.py`: public export of the trial contract.
- `src/rfi/discovery.py`: transcript seed planner, single-trial entry point, compatibility entry
  point, and trial diagnostics.
- `tests/test_task058.py`: focused orchestration, termination, learning, and checkpoint evidence.
- `scripts/task058_orchestration.py`: deterministic before/after observable compatibility proof.
- `Makefile`: focused test, proof, and review-package targets.
- `scripts/generate_task058_review.py`: commit-aware validation and review-package generation.
- `docs/TASK-058-review.md`: this architectural and verification report.
- `tasks/TASK-058-Externalize-Transcript-Acquisition-Orchestration.md`: authoritative completed
  task ticket.
- `docs/design/TRANSCRIPT_LLM_SEED_RECOVERY.md`: authoritative design reference supplied with the
  task.

## Assumptions, Limitations, and Follow-up Observations

- The active ticket explicitly assigns checkpoint advancement and retained-anchor learning to
  orchestration. One paragraph in the design reference lists them under deterministic-trial
  responsibilities; the task-specific invariant was applied as required.
- `TASKS.md` already contains a separate completed row using the identifier TASK-058 for “Pull
  Workflow progress feedback,” while two TASK-058 tickets exist under `tasks/`. That pre-existing
  roadmap identity collision was not changed because resolving task numbering is outside this
  architectural refactor.
- The configured-hint/search path intentionally remains one established fallback pipeline. This
  preserves redirect-alias convergence, global configured-hint traversal diagnostics, and all
  operator-visible behavior. Only learned retained-anchor sequencing was externalized by this
  task.
- Temporary seeds, LLM recovery, selection criteria, HTTP exposure, and backfill remain unstarted.

## Architectural Status Summary

| Subsystem | Responsibility | Status | Important limitations / next milestone |
|---|---|---|---|
| Transcript acquisition orchestration | Learned seed order, trial sequencing, completion, aggregation, durable success, learning, checkpoint finalization | Complete | No temporary-seed or selection-criteria inputs |
| Deterministic transcript trial | One supplied start, traversal, ranking, retrieval, validation, structured diagnostics | Complete | Current acquisition target remains implicit `latest` behavior |
| Configured deterministic fallback | Existing configured hints and bounded identity search | Complete | Deliberately unchanged and retained as one fallback pipeline |
| Persistent retained-anchor learning | Evidence-qualified move-to-front bounded history | Complete | Repository naming remains historical LIFO/stack terminology |
| Pull Workflow and operator surfaces | Existing status, diagnostics, REST/GUI/CLI behavior | Complete | No TASK-058 HTTP or UI changes |
| Explicit acquisition selection criteria | Future target selection beyond current default | Not Started | Next planned architectural milestone |
| Bounded LLM temporary-seed recovery | Propose temporary URL only after deterministic exhaustion | Not Started | Depends on this trial/orchestration boundary |
| Historical transcript backfill | Date/fiscal-period driven acquisition | Not Started | Depends on future selection framework |

The next architectural milestone is explicit acquisition selection criteria with the current
`latest` behavior retained as the default. Bounded LLM-assisted temporary-seed recovery can then be
inserted between deterministic exhaustion and final acquisition completion without restructuring
the deterministic trial.
