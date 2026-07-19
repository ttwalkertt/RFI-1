# ADR-0017 — Fresh SQLite structured-state foundation

## Status

Accepted and implemented by TASK-021.

## Context

TASK-020 selected SQLite authority for structured runtime state and filesystem authority for exact
content-addressed bytes. The POC contains no material artifact corpus requiring preservation.
Building an importer and rollback format before valuable data exists would add a second schema and
authority-transition machinery without business value.

## Decision

New application repositories use one versioned `repository.sqlite3` for concept, firm,
source-profile, pull, acquisition, artifact, observation, checkpoint, and repository-revision
state. Exact artifact bytes remain immutable objects beneath `content/sha256`. Public repository
and artifact query contracts remain the compatibility boundary.

Initialization is fresh and idempotent. Explicit `rfi seed` reseeds the deterministic concept and
firm catalog; no other legacy state is imported. Known legacy-only and mixed layouts fail closed.
No dual-read, dual-write, shadow database, migration fallback, or artifact BLOB exists.

Bytes are flushed before a short structured transaction. Transaction rollback may leave a
diagnostic orphan but never partial visible structured success. A monotonic repository revision
binds query and observation cursors. Hybrid backups use SQLite's online backup API plus a
checksummed content manifest and restore only into fresh state.

## Consequences

Relational constraints and transactions replace structured JSON pointers, revision files,
acquisition ledgers, and pull-run snapshots for newly initialized application repositories.
SQLite schema/version management, integrity checks, WAL-safe backup, content disagreement
detection, and bounded busy handling are now explicit operational responsibilities.

The source-object/retrieval indexes remain rebuildable. Independently portable knowledge and
workspace stores remain separate and are not redesigned here. Their future physical consolidation
requires a separate task. PostgreSQL remains trigger-driven by multi-host/concurrent-writer,
remote-service, HA, or PITR needs.

## Alternatives

- General POC migration was rejected because there is no material corpus to preserve.
- Firms-only import was unnecessary because deterministic explicit seeding is smaller and safer.
- Permanent file compatibility was rejected because it creates dual authority.
- Database BLOBs and PostgreSQL were rejected for the reasons recorded by ADR-0016.
