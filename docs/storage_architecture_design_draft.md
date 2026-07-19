# Structured Repository Storage Architecture Review

Status: Architecture review complete; implementation not authorized by this document  
Task: TASK-020  
Decision date: 2026-07-18

## Executive decision

RFI should adopt a relational database-backed architecture for authoritative structured state,
using an explicit hybrid authority model:

- **SQLite is authoritative for repository-owned structured records.**
- **The content-addressed filesystem artifact store remains authoritative for exact immutable
  source bytes.**
- **Version-controlled documents and acquisition templates remain authoritative as repository
  configuration and governance inputs.**
- **Browser preferences, generated review packages, exports, caches, and rebuildable query/index
  state remain non-authoritative.**

This is a recommendation for a later migration milestone, not a migration. TASK-020 changes no
repository behavior, persistence format, authoritative state, or dependency.

The evidence is sufficient for a go recommendation for a separately authorized implementation
task, provided that task uses an offline, validated cutover and never operates file records and
database rows as simultaneous authorities. SQLite fits the demonstrated local, single-operator,
single-writer workload and is already used through Python's standard library for the rebuildable
source-object catalog. PostgreSQL would add unjustified server operations now. It becomes the
preferred escalation target if RFI requires multi-host service deployment, sustained concurrent
writers, managed high availability, or point-in-time recovery.

## Scope and review method

This review evaluates the storage architecture after TASK-018 established persistence-independent
artifact query contracts and TASK-019 separated artifacts, acquisition observations, and attempts.
It covers authoritative and rebuildable structured state, immutable bytes, query behavior,
transactions, concurrency, operations, recovery, and a conceptual target schema.

It does not implement a database, migration, compatibility shim, schema, dependency, or behavior
change. Product selection follows the architecture comparison; SQLite, PostgreSQL, DuckDB, and
non-relational stores were not assumed at the start.

Repository evidence inspected includes the governing architecture and operating model, TASK-018
and TASK-019 completion records, artifact-query guidance, acquisition and repository contracts,
ADRs 0001 through 0015, ROADMAP.md, BACKLOG.md, the design baseline, all repository persistence
implementations, and the review-package generators.

## Current architecture

RFI has strong logical boundaries and stable public contracts, but its structured persistence is
physically fragmented:

- acquisition uses immutable JSON files for sources, artifacts, observations, attempts, and
  checkpoint events, plus atomically replaced JSON document/checkpoint views;
- concepts, firms, and source profiles each use immutable revision JSON plus a mutable atomic
  catalog pointer;
- pull runs use atomically replaced JSON records;
- knowledge and retrieval use immutable generation directories plus pointer files;
- workspace history uses numbered JSON events, partial-file recovery, a custom hash chain, and a
  custom ZIP backup/restore protocol;
- source objects already use a rebuildable SQLite catalog published by atomic file replacement;
- artifact query currently scans authoritative acquisition records and derives a snapshot digest.

This arrangement successfully proved identity, immutability, replay, corruption detection, and
contract independence. It also requires repository-owned code to implement database mechanics:
exclusive creation, fsync ordering, atomic pointer publication, glob enumeration, uniqueness,
optimistic concurrency, referential checks, replay, generation selection, partial-file recovery,
backup inventory, and query scans. These mechanisms are repeated across bounded contexts.

The current file model provides no multi-record ACID transaction. Acquisition deliberately makes
partial durability observable and repairable across artifact metadata, observation, attempt,
document view, checkpoint event, and checkpoint view. That was proportionate for an acquisition
POC; it is not the preferred long-lived structured-state substrate as relationships and query
needs expand.

## Decision drivers

The comparison weights the following in order:

1. preserve repository authority, immutable evidence, provenance, and public contracts;
2. make cross-record invariants and publication atomic where they are logically one change;
3. reduce custom storage mechanics without retiring RFI-specific semantic validation;
4. support deterministic bounded queries and indexes without exposing physical storage;
5. retain local operation, low deployment burden, offline use, backup portability, and Python
   standard-library compatibility;
6. provide a credible concurrency and server migration path without paying its cost prematurely;
7. keep exact source bytes separate from structured records;
8. provide explicit migration, rollback, restore, rebuild, and corruption behavior.

## Options comparison

