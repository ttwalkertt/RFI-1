# Fixture-backed acquisition engine

TASK-003 connects deterministic source discovery and retrieval to the TASK-002 repository facade.
The repository remains the durable system of record; adapters and run summaries are replaceable
execution state.

## Responsibilities and contracts

`AcquisitionEngine` loads and revalidates an enabled `SourceProfile`, selects the profile's exact
mechanism from `AdapterRegistry`, consumes `DiscoveryPage` values, validates and orders
`AdapterCandidate` values, retrieves exact bytes, and invokes only public
`AcquisitionRepository` operations. `AcquisitionKernel` is the small composition root that runs
enabled sources in source-ID order.

An adapter implements paged `discover(profile, continuation)` and `retrieve(profile, candidate)`.
It owns provider interpretation, continuation tokens, and retrieval diagnostics. It never receives
a repository, assigns artifact identity, writes evidence, publishes checkpoints, or interprets
document meaning. Provider IDs and URL-like references remain provenance only. `RetrievalResult`
carries exact bytes and metadata into the existing repository contract.

Registration is explicit and in-process. There is no dynamic loading or general plugin discovery.
Duplicate mechanisms and missing registrations fail closed, and `registrations()` makes selection
inspectable.

## Run lifecycle and result model

A caller supplies a validated `run_key`; the structured identity is
`run-<source-id>-<run-key>`. Injected clocks provide start and completion time. Results report
pages, discovered and unique candidates, retrievals, durable acquisitions, unchanged operations,
duplicates, skips, failures, checkpoints before and after, provider continuations, per-candidate
outcomes, and diagnostics.

Terminal states are derived from observed effects:

- `complete`: bounded discovery and processing completed and required progress is durable;
- `partial`: retryable failure occurred, possibly after durable evidence;
- `blocked`: non-retryable retrieval/policy condition prevents completion;
- `failed`: malformed output or repository conflict/integrity failure invalidated the run.

A complete run may contain a non-fatal policy skip. Run summaries are execution projections and are
not authoritative replay inputs.

## Candidate ordering, duplicates, and revisions

Each page is sorted by `(position, document_id, revision, candidate_id)`. Pages must be monotonic by
position; equal boundary positions are valid and tie breakers are stable. Exact repeated candidate
semantics are recorded once per candidate/outcome identity as duplicate discovery. Reuse of one
candidate identity with different semantics is malformed output and fails observably.

Repository attempt identity is a hash of repository candidate identity, document identity,
revision, and material outcome. Provider identifiers do not enter repository identity. Equivalent
operations therefore repeat idempotently. A revision uses a new candidate/revision identity and
immutable artifact while retaining the stable repository document identity, so the derived index
relates both artifacts without changing prior records.

## Pagination, checkpoints, and resumption

Provider continuation tokens exist only while the engine traverses pages. They appear in run
diagnostics but never become source identity, repository evidence, or the sole replay record. The
engine checkpoint cursor is instead a digest of the complete bounded candidate set, paired with
its maximum monotonic position.

Candidates at or before the durable checkpoint position are filtered on later equivalent runs.
The engine processes pages incrementally, so exact artifacts and attempt history may be durable
before later discovery or retrieval fails. No new checkpoint is published for an incomplete run.
Retry repeats those repository operations idempotently and continues to completion.

Checkpoint finalization uses the public repository `advance_checkpoint` operation. That operation
requires a durable successful attempt for the same source and then appends the TASK-002 checkpoint
event and derived view. Thus complete bounded discovery, durable evidence, attempt history, and
index publication all precede progress. A policy-only bounded run with no successful anchor is
blocked rather than inventing progress evidence.

## Failure, retry, and concurrency model

Stable classes distinguish transient adapter failure, permanent retrieval failure, malformed
adapter output, policy rejection, repository conflict, and repository integrity failure. Adapter
failures declare retryability. Transient failures preserve partial evidence and invite the same
single-process operator workflow to resume. Permanent failures block. Malformed output and
repository failures fail closed. Every retrieval failure is also written through the public
append-only outcome contract when a valid candidate exists.

The POC remains single-process, single-writer, and sequential by governed source. It provides no
scheduler, distributed retry, locks, queues, or cross-source transaction.

## Fixture representativeness

`FixtureCatalogAdapter` represents a single-page catalog with stable provider IDs, unsorted input,
a policy skip, and a later changed artifact under one stable provider reference and repository
document identity. `FixtureFeedAdapter` represents URL-like references, two pages, opaque
continuation, deliberately unsorted input, an exact duplicate within page one, an exact duplicate
across pages, and transient discovery/retrieval failures. Both decode checked-in JSON and read
checked-in bytes through the production adapter and engine contracts. Neither can write repository
state or open a network connection.

## Configuration and credential boundary

Source profiles contain deterministic, non-secret configuration and may carry only an opaque
`credential_reference`; the catalog fixture demonstrates that shape. Runtime-only values belong
in adapter construction by the composition root and must never be copied into profiles,
diagnostics, fixtures, repository calls, logs, or review artifacts. The fixtures require no
credential and the engine has no credential store. A future live adapter may resolve a reference
at construction time, but it must persist only non-secret provenance returned through repository
contracts.

## Replay boundary and limitations

Replay reads authoritative source records, ledger records, artifact metadata, and exact local
bytes. It neither constructs nor calls adapters and does not inspect fixture provider state.
Deleting both mutable views after multi-source and multi-run acquisition and invoking repository
replay restores deterministic indexes and checkpoints with adapters disabled and socket creation
blocked.

The fixtures do not prove live-service authentication, HTTP semantics, rate limits, changing
pagination windows, real provider schemas, large-corpus performance, or concurrent writers. Those
questions remain for later source-integration tasks. Extraction, knowledge development, AI, search,
projection, and reporting remain outside this subsystem.

## Operator commands

See [development guidance](development.md#acquisition-engine-operator-workflow) for fixture source
registration, adapter inspection, single/all-source execution, partial-run resumption, integrity,
rebuild, replay, and validation commands.
