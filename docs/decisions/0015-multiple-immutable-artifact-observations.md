# ADR-0015 — Multiple immutable artifact observations

## Status

Accepted by TASK-019.

## Context

The acquisition repository correctly derives one immutable artifact identity from exact bytes, but
successful retrieval metadata previously lived only in an attempt record whose engine identity was
derived from candidate semantics and outcome. A later pull could retrieve unchanged bytes with a
new timestamp or provenance while reusing that attempt identity. Immutable ledger comparison then
treated a legitimate new acquisition observation as conflicting attempt semantics.

TASK-018 detail selected the most recent successful attempt for an artifact, but exposed no stable
observation identity, selection contract, or snapshot-bound navigation.

## Decision

Introduce an authoritative immutable `ArtifactObservation` record with an identity distinct from
both content-addressed artifact identity and acquisition-attempt identity. One successful attempt
owns one observation; one artifact may own many observations. Observation metadata includes the
observed timestamp, adapter and mechanism, source-profile revision, candidate/discovery and
retrieval provenance, diagnostics, provider identifiers, and status.

Bind engine acquisition-attempt identity to `run_id` in addition to candidate, document, revision,
and outcome. A retry of the same run remains exactly idempotent. A distinct run that retrieves the
same bytes creates a distinct attempt and observation, while repository artifact identity and
stored content remain deduplicated.

Keep document index and checkpoint replay attempt-derived. Add observation integrity validation
and a deterministic read-only projection for successful pre-TASK-019 attempt records rather than a
metadata migration.

Extend `ArtifactDetail` with exactly one normalized observation selected by `first`, `last`, or
explicit observation ID. Return an opaque cursor binding repository snapshot, document, artifact,
observation, and position. `next` and `previous` reject changed repository state as `stale_cursor`.
The browser defaults to `last` and replaces only observation metadata while artifact identity,
content endpoint, and preview remain fixed.

## Alternatives considered

Changing artifact metadata on every pull was rejected because artifacts and checksums are
immutable byte evidence. Treating repeated pulls as idempotent attempts was rejected because it
discards real observation history and conflicts when timestamps differ. Merging observation
metadata was rejected because no reconciliation authority exists. Reusing ordinary artifact-list
pagination cursors was rejected because observation navigation has a distinct artifact-local
selection contract. Migrating legacy records was rejected because replay compatibility can be
provided without rewriting authoritative evidence.

## Consequences and limits

Repeated unchanged acquisition grows attempt and observation history but not artifact byte
storage. Any authoritative acquisition change invalidates observation navigation cursors. Detail
navigation covers observations of the currently selected immutable artifact, not cross-artifact
revision history. Acquisition `ArtifactObservation` remains distinct from extracted knowledge
observations. Metadata repair, comparison, filtering, timelines, extraction redesign, planning,
and mutation remain out of scope.