| Option | Authority and atomicity | Query/index capability | Operations | Assessment |
| --- | --- | --- | --- | --- |
| Retain file/ledger model | Clear authority, but application-managed multi-file ordering and repair; no cross-record transaction | Deterministic but scan-heavy; each index and cursor snapshot is custom | Lowest external infrastructure, highest custom persistence burden | Reject as long-term structured authority |
| Relational database as rebuildable read model | File records remain authoritative; DB can be discarded | Improves reads and indexing | Adds synchronization, staleness, rebuild, and two formats | Reject as target; acceptable only as a short-lived migration verification tool |
| Relational database as authoritative structured state | Native transactions, constraints, and one authority for related records | Strong typed indexes, joins, bounded pagination, and snapshots | Embedded SQLite is low burden; server database is higher burden | **Select** |
| Explicit hybrid authority | Structured state in relational storage; exact bytes in immutable object/file storage | Joins structured metadata without putting large hostile bytes in rows | Requires coordinated backup manifest and byte integrity checks | **Selected form of relational authority** |
| Another structured store | Product-dependent; key/document stores would retain application joins and integrity checks | No demonstrated graph, document, or analytical workload justifies weaker relational constraints | Adds a new dependency and operational model | Reject; no material justification |

### Retain the current file/ledger model

Strengths are inspectability with ordinary tools, content-addressed files, immutable event history,
easy fixture creation, and proven recovery behavior. The model also made subsystem independence
concrete during early milestones.

It is rejected as the target because every new structured relationship expands hand-built storage
code and scan cost. The current model cannot atomically publish an acquisition observation,
attempt, document state, and checkpoint. Cross-file uniqueness and foreign-key-like rules are
verified after the fact. Multiple processes can race on pointer state even when immutable file
creation prevents silent replacement. Backup consistency across pointer files and record trees
requires application-specific coordination.

Retaining the model would be reasonable only if RFI remained a bounded, single-writer acquisition
demonstrator with small record counts and rare new structured domains. The roadmap instead expects
observations, derivations, enrichments, claims, positions, investigations, and richer retrieval.

### Relational database as a rebuildable read model

This option preserves all file records as authority and builds relational tables for browsing and
planning. It lowers immediate migration risk and could accelerate TASK-018 queries.

It is rejected as the target because it solves query speed but not multi-record durability,
referential integrity, catalog pointer races, or duplicated record handling. RFI would own file
schemas, relational schemas, projection freshness, rebuild logic, and mismatch diagnostics. A read
model is justified only as a temporary shadow-validation artifact during migration; it must never
be presented as authority before cutover.

### Relational database as authoritative structured state

This option delegates transactions, uniqueness, foreign keys, indexes, isolation, and consistent
backup primitives to a relational engine. Immutable domain history remains append-only by schema
and repository API policy. RFI's service and repository contracts continue to own semantics.

It is selected because the record model is already relational: firms own revisions and
identifiers; profiles own items and candidates; documents reference firms and artifacts;
observations reference artifacts and attempts; checkpoints reference successful attempts;
knowledge versions reference source evidence; and workspaces contain ordered event streams.

### Explicit hybrid authority

The selected relational architecture is explicitly hybrid, not a blob-database design. Large or
hostile acquired bytes stay in the content-addressed artifact store. The database owns their
identity, digest, size, media type, content reference, and relationships. A database row without
verified bytes is an integrity failure; an unreferenced byte object is an inspectable orphan, not
an authoritative document.

This boundary retains exact-byte inspection, deduplication, independent hashing, safe preview,
and incremental object backup while giving structured metadata transactional integrity.

### Another structured store

No graph-first, document-first, key-value, or columnar requirement is demonstrated. RFI requires
cross-record constraints, ordered immutable histories, point lookups, filtered listings, temporal
queries, and provenance joins. JSON payloads can remain losslessly retained beside normalized
columns in a relational schema. DuckDB is optimized for embedded analytical work and its official
concurrency guidance centers read/write work in one process; it is not a better transactional
authority for this workload. A graph database might later be a rebuildable relationship-query
projection, but evidence-backed relationships do not justify making it the repository authority.

## Authority model by major record type

