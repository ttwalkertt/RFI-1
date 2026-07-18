# TASK-018 Engineering Guidance — Artifact Query Contract and Read Models

## Purpose

This document provides architectural guidance for TASK-018. It is not an implementation recipe and does not replace the task ticket.

The objective is to ensure that the artifact browser is built on a durable repository-owned query surface rather than on browser-specific endpoints or persistence-aware convenience functions.

The repository query service is expected to become a stable interface used by:

- the artifact browser;
- the future **Bring Repository Up to Date** planner;
- historical retrieval planning;
- exact artifact inspection;
- reporting;
- analysis and intelligence workflows.

The design should therefore favor explicit, typed, semantically stable contracts over broad or storage-shaped APIs.

## Governing Layering

```text
Authoritative repository state
        ↓
Repository-owned query service
        ↓
Normalized artifact read models
        ↓
Consumers
    ├── Artifact browser
    ├── Bring Repository Up to Date planner
    ├── Historical retrieval planner
    ├── Reporting
    └── Analysis and intelligence
```

No consumer should need to understand event-log layout, snapshot format, derived-index representation, blob paths, SEC-specific metadata layout, source-profile persistence details, or adapter internals.

The query service may use derived indexes internally, but those indexes remain rebuildable implementation details.

## Contract Design Principles

### Query by repository semantics

Primary filters should use repository-owned concepts:

- firm identity;
- canonical artifact identity;
- artifact family;
- durable repository status;
- normalized source-effective interval;
- provider identity only when semantically needed;
- repository document identity for exact lookup.

Provider-specific fields such as SEC form code or accession number remain detail metadata unless a typed provider constraint is explicitly justified.

### Separate query, summary, detail, and content

Do not return one oversized object for every use case. Distinguish:

```text
ArtifactQuery
    selects and orders artifacts

ArtifactSummary
    supports trees, lists, counts, latest lookup, and pagination

ArtifactDetail
    supports operator inspection and provenance display

ArtifactContentResponse
    serves stored immutable bytes through a separate read boundary
```

Tree expansion must not require loading full provenance or artifact bytes.

### Preserve unknown and inapplicable values

Read models should distinguish known values, unknown values, inapplicable fields, and malformed durable state.

Do not synthesize dates, titles, provider identifiers, or status values to simplify the UI. The UI may display a human-readable placeholder, but the contract must preserve the actual semantic state.

### Use source-effective ordering

“Latest” means latest according to the artifact’s source semantics, not latest retrieval or ingestion.

A normalized ordering key should be available for generic consumers. It must support:

- a primary source-effective instant or date;
- deterministic secondary ordering;
- stable final tie-breaking by immutable repository or provider identity.

For an SEC filing, semantic inputs may include acceptance datetime, filing date, and accession number. For other artifacts they may include publication time, revision time, or first-observed time. Generic consumers should not parse provider metadata to reconstruct ordering.

### Deterministic pagination

Pagination must remain stable for an unchanged repository view.

A cursor should be opaque to consumers, validated by the query service, tied to the ordering contract, bounded in size, sanitized in errors, and rejected explicitly when malformed or incompatible.

Do not use registration order, filesystem order, dictionary order, or ingestion traversal order as hidden pagination semantics.

### Explicit query bounds

The query surface should require bounded result limits and reject unreasonable requests. Representative typed fields may include:

```text
firm_ids
canonical_artifact_ids
artifact_family_ids
source_effective_from
source_effective_through
provider_ids
durable_statuses
order
limit
cursor
```

This is illustrative, not prescriptive. Do not create a text query language, SQL-like expression language, or arbitrary field-selection mechanism.

### Latest lookup is a projection of ordinary query semantics

Do not create a persistence shortcut that disagrees with normal listing order.

The future planner’s request for the newest durable artifact for firm X and canonical artifact Y should be satisfiable through the same ordering and filtering contract used by the browser, perhaps through a small convenience method delegating to the canonical query path.

The result must expose enough normalized source-effective information for a planner to apply overlap and create an explicit bounded retrieval request. The query service does not decide overlap, continuation policy, or retrieval scope.

### Tree projection is not the repository model

The tree is a UI projection:

```text
Firm
    Artifact family
        Canonical artifact type
            Artifact instance
```

