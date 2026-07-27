# TASK-041 Verification Package

## Implementation summary

TASK-041 makes JSON files in `STATE/firm-config/*.firm-config.json` authoritative for an
independently managed subset of firms. Startup validates the complete discovered set against the
packaged version-1 JSON Schema and repository semantics before one atomic SQLite materialization.
Microsoft is the first managed firm; firms without files retain their existing editor authority.

The materializer appends immutable firm and source-profile revisions, moves current selectors,
upserts verified SEC identities, and records the external authority. It preserves stable firm IDs
and never changes `sec_sources`, acquisition runs or attempts, artifacts, observations, provenance,
resolved URLs, discussions, reports, or other runtime evidence.

## Ownership and failure behavior

- RFI reads but never creates, edits, patches, or rewrites authoritative files.
- Structural and complete-set semantic validation happen before mutation.
- One transaction covers every managed firm, profile, identity, and authority row.
- Invalid input, a missing previously managed file, or persistence failure refuses startup and
  leaves the prior projection intact.
- Repository and HTTP writes for managed firms and profiles fail closed. GET projections remain
  available, and the UI labels managed state and disables affected controls.
- SEC retrieval candidates continue through TASK-040 synthesis from
  `firm_external_identities`; runtime filing URLs and accessions remain derived.

## Validation

- Focused TASK-041 suite: 8 tests passed, covering valid Microsoft materialization, deterministic
  structural and semantic rejection, duplicate identities, rollback, repeated overwrite,
  evidence preservation, missing-file refusal, read access, and managed-write rejection.
- Configuration and acquisition regression suite: 64 tests passed.
- Legacy migrations from schema versions 1, 2, 3, 5, 6, 9, and 10 reach schema version 11.
- Canonical `make validate`: PASS; all 400 tests passed, followed by lint, format, typecheck,
  import, documentation, baseline, deterministic proof, and source-archive integrity gates.
- Published and packaged JSON Schema files are byte-for-byte identical; `git diff --check` passes.
- `make review-package` reproduces focused, regression, diff, and full validation and emits a
  self-contained archive under `.artifacts/review/` with checksums and ZIP integrity evidence.

## Limitations

- The first slice covers Microsoft and the existing SEC filing artifact vocabulary only.
- All other firms remain SQLite/editor-owned until deliberately converted.
- Each startup appends equivalent revisions; no hashes, no-op detection, file watching,
  incremental reconciliation, or revision-history design is included.
- No schedules, SEC URLs, amendments/exhibits, non-SEC adapters, YAML authoring, or RFI-side export
  and generation are part of the file contract.

## Architectural Status Summary

| Subsystem | Responsibility | Status |
| --- | --- | --- |
| External JSON contract | Complete Microsoft firm and supported SEC intent | Complete |
| Structural and semantic validation | Deterministic complete-set fail-closed checks | Complete |
| SQLite materializer | Atomic append/upsert projection with stable firm IDs | Complete |
| Authority enforcement | Reject managed writes while retaining inspection | Complete |
| SEC identity and synthesis | Verified CIK projection and effective candidates | Complete |
| Mutable SEC workflow knowledge | Resolver-owned `sec_sources` state | Complete, unchanged |
| Immutable acquisition evidence | Artifacts, observations, and provenance | Complete, unchanged |
| Remaining firm conversion | External files for the rest of the fleet | Not Started |
| Change detection and file watching | Deferred startup optimization | Not Started |

Architectural change introduced: configuration authority may now be assigned per stable firm to an
external JSON file, with SQLite retained as a runtime projection. The next milestone is operator
evaluation of the Microsoft slice before any deliberate conversion of additional firms.
