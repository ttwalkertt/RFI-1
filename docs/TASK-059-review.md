# TASK-059 Verification Report

## Result

TASK-059 is Complete. Earnings-call transcript acquisition now carries one typed, immutable
`TranscriptAcquisitionTarget` through orchestration, every deterministic trial, candidate
provenance, validation, selection, and durable retrieval evidence. The target contains the firm,
canonical transcript artifact identity, and exactly one `TranscriptAcquisitionSelection`.

Omitted selection remains `latest`. Existing invocation paths, traversal, learned-seed order,
retry behavior, checkpoint ownership, retained-anchor learning, and TASK-058's first-success
behavior for `latest` are unchanged. `first_in_date_range` validates the complete bounded candidate
set across the unchanged trial plan, then publishes exactly one globally earliest qualifying
transcript.

No HTTP/service API, CLI, GUI, operator-supplied seed, LLM, continuation-cursor, or historical
backfill orchestration was introduced.

## Architectural Summary

`TranscriptAcquisitionSelection` is a frozen, typed contract with exactly two modes. `latest`
rejects date boundaries. `first_in_date_range` requires a valid inclusive `start_date` and
`end_date`. Fiscal year and quarter do not appear in the selector.

`TranscriptAcquisitionTarget` is frozen and binds firm identity, canonical artifact identity, and
selection. `TranscriptAcquisitionOrchestrator` constructs it once per attempt and passes the same
object to every `AdapterAcquisitionTrial`; only `starting_seed`, `seed_kind`, and trial identity
vary. The acquisition engine rejects trial plans whose targets differ.

For `latest`, the engine retains the prior streaming behavior: execute learned seeds in FIFO order,
validate candidates in the existing deterministic rank, publish the first validated success, and
stop. For `first_in_date_range`, each trial uses the same traversal and ranking implementation.
Candidate bodies are validated by `EarningsCallTranscriptAcquisition`; only its normalized event
date can qualify the candidate. Qualified results remain non-durable until every planned trial is
evaluated. The engine selects by ascending validated event date and then the existing deterministic
proposal/candidate ordering, persists exactly one result, and applies established success learning
and checkpoint rules.

An unsuccessful range selection publishes no artifact, checkpoint, or learned anchor. A successful
historical selection cannot move an existing checkpoint backward. The requested selection is never
relaxed.

## Selection Contract Definition

- `TranscriptSelectionMode.LATEST`: compatibility default; no dates permitted.
- `TranscriptSelectionMode.FIRST_IN_DATE_RANGE`: one inclusive start/end range.
- `TranscriptAcquisitionSelection`: frozen validation and canonical attribution.
- `TranscriptAcquisitionTarget`: frozen firm, `earnings_transcript`, and selection identity.
- `AdapterAcquisitionTrial.acquisition_target`: the identical target used by every trial.
- `AdapterCandidate.acquisition_target`: the identical target delivered to qualification and
  validation; its canonical form is also retained in provenance.

## Propagation Path

1. `EarningsTranscriptPullAdapter` resolves omitted selection to `latest`.
2. `acquisition_trials()` creates one immutable target from the governed source profile.
3. `TranscriptAcquisitionOrchestrator.plan()` attaches that same target to every seed trial.
4. `AcquisitionEngine` verifies that all trial targets are identical.
5. `discover_trial()` verifies the adapter's immutable selection and attaches the target to every
   ranked candidate and its provenance metadata.
6. `retrieve()` verifies the candidate target against its canonical provenance before invoking the
   existing transcript validator.
7. The engine qualifies only normalized `validated_event_date` evidence and records the selection
   in terminal diagnostics and durable retrieval provenance.

## Compatibility Proof for `latest`

`make task059-proof` compares omitted selection with an explicit `latest` selection and reports:

- identical effective canonical selection;
- identical candidate projection;
- identical deterministic request order; and
- one immutable target across seed trials.

`make task058-proof` remains PASS after excluding only the new TASK-059 attribution fields from its
legacy/trial diagnostic comparison. It still proves identical requests, candidate projection,
redirect aliases, and traversal diagnostics. The TASK-058 focused regression remains unchanged and
passes.

## `first_in_date_range` Verification

Focused tests prove:

- inclusive boundary semantics and malformed-contract rejection;
- a later transcript found by the first seed does not defeat an earlier transcript found by a
  later seed;
