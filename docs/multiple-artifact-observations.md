# Multiple immutable artifact observations

TASK-019 corrects acquisition identity without changing content-addressed artifact identity or
downstream extraction.

## Identity and ownership

```text
AcquisitionAttempt 1 ── observes ── 1 ArtifactObservation n ── belongs to ── 1 Artifact
```

- `artifact_id` is derived only from the SHA-256 of exact stored bytes. The artifact owns media
  type, byte count, checksum, and the single stored byte sequence.
- `observation_id` identifies one immutable successful acquisition observation. It owns observed
  time, adapter/mechanism, source-profile revision, candidate and provider provenance, diagnostics,
  and status. It references exactly one artifact and one successful attempt.
- `attempt_id` identifies one acquisition activity. Engine-generated identities are bound to the
  run, candidate semantics, and material outcome. Repeating the same run remains idempotent;
  another run is another attempt even when bytes are unchanged.

`ArtifactObservation` is acquisition-layer evidence. It is not the downstream knowledge-layer
“Observation” described in `ARCHITECTURE.md`; TASK-019 makes no extraction changes.

## Durable behavior and compatibility

Successful ingress writes or verifies exact artifact bytes first, then publishes artifact metadata,
the immutable attempt and observation, document/checkpoint projections, and repository revision in
one SQLite transaction. A distinct successful attempt that returns an existing checksum appends an
observation and attempt but creates no artifact row or content file.

The SQLite observation table is authoritative and independently integrity checked. Every observation must
reference an existing source, successful attempt, and artifact with the same document relationship.
Fresh TASK-021 repositories contain no pre-TASK-019 records. Legacy file state is rejected rather
than projected or migrated, so no compatibility path creates a second structured authority.

Document index and checkpoint replay remain attempt-derived. Multiple observations of the same
artifact do not duplicate the artifact in the document index. Repeated identical content does not
invoke or redesign extraction.

## Query and cursor contract

`ArtifactDetail` selects exactly one observation of the current immutable artifact for a logical
document. Selection accepts `first`, `last`, or an explicit observation ID; the default is `last`.
The selected `ArtifactObservation` is returned without merging adjacent metadata.

The detail also returns an opaque cursor plus previous/next availability. `next(cursor)` and
`previous(cursor)` bind document ID, artifact ID, observation ID, index, and the authoritative
repository revision token. Any source, attempt, observation, or artifact change produces the
structured `stale_cursor` result. Malformed, mismatched, and boundary cursors fail explicitly.

Navigation is confined to observations belonging to the selected immutable artifact. Artifact
summary, identity, checksum, content endpoint, and preview therefore stay unchanged while only
observation metadata changes.

## Browser behavior and limits

The TASK-018 browser loads last observation by default. Previous/Next delegates to the query
service and treats the cursor as opaque. Preview construction is guarded by artifact identity, so
same-artifact navigation does not reload or replace stored content.

There is no metadata merging, reconciliation, repair, editing, deletion, comparison, filter,
timeline, extraction redesign, retrieval planning, or Bring Repository Up to Date behavior.