The repository query service should not be distorted into a tree-only API. Tree nodes may be produced by a dedicated projection layer composing repository query and count operations.

The same query service must remain useful for tables, latest lookup, date-range retrieval, reports, analysis, and future alternate browsers.

### Counts and category nodes

Category counts should be derived through repository-owned queries or indexes. Counts must state what they represent, such as durable artifact instances, matching documents, or available stored content.

Do not combine failed acquisition attempts, duplicate candidate observations, and durable artifact instances into one unexplained number.

### Artifact identity boundaries

Keep distinct:

- repository document ID;
- canonical artifact ID;
- firm ID;
- provider ID;
- provider-native artifact ID;
- retrieval candidate ID;
- immutable content checksum;
- storage/content reference.

A URL, filename, accession number, or checksum alone is not a substitute for repository document identity.

### Summary contract guidance

An ArtifactSummary should be sufficient for tree leaves and result lists without loading full detail. It should normally expose repository document identity, firm and canonical artifact identity, family, display labels, normalized source-effective value, relevant period label, provider, provider artifact type, durable status, media type, content availability, checksum, ingestion time, and deterministic ordering data.

Avoid raw repository events, full provenance arrays, or stored bytes.

### Detail contract guidance

An ArtifactDetail should extend or reference the summary and expose complete provider identifiers, artifact-specific metadata, acquisition and adapter context where useful, source-profile revision reference, provenance locations, content size, full checksum, integrity result, stored-content availability, original-source availability, timestamps, and explicit unknown or malformed-state indicators.

Raw metadata may be offered as an advanced diagnostic field, but normalized fields remain authoritative for UI behavior.

### Content access remains separate

Stored artifact bytes must be served through a content endpoint that resolves only repository document identity, verifies content availability, rejects arbitrary paths, avoids path leakage, returns a controlled media type, sets defensive headers, supports safe new-tab viewing, and preserves read-only semantics.

The query service may return a repository-owned content link or capability indication. It should not embed large content bodies in artifact detail responses.

### Browser preview security

Externally sourced HTML is untrusted. Assume future artifacts may contain scripts, forms, navigation, trackers, malicious markup, remote-resource references, and attempts to access parent-window state.

The default HTML preview must be sandboxed without script execution, same-origin authority, form submission, popup authority, parent or top navigation, or admin-console credential access.

The stored document may still load remote subresources unless the content boundary deliberately prevents it. Codex must document the chosen behavior and implications. Do not claim a fully offline preview if remote subresources remain possible.

### Repository snapshot and consistency semantics

Codex shall identify the consistency guarantee provided during pagination and tree expansion. Acceptable models may include a fixed repository revision or snapshot token, deterministic current-state queries with explicit stale-cursor rejection, or another model consistent with the repository architecture.

The browser must not silently combine incompatible pages from materially different repository states. Do not add a heavyweight transaction system unless required.

### Read authority and integrity

The query service reports repository state; it does not repair it.

When durable state is inconsistent, missing, or corrupt, return a structured read failure or integrity state, preserve evidence, do not rewrite metadata, and allow operators to understand that an artifact exists but is not previewable where appropriate.

### Browser API shape

HTTP endpoints are presentation adapters over the repository query service. Admin handlers must not inspect repository files directly, independently compute “latest,” parse provider metadata, or create browser-specific repository semantics.

The browser API may expose tree-node, summary, detail, and content endpoints, but they should delegate to normalized service contracts.

### Scope restraint

TASK-018 should not expand into full-text search, semantic search, arbitrary metadata predicates, cross-document joins, analytical aggregations, report DSLs, user-defined saved queries, or mutation workflows.

New requirements discovered during implementation belong in BACKLOG.md unless necessary to satisfy the ticket.

## Required Architectural Evidence

The review package should include type or schema definitions, query examples, summary examples, detail examples, ordering examples, pagination examples, latest-artifact proof, source-effective versus ingestion-time proof, tree projection mapping, content endpoint boundary, preview sandbox policy, consistency or snapshot semantics, replay and rebuild equivalence, and known limitations.

## Decision Standard

A successful implementation should make this statement true:

> Any future component that needs to locate, list, order, inspect, or open durable artifacts can do so through repository-owned read contracts without learning how repository state is physically stored or how a particular provider represents its documents.