- reversing discovery order for same-date candidates does not change the selected artifact;
- URL/title date hints cannot qualify an artifact whose normalized validated event date is outside
  the request;
- exactly one qualifying artifact becomes durable;
- explicit structured no-match is emitted when nothing qualifies;
- unsuccessful selection creates no checkpoint or retained anchor; and
- trial, candidate, validation, terminal, and durable provenance all carry selection attribution.

## Verification Results

- `make task059-test`: PASS, 113 tests, including TASK-059, TASK-058, TASK-057, TASK-056,
  TASK-053, TASK-052, TASK-048/TASK-048A, Pull Workflow, REST, and capability selection.
- Existing REST localhost test: PASS when run with permission to bind an ephemeral loopback port.
- `make task059-proof`: PASS.
- `make task058-proof`: PASS with `observable_behavior_unchanged: true`.
- Lint, formatting, type checking, and diff whitespace checks: PASS.
- `make validate`: PASS; complete repository validation evidence is included in the review package.

## Files Changed

- `src/rfi/acquisition/contracts.py`: typed immutable selection and target contracts.
- `src/rfi/acquisition/engine.py`: target verification, range qualification, globally earliest
  terminal selection, structured diagnostics, and deferred single-result persistence.
- `src/rfi/acquisition/__init__.py`: contract exports.
- `src/rfi/discovery.py`: target construction, propagation, provenance, and selection-aware
  validation intervals.
- `tests/test_task059.py`: focused acceptance and invariant evidence.
- `scripts/task059_selection.py`: manual default compatibility and propagation proof.
- `scripts/task058_orchestration.py`: excludes TASK-059 attribution fields from the TASK-058
  before/after diagnostic comparison.
- `Makefile`: focused test, proof, and review-package targets.
- `scripts/generate_task059_review.py`: commit-aware package generation and verification.
- `docs/TASK-059-review.md`: this report.
- `tasks/TASK-059-Add-Explicit-Transcript-Acquisition-Selection-Criteria.md`: completed ticket.
- `TASKS.md`: milestone status.

## Assumptions, Limitations, and Recommended Follow-on Work

- Date-range selection is an internal acquisition contract only. Existing public invocation paths
  intentionally supply no selection and therefore remain `latest`.
- The candidate/traversal bounds are unchanged. “Earliest” means the earliest fully validated
  transcript in the complete bounded deterministic trial result, not an assertion of unbounded web
  completeness.
- Same-day ambiguity uses existing deterministic ranking and candidate tie-breaking. No continuation
  identity or cursor was added.
- Range attempts exhaust the existing seed plan before terminal selection so starting-seed order
  cannot select a later qualifying date. This changes only when success is declared for the new
  mode; orchestration still owns trial order, exhaustion, and terminal publication.
- Future work may expose this contract through service/operator invocation paths. LLM temporary-seed
  recovery and repeated historical backfill remain separate milestones.

## Architectural Status Summary

| Subsystem | Responsibility | Status | Important limitations / next milestone |
|---|---|---|---|
| Transcript selection contract | Immutable qualification mode and optional inclusive date range | Complete | Internal only; no public caller input |
| Transcript acquisition target | Firm, canonical artifact, and selection identity shared across trials | Complete | Transcript-specific target |
| Transcript orchestration | Unchanged learned-seed planning, trial ownership, and terminal publication | Complete | Range mode exhausts bounded trials before selection |
| Deterministic transcript trial | One starting seed, unchanged traversal/ranking, validation, diagnostics | Complete | Existing discovery budgets remain authoritative |
| Candidate qualification | Validated event-date eligibility and deterministic earliest selection | Complete | Same-day identity uses existing tie-breaking |
| Persistence, learning, checkpointing | Publish one success; never learn/checkpoint from no-match | Complete | Historical success does not move checkpoint backward |
| Structured diagnostics/provenance | Mode, requested range, qualification, validation, terminal outcome | Complete | Bounded candidate samples |
| Public selection invocation | Service/operator selection input | Not Started | Recommended next exposure milestone |
| LLM temporary-seed recovery | Bounded advisory starting-seed proposals | Not Started | Separate future milestone |
| Historical backfill orchestration | Repeated range requests and continuation policy | Not Started | Separate future milestone |

The next architectural milestone should expose the immutable selection contract through an explicit
service/operator invocation boundary while preserving omitted `latest` behavior. LLM seed recovery
and historical backfill should remain separately reviewed milestones.