| Major record type | Current authority | Recommended authority | Notes |
| --- | --- | --- | --- |
| Governing docs, ADRs, task records | Version-controlled files | Version-controlled files | Human governance, not runtime state |
| Canonical acquisition template | Version-controlled YAML | Version-controlled YAML | Loaded and validated; schema version recorded in DB when used |
| Firm identity and immutable revisions | JSON revisions + catalog pointer | SQLite authoritative tables | Stable identity, immutable revisions, current selector transactionally constrained |
| Concept definitions and immutable revisions | JSON revisions + catalog pointer | SQLite authoritative tables | Preserve history and optimistic expected-revision checks |
| Firm source-profile revisions/items/candidates | JSON revisions + catalog pointer | SQLite authoritative tables | Preserve exact revision snapshot used by acquisition |
| Governed acquisition sources | Immutable JSON records | SQLite authoritative tables | Identity and policy references remain repository-owned |
| Artifact exact bytes | Immutable content files | Immutable content-addressed files | Never place hostile/large bytes in ordinary structured rows |
| Artifact metadata | Immutable JSON metadata | SQLite `artifacts` rows | Digest/content reference unique and immutable |
| Artifact observations | Immutable JSON records | SQLite append-only rows | One successful attempt to one observation; many observations to one artifact |
| Retrieval attempts and outcomes | Immutable JSON ledger records | SQLite append-only rows | Run-bound identity and exact diagnostic payload retained |
| Checkpoint-advance events | Immutable JSON ledger records | SQLite append-only rows | Must reference a successful attempt for the same source |
| Current source checkpoints | Derived JSON view | Rebuildable table/view | Updated in the same transaction as its event; replay-equivalent |
| Logical document/artifact associations | Derived JSON index | Rebuildable table/view | Public query semantics unchanged |
| Pull runs and artifact results | Mutable JSON run snapshot | SQLite structured rows | Lifecycle transitions constrained; terminal history retained |
| Source-object catalog | Rebuildable SQLite file | Rebuildable SQLite schema/database | Existing authority classification remains rebuildable structural index |
| Knowledge objects, versions, provenance, failures | JSON generations; versioned interpretive authority | SQLite authoritative history and generation publication | Preserve source/knowledge authority separation in contracts and schema modules |
| Retrieval/vector generations | Rebuildable JSON generations | Rebuildable SQLite tables or replaceable sidecar | Never promoted to authority; implementation may remain replaceable |
| Intelligence execution results | Ephemeral public records; workspace reference snapshots | Ephemeral unless retained by workspace | Do not create a competing evidence authority |
| Workspace investigations, events, annotations, execution references | Numbered JSON hash-chain events | Separate SQLite workspace database | Remains independently backupable; append-only event semantics retained |
| Workspace exports | Generated files | Generated files | Reproducible projection, not authority |
| Browser-local preferences | Browser localStorage | Browser localStorage | Disposable presentation state |
| Review/build/runtime artifacts | Generated files | Generated files | Evidence packages are review records, not runtime repository authority |
| Secrets and provider credentials | Environment/external secret source | Environment/external secret source | Never store in repository database or backup |

## Structured data and immutable-byte boundary

The database owns structured identity and relationships. The artifact store owns exact acquired
bytes. The contract is:

1. artifact content is named by a SHA-256-derived `artifact_id` and created immutably;
2. content is flushed before a structured transaction may reference it;
3. the transaction inserts or verifies artifact metadata, then atomically records observation,
   attempt, logical-document association, checkpoint event, and checkpoint projection as needed;
4. transaction failure may leave an unreferenced content object, which integrity inspection can
   report and a separately authorized retention policy may later collect;
5. structured state never claims available content unless digest, size, and content reference
   verify against stored bytes;
6. backup and restore validate both database consistency and a manifest of referenced immutable
   bytes.

Do not store artifact bytes, source context bodies, raw model input/output, credentials, or review
ZIPs in the authoritative structured database. Small canonical JSON payloads may be retained in
rows for lossless compatibility, but identities, foreign keys, query keys, lifecycle state, dates,
and ordering fields must be normalized and constrained.

## Repository-owned code: retain versus retire

### Retain

RFI must retain code that defines domain meaning:

- stable identity derivation and canonical payload hashing;
- immutable revision, append-only history, and optimistic expected-revision semantics;
- source-effective chronology and deterministic tie-break rules;
- provider and canonical-artifact normalization;
- acquisition ordering and the exact-byte-before-reference invariant;
- public repository, artifact query, summary, detail, content, and reader contracts;
- provenance validation, artifact checksum verification, and authority fingerprints;
- bounded query inputs, opaque cursor encoding, stale-snapshot behavior, and sanitized failures;
- adapter selection, acquisition policy, knowledge lifecycle, and workspace semantics;
- migration reconciliation and compatibility validation.

### Retire after verified cutover

RFI should retire storage mechanics now provided by the relational engine:

- per-record JSON path construction and glob enumeration;
- repeated `create_immutable`, temporary-file, fsync-directory, and atomic-pointer helpers for
  structured records;
- hand-built catalog current-pointer files and revision inventories;
- custom uniqueness and referential scans that duplicate database constraints;
- application-generated document/checkpoint snapshots that can be transactional projections;
- structured generation-directory publication and pointer selection;
- offset scans over all authoritative acquisition files for ordinary artifact queries;
- partial structured-state files and their quarantine mechanics;
- raw filesystem copying as a structured-state backup method.

