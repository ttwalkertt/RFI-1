# TASK-041: External Firm-Configuration Materialization

## Status

Complete

## Objective

Make externally generated, schema-validated JSON authoritative for a bounded set of firm and
source-profile configuration while retaining SQLite as the runtime/query projection.

## Scope

- Discover one complete file set from `<state>/firm-config/*.firm-config.json`.
- Validate every file structurally and semantically before any configuration mutation.
- Materialize file-owned firm revisions, verified SEC external identities, and source-profile
  revisions in one transaction.
- Preserve stable firm identities and all immutable revision history.
- Support Microsoft as the first independently managed firm while other firms remain editor-owned.
- Reject UI, API, and repository writes for externally managed firms while preserving read access.
- Keep `sec_sources` and every acquisition/evidence subsystem outside the materialization boundary.

## Invariants

- RFI never generates, edits, patches, or rewrites authoritative JSON files.
- The whole discovered file set validates before SQLite changes.
- A materialization failure rolls back the complete set.
- Missing files for previously managed firms fail startup rather than transferring authority.
- Runtime SEC URLs, accessions, artifacts, provenance, observations, discussions, reports, and
  mutable SEC workflow knowledge are untouched.
- SEC retrieval candidates continue to be synthesized from `firm_external_identities`.

## Out of Scope

- YAML authoring, JSON export, configuration generation, file watching, hashes, no-op detection,
  incremental reconciliation, schedules, new acquisition adapters, or non-SEC parser work.

## Acceptance Criteria

- The narrowed version-1 JSON Schema and Microsoft example are checked in and packaged.
- Startup validates and transactionally materializes all discovered files before serving or pulling.
- Microsoft can coexist with editor-owned firms and is inspectable but not editable.
- Repeated startup may append revisions but produces the same effective configuration.
- Invalid or partially failing loads leave configuration and evidence unchanged.
- Focused preservation, synthesis, startup, API, migration, and canonical validation pass.
- A review package records ownership, tables, startup ordering, rollback, preservation, limitations,
  and an Architectural Status Summary.

## Repair acceptance criteria

- Synthesized managed SEC candidates satisfy the canonical retrieval-mode requirements.
- Microsoft 10-K, 10-Q, and 8-K planning selects the existing numbered-form adapters.
- A fixture-backed Microsoft pull traverses the same planner, adapter, and acquisition path as an
  editor-owned firm.
- Missing or malformed managed SEC identity fails before a blank enabled candidate can be admitted.
- The repair does not write `sec_sources` or weaken managed-write protection.

## Maintenance repair acceptance criteria

- SEC primary-document validation accepts the proven Microsoft Inline XBRL XML/comment prolog.
- HTML recognition remains bounded and rejects comments containing decoy HTML, missing roots, and
  roots beyond the inspection boundary.
- The exact Microsoft 10-K accession succeeds through the existing provider without changing
  configuration, adapter selection, filing policy, or immutable evidence semantics.
