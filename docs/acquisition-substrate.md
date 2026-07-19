# Acquisition substrate

TASK-002 implements the repository-owned boundary that accepts deterministic candidates and exact
retrieval results from future adapters. It does not discover or retrieve anything itself.

## Contracts and identity

`SourceProfile` governs a source by stable `source_id`, explicit enablement, generic mechanism,
deterministic configuration, and policy. `CandidateDocument` separately carries a repository-owned
`candidate_id` and `document_id`. `DiscoveryProvenance` and `RetrievalResult` retain provider
identifiers and mutable locations as attributes; neither can define repository identity.

The repository derives `artifact_id` from the SHA-256 digest of exact bytes. Every successful
acquisition creates a separate immutable `observation_id`, and a caller supplies a stable
`attempt_id` for each materially distinct retrieval activity. These identity domains
are never interchangeable:

| Identity | Owner | Meaning |
|---|---|---|
| `source_id` | repository governance | configured acquisition source |
| `document_id` | repository domain | stable logical source document |
| `artifact_id` | repository evidence | one exact byte sequence |
| `observation_id` | repository evidence | one successful acquisition observation |
| `attempt_id` | repository history | one materially distinct activity |
| provider identifiers | external provider | provenance attributes only |

## Authoritative and derived state

Authoritative state consists of governed source records, immutable artifact-observation records,
immutable retrieval-attempt records, checkpoint-advance events, and artifact integrity metadata in
SQLite, plus immutable artifact bytes in the content-addressed filesystem. The document and current
checkpoint projections are transactionally maintained structured state. Physical schema and object
paths remain private repository implementation details.

Artifact metadata records SHA-256, byte count, media type, and a relative content reference.
Content writes use exclusive creation and flush file content and its directory entry. Existing
exact content is idempotent; different content under an existing immutable identity raises a
conflict. Integrity verification recomputes bytes independently and validates every successful
structured reference.

Attempt, observation, and checkpoint-event rows are immutable domain records. The repository API
can append or accept an exact idempotent repeat, but cannot update a completed record.
Failed, skipped, duplicate, and successful outcomes retain source, candidate, document, time,
mechanism, diagnostics, and artifact/checkpoint relationships where applicable.

## Durability and failure ordering

A successful operation orders effects as follows:

1. store or verify exact artifact bytes in content-addressed storage;
2. start one immediate SQLite write transaction;
3. insert or verify immutable artifact metadata;
4. insert the successful attempt and its immutable observation;
5. publish the document projection and optional checkpoint event/current checkpoint;
6. advance the repository revision and commit once.

The checkpoint event is the durable progress fact. It cannot commit without the related successful
attempt. A failure before artifact durability leaves nothing. A failure after artifact durability
but before commit can leave inspectable orphan evidence; all structured changes roll back. A
failure before transaction commit never advances progress. Retrying the same attempt is
idempotent and never duplicates immutable records.

No cross-substrate ACID transaction is claimed. Partial durability is explicit and detectable.
SQLite serializes structured writers with bounded busy handling while WAL permits local readers;
immutable content creation prevents silent byte replacement.

## Checkpoints and replay

Checkpoints are source-scoped pairs of a non-negative monotonic `position` and an opaque `cursor`.
Positions cannot move backward. Reusing a position with a different cursor is ambiguous and is
rejected. The cursor is not interpreted by the substrate.

The public `advance_checkpoint` operation supports bounded engine finalization. It requires an
existing successful attempt for the same source before appending the normal repository-owned
checkpoint event. This is an additive TASK-003 facade operation; storage layout and TASK-002
ordering semantics are unchanged.

Replay validates authoritative records and recomputes the document and source-progress projections
inside SQLite. It reads local state only. It does not call adapters, open network connections,
interpret documents, or create downstream knowledge. A failed replay transaction leaves the prior
projections intact.

## Operator commands

Run `make acquisition-demo` for the deterministic fixture lifecycle and `make validate` for all
project checks. Inspection, integrity, deletion, and rebuild commands are listed in
[development guidance](development.md#acquisition-operator-workflow).