Semantic verification remains necessary even when storage checks become database constraints.
Workspace hash chaining may remain as tamper-evident business history, but it should hash canonical
event payloads stored in rows rather than serve as a substitute transaction mechanism.

## Preservation of repository and query contracts

The migration must be an adapter replacement behind existing public protocols. No browser,
planner, acquisition engine, provider adapter, knowledge consumer, or intelligence component may
issue SQL or depend on table names.

TASK-018 semantics remain binding:

- separate query, summary, detail, page/cursor, and content contracts;
- canonical artifact rather than provider-shaped hierarchy;
- source-effective latest/oldest ordering;
- bounded queries and deterministic tie-breaks;
- exactly one selected TASK-019 observation with no metadata merging;
- snapshot-bound stale cursor rejection;
- stored exact bytes as the primary inspection path;
- read-only query behavior and structured corruption failures.

Cursor tokens may change format at the migration boundary but must remain opaque. A cutover must
invalidate pre-cutover cursors explicitly rather than reinterpret them. Repository service
contract tests and golden query fixtures are the compatibility gate.

## Transactions and concurrency

### Required transaction boundaries

- Creating or revising a firm, concept, or source profile: insert immutable revision, dependent
  items, history edge, and current selector in one transaction.
- Publishing a source-profile batch: all requested initial revisions and selectors succeed or
  none do.
- Successful acquisition: after artifact bytes are durable, insert/verify artifact metadata,
  observation, attempt, document association, checkpoint event, and current checkpoint in one
  short transaction.
- Failed/skipped/duplicate acquisition outcome: append the attempt and pull-result transition in
  one transaction where the workflow owns both.
- Publishing a knowledge generation: versions, provenance edges, failures, and selected generation
  become visible atomically.
- Appending a workspace event: sequence allocation, previous hash, event payload, and current
  projection update are one transaction.

Transactions must not include provider network I/O, model calls, artifact streaming, HTML parsing,
or long-running index construction. Those occur before a short publication transaction.

### SQLite concurrency policy

Use WAL mode on a local filesystem, foreign keys enabled on every connection, a bounded busy
timeout, explicit transaction modes, and short writer transactions. SQLite supports concurrent
read transactions but one writer at a time; that matches measured RFI operation. Application
services should serialize or retry bounded write conflicts and preserve optimistic revision IDs.

WAL databases must not live on a network filesystem. Long-lived read transactions must be bounded
so checkpoint progress is not starved. Schema migration obtains exclusive application ownership.

### PostgreSQL escalation triggers

Select PostgreSQL instead of SQLite before implementation, or migrate later through the same
repository contracts, if any of these become committed requirements:

- writers on more than one host;
- sustained simultaneous writer workload for acquisition, admin, and workspace services;
- remote service deployment where a database daemon is already an accepted dependency;
- managed replication, automatic failover, or high-availability objectives;
- point-in-time recovery with a defined recovery-point objective smaller than periodic embedded
  backups can meet;
- database size/query workload that demonstrates embedded operation is inadequate.

PostgreSQL provides MVCC and server-grade backup/PITR capabilities, but those benefits do not
justify provisioning, authentication, patching, monitoring, pooling, and recovery operations for
the current local POC.

## Query and index implications

The relational model should make TASK-018 queries index-backed without exposing SQL. Initial
indexes should follow demonstrated contracts, not speculative analytics:

- artifacts/documents by `(firm_id, canonical_artifact_id, durable_status)`;
- source-effective ordering by normalized effective timestamp/date, secondary identity,
  `document_id`, and `artifact_id` in both practical traversal directions;
- observations by `(artifact_id, observed_at, observation_id)` and unique `attempt_id`;
- attempts by `source_id`, `document_id`, `run_id`, `occurred_at`, and outcome;
- checkpoints and checkpoint events by `(source_id, position)`;
- current firm/concept/profile selectors and their unique current identifiers;
- knowledge provenance by source object, document, artifact, and knowledge version;
- workspace events by `(workspace_id, sequence)` and `(investigation_id, sequence)`.

Keep provider-specific fields in typed extension tables or canonical JSON unless a demonstrated
query contract requires an index. Do not create a generic SQL, JSON-path, or arbitrary predicate
API. Full-text, vector, and graph indexes remain rebuildable candidate-generation facilities.

For cursor consistency, expose a repository revision/authority epoch changed by every relevant
committed mutation. A query transaction obtains the epoch and ordered keyset position. Continuation
rejects a changed epoch as `stale_cursor`, preserving current behavior. Keyset pagination is
preferred over a raw offset once corpus size makes offset cost material.

## Conceptual target schema

This is a compatibility design, not executable DDL. Names may change during implementation.

