# ADR-0002: Acquisition substrate and repository contracts

- Status: accepted
- Scope: TASK-002

## Context

Later deterministic adapters need a repository-owned boundary that preserves evidence and audit
semantics without importing source-specific behavior. The POC must prove immutable artifacts,
append-only history, rebuildable access, replay, and safe progress ordering with no network or
downstream intelligence capability.

## Decision

Use dependency-free frozen dataclasses for provider-neutral input contracts and a single
`AcquisitionRepository` facade for repository operations. Keep its filesystem layout private.
Represent authoritative source profiles, artifact content and metadata, retrieval attempts, and
checkpoint events as exclusive-create immutable files. Derive content-addressed artifact identity
from SHA-256 while callers provide repository-governed source, document, candidate, and attempt
identities. Provider identifiers and URLs remain provenance attributes.

Use a disposable JSON document index derived from successful attempt records. Treat checkpoint
events as authoritative and the checkpoint JSON file as a disposable view. Checkpoint position is
an explicit monotonic integer; cursor content remains opaque. Publish checkpoint events only after
artifact, ledger, and index durability. Replay validates local authoritative state and atomically
replaces both derived views without contacting any external source.

The POC assumes a single writer. File and directory fsync plus exclusive creation prevent silent
replacement and make partial durability observable. It does not claim a multi-file ACID
transaction. Deterministic failure points verify each ordered boundary and retry/replay behavior.

## Alternatives considered

- SQLite could supply transactions and constraints, but would make the initial authoritative
  repository less directly inspectable and combine append-only facts with mutable views. It
  remains credible for an MVP after concurrency and scale are observed.
- One JSONL ledger would make chronological scanning convenient, but crash-safe append framing,
  idempotent identity lookup, and external truncation detection add machinery. Immutable records
  make identity conflicts and partial writes simpler for this single-owner POC.
- Using URLs, filenames, or provider document IDs as internal identity was rejected because those
  values are mutable or provider-owned.
- Advancing a mutable checkpoint file directly was rejected because it would be the sole owner of
  progress history and could advance before other required effects.
- Rebuilding the index by scanning artifacts alone was rejected because bytes do not contain the
  complete candidate, document, source, retrieval, and diagnostic provenance.
- A general adapter or transaction framework was rejected because TASK-002 has no real adapter and
  the current requirements need only a repository sink and explicit ordered effects.

## Consequences and limits

The system is offline, inspectable, content-verifiable, idempotent by immutable identity, and
replayable after total loss of derived state. Orphan artifacts can remain after an interrupted
operation; they are preserved and reported as evidence rather than silently removed. Immutable
records can still be modified by an actor with filesystem permission, but integrity checks expose
artifact corruption and repository review exposes record changes. Multi-process writer locking,
permissions hardening, cryptographic ledger chaining, schema migration, large-corpus indexing,
backup policy, and production object storage are deferred until operational evidence justifies
them.
