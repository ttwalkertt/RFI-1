# TASK-019 — Multiple Artifact Observations

## Status
Complete

## Objective
Allow a single immutable artifact to own multiple immutable ArtifactObservation records, eliminating immutable identity conflicts during repeated acquisition while preserving artifact identity.

## Architectural Intent

Artifact
 1 -> n ArtifactObservation

Artifacts represent durable source objects.
ArtifactObservations represent immutable acquisition observations.
Artifact identity is independent of observation identity. Observation identity is independent of acquisition attempt identity.

Artifact
    1
     \
      \
       n
ArtifactObservation
       |
       | observed during
       |
AcquisitionAttempt

## Artifact Responsibilities

Artifacts remain immutable and own:
- repository identity
- canonical artifact identity
- provider identity
- source-effective date
- stored bytes
- checksum

## ArtifactObservation Responsibilities

Each successful acquisition creates one immutable observation containing acquisition-specific metadata (timestamp, adapter, provenance, diagnostics, source-profile revision, status, etc.).

Observations never redefine artifact identity.

## Acquisition Behavior

Repeated acquisition of identical content shall:
- create one additional ArtifactObservation;
- reuse the existing artifact;
- reuse stored bytes and checksum;
- never produce immutable repository conflicts.

## Query Expansion

ArtifactDetail shall support observation selection:
- first
- last
- explicit observation id

Exactly one observation is returned.
No metadata merging is performed.

## Observation Cursor

ArtifactDetail returns an opaque observation cursor.

Repository operations:
- Next(cursor)
- Previous(cursor)

The browser treats the cursor as opaque.

## Snapshot Semantics

Observation cursors are snapshot-bound.
Repository changes return a structured stale_cursor rather than changing navigation silently.

## Browser

One artifact.
One selected observation.

Default observation: last.

Previous/Next changes observation metadata only.
Artifact preview remains unchanged.

## Query Responsibilities

The query layer performs observation selection and navigation only.
It shall not merge, reconcile, synthesize, or repair metadata.

## Extraction

No extraction changes.
Repeated acquisition of identical content shall not trigger re-extraction.

## Functional Proof

1. Pull identical document twice.
2. One artifact exists.
3. Two ArtifactObservations exist.
4. No immutable conflict.
5. first/last/explicit observation queries succeed.
6. Previous/Next navigation works.
7. Browser defaults to last observation.
8. Preview remains identical.
9. Replay preserves ordering.
10. TASK-018 browser remains functional.

## Non-Goals

No metadata merging, editing, deletion, comparison, filtering, timelines, retrieval planning, Bring Repository Up to Date, extraction redesign, or browser redesign.

## Validation

Include repeated-acquisition regression, observation navigation, replay, browser integration, TASK-018 regression, full validation, and regenerated review package.

## Codex Constraints

Treat this as an architectural correction.
Extend TASK-018 contracts.
Do not redesign the repository.
Do not implement metadata merge policy.
Do not commit, push, merge, or mark complete until validation and review evidence are complete.

## Completion Record

TASK-019 was completed on branch `codex/task-019-multiple-artifact-observations` without staging,
committing, pushing, merging, cleaning, or deleting branches.

### Implemented Architecture

- Added a separate authoritative immutable artifact-observation store. Each successful acquisition
  has a distinct `observation_id` referencing exactly one successful attempt and one immutable
  content-addressed artifact.
- Bound engine attempt identity to `run_id` plus candidate/document/revision/outcome semantics.
  Retry of one run remains idempotent; another pull records another attempt and observation.
- Preserved artifact checksum identity, exact stored bytes, document-index deduplication,
  checkpoint semantics, replay, rebuild, and integrity verification.
- Added a non-mutating legacy projection for successful pre-TASK-019 inline attempt records.
- Extended TASK-018 detail with one normalized observation selected by `first`, `last`, or explicit
  observation ID. No metadata is merged.
