# TASK-021 — SQLite Structured-State Repository Foundation

## Status

Ready

## Objective

Build the new authoritative SQLite-backed structured repository for RFI-1 from a clean state.

Preserve the existing public repository, acquisition, artifact-query, artifact-observation, browser, and content-access contracts while replacing the current file-based authoritative structured-state implementation for newly initialized repositories.

Retain immutable artifact bytes in the content-addressed filesystem.

Do not implement general migration tooling for existing POC repositories. Current artifacts, observations, attempts, pull history, indexes, and other disposable POC state may be discarded and recreated. Preserve or reseed only the firm catalog where useful.

## Context

TASK-020 selected an explicit hybrid authority model:

```text
SQLite
    authoritative structured runtime state

Content-addressed filesystem
    authoritative immutable artifact bytes

Public repository/query contracts
    stable compatibility boundary
```

The current repository contains no materially valuable artifact corpus requiring migration. Building and validating a general legacy migration framework now would add cost and complexity before there is business data worth preserving.

TASK-021 therefore establishes a fresh SQLite-backed repository implementation rather than migrating legacy structured state.

The implementation must preserve the domain architecture proven through TASK-019:

- immutable artifact identity;
- immutable artifact bytes;
- distinct acquisition-attempt identity;
- multiple immutable `ArtifactObservation` records per artifact;
- deterministic source-effective ordering;
- first, last, and explicit observation selection;
- opaque snapshot-bound cursors;
- repository-owned query contracts;
- read-only artifact browser;
- integrity verification and deterministic recovery behavior.

## Governing Decision

For newly initialized repositories:

- SQLite is authoritative for structured state.
- The content-addressed filesystem is authoritative for immutable artifact bytes.
- Public repository and query contracts remain unchanged.
- Legacy POC structured state is not automatically migrated.
- Permanent dual-read and dual-write are prohibited.
- Artifact bytes are not stored as database BLOBs.
- PostgreSQL remains a future escalation path for multi-host writers, sustained concurrency, high availability, or point-in-time recovery requirements.

## Scope

TASK-021 shall:

1. Define the authoritative SQLite schema and schema-version mechanism.
2. Implement SQLite-backed repository persistence behind existing public contracts.
3. Initialize new repositories from a clean state.
4. Preserve or reseed the firm catalog through the smallest justified mechanism.
5. Retain immutable artifact bytes in the existing content-addressed filesystem.
6. Preserve acquisition, artifact, observation, query, browser, and content behaviors.
7. Remove new-repository dependence on legacy authoritative structured-state files and mutable pointer files.
8. Provide backup, restore, integrity, and failure semantics appropriate to the new hybrid model.
9. Prove contract and behavioral equivalence with focused and full validation.
10. Record legacy POC state as unsupported for automatic import unless a future task explicitly authorizes migration.

## Non-Migration Policy

TASK-021 is not a legacy migration task.

Do not implement:

- general import of existing artifacts;
- artifact-observation migration;
- acquisition-attempt migration;
- pull-history migration;
- provenance-history migration;
- dual-read compatibility;
- dual-write compatibility;
- automatic repository-format conversion;
- long-lived shadow databases;
- rollback to the legacy structured-state implementation after cutover;
- migration of review packages, caches, or browser preferences.

A small firm-catalog preservation path is permitted if it is simpler and safer than manual reseeding. It must remain narrowly scoped to firms and must not become a general migration framework.

If current source profiles are inexpensive to recreate, they may be reseeded rather than migrated. Codex shall document the chosen treatment.

## Authority Model

### SQLite authoritative structured state

SQLite shall become authoritative for structured records including, as applicable:

- firms;
- canonical artifact catalog references where stored rather than code-defined;
- source profiles and revisions;
- pull executions;
- acquisition attempts;
- artifacts;
- `ArtifactObservation` records;
- provenance records;
- content references;
- checksums and integrity metadata;
- repository revisions or equivalent snapshot/version state;
- query and cursor-supporting structured state.

### Filesystem authoritative immutable bytes

The content-addressed filesystem remains authoritative for:

- exact artifact bytes;
- content-addressed object identity;
- large immutable evidence objects where already appropriate.

SQLite stores only the structured content reference and integrity facts required to locate and verify those bytes.

### Explicit disagreement handling

The implementation shall define behavior when:

