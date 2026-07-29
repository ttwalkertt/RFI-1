# TASK-047 Review

## Implementation Summary

TASK-047 adds the shared closed-open date-interval request/result contract, complete/incomplete/
indeterminate coverage, structured failures, and a narrow application integration. Successful
envelopes reuse `CandidateDocument`, `RetrievalResult`, and
`AcquisitionRepository.record_success`. Schema 13 adds interval outcome history that references the
existing successful attempts and observations.

No production earnings-call retriever, press-release retriever, provider discovery, HTTP logic,
parser, production adapter, or generic retrieval framework was added. The only acquisition
implementation used for proof is a test-local non-production fake.

## Architecture and Responsibility Boundaries

- The request references the existing firm catalog `firm_id` and canonical acquisition-template
  `artifact_id`; it establishes no parallel identifier catalogs.
- Acquisition owns discovery, retrieval, bounded within-invocation transient retries, successes,
  structured failures, and truthful coverage.
- The application validates canonical firm/type and governed-source policy, sends successful
  envelopes through existing ingress, records the outcome, and retains ownership of later retry and
  scheduling policy.
- The repository retains content-hash artifact identity, immutable bytes, candidate/document
  ingress, duplicate handling, observations, attempts, and acquisition history.
- Interval outcome rows are additive history. Their artifact members reference existing attempt and
  observation rows; there is no second artifact/document/observation canonicalization pipeline.
- The public result has no ordering semantics and exposes no sessions, callbacks, workers, queues,
  resume protocol, context manager, concurrency, or synchronous/asynchronous requirement.

## Schema and Compatibility

Schema 13 adds `interval_acquisition_outcomes`, `interval_acquisition_artifacts`, and one history
index. Outcomes retain request boundaries, coverage, failure count, time, and canonical structured
history. Artifact membership links existing `acquisition_attempts` and `artifact_observations`.
Migration from schema 12 is additive; historical migration tests from versions 1 through 11 now
verify arrival at schema 13. Existing acquisition and SQLite repository tests remain unchanged in
behavior.

## Recovery Evidence

`test_incomplete_successes_are_retained_and_later_run_fills_hole` proves a first invocation can
persist one artifact with incomplete coverage and a structured missing-artifact failure. Reacquiring
the same interval later returns both artifacts with complete coverage. The repository retains two
content artifacts, reuses the first immutable artifact, records three ordinary observations, and
keeps both interval outcomes (`incomplete`, then `complete`). Repository integrity reports `PASS`.

The empty-interval/no-match test records `complete` with zero artifacts and zero failures. Separate
history assertions preserve `incomplete` and `indeterminate` as distinct values. Partial successes
are persisted even when overall coverage is incomplete.

## Changed-File Inventory

- Contract/application/repository: `src/rfi/acquisition/contracts.py`,
  `src/rfi/acquisition/interval.py`, `src/rfi/acquisition/repository.py`,
  `src/rfi/acquisition/__init__.py`.
- Schema/migration: `src/rfi/storage/sqlite.py`.
- Focused and compatibility tests: `tests/test_task047.py`, acquisition/foundation inventory tests,
  and prior schema-version assertions.
- Architecture/task documentation: `docs/date-delimited-acquisition-contract.md`,
  `docs/acquisition-substrate.md`, `ARCHITECTURE.md`, the supplied concept note, task ticket,
  `TASKS.md`, and this review.
- Review/baseline tooling: `scripts/generate_task047_review.py`, `scripts/check_baseline.py`, and
  `docs/design-baseline.json`.

## Verification

The self-contained review package retains complete command output for:

- `PYTHONPATH=src .venv/bin/python -m unittest tests.test_task047 -v`;
- `PYTHONPATH=src .venv/bin/python -m unittest tests.test_acquisition tests.test_task021 -v`;
- `git diff --check`;
- `make validate`.

The final package manifest records exit codes, changed files, SHA-256 checksums, the complete patch,
ZIP member inventory, and ZIP integrity output.

## Limitations and Follow-On Work

- A process interruption after one or more ordinary success ingresses but before interval-outcome
  recording can leave those successful attempts visible without an interval link. Recovery remains
  safe by reacquiring the interval; no session or rollback protocol is introduced.
- The service records a completed result and deliberately does not choose, register, or orchestrate
  future retrievers.
- Earnings-call and press-release implementations remain separate follow-on tasks and should
  initially implement this contract independently.
- Common production infrastructure should be extracted only after multiple implementations prove
  semantic equivalence.

## Architectural Status Summary

| Subsystem | Responsibility | Status |
| --- | --- | --- |
| Interval contract | Canonical request, result, failure, and coverage semantics | Complete |
| Application integration | Canonical policy validation and existing-ingress consumption | Complete |
| Immutable acquisition ingress | Artifact/document/attempt/observation persistence | Complete, reused |
| Interval outcome history | Durable request, coverage, failures, and existing-ingress links | Complete |
| Retry ownership | Invocation retries in acquisition; later policy in application | Complete |
| Recovery | Reacquire interval and rely on repository idempotency | Complete |
| Production earnings-call retriever | Artifact-specific implementation | Not Started |
| Production press-release retriever | Artifact-specific implementation | Not Started |

Architectural change: one observable interval boundary and additive outcome history are now shared;
execution mechanics remain artifact-family-specific. Important limitation: ingress and interval
history are sequential durable operations, with safe interval reacquisition as interruption
recovery. Next architectural milestone: implement the first production artifact-family retriever
independently against this contract.
