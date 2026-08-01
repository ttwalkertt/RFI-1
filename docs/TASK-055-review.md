# TASK-055 Verification Report

## Result

TASK-055 is Complete. The admin console detects divergence between authoritative external firm
configuration and the last successfully materialized repository projection without parsing,
validating, materializing, advancing revisions, or otherwise writing during detection.

## Architecture and Boundaries

`firm_configuration_fingerprint(state)` hashes the sorted configuration filenames and exact bytes
with length-delimited framing. Modification times and decoded JSON are excluded. The imported
fingerprint is repository metadata in `firm_configuration_imports`; schema version 14 introduces
that single-row authority. `prepare_firm_configuration(state)` fingerprints before validation,
uses the existing complete-set validation path, confirms the bytes did not change while being
prepared, and writes the fingerprint inside the same transaction as projections and repository
authority advancement. There is no second validation or materialization path.

`inspect_firm_configuration_status(state)` reads only the imported fingerprint and external bytes.
It reports `current`, `changes_available`, or `inspection_failure`. Admin startup stores this
comparison in process memory and continues with existing projections. The fixed read-only status
endpoint recomputes on each Target Firms page load. Successful TASK-054 reload refreshes status
immediately while preserving the existing reload response, concurrency, rollback, and pull
snapshot contracts.

## Operator Workflow and Color Evidence

Target Firms exposes an always-visible textual status adjacent to the existing Reload Firm
Profiles action. Current is green; external changes available is amber with an actionable reload
reminder; inspection failure is red. Pull Workflow outcome badges are green for success, blue for
duplicate/informational, amber for indeterminate/no-change/skipped, and red for configuration or
retrieval failure. Labels, `role=status`, `aria-live`, and `data-outcome` preserve non-color
semantics.

## Verification

`make task055-test` covers unchanged, added, removed, renamed, byte-changed, and timestamp-only
sets; non-parsing malformed bytes; explicit inspection failure; startup write-freedom and normal
continuation; page-load refresh; reload fingerprint atomicity and reminder clearing; accessible
colors; TASK-054 reload compatibility; pull snapshot isolation; acquisition evidence; unrelated
durable state; and schema migration.

`make task055-proof` reproducibly demonstrates current, timestamp-only current, byte divergence,
and current immediately after reload. `make validate` runs the complete repository validation
matrix. Exact commands and captured results are included in the commit-aware review package.

## Changed-File Inventory

- `src/rfi/firm_configuration.py`: raw configuration-set fingerprint, read-only comparison, and
  transaction-owned imported fingerprint.
- `src/rfi/storage/sqlite.py`: schema-14 imported-fingerprint metadata and additive migration.
- `src/rfi/admin/server.py`: startup, status-endpoint, and post-reload comparison schedule.
- `src/rfi/admin/firms.html`: persistent accessible configuration status and reload reminder.
- `src/rfi/admin/pull_sources.html`: accessible semantic outcome colors.
- `tests/test_task055.py`: focused status, write-freedom, atomicity, UI, and API evidence.
- `scripts/task055_configuration_status.py`, `scripts/generate_task055_review.py`, and `Makefile`:
  reproducible proof, validation, and review packaging.
- schema-migration regression expectations, operator documentation, task roadmap, ticket, and
  governed design-baseline metadata.

## Retained Limitations

Detection is scheduled only at startup, Target Firms load, and after successful reload. It has no
poller, watcher, automatic reload, per-firm diff, or browser editor. Repository projections remain
active until explicit reload. TASK-054's init-equivalent creation of new revisions for unchanged
files remains intentional.

## Architectural Status Summary

- **External configuration authority — Complete.** External JSON remains authoritative; the
  browser remains read-only.
- **Imported fingerprint ownership — Complete.** SQLite owns one fingerprint committed atomically
  with successful materialization.
- **Read-only change detection — Complete.** Raw filenames/bytes are compared without parsing or
  repository writes; failures are explicit.
- **Target Firms operator status — Complete.** Current, changes available, and inspection failure
  are persistent, actionable, accessible, and semantically colored.
- **Reload/materialization boundary — Complete.** Only `prepare_firm_configuration(state)` validates
  and materializes; TASK-054 concurrency, rollback, response, and snapshot behavior remain intact.
- **Scheduling — Usable with limitations.** Detection is intentionally event-driven. A likely next
  milestone is change-aware no-op materialization; background monitoring remains out of scope.
