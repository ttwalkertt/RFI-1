# TASK-038 — Configuration Backup and Restore for RBF Resets

## Status

**Complete**

---

## Objective

Provide a configuration-only backup and restore mechanism whose principal purpose is to make RBF artifact-storage resets fast, safe, and repeatable.

The workflow must allow an operator to preserve durable RFI configuration, initialize a clean target state, restore that configuration, and then reacquire artifacts from authoritative sources.

This task is intended for situations such as the current duplicate and historical conflict cleanup, where the artifact corpus should be discarded and rebuilt without forcing the operator to manually recreate firms, sources, streams, policies, and related operator-authored setup.

Assume the operator has already created and checked out the `TASK-038` branch.

---

## Intended Operator Workflow

```text
export configuration from current state
→ preserve the old full-state backup for rollback
→ initialize a clean target state
→ import configuration
→ reacquire artifacts from source
```

Representative CLI shape:

```bash
rfi config export --state OLD_STATE --output rfi-config.yaml
rfi init --state NEW_STATE
rfi config import --state NEW_STATE --file rfi-config.yaml
```

The exact command spelling may follow existing CLI conventions, but the behavior and boundaries below are required.

---

## Primary Use Case

The primary use case is an RBF reset of artifact storage.

An operator must be able to:

1. export durable configuration from the current state;
2. initialize a fresh current-schema target;
3. import the configuration into that target;
4. confirm that no artifact or artifact-derived state was transferred;
5. reacquire source material without rebuilding configuration manually.

This is a reset-enablement feature for disposable acquisition evidence.

---

## In Scope

Export and restore durable operator-authored configuration needed to resume acquisition.

At minimum, inspect the current repository model and include applicable configuration such as:

- firms and firm metadata;
- mailing-list source definitions;
- SEC identities and source configuration;
- stream definitions;
- current effective stream revisions or equivalent active configuration;
- acquisition policies;
- selection policies;
- enabled or disabled states;
- other durable application settings required to resume configured acquisition.

The implementation should preserve relationships using stable domain identifiers rather than SQLite row IDs.

---

## Explicitly Excluded

The configuration package must contain no artifact or artifact-derived data.

Exclude:

- artifact bytes;
- artifact metadata;
- artifact IDs;
- artifact hashes;
- retained source documents;
- canonical Message-ID registrations;
- mailing-list messages;
- acquisition runs;
- queue history;
- acquisition observations;
- coverage state;
- projections;
- discussion memberships;
- conflict cases;
- conflict observations;
- derived indexes;
- internal database primary keys;
- foreign keys whose meaning depends on artifact or run records;
- local absolute paths that are not themselves intentional configuration.

This task must not become a partial database dump.

---

## Import Contract

The target state must already be initialized with the current supported schema.

The importer must:

- refuse a missing or uninitialized target;
- refuse an incompatible target schema;
- validate the complete input before making changes;
- apply changes transactionally;
- resolve relationships using stable domain identities;
- be idempotent when importing the same configuration repeatedly;
- fail with actionable diagnostics when existing target configuration materially conflicts;
- avoid silently overwriting materially different configuration.

A dry-run or check mode is optional unless the existing CLI structure makes it inexpensive.

---

## Export Format

Use a deterministic, human-readable, versioned format.

Preferred shape:

```yaml
format: rfi-config
version: 1

firms:
  ...

sources:
  ...

streams:
  ...

policies:
  ...
```

The configuration format version must be independent of the SQLite schema version.

The export must be reconstructive rather than referential:

- no dependence on SQLite primary keys;
- no artifact IDs;
- no run IDs;
- no hidden dependence on database insertion order;
- no dependence on the original state directory path.

For unchanged configuration, repeated exports should produce equivalent deterministic output.

---

## Architectural Constraints

Preserve existing domain ownership and repository boundaries.

Do not:

- introduce a generic migration framework;
- redesign artifact storage;
- alter artifact immutability rules;
- migrate historical artifact evidence;
- add selective artifact restore;
- combine this feature with full-state backup;
- preserve acquisition history as configuration;
- broaden the task into a general synchronization system.

Reuse existing configuration import/export facilities where appropriate, but produce one coherent operator workflow for rebuilding a clean RFI state.

---

## Required Reconnaissance

Before implementation, identify:

- all durable configuration categories currently stored under the state repository;
- which categories are operator-authored versus derived;
- stable domain identities available for reconstructing relationships;
- existing import/export code that can be reused;
- ordering or dependency requirements during import;
- any configuration that cannot safely be represented without artifact-related references.

Keep the reconnaissance concise and proceed with the smallest coherent implementation.

---

## Acceptance Criteria

Demonstrate all of the following:

1. Durable supported configuration can be exported from an existing state.
2. The export contains no artifact bytes, artifact metadata, artifact hashes, or artifact IDs.
3. The export contains no acquisition runs, coverage, projections, conflicts, or other artifact-derived records.
4. Import requires an initialized current-schema target.
5. Import validates input before mutation.
6. Import is transactional.
7. Relationships are restored using stable domain identifiers.
8. Re-importing the same package is idempotent.
9. Material conflicts in the target fail with actionable diagnostics rather than silent overwrite.
10. Repeated export of unchanged configuration is deterministic or semantically equivalent under the chosen serialization rules.
11. A fresh target restored from the export contains the required firms, sources, streams, policies, and enabled states.
12. The restored target contains zero artifacts and zero artifact-related operational history before reacquisition.
13. The Linux Block Layer acquisition can be started from the restored configuration without manually recreating its firm, source, stream, or policy setup.
14. Existing full-state backup and restore behavior remains unchanged.
15. Full repository validation passes.

---

## Required End-to-End Proof

Provide an end-to-end test or review proof tied to the immediate RBF reset use case:

1. Export configuration from a populated state.
2. Initialize a fresh target state.
3. Import the exported configuration.
4. Verify expected configuration is present.
5. Verify artifacts, acquisition runs, coverage, projections, and conflicts are absent.
6. Start or exercise the configured Linux Block Layer acquisition path sufficiently to prove that manual configuration reconstruction is unnecessary.

The proof must not rely on copying the original SQLite database or artifact store.

---

## Validation

Run:

- focused tests for export;
- focused tests for import;
- malformed and incompatible input tests;
- transaction rollback tests;
- idempotent re-import tests;
- conflict diagnostic tests;
- deterministic export tests;
- clean-target exclusion tests;
- the RBF reset end-to-end proof;
- full `make validate`.

---

## Documentation

Document:

- the purpose of configuration-only backup and restore;
- the RBF reset workflow;
- what is included;
- what is explicitly excluded;
- the initialized-target requirement;
- conflict behavior;
- the distinction from full-state backup and restore.

---

## Required Review Package

Provide a concise review package containing:

- architectural summary;
- configuration inventory;
- export format summary;
- import behavior;
- exclusion proof;
- end-to-end RBF reset proof;
- validation results;
- known limitations.

Do not generate unnecessary review artifacts beyond what is needed to verify the task.

---

## Git Instructions

Assume the operator has already created and checked out the `TASK-038` branch.

Required:

- implement the task;
- add focused tests;
- run full validation;
- update the task ticket;
- create the required review package;
- commit all task-related changes.

Do not:

- merge;
- rebase;
- push;
- create or delete branches;
- switch branches;
- perform repository cleanup.

---

## Success Definition

An operator can preserve durable RFI configuration, initialize a clean state repository, restore the configuration, and reacquire artifacts without manually rebuilding firms, sources, streams, policies, or other supported setup.

No artifact or artifact-related data crosses the reset boundary.

---

## Completion Evidence

Implemented `rfi config export` and `rfi config import` as a version-1 deterministic YAML contract.
The supported inventory is current effective firms, firm source profiles, governed mailing-list
sources and transport policy, verified SEC source identities, and current effective streams.
Configuration relationships are reconstructed through stable firm, source, canonical artifact
family, and stream identifiers. Revision IDs, database row IDs, original paths, and historical
configuration revisions are not part of the package contract.

Import opens only an initialized current-schema target, parses and validates the complete package
by reconstructing it in an isolated current-schema staging repository, detects material conflicts
by stable identity, and copies only missing validated configuration rows in one target transaction.
Exact repetition creates no rows. Existing full-state backup and restore code is unchanged.

`tests/test_task038.py` provides focused export, deterministic serialization, malformed/version and
target compatibility, transaction/no-mutation, conflict, idempotence, exclusion, and end-to-end RBF
reset coverage. Its end-to-end case performs fixture-backed Linux Block Layer acquisition and a
stream run in the source state, imports into fresh initialized state, proves artifact and
artifact-derived tables are empty, and starts fixture-backed acquisition preview using only restored
configuration.

Validation completed on 2026-07-26:

- focused TASK-038 suite: **PASS**, 5 tests;
- focused TASK-038 plus unchanged full-state backup/restore regression: **PASS**, 13 tests;
- full `make validate`: **PASS**, including 384 tests, offline architectural proofs, lint,
  formatting, type checking, import, documentation, design baseline, and source archive build;
- review package: `.artifacts/review/TASK-038/`.

## Architectural Status Summary

- Configuration package boundary: **Complete** for acquisition-resumption configuration listed
  above; versioned independently from SQLite.
- Configuration import: **Complete** for validated, conflict-safe, idempotent, transactional import
  into current-schema initialized state.
- RBF reset workflow: **Complete** for export → init → import → reacquire, with Linux Block Layer
  end-to-end proof.
- Full-state rollback: **Complete and unchanged**; `rfi backup`/`rfi restore` remain the only way to
  preserve and restore evidence and operational history.
- Artifact migration or synchronization: **Not started and explicitly out of scope**.
- Important limitation: only current effective configuration is transferred; configuration revision
  history, browser-local preferences, consulting workspaces, and secrets/environment credentials are
  not transferred.
- Next architectural milestone: perform the operator-controlled RBF reset and reacquisition using
  the reviewed package while retaining the full-state rollback backup.