- SQLite references missing content;
- content exists without a structured SQLite record;
- checksum verification fails;
- a transaction commits but content finalization fails;
- content is written but the structured transaction fails.

Do not silently reconcile inconsistent authority.

Return structured integrity or repository failures and preserve evidence for diagnosis.

## Repository Initialization

Provide a deterministic initialization path for a new SQLite-backed repository.

Initialization shall:

- create the database safely;
- create the authoritative schema;
- record the schema version;
- configure required SQLite behavior;
- create or validate the content-store location;
- initialize repository revision state;
- create empty structured catalogs where appropriate;
- preserve existing `rfi init` semantics unless a documented contract change is unavoidable;
- remain idempotent;
- never seed optional starter data implicitly if current CLI policy requires explicit `rfi seed`.

Repeated initialization shall report existing compatible state without modifying authoritative records.

Incompatible or corrupt state shall produce actionable errors.

## Schema Design

Create an implementation-ready schema and schema-version foundation for the new repository format.

The schema shall cover at least:

- firm records;
- source-profile records and revisions;
- pull executions;
- acquisition attempts;
- artifacts;
- `ArtifactObservation` records;
- provenance or observation-provenance relationships;
- content references;
- checksums and integrity state;
- repository or snapshot revisions;
- schema metadata.

The schema shall define:

- primary keys;
- immutable identity columns;
- uniqueness constraints;
- foreign keys;
- not-null requirements;
- authoritative timestamps;
- deterministic ordering fields;
- indexes required by current query contracts;
- transaction boundaries;
- deletion policy;
- update policy;
- schema-version metadata.

Use relational constraints for generic storage guarantees while retaining domain-specific identity and policy logic in RFI code.

## Domain Invariants

The SQLite implementation must preserve:

### Identity separation

- Artifact identity is independent of `ArtifactObservation` identity.
- `ArtifactObservation` identity is independent of acquisition-attempt identity.
- Same-run retries remain idempotent.
- Distinct successful pulls may create distinct observations.
- Repeated unchanged acquisition reuses the artifact and stored bytes.

### Immutability

- Artifact identity and content checksum are immutable.
- `ArtifactObservation` records are immutable after creation.
- Acquisition attempts are immutable after completion except where an existing public lifecycle contract explicitly requires bounded state transition.
- Provenance evidence is not overwritten.
- Content-addressed bytes are not mutated in place.

### Deduplication

- Identical stored bytes are retained once.
- Repeated acquisition of the same logical artifact does not duplicate the artifact.
- Repeated successful acquisition creates a new observation where required by TASK-019.
- Unique constraints must not collapse distinct identity domains.

### Ordering

- Source-effective artifact ordering remains deterministic.
- Observation ordering remains deterministic and stable.
- Retrieval or insertion time does not replace source-effective ordering where source semantics exist.

## Transaction Design

Define and implement explicit transactional behavior for repository writes.

At minimum, establish transaction boundaries for:

- pull execution creation;
- acquisition-attempt creation and completion;
- artifact insertion or reuse;
- `ArtifactObservation` insertion;
- provenance insertion;
- repository revision advancement;
- content-reference registration;
- deduplication checks.

A failed logical repository operation must not leave a partially visible structured result.

Codex shall document the chosen sequence for coordinating SQLite transactions with filesystem content writes.

The design must minimize orphaned files and dangling database references without pretending SQLite and the filesystem share one atomic transaction.

A bounded recovery or integrity procedure is required for interrupted cross-substrate writes.

## SQLite Configuration

Select and document appropriate SQLite settings for the RFI-1 workload.

Evaluate and configure, where justified:

- foreign-key enforcement;
- journal mode;
- synchronous mode;
- busy timeout;
- transaction mode;
- connection lifecycle;
- read-only connections;
- typed row mapping;
- integrity checking;
- schema-version management.

Do not optimize speculatively.

The configuration must support:

- local single-user operation;
- admin browser reads during pulls;
- deterministic tests;
- clean shutdown;
- backup and restore;
- future moderate concurrency within one host.

## Repository Contract Preservation

Existing public contracts are the compatibility boundary.

Preserve behavior for:

