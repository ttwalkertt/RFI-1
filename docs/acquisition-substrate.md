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

Authoritative state consists of governed source records, immutable artifact bytes and integrity
metadata, immutable artifact-observation records, immutable retrieval-attempt records, and
immutable checkpoint-advance events. The
document index and checkpoint view are derived. Their physical layout is intentionally private to
the filesystem implementation.

Artifact metadata records SHA-256, byte count, and media type. Writes use exclusive creation,
flush file content, and flush their directory entry. Existing exact content is idempotent;
different content under an existing immutable identity raises a conflict. Integrity verification
recomputes bytes independently and validates every successful ledger reference.

Ledger records are individually immutable files rather than mutable current-state rows. The
repository API can append or accept an exact idempotent repeat, but cannot update a record.
Failed, skipped, duplicate, and successful outcomes retain source, candidate, document, time,
mechanism, diagnostics, and artifact/checkpoint relationships where applicable.

## Durability and failure ordering

A successful operation orders effects as follows:

1. store exact artifact bytes and immutable integrity metadata;
2. store the immutable successful acquisition observation;
3. append the successful retrieval-attempt record;
4. atomically publish the derived document index;
5. append the authoritative checkpoint event;
6. atomically publish the derived checkpoint view.

The checkpoint event is the durable progress fact. It cannot exist until artifact, retrieval
history, and index publication succeeded. A failure before artifact durability leaves nothing. A
failure after artifact durability can leave inspectable orphan evidence. A failure after ledger
append is repairable by replay. A failure before checkpoint publication never advances progress.
Retrying the same attempt completes missing later effects without duplicating immutable records.

No multi-file ACID transaction is claimed. Partial durability is explicit, detectable, and
recoverable. POC operation assumes one technical owner and no concurrent writers; exclusive files
prevent silent replacement, but full writer serialization and cross-process locking are deferred.

## Checkpoints and replay

Checkpoints are source-scoped pairs of a non-negative monotonic `position` and an opaque `cursor`.
Positions cannot move backward. Reusing a position with a different cursor is ambiguous and is
rejected. The cursor is not interpreted by the substrate.

The public `advance_checkpoint` operation supports bounded engine finalization. It requires an
existing successful attempt for the same source before appending the normal repository-owned
checkpoint event. This is an additive TASK-003 facade operation; storage layout and TASK-002
ordering semantics are unchanged.

Replay validates authoritative records, regenerates the complete document index from successful
attempts, and regenerates source progress from checkpoint events. It reads local files only. It
does not call adapters, open network connections, interpret documents, or create downstream
knowledge. Derived replacement uses same-directory atomic rename, so an injected replay failure
before publication leaves no partial views.

## Operator commands

Run `make acquisition-demo` for the deterministic fixture lifecycle and `make validate` for all
project checks. Inspection, integrity, deletion, and rebuild commands are listed in
[development guidance](development.md#acquisition-operator-workflow).
