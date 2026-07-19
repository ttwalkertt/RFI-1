# TASK-020 — Structured Repository Storage Architecture Review

## Status

Complete

## Objective

Perform a neutral architecture review of RFI's structured repository storage and recommend
whether to retain the file/ledger model, use a relational rebuildable read model, adopt relational
authority, use explicit hybrid authority, or adopt another materially justified store.

## Constraints

- Do not implement a migration.
- Do not add a database dependency.
- Do not change repository behavior or authoritative state.
- Do not assume SQLite, PostgreSQL, or another product before comparison.
- Preserve repository/query contracts and immutable evidence boundaries.
- State uncertainty rather than manufacture a recommendation.

## Required review coverage

The review must make explicit authority for every major record type; structured-data versus
immutable-byte boundaries; record-handling code to retain or retire; transaction, concurrency,
query, and index implications; migration, rollback, backup, restore, replay, rebuild, and
corruption handling; embedded versus server storage; operational burden; conceptual target schema;
decision triggers; alternatives; risks; unresolved questions; and go/no-go for later implementation.

Primary deliverable: `docs/storage_architecture_design_draft.md`.

## Completion Record

TASK-020 completed a repository-grounded architecture review without implementing migration,
adding a dependency, changing behavior, or changing runtime authority.

### Recommendation

Adopt a relational database-backed architecture with explicit hybrid authority:

- SQLite is the recommended authoritative store for structured runtime state.
- Content-addressed immutable artifact files remain authoritative for exact acquired bytes.
- Version-controlled governance/configuration inputs remain files.
- Rebuildable indexes and projections remain non-authoritative.
- PostgreSQL is deferred until explicit multi-host, concurrent-writer, HA, or PITR triggers.

The recommendation is a GO for a separately authorized migration task and a NO-GO for ad hoc
schema changes, permanent dual-write, database artifact BLOBs, or any TASK-020 migration.

### Decision rationale

The existing file architecture proved the domain invariants, but now repeats database mechanics
across acquisition, catalogs, pull runs, generations, and workspaces. Native relational
transactions, constraints, and indexes address demonstrated structured-state atomicity and query
needs while SQLite preserves local/offline operation and introduces no server burden. A relational
read model alone would add synchronization without retiring custom write mechanics. Other stores
lack a materially justified workload advantage.

### Durable records

- `docs/storage_architecture_design_draft.md`: full comparison, authority matrix, storage
  boundary, schema concept, migration/rollback/recovery plan, risks, questions, and recommendation.
- `docs/decisions/0016-hybrid-sqlite-structured-state.md`: accepted direction and constraints.
- `BACKLOG.md`: later migration candidate and authorization boundary.
- `TASKS.md`, `ARCHITECTURE.md`, `ROADMAP.md`, and design-baseline records: material project
  direction updated.
- `scripts/generate_task020_review.py`: reproducible complete review package and validation record.

### Verification and review evidence

Documentation, design baseline, lint, import, full project validation, copied-tree validation,
sensitive-output scan, cumulative patch capture, manifest/member checksum verification, archive
checksum, and ZIP integrity are required before this record is complete. Exact commands and raw
outputs are retained in `.artifacts/review/TASK-020/`.

Completion evidence was produced on branch `codex/task-020-structured-storage-review` from base
and unchanged HEAD `80e887681d426e5ee83d6dcff98270f0b055f8f5` (the merged TASK-019 baseline):

- documentation validation — PASS;
- design-baseline validation — PASS;
- lint, format, type, and import validation — PASS;
- full `make validate` — PASS, including 201 tests, all deterministic operator proofs through
  TASK-019, documentation/baseline gates, and source-archive integrity;
- copied-tree validation without Git, repository state, generated artifacts, caches, or
  credentials — PASS;
- sensitive-output scan — PASS;
- review manifest, member checksums, exact ZIP listing, ZIP member integrity, and archive checksum
  — PASS.

Review directory: `.artifacts/review/TASK-020/`

Review archive: `.artifacts/review/TASK-020-review.zip`

Archive checksum record: `.artifacts/review/TASK-020-review.zip.sha256`

### Known limitations and unresolved questions

- No production corpus metrics or concurrent-writer measurements exist; SQLite is selected for
  demonstrated needs, with explicit PostgreSQL triggers.
- The physical database boundary for authoritative knowledge requires implementation-task design.
- Pull-run/acquisition transaction ownership, recovery objectives, legacy malformed-state policy,
  and authority-marker format remain unresolved.
- No migration tool, schema, compatibility adapter, backup implementation, or cutover exists.

## Architectural Status Summary

| Subsystem | Status | Boundary after TASK-020 |
| --- | --- | --- |
| Immutable artifact evidence | Complete, unchanged | Exact content-addressed bytes remain filesystem authority. |
| Structured repository authority | Usable with Limitations | Existing file authority remains active; SQLite migration recommended. |
| Artifact query contracts | Complete, unchanged | Persistence-independent compatibility gate for later migration. |
| Catalog authorities | Complete semantics; provisional storage | Immutable revision behavior retained; relational authority recommended. |
| Source objects | Complete, rebuildable | Existing SQLite catalog supports product fit but remains non-authoritative. |
| Knowledge | Provisional | Authority class retained; physical target boundary unresolved. |
| Retrieval | Provisional, rebuildable | Candidate state remains disposable. |
| Workspace | Usable with Limitations | Independent authority retained; separate SQLite workspace recommended. |
| Storage architecture review | Complete | Explicit hybrid SQLite/file authority selected. |
| Storage migration | Not Started | Separate task, offline reconciliation, backup/restore, and atomic cutover required. |

Architectural change: RFI now has a selected structured-storage direction but no implemented
migration. Proposed next milestone: authorize a bounded hybrid SQLite migration task that begins
with inventory, schema/contract fixtures, offline shadow import, differential validation, and a
rehearsed rollback boundary.