- repository initialization;
- firm catalog operations;
- source-profile operations;
- pull planning and execution;
- acquisition attempts;
- artifact insertion and deduplication;
- `ArtifactObservation` creation;
- artifact query service;
- artifact summaries and details;
- first, last, and explicit observation selection;
- previous and next observation navigation;
- deterministic source-effective ordering;
- latest and oldest lookup;
- bounded pagination;
- stale-cursor behavior;
- stored-content access;
- artifact-browser APIs;
- integrity verification;
- network-independent browsing and preview.

Consumers shall not know whether structured state is implemented through JSON files or SQLite.

If an existing public contract cannot be preserved, Codex must stop and report the conflict before changing it.

## Query Implementation

Implement current repository query contracts efficiently against SQLite.

Support at least:

- firm enumeration;
- artifact-family and canonical-type projection;
- artifact counts;
- firm and artifact-type filtering;
- provider filtering where already supported;
- durable-status filtering;
- source-effective date bounds;
- newest and oldest ordering;
- exact artifact lookup;
- latest and oldest lookup;
- first, last, and explicit observation selection;
- previous and next observation navigation;
- bounded pagination;
- snapshot-bound or equivalent deterministic cursor behavior.

Do not introduce a user-authored SQL or free-form query surface.

Repository services shall use parameterized queries and typed mappings.

## Cursor and Snapshot Semantics

Preserve the deterministic cursor guarantees established by TASK-018 and TASK-019.

Codex shall define how SQLite-backed queries bind cursors to a stable repository view.

Acceptable approaches include:

- repository revision tokens;
- explicit snapshot or version identifiers;
- another deterministic mechanism consistent with SQLite and the existing contracts.

Repository changes that invalidate continuation shall return `stale_cursor` rather than silently mixing result sets.

Cursor representation remains opaque to consumers.

## Content Store Integration

Retain the existing content-addressed filesystem unless a narrowly scoped correction is required.

The SQLite repository shall store:

- content identity;
- checksum;
- media type;
- size;
- storage reference;
- integrity metadata.

The content endpoint shall continue to:

- resolve by repository document identity;
- verify content integrity;
- prevent arbitrary path access;
- support byte ranges where already supported;
- emit defensive headers;
- preserve isolated HTML preview behavior;
- avoid exposing filesystem paths.

Do not store artifact bytes as SQLite BLOBs.

## Firm Catalog Treatment

The firm catalog is the only current data with potential preservation value.

Choose and document one of these bounded approaches:

1. reseed firms from deterministic repository seed definitions;
2. provide a firms-only import from the current catalog;
3. require explicit operator recreation if the current catalog is trivial.

The chosen approach must be:

- deterministic;
- idempotent;
- narrow;
- independently tested;
- clearly separated from general migration infrastructure.

Do not import artifacts or other legacy structured state through the firm path.

## Fresh-State Cutover

New repositories shall use SQLite structured state exclusively.

The implementation shall define:

- how a new SQLite repository is identified;
- how incompatible legacy state is detected;
- what the operator sees when a legacy POC state directory is supplied;
- whether the operator must select a new state path or explicitly reset old state;
- how fresh state is created safely;
- how accidental mixing of old and new authority is prevented.

Do not silently read legacy structured state and write SQLite state in the same repository.

Do not delete legacy state automatically.

An operator may archive or remove disposable POC state outside the application after confirming the new repository works.

## Backup and Restore

Provide a proportionate backup and restore model for the new hybrid repository.

The design shall account for both authoritative components:

- SQLite structured database;
- content-addressed filesystem.

At minimum, document and prove:

- consistent backup sequencing;
- SQLite-safe backup behavior;
- content-store inclusion;
- manifest or integrity verification;
- restore into a fresh location;
- schema compatibility checks;
- content-reference verification;
- failure handling.

A full production disaster-recovery system is not required.

The result must be sufficient to protect future valuable repositories.

## Integrity and Recovery

Provide or extend repository integrity checks for:

- SQLite database integrity;
- foreign keys;
- uniqueness invariants;
- artifact-to-content references;
- checksums;
- missing files;
- orphaned content;
- observation relationships;
- acquisition-attempt relationships;
- provenance relationships;
- repository revision consistency.

Define recovery boundaries.

Integrity tooling may report and classify problems but shall not silently rewrite evidence or infer repairs.

## Schema Evolution

Introduce schema-version infrastructure from the beginning.

The initial SQLite repository format shall have an explicit version.

Provide:

- schema-version read and validation;
- incompatible-version failure;
- migration entry-point structure or placeholder sufficient for future versions;
- no general legacy POC migration;
- tests for compatible and incompatible versions.

Do not build speculative future migrations.

## Legacy Structured-State Retirement

For new repositories, retire reliance on legacy authoritative structured files and pointer files.

Identify which legacy mechanisms are:

- no longer used by new repositories;
- retained only for fixtures or historical test evidence;
- removable in this task;
- deferred for later cleanup because removal would create unnecessary risk.

Do not retain parallel authority merely to keep obsolete code alive.

Do not perform unrelated broad cleanup.

The completion record must explicitly list remaining legacy persistence code and why it remains.

## Operator Experience

Preserve or improve operator-visible behavior for:

- `rfi init`;
- `rfi seed`;
- `rfi admin`;
- pull execution;
- artifact browsing;
- missing state;
- corrupt state;
- incompatible schema;
- content-integrity failures;
- backup and restore.

Errors shall be actionable and must not expose internal SQL, filesystem paths, or sensitive data unnecessarily.

## Functional Proof

Demonstrate at minimum:

1. A clean state directory initializes a valid SQLite-backed repository.
2. Repeated initialization is idempotent.
3. `rfi seed` preserves existing explicit-seeding behavior.
4. The firm catalog is available through the selected bounded preservation or reseeding approach.
5. A source profile can be created and read.
6. A pull execution is stored transactionally.
7. The SEC Form 10-K adapter can retrieve an artifact into fresh SQLite-backed state.
8. Stored bytes remain in the content-addressed filesystem.
9. The database stores a content reference, not artifact bytes.
10. Pulling the same filing twice produces one artifact, two observations, and one stored content object.
11. Same-run retries remain idempotent.
12. No immutable identity conflict occurs.
13. Artifact query contracts return equivalent normalized results.
14. Latest and oldest lookup work.
15. First, last, and explicit observation selection work.
16. Previous and next observation navigation work.
17. Stale-cursor behavior remains deterministic.
18. Artifact browser tree, metadata, and preview work.
19. Stored HTML remains isolated.
20. Content range responses and integrity verification work.
21. Network-blocked inspection works without provider access.
22. Process restart preserves all structured state and query results.
23. SQLite integrity and foreign-key checks pass.
24. Missing content is detected.
25. Orphan or dangling structured references are detected.
26. Backup and restore to a fresh location reproduce equivalent queries and content checksums.
27. An incompatible schema version fails explicitly.
28. Legacy POC structured state is not silently imported or mixed with SQLite authority.
29. Full project validation passes.
30. Isolated copied-tree validation passes.

## Failure Semantics

Distinguish at least:

- missing database;
- uninitialized state;
- already initialized compatible state;
- incompatible schema version;
- corrupt SQLite database;
- foreign-key integrity failure;
- uniqueness conflict;
- repository transaction failure;
- database locked or busy;
- missing content object;
- checksum mismatch;
- orphaned content object;
- dangling content reference;
- invalid firm import or seed;
- legacy state detected;
- unsupported automatic migration;
- invalid or stale cursor;
- artifact conflict;
- observation conflict;
- backup failure;
- restore failure;
- successful initialization;
- successful artifact reuse;
- successful new observation creation;
- successful backup and restore.

Failures shall be structured, sanitized, operator-visible, and testable.

## Validation Requirements

Validation shall include:

- schema creation tests;
- schema-version tests;
- SQLite configuration tests;
- foreign-key and uniqueness tests;
- transaction rollback tests;
- interrupted cross-substrate write tests;
- repository initialization and repeated-init tests;
- firm catalog tests;
- source-profile tests;
- acquisition-attempt tests;
- duplicate-pull regression;
- `ArtifactObservation` tests;
- artifact query equivalence tests;
- ordering and cursor tests;
- browser integration tests;
- stored-content endpoint tests;
- checksum and integrity tests;
- backup and restore tests;
- restart tests;
- network-blocked tests;
- legacy-state detection tests;
- no-BLOB proof;
- parameterized-query or injection-boundary tests;
- TASK-015 through TASK-020 regression coverage as applicable;
- full `make validate`;
- isolated copied-tree validation;
- documentation and design-baseline validation;
- sensitive-output scan;
- review-package manifest and ZIP integrity validation.