### Repository metadata

- `schema_migrations(module, version, applied_at, checksum)`
- `repository_state(repository_id, authority_epoch, created_at, product_version)`
- `migration_audits(migration_id, source_fingerprint, target_fingerprint, status, report_json)`

### Catalog authorities

- `firms(firm_id, current_revision_id)`
- `firm_revisions(revision_id, firm_id, revision_number, predecessor_id, status, valid_from,
  valid_through, created_at, canonical_json)`
- `firm_identifiers(revision_id, kind, market, value)`
- `firm_domains(revision_id, domain)`
- `concepts(concept_id, current_revision_id)`
- `concept_revisions(revision_id, concept_id, revision_number, predecessor_id, status,
  valid_from, valid_through, canonical_json)`
- `concept_methods(revision_id, method_id, kind, result_shape, configuration_json)`
- `source_profiles(firm_id, current_revision_id)`
- `source_profile_revisions(revision_id, firm_id, revision_number, predecessor_id, created_at,
  canonical_json)`
- `source_profile_items(revision_id, artifact_id, enabled, operator_notes)`
- `retrieval_candidates(revision_id, artifact_id, candidate_id, priority, mode, canonical_json)`

### Acquisition and artifacts

- `governed_sources(source_id, profile_revision_id, enabled, mechanism, policy_json)`
- `artifacts(artifact_id, sha256, byte_count, media_type, content_reference, created_at)`
- `documents(document_id, firm_id, canonical_artifact_id, durable_status)`
- `document_artifacts(document_id, artifact_id, first_attempt_id, last_attempt_id)`
- `acquisition_attempts(attempt_id, run_id, source_id, candidate_id, document_id, outcome,
  occurred_at, mechanism, artifact_id, diagnostics_json, canonical_json)`
- `artifact_observations(observation_id, attempt_id, artifact_id, document_id, source_id,
  observed_at, adapter_id, profile_revision_id, provenance_json, canonical_json)`
- `checkpoint_events(event_id, source_id, attempt_id, position, cursor, created_at)`
- `current_checkpoints(source_id, event_id, position, cursor)` as a rebuildable table or view
- `pull_runs(run_id, firm_id, profile_revision_id, state, started_at, completed_at, summary_json)`
- `pull_results(run_id, artifact_id, ordinal, state, attempt_id, diagnostics_json)`

Foreign keys enforce observation-to-attempt/artifact/document/source relationships and
checkpoint-to-successful-attempt relationships where expressible. Triggers should be used
sparingly; repository methods remain the readable domain boundary.

### Knowledge and rebuildable projections

- `knowledge_generations(generation_id, source_fingerprint, published_at, selected)`
- `knowledge_objects(object_id, semantic_key)`
- `knowledge_versions(version_id, object_id, generation_id, predecessor_id, status, confidence,
  payload_json, derivation_id)`
- `knowledge_provenance(version_id, source_object_id, document_id, artifact_id, byte_start,
  byte_end, content_sha256)`
- `knowledge_failures(generation_id, failure_id, failure_json)`
- rebuildable `source_objects`, parse outcomes, retrieval generations, candidate vectors, and
  searchable metadata remain in separately replaceable schemas or database files.

Logical separation is enforced by repository modules and migration ownership even if the first
authoritative modules share one SQLite database file. Physical consolidation must not collapse
evidence, knowledge, retrieval, intelligence, or workspace authority classes.

### Workspace boundary

Each independently portable workspace should retain its own `workspace.sqlite3` with:

- `workspace_metadata`
- `investigations`
- `workspace_events(workspace_id, sequence, investigation_id, event_type, occurred_at,
  previous_hash, event_hash, payload_json)`
- rebuildable current projections
- export manifests and references, not copied evidence bodies.

This preserves independent backup/restore and prevents a consulting workspace from becoming an
evidence repository.

## Migration boundary and cutover

A later task should migrate structured authorities only. Exact artifact bytes, version-controlled
governance/configuration, browser preferences, generated exports, and review packages remain in
their current classes.

Recommended phases:

1. **Contract and inventory freeze.** Enumerate every schema version, record type, identity,
   relationship, legacy projection, corruption state, and public query fixture. Define canonical
   source fingerprints and target reconciliation reports.
2. **Schema and adapter implementation.** Add a database-backed repository implementation behind
   existing contracts. Create schema migrations and transaction/integrity tests. Do not change the
   active file authority.
3. **Offline shadow import.** With writers stopped, import a copy of file authority into a
   candidate database. Do not dual-write. Compare counts, identities, canonical payload hashes,
   histories, current selectors, checkpoints, artifact references, TASK-018 queries, TASK-019
   observation order, replay results, and workspace chains.
