# ADR-0003: Fixture-backed acquisition engine

- Status: accepted
- Scope: TASK-003

## Context

TASK-002 owns immutable evidence, append-only attempts, derived views, checkpoint events, replay,
and integrity. TASK-003 must orchestrate credible discovery and retrieval behavior without allowing
provider state or engine control flow to become authoritative and without implementing a live
source.

## Decision

Use one sequential `AcquisitionEngine` over the public `AcquisitionRepository` facade, selected
through an explicit mechanism-to-instance `AdapterRegistry`. Keep the adapter contract to paged
discovery and exact-byte retrieval. Use frozen values for pages, candidates, outcomes, and run
results. Sort candidates deterministically, reject ambiguous identity reuse and continuation
cycles, record exact duplicates, and derive stable attempt identity from repository candidate,
document, revision, and outcome semantics.

Treat provider continuations as ephemeral in-run state. Treat durable progress as a bounded-run
checkpoint derived from the complete observed candidate set. Add a compatible public repository
operation that may finalize a checkpoint only against an existing successful attempt for the same
source; physical records and ordering remain repository-owned. Incomplete runs retain durable
artifacts/history but do not publish new progress, and retries complete through idempotent public
operations.

Use two checked-in file-backed adapters: a single-page stable-ID catalog with skip and revision
behavior, and a paginated URL-like feed with within/across-page duplicates and injected transient
failures. Adapter construction is the runtime-only configuration/credential boundary; governed
profiles may hold a non-secret reference but no credential value.

Retain TASK-002's single-writer assumption. Execute sources sequentially in stable source-ID order.

## Alternatives considered

- Advancing checkpoints after every candidate would expose more incremental progress but could
  hide an unprocessed later candidate after a page or discovery failure. Bounded finalization is
  simpler and fails conservatively.
- Persisting provider cursors would make resumption begin later, but would elevate replaceable
  provider state into durable semantics and complicate cross-provider replay.
- Buffering all pages before retrieval would simplify global sorting, but would not exercise the
  required failure after one page's candidates become durable and before the next page.
- A dynamic plugin framework would anticipate future adapters without evidence. Explicit
  registration is inspectable and sufficient for two demonstrated behaviors and the next adapter.
- Giving adapters repository access would reduce conversions but would violate repository
  ownership of identity, evidence, checkpoints, and replay.
- Recording every equivalent run under a new attempt identity would retain more execution noise.
  Stable material-operation identity instead keeps equivalent complete runs repository-idempotent;
  distinct transient failure and success outcomes remain separate append-only evidence.
- A scheduler, queue, parallel workers, or automatic backoff would exceed the single-owner POC and
  obscure deterministic retry semantics.

## Consequences and limits

The engine is small, explicit, offline-testable, adapter-replaceable, and independently auditable.
Partial work is visible and safely resumable, while checkpoints cannot overstate bounded progress.
Repeated complete runs leave repository-derived state unchanged; revisions add evidence without
rewriting history. The proof does not address real network behavior, provider authentication,
concurrency, large-scale pagination drift, or downstream document understanding.
