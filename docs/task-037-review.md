# TASK-037 Review Package — Message-ID Conflict Quarantine

## Architectural Summary

TASK-037 adds a Message-ID-specific quarantine path inside the existing
mailing-list acquisition boundary. Canonical Message-ID registration remains
fail-closed and unchanged: an existing canonical row is never overwritten and a
conflicting candidate never receives a canonical registration. The acquisition
repository retains the candidate's exact RFC822 bytes under a stable quarantine
document identity, the mailing-list repository records one durable unresolved
case plus per-run conflicted/skipped observations, and acquisition continues with
the remaining planned messages.

The durable run remains a successful acquisition with explicit `conflict_count`
and `conflicted_message_ids`; the operator UI renders that combination as
**Completed with conflicts**. Conflict-bearing runs do not advance complete
coverage.

## Workflow Diagram

```text
fetched RFC822 candidate
        |
        v
normalize Message-ID ---- invalid/other failure ----> existing failure behavior
        |
        v
lookup canonical registration
        |
        +-- absent/equal bytes --> existing retain/reuse and publication path
        |
        +-- different bytes
              |
              v
       retain content-addressed candidate bytes
              |
              v
       upsert Message-ID conflict case
       + append run observation: conflicted_skipped
              |
              v
       exclude candidate from canonical projection
       continue next planned message
              |
              v
       publish run with explicit conflict diagnostics
```

## Conflict Lifecycle

1. The first byte mismatch creates a stable quarantine document and artifact,
   one `unresolved` conflict case, and one run observation.
2. The canonical message row continues to reference its original artifact and
   document.
3. Re-observation of the same canonical/candidate artifact pair reuses the
   artifact and case, updates `last_detected_at` and `occurrence_count`, and adds
   the current run's conflicted/skipped observation.
4. Resolution policy is deliberately not implemented. The status column makes
   unresolved cases explicitly queryable without introducing a generic conflict
   framework.

## Evidence and Operator Diagnostics

Focused acceptance coverage demonstrates that:

- the canonical artifact ID is identical before and after conflict acquisition;
- candidate bytes read back exactly from the immutable artifact repository;
- the candidate artifact differs from the canonical artifact and has no
  canonical Message-ID registration;
- a second discovered message receives a canonical registration after the first
  message is quarantined;
- repeat acquisition leaves one candidate artifact and one conflict case while
  incrementing its observation count;
- the mailing-list query service returns unresolved conflict diagnostics scoped
  to the acquisition run;
- the Linux mailing-list result API includes those diagnostics, and the existing
  result panel displays normalized Message-ID, canonical artifact, candidate
  artifact, status, observation count, and last-observed time.

## Validation Results

- Focused continuation, idempotency, canonical preservation, immutable byte
  retention, non-conflict failure, and migration tests: **PASS**.
- Complete `tests.test_task023` mailing-list module: **PASS** (17 tests).
- Full `make validate`: **PASS** — 379 tests plus all repository proof scripts,
  lint, format, typecheck, documentation checks, baseline checks, and source
  archive integrity.

## Known Limitations

- Conflict resolution, candidate promotion, and canonical replacement are out of
  scope; cases remain unresolved for later operator investigation.
- Conflict-bearing runs preserve all safe evidence but intentionally do not
  advance complete repository coverage.
- The run lifecycle uses the existing `succeeded` storage invariant plus explicit
  conflict fields; the operator-facing equivalent is **Completed with
  conflicts**. This avoids broadening lifecycle semantics outside mailing-list
  acquisition.

## Architectural Status Summary

| Subsystem | Responsibility | Status |
|---|---|---|
| Immutable acquisition repository | Content-addressed retention of canonical and quarantined candidate bytes | Complete |
| Canonical mailing-list registry | One fail-closed canonical artifact per normalized Message-ID | Complete |
| Message-ID quarantine evidence | Durable unresolved case, timestamps, repeat count, and per-run outcome | Complete |
| Mailing-list acquisition workflow | Skip only retained byte conflicts and continue remaining messages | Complete |
| Operator query and console | Expose and render unresolved run conflicts | Complete |
| Conflict resolution policy | Resolve, promote, or replace evidence | Not Started (explicit non-goal) |

Architectural change introduced: a localized recoverable edge from per-message
retention back to acquisition iteration, backed by Message-ID-specific durable
evidence. No acquisition engine, generic conflict abstraction, canonical
identity rule, or immutable artifact rule changed. The next architectural
milestone is operator-directed conflict resolution if and when separately
authorized.