4. **Backup and cutover.** Produce a verified pre-cutover backup. Record an authority marker and
   migration audit. Atomically switch startup configuration to the database implementation. Old
   structured files become a frozen rollback snapshot and are never written again.
5. **Post-cutover verification.** Run full validation, offline restart, integrity checks, artifact
   byte verification, query golden tests, backup/restore rehearsal, and failure injection before
   accepting new operational writes.
6. **Deferred retirement.** Remove legacy structured-file writers only after an observation
   period and explicit acceptance. Keep a versioned importer for retained backups; do not keep two
   live authorities.

The first implementation task should be bounded to acquisition plus shared catalog authorities if
one full migration is too large. Partial migration is safe only when each record type has exactly
one declared authority and cross-boundary references are validated through public contracts.

## Rollback

- Before cutover: discard the candidate database; file authority is untouched.
- After cutover but before any accepted database-only write: restore the authority marker to the
  frozen file snapshot after verification.
- After database-only writes: do not silently fall back to stale files. Restore the database from
  a verified backup or run an explicitly designed reverse export/reconciliation process. Prefer
  roll-forward repair.
- A failed migration never mutates source files in place. Every migration audit records source and
  target fingerprints, tool version, schema version, and validation result.

Rollback is an operational procedure with evidence, not a configuration toggle that permits
split-brain authority.

## Backup, restore, replay, rebuild, and corruption

### Backup and restore

Use SQLite's online backup API (available through Python's standard library connection backup
support) or a verified offline database copy, never an uncoordinated copy of a live database plus
WAL sidecars. A complete repository backup contains:

- a consistent SQLite snapshot for every authoritative database;
- a manifest of database schema/version, size, and SHA-256;
- every referenced immutable artifact content object, deduplicated by digest;
- workspace databases selected for the backup;
- the version-controlled configuration revision or exported canonical template inputs required
  to interpret state;
- a complete member inventory and checksums.

Restore into staging, verify database integrity and foreign keys, verify the artifact manifest,
open through public repository contracts, run replay equivalence, then atomically publish the
restored state root. Define and test recovery-point and recovery-time objectives before claiming
production durability.

### Replay and rebuild

Retain authoritative events where their history is meaningful: acquisition attempts, observations,
checkpoint events, immutable revisions, knowledge versions, and workspace events. Rebuild only
declared projections: current checkpoints, document access tables, source objects, retrieval
indexes, current workspace views, and caches. Rebuild must be local and deterministic, must not
contact providers or models, and must publish atomically.

Relational storage does not justify event-sourcing every mutable value. Current selectors may be
ordinary constrained rows when immutable revision history is authoritative. Replay contracts must
remain explicit per subsystem.

### Corruption handling

- fail closed on database open, migration checksum mismatch, failed SQLite integrity/quick check,
  failed foreign-key check, invalid canonical payload, broken event chain, or artifact mismatch;
- report structured, sanitized diagnostics without rewriting evidence;
- distinguish database-page corruption, semantic inconsistency, missing artifact bytes,
  unreferenced artifact bytes, and stale rebuildable state;
- restore authoritative corruption from a verified backup and replay later derived state;
- rebuild only state declared rebuildable;
- never auto-salvage corrupt authoritative rows into a trusted database;
- retain the corrupt source read-only for forensic inspection.

## Embedded versus server-based relational storage

| Concern | SQLite | PostgreSQL |
| --- | --- | --- |
| Deployment | Embedded, one local file plus WAL/SHM while active; Python standard library | Separate server, credentials, lifecycle, network, pooling |
| Current workload fit | Strong: local, offline, one technical owner, one writer | Excess capacity and burden |
| Read/write concurrency | Concurrent readers, one writer; WAL suits short local transactions | MVCC and many concurrent sessions/writers |
| Cross-host use | Not a WAL/network-filesystem design | Native client/server |
| Backup | Online backup API or verified offline copy | Dumps, filesystem backup, continuous archive/PITR |
| Operations | Checkpointing, backup, integrity checks, file permissions | Provisioning, patching, roles, TLS, monitoring, vacuum, replication/recovery |
| Migration path | Immediate recommendation | Triggered escalation target |

SQLite foreign-key enforcement must be enabled explicitly on every connection. WAL improves reader
and writer coexistence but still permits only one writer and requires same-host storage. These are
accepted constraints, not hidden promises.

## Operational burden

SQLite introduces schema migrations, connection configuration, transaction discipline, backup
rehearsals, WAL checkpoint monitoring, and integrity checks. It removes much more application-owned
mechanical code: pointer publication, record-file inventory, cross-file partial state, manual
uniqueness, and scan-based joins.