- Added opaque snapshot-bound `next` and `previous` observation cursors with structured
  `invalid_cursor`, `stale_cursor`, and `observation_boundary` failures.
- Defaulted the browser to last observation. Previous/Next changes observation metadata; preview
  construction remains guarded by immutable artifact identity.
- Made no extraction, repair, mutation, comparison, filtering, timeline, or planner changes.

### Functional Evidence

The focused duplicate-pull regression publishes two source-profile revisions and runs the shared
Pull Workflow twice against identical bytes. Results are one successful first pull and one
duplicate second pull, one artifact metadata/content record, two distinct immutable observations,
unchanged stored bytes, no immutable conflict, and repository integrity PASS.

Focused query proof covers first, last, explicit ID, next, previous, invalid boundary, and stale
cursor behavior. Artifact summary/ID and stored content remain equal across navigation. Browser API
integration defaults to last, navigates to previous metadata, and returns an unchanged summary.
Replay deletes and rebuilds derived views while preserving observation order, artifact inventory,
document-index semantics, checksum, and exact bytes. Legacy projection is verified without writing
a replacement observation.

### Validation Evidence

- `python -m unittest tests.test_task019 -v` — PASS, 7 tests.
- `python -m unittest tests.test_task018 -v` — PASS, 5 TASK-018 regression tests.
- `python scripts/task019_artifact_observations.py` — PASS.
- `make validate` — PASS, including the complete test suite, all operator proofs, lint, format,
  type, imports, documentation, design baseline, and source archive.
- Copied-tree validation without Git metadata, repository state, generated artifacts, caches, or
  credentials — PASS.
- Review-package sensitive-output scan, manifest/member checksums, exact ZIP listing, archive
  checksum, and ZIP member integrity — PASS.

The generated review directory is `.artifacts/review/TASK-019/`; the archive is
`.artifacts/review/TASK-019-review.zip`; its checksum is recorded in
`.artifacts/review/TASK-019-review.zip.sha256`.

### Known Limitations

- Observation navigation covers observations of the current immutable artifact selected for a
  document, not a cross-artifact revision or acquisition-attempt timeline.
- Current query work scans the POC authoritative record set and binds cursors to any authoritative
  acquisition change.
- Successful legacy attempts are projected as observations at read time; authoritative legacy
  records are intentionally not migrated or rewritten.
- Acquisition `ArtifactObservation` is distinct from extracted knowledge observations. No
  extraction or re-extraction policy was added.

## Architectural Status Summary

| Subsystem | Status | Boundary after TASK-019 |
| --- | --- | --- |
| Immutable artifact store | Complete | Owns exact bytes, checksum, size, media type, and content-addressed identity. |
| Artifact observation store | Complete | Owns immutable per-success acquisition metadata and links one attempt to one artifact. |
| Acquisition attempts | Complete | Run-bound activity identity; exact same-run retry remains idempotent. |
| Pull Workflow | Complete | Distinct unchanged pulls produce duplicate outcome plus a new observation. |
| Replay and rebuild | Complete | Existing document/checkpoint views remain attempt-derived; observations remain authoritative. |
| Integrity verification | Complete | Verifies observation source, attempt, artifact, and document relationships. |
| Artifact query detail | Complete | Selects exactly one first/last/explicit observation with no metadata merge. |
| Observation cursor navigation | Complete | Opaque snapshot-bound previous/next with stale rejection. |
| Artifact browser | Complete | Defaults last; navigation updates metadata while keeping artifact preview fixed. |
| Legacy repository compatibility | Usable with Limitations | Read-only observation projection preserves pre-TASK-019 successful attempts without migration. |
| Extraction and knowledge development | Unchanged | No re-extraction or knowledge-observation redesign. |
| Metadata repair, timelines, and planning | Not Started | Explicitly outside TASK-019. |

Architectural change: artifact identity now represents exact evidence only; successful acquisition
history has a separate immutable observation identity and a separately run-bound attempt identity.
The next milestone remains a separately authorized roadmap decision; TASK-019 adds no planner.
