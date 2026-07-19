# Artifact repository query service and read-only browser

TASK-018 establishes a repository-owned read surface for durable artifacts. The browser, future
Bring Repository Up to Date planner, historical retrieval, reporting, and intelligence code use
the same normalized contracts and do not traverse acquisition storage.

## Layering and contracts

```text
Authoritative acquisition state
    → ArtifactQueryService
        → ArtifactQuery / ArtifactPage / ArtifactSummary
        → ArtifactDetail
        → ArtifactContent
            → browser, future planner, reporting, analysis
```

`ArtifactQuery` supports bounded firm, canonical family/type, provider, durable-status, and
source-effective date filters; newest/oldest order; a limit from 1 through 100; and an opaque
cursor. Unknown and unsupported inputs produce structured error codes. A valid no-match query is a
successful empty page. `latest(firm, canonical_type)` and `oldest(...)` are limit-one projections
of the ordinary query path.

`ArtifactSummary` contains repository document/artifact identity, firm and canonical semantics,
normalized source-effective ordering, provider metadata, ingestion time, media type, size,
checksum, durable status, and stored-content availability. `ArtifactDetail` adds exactly one
selected immutable `ArtifactObservation`, provenance, adapter/acquisition context, profile
revision, provider-native metadata, integrity, and the separately labeled original-source
location. Selection accepts `first`, `last`, or an explicit observation ID and performs no
metadata merging. `ArtifactContent` carries only integrity-verified stored bytes and controlled
media metadata.

## Source-effective ordering

The primary value is chosen from source semantics in this order: acceptance datetime,
publication datetime, filing date, publication date, source observation time, and finally an
explicit retrieval-time fallback. Normalized values are UTC ISO timestamps. Equal primary values
use provider-neutral secondary identity (for SEC, accession), document ID, then immutable artifact
ID. Both ascending and descending sorts use that exact tuple.

One logical document is represented once. If it has multiple retained content revisions, the
current summary selects the latest ingested immutable revision for that document only. Ingestion
does not decide chronology among different documents.

## Pagination and consistency

Every page reports an authoritative-state SHA-256 snapshot digest. The opaque cursor contains the
snapshot digest, a typed-query fingerprint, and the next offset. It is size-bounded by the service
shape and validated on use. A malformed cursor returns `invalid_cursor`; changed authoritative
state returns `stale_cursor`. The browser restarts expansion rather than combining revisions.

Artifact detail separately returns an opaque artifact-local observation cursor. `next` and
`previous` bind the snapshot, document, artifact, selected observation, and position. Any
authoritative change returns `stale_cursor`; malformed, mismatched, and boundary navigation fails
explicitly.

## Tree and interaction projection

The operator console route `/artifacts` lazily expands:

```text
Firm → canonical artifact family → canonical artifact type → artifact document
```

Counts mean durable logical documents. Provider form names never define tree nodes. Leaves load in
source-effective order, 25 at a time, with Load more continuation. The desktop view is a draggable
split pane; narrow screens stack the panes. Selection fills normalized metadata and remaining
space with preview. Split and metadata-collapse preferences are disposable browser-local state.

Artifact detail defaults to the last observation. Previous/Next replaces only observation
metadata. The stored-content URL and preview remain fixed while artifact identity is unchanged.

## Content and preview boundary

`GET /api/artifacts/{document_id}/content` resolves only repository identity. It verifies exact
bytes/checksum, supports a bounded single byte range, normalizes unsupported content to
`application/octet-stream`, never exposes a filesystem path, and sets `nosniff`, no-referrer,
same-origin framing, and a restrictive CSP.

HTML and XHTML are rendered in an iframe with an empty sandbox capability list. Response CSP also
uses `sandbox; default-src 'none'`; scripts, forms, popups, top navigation, same-origin authority,
and remote subresources are unavailable. The same CSP protects Open stored document in new tab.
PDF and controlled textual media use the stored endpoint. Other binary media receive a safe
fallback and the explicit stored-document action.

The original source action is provenance convenience only. Preview and query work after restart,
with provider adapters unavailable, with network blocked, and after replay/rebuild.

## Failure semantics

Stable codes include `invalid_query`, `unsupported_filter`, `unknown_firm`,
`unknown_artifact_family`, `unknown_canonical_artifact`, `unknown_document_id`,
`unknown_observation_id`, `invalid_cursor`, `stale_cursor`, `observation_boundary`,
`repository_read_failure`, `malformed_provenance`, `missing_stored_content`, and
`checksum_mismatch`. Unsupported inline media is a successful detail/content state with a safe UI
fallback, not invented rendering.

## Limitations

Current queries scan the POC authoritative record set; performance indexing awaits measured need.
The service returns the current immutable revision of each logical document and navigates only
that artifact's observations; it is not a cross-artifact attempt-history browser. There is no
search, extraction, arbitrary metadata query, repair, mutation, annotation, or Bring Repository Up
to Date planner.
