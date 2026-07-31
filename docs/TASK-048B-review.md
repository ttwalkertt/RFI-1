# TASK-048B Review

## Outcome

Source-profile revisions now validate against their original digest schema. Pre-TASK-048A JSON
omits `discovery_class`; the short-lived unversioned TASK-048A shape includes it; new publications
carry and authenticate digest schema 3 together with every candidate's `discovery_class`.

Ordinary `rfi admin` startup and shared established-state opening validate external firm JSON but do
not call the TASK-041 materializer. Fresh `rfi init` and explicit materialization retain governed
write authority.

## Compatibility and Integrity

- Legacy canonicalization removes only the field that did not exist in schema 1.
- Transitional canonicalization is selected only when every persisted candidate contains the new
  field and no revision-level marker exists; mixed candidate shapes fail closed.
- Current canonicalization requires authenticated schema 3 and requires the field on every
  candidate. Empty values remain authenticated; omission is not inferred from an empty string.
- Digest, chain, ordering, pointer, and tamper checks remain active for every era.

## Copied Production Startup Evidence

Copy: `/tmp/rfi-startup-proof.OcrRzB/state`.

Before, after first startup, and after repeated startup:

| Evidence | Stable value |
| --- | --- |
| Firm revisions | 253 |
| Source-profile revisions | 240 |
| Authority revision | 2766 |
| SQLite database SHA-256 | `4d7aace82ff233a854abc32f7cc4d6ef15034fb19d3a188fe89609428d7e474c` |
| Persistent-file manifest SHA-256 | `d8a332c2b139169bf96e7a30a4ed6e8f30ce11531fd05c56bc1c60dde57a8ccd` |
| Ordered firm/source-profile history SHA-256 | `3acc0cf04c1ab16c9d21f4cbcd170f577e36c5a3078158f8eecd44e046dce0f8` |

Both admin processes reached `http://127.0.0.1:8765/` and stopped cleanly. Full pointer lists were
captured before startup; stable database bytes prove pointers and every other persistent SQLite
value remained unchanged.

## Verification

Focused coverage includes TASK-041, TASK-048A, source-profile repository/API, legacy/current
digest tampering, mixed histories, admin startup, explicit materialization, and copied production
startup. The review package retains focused and full `make validate` transcripts, the complete
patch, changed-file inventory, checksums, and ZIP integrity evidence.

## Architectural Status Summary

| Subsystem | Responsibility | Status |
| --- | --- | --- |
| Source-profile digest schemas | Authenticate immutable revisions by creation-era shape | Complete |
| Source-profile chain verification | Sequence, predecessor, ordering, pointer, and digest checks | Complete |
| External configuration validation | Load and validate authoritative JSON at startup | Complete |
| External configuration publication | Explicit governed creation of immutable projections | Complete |
| Admin startup | Read-only opening of established firm/profile history | Complete |
| Production rollback | Remove only the reviewed accidental append transaction | Pending code commit |

Architectural change: validation/loading and immutable projection publication are separate
operations. The main limitation is that pre-version-marker revisions require deterministic shape
recognition; all future revisions carry the authenticated marker. The next milestone should keep
schema evolution explicit at the immutable digest boundary.