Tests shall assert durable behavior and failure semantics, not only helper return values.

## Required Review Package

Produce the standard TASK-021 review directory and ZIP containing at least:

- task ticket;
- executive summary;
- implementation summary;
- architecture decisions;
- alternatives considered;
- authority model;
- SQLite schema and version;
- schema ownership matrix;
- transaction-boundary analysis;
- content-store coordination model;
- repository contract preservation matrix;
- cursor and snapshot model;
- firm catalog treatment;
- fresh-state cutover behavior;
- legacy-state handling;
- backup and restore procedure;
- integrity and recovery model;
- remaining legacy persistence inventory;
- known limitations and deferred work;
- changed-file inventory with rationale;
- cumulative task-scoped patch;
- repository tree;
- Git branch, base, HEAD, staged, unstaged, and untracked state;
- exact validation commands;
- complete raw focused-validation output;
- complete raw full-validation output;
- schema proof;
- initialization proof;
- duplicate-pull proof;
- artifact/observation/content-count proof;
- query-equivalence proof;
- browser proof;
- no-BLOB proof;
- backup/restore proof;
- restart proof;
- network-blocked proof;
- integrity proof;
- incompatible-version proof;
- legacy-state rejection proof;
- sensitive-output scan;
- machine-readable manifest;
- member checksums;
- ZIP checksum and integrity evidence.

A passing summary without independently reviewable raw evidence is insufficient.

## Documentation and Durable Design Record

Update repository documentation and ADRs as warranted.

The durable record shall explain:

- why TASK-021 uses fresh-state initialization instead of legacy migration;
- why only firms may be preserved or reseeded;
- why SQLite is authoritative for structured state;
- why immutable bytes remain filesystem evidence;
- why permanent dual authority is prohibited;
- how transactions coordinate with content writes;
- how cursors retain deterministic semantics;
- how backup and restore cover both authoritative substrates;
- how future schema migrations will be introduced;
- which legacy persistence mechanisms remain and why;
- what triggers future PostgreSQL evaluation;
- what triggers future legacy migration tooling.

Update TASK-021 as the durable completion record with:

- implementation resolution;
- files changed and rationale;
- schema summary;
- contract-preservation summary;
- exact validation results;
- fresh-state proof;
- duplicate-pull proof;
- backup/restore proof;
- known limitations;
- deferred work;
- Architectural Status Summary.

## Backlog and Deferred Work

Review `BACKLOG.md`.

Add only genuine newly discovered unscheduled work.

Potential deferred items include:

- migration tooling once repositories contain material business data;
- PostgreSQL transition when concurrency or availability triggers are met;
- performance indexes justified by measured corpus size;
- advanced backup scheduling;
- repair tooling;
- artifact revision-history browsing.

Do not pull deferred work into TASK-021 unless required for correctness.

## Non-Goals

TASK-021 does not implement:

- general legacy repository migration;
- artifact migration;
- observation migration;
- acquisition-history migration;
- permanent dual-read;
- permanent dual-write;
- artifact BLOB storage;
- PostgreSQL;
- multi-host writers;
- high availability;
- point-in-time recovery;
- distributed locking;
- cloud deployment;
- ORM adoption unless strictly required and explicitly justified;
- full-text search;
- semantic search;
- extraction redesign;
- Bring Repository Up to Date;
- metadata merging;
- artifact mutation;
- observation mutation;
- broad cleanup unrelated to the new structured-state foundation.

## Codex Execution Constraints

- Work only within the RFI-1 repository and the prepared TASK-021 branch.
- Read the governing project documents, TASK-018 through TASK-020 records, `docs/storage_architecture_design_draft.md`, ADR-0016, repository/query contracts, acquisition architecture, content-store design, `BACKLOG.md`, and review-package conventions before implementation.
- Treat the task as a fresh-state repository foundation, not a migration task.
- Do not import legacy artifacts or structured history.
- Preserve or reseed only the firm catalog if useful.
- Preserve public repository/query contracts.
- Keep artifact bytes outside SQLite.
- Use parameterized SQL.
- Add no permanent dual authority.
- Stop and report any conflict with established identity, immutability, or repository-contract invariants.
- Do not commit, stage, push, merge, clean, delete branches, or perform unrelated repository cleanup.
- Do not mark TASK-021 Complete until all required validation and review evidence exists.
