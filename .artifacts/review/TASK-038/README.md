# TASK-038 review package

Commit: `92eac0cd20ddcfa79ef7e3d48af82159e9ddf533`
Branch: `TASK-038`
Generated: 2026-07-26

## Architectural summary

TASK-038 adds a configuration-only boundary beside, and independent from, the unchanged full-state
backup/restore boundary. Export reads current effective acquisition-resumption configuration and
emits deterministic `rfi-config` version 1 YAML. Import reconstructs and validates the complete
package in an isolated current-schema staging repository, compares stable domain identities against
the target, and copies only missing validated configuration in one target transaction.

## Configuration inventory

- current effective firms and firm metadata;
- current effective firm source profiles, canonical artifact-family selections, retrieval
  candidates, enabled states, and operator notes;
- governed mailing-list source definitions, endpoints, enabled state, provider, and transport
  policy;
- verified SEC identity/source configuration, including parent-firm relationships;
- current effective stream definitions, selection and expansion policy, bounds, enabled state, and
  stable source/stream dependencies.

Relationships use stable firm IDs, source IDs, canonical artifact-family keys, and stream IDs. The
package contains no SQLite row IDs and no original state path.

## Export format and import behavior

The YAML root is `format: rfi-config`, `version: 1`, followed by deterministic lists for `firms`,
`source_profiles`, `sources`, `sec_sources`, and `streams`. The package version is independent of
SQLite schema version. Import refuses missing, uninitialized, or incompatible targets; validates
before target mutation; is idempotent for exact repetition; and rejects materially different
configuration under an existing stable identity with an actionable conflict.

## Exclusion proof

The populated source fixture contains artifacts, acquisition attempts, mailing-list runs and fetch
history, stream projections/runs/memberships, and discussion projections. The reset proof asserts
the fresh restored target has zero rows in all of those tables, plus zero conflict rows. The YAML is
also checked for evidence artifact IDs, run IDs, coverage/conflict/projection keys, and the original
absolute state path. No content-store file or SQLite database is copied.

## End-to-end RBF reset proof

`tests/test_task038.py` initializes and configures Seagate, a full firm source profile, Linux Block
Layer Lore source and transport policy, verified SEC identity, and a bounded Linux block stream. It
then performs fixture-backed mailing-list acquisition and a stream run, exports configuration,
initializes a fresh state, imports, verifies semantic equality and empty evidence/operational state,
reimports idempotently, and starts fixture-backed Linux Block Layer acquisition preview without any
manual configuration reconstruction. A separate test executes the exact CLI export → init → import
operator workflow.

## Validation

- `PYTHONPATH=src .venv/bin/python -m unittest tests.test_task038 -v`: PASS, 5 tests.
- TASK-038 plus existing TASK-021 full-state backup/restore regression: PASS, 13 tests.
- `make validate`: PASS after final baseline update; 384 tests plus all offline proof scripts,
  lint, format, typecheck, import, documentation, design-baseline, and source-archive checks.
- Final focused/static audit after the full run: PASS.

The first sandboxed `make validate` attempt could not bind loopback ports and also identified the
expected governed source-file inventory updates. The inventory was updated and both subsequent
permission-enabled full runs cleared all unit tests; the final run passed every validation target.

## Changed files

- `src/rfi/storage/configuration.py`
- `src/rfi/cli.py`
- `tests/test_task038.py`
- `tests/test_acquisition.py`
- `tests/test_foundation.py`
- `docs/application-cli.md`
- `tasks/TASK-038-configuration-backup-and-restore-for-rbf-resets.md`
- `TASKS.md`
- `docs/design-baseline.json`
- `scripts/check_baseline.py`

## Known limitations

- Only current effective configuration is transferred; historical configuration revisions are not.
- Browser-local preferences, consulting workspaces, secrets, and environment credentials are not
  transferred.
- Format version 1 is intentionally limited to the acquisition-resumption categories above; it is
  not a migration, sync, selective artifact backup, or database-dump framework.
- Reacquisition remains an explicit operator action after import.

## Architectural Status Summary

- Configuration-only export/import: **Complete** for the supported inventory.
- Transactional, validated, conflict-safe, idempotent current-schema import: **Complete**.
- RBF export → init → import → reacquire workflow: **Complete**, fixture proven for Linux Block
  Layer.
- Full-state rollback backup/restore: **Complete and unchanged**.
- Artifact transfer or synchronization: **Not started and out of scope**.
- Next milestone: operator-controlled RBF reset and authoritative reacquisition with the preserved
  full-state backup retained for rollback.

## Archive

This review directory is packaged as `../TASK-038-review-package.zip`. The archive preserves the
stable relative `TASK-038/` review paths and was verified with both `unzip -t` and `unzip -l`.

The archive is self-contained and includes:

- this architectural review and inventory;
- explicit RBF reset, export/import, and exclusion proof narratives under `TASK-038/evidence/`;
- focused TASK-038 and full-state-backup regression output under `TASK-038/validation/`;
- complete `make validate` output under `TASK-038/validation/`;
- the authoritative task ticket and operator documentation;
- the committed configuration implementation and CLI integration;
- the executable TASK-038 acceptance tests and repository boundary tests;
- implementation commit metadata and a SHA-256 manifest.
