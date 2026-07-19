# SQLite structured-state repository

TASK-021 implements the TASK-020 hybrid authority decision for newly initialized application
repositories. It is a fresh-state format, not a migration layer.

## Authority model

```text
<state>/repository.sqlite3
    authoritative structured runtime state

<state>/content/sha256/<prefix>/<sha256>
    authoritative immutable artifact bytes

repository and query contracts
    only supported consumer boundary
```

SQLite owns concepts, firms and immutable revisions, source-profile revisions and candidates,
governed acquisition sources, artifact metadata and content references, logical documents,
acquisition attempts, artifact observations, checkpoint events/current checkpoints, pull runs,
repository identity, schema version, and the monotonic authority revision. Artifact bytes never
enter SQLite. Governance documents and the canonical acquisition template remain version-controlled
file authorities. Browser preferences, review packages, source-object/retrieval indexes, and other
declared rebuildable projections remain non-authoritative.

Independently portable knowledge and workspace implementations retain their pre-existing stores.
They are not initialized by `rfi init`, do not participate in application acquisition transactions,
and remain an explicit later physical-storage decision rather than a hidden second authority for
TASK-021 records.

## Repository format and schema

The database is identified by `schema_metadata.schema_name = rfi-structured-state` and schema
version `1`. `repository_state` owns a random repository identity and `authority_revision`.
Every committed mutation that can affect repository readers advances that revision. Artifact query
and observation cursors bind to it and return `stale_cursor` after a change.

The executable DDL is owned by `rfi.storage.sqlite`. Its tables are:

| Area | Tables | Policy |
| --- | --- | --- |
| Schema/repository | `schema_metadata`, `repository_state` | one row each; explicit compatible version |
| Concepts | `concepts`, `concept_revisions` | current selector plus immutable numbered history |
| Firms | `firms`, `firm_revisions`, `firm_identifiers`, `firm_domains` | stable identity, immutable revisions, repository validation of current recognition uniqueness |
| Profiles | `source_profiles`, `source_profile_revisions`, `source_profile_items`, `retrieval_candidates` | immutable firm-owned revision snapshots |
| Acquisition | `governed_sources`, `acquisition_attempts`, `checkpoint_events`, `current_checkpoints` | immutable activity/history; transactional current progress |
| Evidence | `artifacts`, `documents`, `artifact_observations` | byte-derived artifact identity; distinct document, observation, and attempt identities |
| Pull workflow | `pull_runs` | durable lifecycle record updated transactionally |

Primary keys, unique constraints, foreign keys, not-null checks, lifecycle checks, and query indexes
enforce generic storage guarantees. Canonical JSON text is retained for lossless public-contract
projection, but identity, relationship, outcome, time, ordering, and content-reference fields are
normalized. No table declares a BLOB column.

Checkpoint positions are decimal text because the established engine contract permits non-negative
Python integers larger than SQLite's signed 64-bit integer. Repository code parses and compares
them as integers, preserving the public monotonic-position contract without truncation.

## SQLite configuration and connection model

Every connection enables foreign keys and a 5-second busy timeout. Writers use WAL, `synchronous =
FULL`, and short `BEGIN IMMEDIATE` transactions. Reads use read-only connections where practical.
Provider calls, parsing, and content streaming never occur in a database write transaction. This
supports local readers during one local writer and makes contention bounded and visible; it does
not claim multi-host writer support.

## Transaction and content coordination

Successful acquisition uses this sequence:

1. Derive artifact identity and content reference from the exact SHA-256.
2. Preflight an existing attempt identity so a conflicting retry cannot create bytes.
3. Exclusively create and flush the immutable content object, or verify an exact existing object.
4. Start `BEGIN IMMEDIATE`.
5. Insert or verify artifact metadata, then insert the attempt, observation, logical-document
   projection, optional checkpoint event/current checkpoint, and repository revision.
6. Commit once.

Failure before the content write leaves no effect. Transaction failure rolls back every structured
effect but can leave one unreferenced, content-addressed object. Integrity verification reports
that orphan and does not delete or adopt it. A committed database reference with missing or
checksum-invalid bytes is a dangling-reference integrity failure. Neither disagreement is silently
reconciled. Recovery is restore from a verified backup or an explicitly authorized future repair;
TASK-021 supplies no evidence-rewriting repair command.

Concept, firm, and source-profile publication inserts one immutable revision and advances its
current selector in one transaction. Firm batches are all-or-nothing. Pull-run create/save is one
transaction per durable lifecycle publication.

## Initialization and legacy handling

`rfi init` creates the database, schema metadata, repository identity/revision, and content root.
It creates no starter data. Repeating initialization validates the schema and integrity and does
not change authoritative records or the repository revision. `rfi seed` remains the explicit,
idempotent starter path for concepts and the deterministic three-firm catalog.

Known legacy catalog pointers, acquisition authoritative directories, and pull-run directories are
detected before creation and whenever SQLite state is opened. Legacy-only or mixed state fails with
an actionable message: automatic migration is unsupported, legacy data is not deleted, and the
operator must choose a fresh path or archive the old state. There is no dual read, dual write,
legacy observation projection, or rollback switch.

## Integrity, backup, and restore

`rfi verify --state STATE` runs SQLite integrity and foreign-key checks, verifies every artifact
reference, recomputes content hashes and sizes, and rejects missing or orphaned objects.

Create and restore a complete hybrid backup with:

```sh
rfi backup --state STATE --output repository-backup.zip
rfi restore --input repository-backup.zip --state FRESH_STATE
```

Backup first verifies both authorities, uses SQLite's online backup API rather than copying a live
database/WAL pair, and packages the database plus all content objects. `backup-manifest.json`
records format/schema versions and every member's size and SHA-256. Restore accepts only a fresh
directory, rejects duplicate/extra/unsafe/mismatched members, validates the restored schema,
SQLite integrity, foreign keys, content references, and checksums, and removes a failed partial
restore.

## Contract preservation and limits

Firm, source-profile, pull, acquisition, artifact query/detail/content, observation-selection,
cursor, and browser callers retain their established methods and normalized records. Queries read
parameterized SQLite repository operations; no SQL is exposed to consumers. Latest/oldest and
source-effective ordering remain repository semantics. Browser HTML isolation, defensive content
headers, range responses, network-independent inspection, and read-only behavior are unchanged.

TASK-021 does not migrate POC state, redesign the browser/extraction/Bring Repository Up to Date,
store artifact BLOBs, add PostgreSQL, add multi-host writers, or add automatic orphan repair.
PostgreSQL evaluation remains triggered by multi-host or sustained concurrent writers, remote
service deployment, HA, or PITR requirements. General legacy migration is reconsidered only when
material retained business data justifies reconciliation tooling.