The operator runbook must cover database location and permissions, supported SQLite/Python
versions, startup pragmas, busy behavior, backup cadence, restore rehearsal, integrity checks,
artifact-manifest verification, migration ownership, and disk-full behavior. Metrics should expose
database bytes, WAL bytes, checkpoint age, write contention, transaction latency, artifact orphan
counts, failed integrity checks, backup age, and restore-test age.

PostgreSQL would additionally require server provisioning, secrets, access control, network/TLS,
patching, connection pooling, vacuum/bloat monitoring, replication, failover, and PITR operations.
No current evidence funds that burden.

## Alternatives rejected

- **Current files indefinitely:** custom storage mechanics and non-atomic structured publication
  grow faster than their inspectability benefit.
- **Relational read model only:** duplicates formats and freshness logic while leaving write
  integrity unchanged.
- **PostgreSQL now:** its concurrency, HA, and PITR strengths exceed demonstrated requirements and
  add a server security/operations surface.
- **DuckDB:** its analytical orientation and process-centered write model do not improve this
  transactional authority workload over SQLite.
- **Document database:** most records have stable identities and relationships requiring
  constraints; nested JSON can be retained without surrendering relational integrity.
- **Key-value or append-only log product:** would preserve application-owned joins, current-state
  projections, and referential validation.
- **Graph database authority:** relationship traversal is not yet a demonstrated dominant workload;
  a graph projection can remain rebuildable if later justified.
- **Database artifact BLOBs:** couples large hostile evidence bytes to transaction, backup, and
  vacuum behavior and weakens content-addressed operational independence.
- **One database per existing JSON directory:** reproduces fragmentation and prevents useful
  transaction boundaries without preserving a meaningful authority distinction.
- **Permanent dual-write:** creates two authorities and ambiguous recovery; migration uses offline
  import, reconciliation, and one cutover marker.

## Major risks and mitigations

| Risk | Consequence | Mitigation |
| --- | --- | --- |
| Migration silently changes contract semantics | Browser/planner/intelligence disagreement | Golden public-contract fixtures, source/target fingerprints, differential queries |
| Physical consolidation collapses authority classes | Evidence, knowledge, retrieval, and workspace become coupled | Module-owned schemas/repositories; separate rebuildable and workspace databases; no consumer SQL |
| SQLite writer contention grows | Busy errors and delayed acquisition/admin writes | Short transactions, bounded retries, metrics, one writer policy, PostgreSQL triggers |
| WAL or raw-copy backup is mishandled | Inconsistent restore | Online backup API/offline shutdown copy, verified manifest, restore drills |
| Artifact store and DB diverge | Missing evidence or orphans | Bytes-first publication, foreign references, integrity scanner, coordinated backup manifest |
| Schema migrations damage history | Authority loss | Additive migrations where possible, preflight copy, transaction, backup, checksums, no in-place file rewrite |
| Legacy history cannot be losslessly represented | Unreliable recommendation/cutover | Canonical JSON retention, legacy projection tests, explicit blocked cutover on mismatch |
| Product choice becomes sticky | Costly later server migration | Persistence-independent contracts, conservative SQL subset, migration-owned adapters |

## Unresolved questions

These do not prevent selecting SQLite, but must be resolved by the implementation ticket:

1. Should authoritative knowledge share the main repository database or use a separate SQLite
   authority file to preserve independent backup and schema lifecycle?
2. What is the exact transaction boundary between pull-run lifecycle state and acquisition
   records when a run contains several independent artifact outcomes?
3. Which legacy malformed or partial states exist outside fixtures, and must any be imported as
   quarantined records rather than rejected?
4. What recovery-point and recovery-time objectives apply to authoritative structured state and
   immutable bytes?
5. What observed corpus size, query latency, and write-contention thresholds trigger keyset index
   changes or PostgreSQL evaluation?
6. Is an authority marker stored beside the state root sufficient, or should startup require a
   signed/hashed migration manifest tied to the database repository identity?
7. How long must frozen pre-cutover file authority and its importer be retained?

## Decision triggers if implementation is deferred

If no migration task is authorized now, reconsider immediately when any trigger occurs:

- a new authoritative structured subsystem or relationship graph is proposed;
- another custom catalog pointer, generation store, or replay implementation would be added;
- artifact query scans or cursor digest construction exceed an agreed latency budget;
- concurrent admin, acquisition, or workspace writes become an operational need;
- an integrity incident exposes cross-file partial state or backup inconsistency;
- backup/restore objectives cannot be met with the fragmented state tree;
- authoritative structured record count or repository start/replay time grows materially;
- a remote or multi-operator deployment is authorized.

