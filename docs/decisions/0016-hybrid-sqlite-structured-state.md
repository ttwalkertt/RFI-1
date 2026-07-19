# ADR-0016 — Hybrid SQLite authority for structured repository state

## Status

Accepted as the TASK-020 architecture recommendation. No migration is implemented.

## Context

RFI's public repository contracts, immutable evidence model, and lifecycle boundaries are mature,
but most authoritative structured state is persisted through custom immutable JSON records,
catalog pointers, generation directories, replay code, and filesystem consistency checks.
TASK-018 made artifact reads independent of that layout. TASK-019 clarified artifact,
observation, and attempt identities. The roadmap will add more structured relationships and
queries.

The source-object subsystem already demonstrates a rebuildable SQLite catalog. Current runtime
operation remains local, offline-capable, single-operator, and single-writer.

## Decision

Recommend an explicit hybrid relational architecture for a later task:

- SQLite is authoritative for structured runtime records and relationships.
- Content-addressed immutable artifact files remain authoritative for exact acquired bytes.
- Version-controlled governance documents and acquisition templates remain file authorities.
- Rebuildable source, retrieval, and query indexes remain non-authoritative.
- Independently portable workspaces retain separate authority and should use separate SQLite
  databases.

Public repository, reader, artifact query, content, and service contracts remain the only consumer
interfaces. Database schema is private. Immutable revisions and events remain append-only domain
semantics enforced through schema constraints and repository methods.

Use SQLite because it matches the demonstrated workload, is available through Python's standard
library, supports transactions and indexes, and adds no server operations. Use WAL only on local
storage, enable foreign keys on every connection, bound write transactions and busy waits, and
back up with the online backup API or a verified offline copy.

PostgreSQL is the escalation target when multi-host or sustained concurrent writers, remote
service deployment, managed HA, or point-in-time recovery become requirements.

Migration must use an offline shadow import, source/target differential validation, verified
pre-cutover backup, and one atomic authority marker. Permanent dual-write and silent fallback to
stale file authority are prohibited. Exact artifact bytes are not migrated into database BLOBs.

## Consequences

Structured publication can use transactions, foreign keys, uniqueness, and indexes rather than
multi-file ordering and repair. RFI can retire repeated pointer, inventory, atomic structured-file,
and scan mechanics after verified cutover while retaining semantic identity, provenance,
integrity, replay, and query code.

Physical consolidation must not collapse evidence, knowledge, retrieval, intelligence, and
workspace authority classes. Schema migrations, backup/restore rehearsal, WAL operations,
database integrity checks, and bounded writer coordination become explicit responsibilities.

TASK-020 itself changes no dependency, state, behavior, or authority. A separate task is required
before implementation.

## Alternatives considered

- Retaining file/ledger storage was rejected as the long-term target because custom storage and
  consistency mechanics expand with every structured domain.
- A relational read model was rejected as the target because it duplicates schemas and freshness
  logic without fixing structured write atomicity.
- PostgreSQL was deferred because current evidence does not justify server operations.
- DuckDB, document, key-value, graph, and log products were rejected because no demonstrated
  workload outweighs relational transaction and integrity needs.
- Database artifact BLOBs were rejected because exact hostile evidence bytes should retain
  content-addressed storage and independent integrity/backup behavior.

## Decision triggers and proof limits

If implementation is deferred, reconsider before adding another custom structured authority or
when query latency, concurrency, backup, restore, or integrity evidence exceeds the current file
model. The implementation task must resolve the physical boundary for authoritative knowledge,
define pull/acquisition transaction ownership, inventory real legacy states, set recovery
objectives, and prove differential query and replay equivalence.

See `docs/storage_architecture_design_draft.md` for the complete comparison, schema concept,
migration/rollback design, risks, and go/no-go conditions.