Deferral should not add a relational read model by default. Continue using public contracts and
record metrics needed for the implementation design.

## Product evidence

The recommendation relies on product capabilities documented by their maintainers:

- SQLite supports multiple simultaneous readers but one simultaneous writer, and WAL allows
  readers and a writer to proceed concurrently while remaining a same-host design:
  <https://www.sqlite.org/lang_transaction.html> and <https://www.sqlite.org/wal.html>.
- SQLite foreign keys are supported but must be enabled by the application:
  <https://www.sqlite.org/foreignkeys.html>.
- SQLite's online backup API creates a consistent snapshot of a live database:
  <https://www.sqlite.org/backup.html>.
- PostgreSQL documents MVCC concurrency and SQL dump, filesystem, and continuous-archive/PITR
  backup models: <https://www.postgresql.org/docs/current/mvcc.html> and
  <https://www.postgresql.org/docs/current/backup.html>.
- DuckDB documents its in-process write concurrency model:
  <https://duckdb.org/docs/current/connect/concurrency>.

Product documentation supports capability comparison; repository evidence determines fit.

## TASK-021 implementation resolution

TASK-021 implemented the selected hybrid model as a fresh-state foundation. It deliberately did
not execute the migration and rollback sequence below because the POC state was disposable and no
material retained corpus justified import tooling. New application state has one SQLite structured
authority, one immutable content authority, explicit schema version 1, revision-bound cursors, and
verified hybrid backup/restore. Legacy file state is rejected and never silently mixed.

The migration sections remain the TASK-020 analysis for a future material legacy corpus; they do
not describe the TASK-021 cutover mechanism. See
[`sqlite-structured-state-repository.md`](sqlite-structured-state-repository.md) and ADR-0017 for
the implemented schema and transaction model.

## Final recommendation and go/no-go

**Recommendation: adopt a relational database-backed architecture using explicit hybrid authority.**

- Selected authority model: SQLite owns authoritative structured records; the filesystem owns
  immutable content-addressed artifact bytes; governance/configuration files retain their current
  version-controlled authority; rebuildable indexes remain non-authoritative.
- Recommended product: SQLite for current local operation, accessed through Python's standard
  library. PostgreSQL is the documented escalation target, not a current dependency.
- Migration boundary: structured runtime authorities and projections only, behind existing public
  contracts; no artifact-byte, governance-document, browser-preference, export, or secret migration.
- Decision rationale: native transactions, constraints, and indexes materially reduce custom
  record mechanics and partial structured state while preserving low-burden offline operation and
  exact-byte evidence.
- Go/no-go: **GO** for a later, separately ticketed migration implementation with offline shadow
  import, differential contract proof, verified backup/restore, one atomic authority cutover, and
  no permanent dual-write. **NO-GO** for ad hoc table creation, a query-only database presented as
  authority, database BLOB migration, PostgreSQL deployment without triggers, or any TASK-020
  behavior change.

## Architectural Status Summary

| Subsystem | Status after TASK-021 | Architectural boundary |
| --- | --- | --- |
| Immutable artifact store | Complete | Exact content-addressed bytes remain filesystem authority. |
| Acquisition structured state | Complete for schema version 1 | SQLite is authoritative; public contracts remain the boundary. |
| Artifact observations and attempts | Complete | Identity contracts preserved; future rows remain immutable/append-only. |
| Artifact query service | Complete | Storage-independent contract is the migration compatibility gate. |
| Firm, concept, and source-profile catalogs | Complete for schema version 1 | Immutable revisions and current selectors publish transactionally in SQLite. |
| Source-object catalog | Complete, rebuildable | Existing SQLite use validates embedded relational fit; not authority. |
| Knowledge store | Provisional | Interpretive authority remains separate; physical database boundary unresolved. |
| Retrieval index | Provisional, rebuildable | Remains disposable and must never become authority. |
| Workspace | Usable with Limitations | Independent event authority retained; separate SQLite workspace recommended. |
| Structured storage target | Complete for fresh state | Explicit hybrid SQLite/file authority implemented and verified. |
| Legacy migration implementation | Not Started by policy | Requires a new ticket only if material retained state later justifies it. |
| Server database | Deferred | PostgreSQL only on explicit concurrency/operations triggers. |

Architectural change: fresh application repositories now use SQLite authority for structured state
while retaining immutable byte evidence on the filesystem. The next storage milestone is driven by
operating evidence: a versioned schema change, material legacy corpus, or documented PostgreSQL
trigger—not general cleanup or speculative migration.
