# Agent-legible RFI MCP surface design

Status: accepted design for a bounded experiment; no MCP implementation exists

Task: TASK-072

Decision date: 2026-08-09

## Design disposition

**Proceed with MCP experiment.**

RFI has enough real repository and transcript-access capability to justify a bounded MCP
experiment, but the experiment must not be a direct wrapper around TASK-071. The first
implementation slice must close three evidence-access correctness gaps as part of the slice:

1. exact content must be addressable by immutable `artifact_id`, not only by a mutable current
   `document_id` projection;
2. transcript access must expose a named access generation, health, applied bounds, typed outcomes,
   and stale-generation behavior; and
3. schema/data-dictionary discovery must be separate from one instance-specific corpus response.

Those are small repository/access corrections, not investigative machinery. The experiment should
then expose governed catalog query, transcript candidate search, stable resources for repository
objects and exact segments, and bounded exact-byte reads. Codex Work or another capable runtime
must own the question, plan, query reformulation, counterevidence search, context allocation,
stopping, sufficiency judgment, synthesis, and report construction.

The principal risks are lexical recall, incomplete retained coverage, missing transcript speaker
and historical event-kind metadata, client support for resource discovery, and accidentally
turning access diagnostics into investigative advice. The hypothesis is weakened if an unfamiliar
capable runtime, after reading the proposed dictionary and capability records, still needs a large
RFI-specific procedural prompt or question-specific convenience tools to use correct evidence; if
it routinely treats successful empty searches as proof of corpus absence; or if it cannot produce
support quality comparable to TASK-071 despite correct and complete MCP responses.

## 1. Question answered

The smallest semantically rich surface is not one universal `search` function and not the four
TASK-071 model tools copied into MCP. It is a small common evidence envelope, addressable repository
resources, a live capability registry, governed selection tools, and evidence-type-specific access
extensions:

```text
descriptive resources
    server/repository identity
    versioned data dictionary
    live capability and health registry

common addressable resources
    logical document projection
    immutable artifact
    immutable acquisition observation

governed tools
    bounded artifact query
    bounded artifact history query
    bounded exact artifact-byte read

transcript extension
    parameterized transcript-corpus view
    lexical/temporal segment search tool
    exact verified transcript-segment resource
    bounded ordered document-segment view
```

This is rich because identity, authority, provenance, time, integrity, query semantics, bounds,
coverage, and exact evidence remain explicit. It is procedurally weak because none of these
capabilities selects an investigative question, hypothesis, next step, stopping rule, citation,
conclusion, or report structure.

The architecture should support other evidence types through their own justified extensions—for
example mailing-list discussion traversal or knowledge-version navigation—rather than flattening
all retained objects into transcript paragraphs or a generic graph/query language.

## 2. Review method and implementation evidence

This design was grounded in current code, tests, and the retained Seagate proving records. It did
not infer the interface from TASK-071 prose alone. The inspected implementation included:

- `rfi.artifacts.contracts` and `ArtifactQueryService`, including query validation, snapshot-bound
  pagination, normalized summary/detail projections, observation cursors, and content integrity
  reads;
- `AcquisitionRepository` artifact, observation, attempt, source, revision, and exact-byte reads;
- transcript classification and interval-coverage contracts;
- `TranscriptKnowledgeAccess` index construction, corpus description, FTS5 search, segment
  identities, exact expansion, bounded document inspection, schemas, and dispatch behavior;
- `TranscriptInvestigator` only to separate harness responsibilities from access semantics;
- the source-object, knowledge, retrieval/evidence-package, mailing-list, feed, and stream public
  contracts;
- TASK-018, TASK-005/006, and TASK-071 tests; and
- all five retained-corpus TASK-071 traces and the 21-document Seagate corpus description.

Important implementation findings are:

1. `ArtifactQueryService.query()` is a useful public catalog contract. It exposes typed filters,
   normalized source-effective time, deterministic order, a repository revision, total count,
   bounded diagnostics, and stale cursors.
2. `ArtifactQueryService.detail()` exposes one selected observation only for the current artifact
   revision of a logical document. Its next/previous cursors navigate observations of that current
   artifact, not the document's earlier content revisions.
3. `ArtifactQueryService.content(document_id)` verifies exact bytes, but resolves through the
   document's current artifact. `AcquisitionRepository.read_artifact(artifact_id)` can read the
   immutable artifact directly, but that semantic is not exposed by the normalized artifact read
   service.
4. `ArtifactDetail.content_integrity` is set to `verified` when artifact metadata is present; the
   actual checksum verification occurs later in `content()`. MCP must not repeat that label as if
   the bytes had already been read and verified.
5. `TranscriptKnowledgeAccess` is a useful evidence-type-specific prototype. It creates stable
   segment IDs from artifact ID, exact byte range, and range digest; supports lexical and temporal
   selection; separates compact hits from exact expansion; and reports real metadata gaps.
6. The transcript access object records the artifact-query snapshot at build time but does not
   enforce it on later calls. Expansion re-reads by `document_id`, so a later document revision can
   cause the returned bytes to differ from the artifact identity embedded in the segment.
7. The transcript build stops at 100 documents, drops `ArtifactPage.diagnostics`, fails the whole
   build on one unsegmentable retained document, and has no externally visible generation health.
8. Search counts every FTS match, fetches at most 200 ranked rows internally, applies per-document
   diversity, and returns at most 12 hits. The response reports final truncation but not every
   applied bound separately.
9. `ResearchError` is an untyped exception. TASK-071's harness turns many failures into an ordinary
   `{"error": "..."}` result, while special invalid-identifier warnings are implemented in the
   harness rather than the access layer. Copying that behavior would make diagnostic attribution
   unreliable.
10. Corpus coverage is a conservative prose caveat, not a queryable repository coverage ledger.
    Acquisition does have explicit complete/incomplete/indeterminate interval outcomes, but the
    artifact and transcript read contracts do not aggregate them into retained-corpus coverage.
11. Historical Seagate transcript bytes lack speaker labels and observations lack event-kind
    diagnostics. All 21 selected documents are canonically `earnings_transcript`, even though
    titles include conferences and investor events. MCP must expose the conflict, not repair it.

These findings are the reason the proposal is not `describe_corpus`, `search_transcripts`,
`expand_segments`, and `inspect_document` renamed as MCP calls.

## 3. Governing responsibility boundary

| Concern | RFI / MCP | Investigative runtime |
| --- | --- | --- |
| Retained bytes, checksum, artifact identity | Owns and verifies | Consumes; never redefines |
| Logical document and canonical association | Owns | Uses as scope/context |
| Observation and provenance facts | Owns | Inspects and cites as needed |
| Source-effective time and its basis | Normalizes and labels | Chooses comparison periods |
| Deterministic classification and metadata | Owns with basis/gaps | Does not silently repair |
| Segment/index generation | Builds, identifies, bounds, reports health | Chooses whether/how to search |
| Query filters, orderings, cursors, counts | Defines and executes | Selects query strategy |
| Exact passage expansion | Resolves and verifies | Chooses candidates/context |
| Coverage and omission facts | Reports only what repository contracts establish | Decides what those facts permit answering |
| Question interpretation and decomposition | Does not own | Owns |
| Hypotheses and counterevidence strategy | Does not own | Owns |
| Context/token/tool-call management | Server applies only per-call safety bounds | Owns investigation-wide budgets |
| Stopping and sufficiency | Does not own | Owns |
| Claim admission and synthesis | Does not own | Owns |
| Report construction and persistence | Does not own in this task | Owns outside retained truth |
| MCP/request instrumentation | Records access facts and outcome | Correlates with runtime trace |

RFI may say that a search completed against generation X, matched zero indexed segments, and was
bounded in specified ways. It may not say that the investigator has searched enough or that the
question is unanswerable.

## 4. Current capability inventory

| Current capability | Public contract and implementation | MCP relevance | Current limits |
| --- | --- | --- | --- |
| Artifact catalog query | `ArtifactQuery`, `ArtifactPage`, `ArtifactSummary`; `ArtifactQueryService.query()` | Core governed selection; substantially reusable | No arbitrary text search; unknown firm filter currently behaves as a successful empty query; diagnostics are capped without a truncation flag |
| Source-effective ordering | `SourceEffectiveOrder`; `ArtifactQueryService._effective()` | Core temporal semantics | Some bases are fallbacks; title/basis authority is not uniformly described |
| Current document detail | `ArtifactDetail`, `ArtifactObservation`; `detail()` | Document and selected-observation resources | Current artifact only; no normalized document-revision history |
| Observation navigation | `detail(first/last/id)`, `next()`, `previous()` | Provenance/history input | Cursor-shaped navigation is awkward for external query; no direct observation lookup contract |
| Exact document content | `ArtifactContent`; `content(document_id)` | Exact evidence | Resolves current document revision, not immutable artifact ID |
| Exact immutable artifact bytes | `AcquisitionRepository.read_artifact(artifact_id)` | Required authority primitive | Exists below the preferred normalized read boundary; needs semantic promotion/adaptation |
| Artifact diagnostics | `ArtifactReadDiagnostic`; `diagnostics()` and query page | Failure attribution | Limited to 100 without `diagnostics_truncated`; malformed records are omitted from summaries |
| Acquisition coverage | `IntervalCoverage`, interval outcome receipts | Coverage semantics | Not aggregated into a current retained-corpus coverage view |
| Transcript classification | `classify_transcript_event()` and retained diagnostics | Canonical type/event-kind semantics | Historical artifacts predate event-kind retention; canonical history is append-only |
| Transcript corpus orientation | `CorpusDescription`, `describe_corpus()` | Basis for a parameterized view | Mixes schema dictionary with one instance, has hard-coded caveats, and hides several document fields in dispatch |
| Transcript lexical/temporal search | `SearchResult`; `TranscriptKnowledgeAccess.search()` | Evidence-specific query extension | Process-local FTS5, maximum 100 documents, 200 internal rows, 12 results, no generation health or cursor |
| Transcript exact segment locator | `TranscriptSegment`, `EvidenceExcerpt`, `expand()` | Excellent resource identity pattern | Expansion is document-addressed and not stale-generation-safe; error is untyped |
| Transcript ordered window | `inspect_document()` | Parameterized document-segment view | In-memory text is not reverified during read; maximum five segments |
| Source objects | `SourceObjectReader`, stable artifact/span/digest locators, bounded context | Future structural evidence extension | SEC SGML/header only; independent POC lifecycle; not transcript-capable |
| Versioned derived knowledge | `KnowledgeReader`, `DerivedObject`, provenance, status/confidence | Future knowledge resource extension | Narrow ontology and independent POC generation; not product-composed |
| Governed retrieval | `RetrievalQuery`, `RetrievalResponse`, `RetrievalTrace`, `EvidencePackage`, health | Future query/evidence extension | SEC POC corpus, deterministic hashing vectors, separate lifecycle, no transcript body index |
| Mailing-list query | `MailingListQueryService` discussion/message/search/incomplete/content contracts | Future relationship-rich extension | Domain-specific identity, tombstones, connectivity and projection health must be retained |
| Feed observations | `FeedRepository` entry/tombstone/fulfillment/run reads | Future observation/negative-evidence extension | Public reads are repository/service-specific dict projections; summary text is not exact full evidence |
| Stream memberships | `StreamService`/repository revision, run, membership, lineage reads | Future scoped-corpus and lineage extension | Membership is selection authority, not artifact content authority |
| Intelligence and reports | TASK-007 contracts and TASK-071 harness/report types | Explicitly outside MCP substrate | Non-authoritative analysis; exposing them would blur the target experiment |

The inventory supports a common evidence envelope, not one universal object grammar. Artifact,
mail, feed, stream, source-object, knowledge, and transcript extensions retain different semantics.

## 5. MCP primitive selection

### Resources

Resources suit known, addressable things whose identity matters independently of the operation that
found them: server/dictionary records, logical documents, immutable artifacts, observations, and
exact transcript segments. Resource content may change only where the URI intentionally denotes a
current projection, such as a logical document. Immutable artifact, observation, and segment URIs
must continue to resolve to the same authority and bytes.

### Resource templates

Templates suit parameterized but still addressable repository views: one transcript corpus and one
bounded ordered segment window. The URI must encode all parameters that materially change the
representation. Results identify repository snapshot and access generation.

### Tools

Tools suit selection and bounded computation: filtered artifact query, typed history query,
lexical segment search, and exact byte-range read. They return candidates or repository facts; they
do not decide investigative actions.

### Prompts

RFI should expose **no MCP prompts** in the first experiment. A prompt such as “investigate this
company,” “find support and counterevidence,” or “write a report” would import investigative
procedure into the repository boundary. Evidence-handling rules belong in tool/resource
descriptions and the data dictionary, not in a large RFI-specific workflow prompt. If a later
experiment demonstrates a client-discovery defect that only an MCP prompt can address, that is
evidence against the present agent-legibility design and should be reviewed explicitly.

### Inappropriate exposure

Do not expose SQLite/SQL, content-store paths, repository event tables, provider adapters,
acquisition mutation, TASK-071 model/harness state, adjudication, recovery work orders, report
emission, raw internal index rows, vector implementation parameters, or arbitrary Python method
dispatch.

## 6. Common representation contract

Every JSON resource and tool result uses a versioned envelope. MCP transport errors remain MCP
errors; RFI domain details use a stable nested record.

```json
{
  "schema_version": "rfi.mcp.v1alpha1",
  "request_id": "mcp-request-...",
  "repository_snapshot": "sqlite-revision-8237",
  "access_generation": {
    "capability_id": "transcript.lexical.v1",
    "generation_id": "transcript-access-...",
    "authority_snapshot": "sqlite-revision-8237",
    "health": "ready"
  },
  "outcome": "ok",
  "data": {},
  "page": {
    "limit": 25,
    "returned": 21,
    "total_matching": 21,
    "next_cursor": null,
    "truncated": false,
    "bounds_applied": []
  },
  "coverage": {
    "scope": {},
    "state": "indeterminate",
    "basis": "retained inventory only",
    "notes": []
  },
  "diagnostics": [],
  "links": []
}
```

Fields not relevant to a response may be absent; their semantics may not silently change.

`outcome` is one of `ok`, `empty`, or `partial`. `empty` is a successful, fully executed query with
no match under the declared query semantics. `partial` means usable data is returned with named
omissions or access bounds; it never disguises a repository failure. Errors do not use `empty`.

Every evidence-bearing object includes:

- stable repository or deterministic locator identity;
- `authority_class`: `source_evidence`, `repository_metadata`, `deterministic_derived_metadata`,
  `versioned_derived_knowledge`, or `access_projection`;
- authoritative identity links (`document_id`, `artifact_id`, observation where applicable);
- source-effective and observation/build time in separate fields;
- integrity status and what was actually verified;
- typed provenance links;
- the dictionary type/schema URI; and
- candidate-versus-exact-evidence status.

Search scores, snippets, ranks, counts, metadata-gap summaries, and index generations are derived.
Exact bytes, artifact checksum, artifact identity, immutable observation, governed canonical
association, and retained metadata are authoritative. Normalized time/title/classification fields
must carry a `basis` and may not obscure fallback or missing state.

## 7. Proposed descriptive resources

### 7.1 `rfi://about`

- **Primitive/name:** static resource, `rfi://about`.
- **Purpose/use:** first-contact identity: server schema version, read-only status, repository
  identity/snapshot, deployment mode, and links to dictionary/capabilities. An agent verifies that
  it is using RFI retained truth rather than an analytical service.
- **Input/URI:** no parameters.
- **Result:** common envelope plus server build, repository authority statement, snapshot kind,
  supported schema versions, and resource links.
- **Authority:** repository snapshot/build identity is repository metadata; descriptions are
  versioned interface metadata.
- **Underlying contract:** `AcquisitionRepository.repository_revision()` plus application build
  identity; thin adaptation.
- **Failure:** `repository_read_failure` if snapshot cannot be read; never an empty resource.
- **Bounds:** small fixed document.
- **Traceability:** request ID, snapshot, build identity.
- **Why RFI:** only RFI can state which repository authority and contract version the server
  represents.

### 7.2 `rfi://dictionary`

- **Primitive/name:** static descriptive resource, `rfi://dictionary`.
- **Purpose/use:** versioned model-facing definitions for retained object types, identity domains,
  authority classes, artifact/document distinction, provenance, time, transcript classification,
  relationships, coverage, integrity, candidate/exact evidence, filters, ordering, and bounds.
- **Input/URI:** no parameters; optional future versioned URI may be linked from this current URI.
- **Result:** type definitions, field definitions, enumerations, examples, and links to live
  capabilities. It describes semantics, not a particular Seagate corpus.
- **Authority:** interface/governance metadata; it does not become source evidence.
- **Underlying contract:** artifact/research/source-object/knowledge/retrieval dataclasses and the
  canonical acquisition template. A new explicit dictionary assembly contract is missing.
- **Failure:** `dictionary_unavailable` is a server/configuration failure and blocks agent-legible
  operation.
- **Bounds:** fixed, versioned, expected to fit one resource read; split by linked type resources
  only if measured size requires it.
- **Traceability:** schema version and content digest.
- **Why RFI:** field authority and identity semantics are repository contracts, not knowledge the
  runtime should infer from examples.

### 7.3 `rfi://capabilities`

- **Primitive/name:** live descriptive resource, `rfi://capabilities`.
- **Purpose/use:** discover what can be queried now, relevant filters/orderings, result/resource
  types, bounds, access health, generation identity, and unavailable/deferred capabilities.
- **Input/URI:** no parameters.
- **Result:** ordered capability records with `capability_id`, version, description, status
  (`ready`, `unavailable`, `stale`, `corrupt`, `deferred`), authority inputs, result types, tool or
  resource names, filters, orders, bounds, repository snapshot, access generation, diagnostics,
  and dictionary links.
- **Authority:** capability registration and health are RFI access metadata; not source evidence.
- **Underlying contract:** `RetrievalHealth` is a useful precedent; no common capability registry
  exists. Missing repository/IQA capability.
- **Failure:** repository can still expose a capability as unavailable with a typed reason; failure
  to build the registry is `capability_registry_failure`.
- **Bounds:** fixed registry; future pagination only after demonstrated need.
- **Traceability:** snapshot, generation, implementation identity, health timestamp.
- **Why RFI:** the access layer alone knows what was built, against which authority, with which
  bounds and health.

## 8. Proposed addressable resource templates

### 8.1 `rfi://documents/{document_id}`

- **Primitive/name:** resource template, logical document projection.
- **Purpose/use:** inspect canonical document identity, current artifact revision, governed
  association, normalized time with basis, selected observation, metadata gaps, and links.
- **Input/URI:** validated repository `document_id` only.
- **Result:** normalized `ArtifactSummary` and current `ArtifactDetail`, with explicit
  `projection_kind=current_document`, `current_artifact_id`, selected observation URI, content
  capability, and history-tool link.
- **Authority:** document/canonical association and retained observation fields are authoritative;
  display title and normalized source-effective values are deterministic projections with basis;
  “current artifact” is a snapshot-relative projection.
- **Underlying contract:** `ArtifactQueryService.detail()`; thin adaptation plus corrected
  integrity wording.
- **Failure:** `unknown_object`, `repository_read_failure`, `malformed_provenance`, or visible
  partial diagnostics. Unknown is not an empty resource.
- **Bounds:** one document; provider metadata remains bounded/sanitized.
- **Traceability:** repository snapshot, artifact/observation IDs, source and provenance URIs.
- **Why RFI:** logical identity and current revision selection are repository semantics.

### 8.2 `rfi://artifacts/{artifact_id}`

- **Primitive/name:** resource template, immutable artifact envelope.
- **Purpose/use:** resolve the immutable identity used by citations independent of later logical
  document revision.
- **Input/URI:** validated `artifact_id`.
- **Result:** artifact checksum, size, controlled media type, actual integrity-read state, known
  document/observation links, exact-byte tool link, and authority labels. It does not embed large
  content.
- **Authority:** identity, checksum, size, media type, and exact content are source-evidence
  authority; associations are repository facts.
- **Underlying contract:** acquisition artifact metadata and `read_artifact()` exist; a normalized
  artifact-ID lookup is missing from `ArtifactQueryService`.
- **Failure:** `unknown_object`, `exact_evidence_unavailable`, `integrity_failure`, or
  `repository_read_failure`.
- **Bounds:** one artifact metadata record; association links may be paged through history query.
- **Traceability:** immutable checksum and all returned repository relations.
- **Why RFI:** a runtime must not guess that a document URL or current document projection is the
  immutable cited object.

### 8.3 `rfi://observations/{observation_id}`

- **Primitive/name:** resource template, immutable acquisition observation.
- **Purpose/use:** inspect where, when, how, and under which governed source an artifact was
  observed, including retained diagnostics and provider identifiers without treating them as
  canonical identity.
- **Input/URI:** validated `observation_id`.
- **Result:** normalized `ArtifactObservation`, document/artifact/source links, provenance
  locations and roles, canonical association observed at retention, and malformed fields.
- **Authority:** observation, source, attempt, diagnostics, and provenance are authoritative
  retained metadata; display labels are derived.
- **Underlying contract:** `ArtifactObservation` exists, but public direct lookup does not.
  Existing capability requires semantic cleanup/history adapter.
- **Failure:** `unknown_object`, `provenance_unavailable`, `provenance_malformed`, or repository
  failure; malformed provenance must remain distinguishable from absence.
- **Bounds:** one observation; large diagnostic values are subject to named field-size bounds and
  produce `partial` with paths, never silent truncation.
- **Traceability:** links to immutable artifact, logical document, source, and acquisition attempt.
- **Why RFI:** provenance and provider/canonical distinction are repository semantics.

### 8.4 Transcript corpus view

- **Primitive/name:** resource template,
  `rfi://transcript-corpora/{firm_id}?from={date}&through={date}&types={type-list}&cursor={cursor}&limit={limit}`.
- **Purpose/use:** orient to one retained transcript corpus and its access quality without forcing
  an agent to receive every document in one tool response.
- **Input/URI:** firm, canonical transcript types, optional closed date bounds, order/cursor, and
  limit 1–100. Defaults are declared in the template schema, not hidden.
- **Result:** scope echo, page of `TranscriptDocument` projections and resource links, corpus/date
  counts, metadata-gap counts, coverage facts, diagnostics, repository snapshot, and transcript
  access generation/health.
- **Authority:** document/artifact/type/retained metadata are authoritative; segment counts,
  metadata-gap aggregations, title conflict notices, and access health are derived.
- **Underlying contract:** `ArtifactQueryService.query()` and `describe_corpus()`; existing
  capability requires separation of schema from instance and explicit generation semantics.
- **Failure:** invalid scope, unknown firm, unavailable/stale/corrupt transcript access, partial
  corpus due isolated document diagnostics, or repository read failure. A corpus with zero
  documents is a successful empty view.
- **Bounds:** query page and named build/index bounds; no hard unreported 100-document failure.
- **Traceability:** every item links to document/artifact; view records snapshot and generation.
- **Why RFI:** corpus membership, retained metadata quality, and index health are access facts;
  deciding whether that corpus can answer a question remains with the runtime.

### 8.5 `rfi://transcript-segments/{segment_id}`

- **Primitive/name:** resource template, exact verified transcript segment.
- **Purpose/use:** convert a search candidate into citable exact retained evidence.
- **Input/URI:** stable deterministic segment ID returned by transcript search/window resources.
- **Result:** artifact/document IDs, ordinal, exact half-open byte span, segment digest, exact text,
  source-effective time with basis, title with basis, canonical type, event-kind status, optional
  speaker label, observation/provenance links, verification timestamp, snapshot/generation, and
  `evidence_state=exact_verified`.
- **Authority:** text is exact source evidence; artifact ID/checksum and canonical association are
  authoritative; locator/ordinal are deterministic derived metadata; rank/snippet are absent.
- **Underlying contract:** `TranscriptSegment`/`EvidenceExcerpt` and artifact byte reads. Requires
  artifact-ID read and re-verification at resource-read time.
- **Failure:** unknown segment, unavailable/stale/corrupt access generation, exact evidence
  unavailable, span/digest mismatch, provenance malformed, or repository failure.
- **Bounds:** one segment. It is not expanded to neighbors implicitly.
- **Traceability:** artifact checksum, range checksum, document/artifact/observation URIs, access
  generation.
- **Why RFI:** only the repository/access layer can prove that returned text is the exact retained
  span identified by the candidate.

### 8.6 Ordered transcript document window

- **Primitive/name:** resource template,
  `rfi://transcript-documents/{document_id}/segments?start={ordinal}&count={count}`.
- **Purpose/use:** inspect local ordered context when a lexical hit or exact segment is ambiguous.
- **Input/URI:** document ID, 1-based start ordinal, count 1–20; optional generation ID only when
  the client wants fail-on-generation-change behavior.
- **Result:** ordered exact segment links plus compact text and locators, preceding/following
  availability, document size/count, snapshot/generation, and bounds.
- **Authority:** text must be reverified against artifact bytes; window/ordinal are deterministic
  access projections.
- **Underlying contract:** `inspect_document()`; semantic cleanup required for artifact-ID
  verification and typed stale behavior.
- **Failure:** invalid range, unknown document, stale generation, exact-evidence/integrity failure,
  or successful empty only when `start` is beyond the known segment count and the contract
  explicitly permits that form.
- **Bounds:** maximum 20 segments and named response-byte cap; returns links for further exact read.
- **Traceability:** current document/artifact identity and each segment URI/digest.
- **Why RFI:** deterministic segmentation and byte-locator integrity belong to the evidence-type
  access layer; deciding which window to inspect belongs to the runtime.

## 9. Proposed tool catalog

### 9.1 `query_artifacts`

- **Primitive/name:** MCP tool, `query_artifacts`.
- **Purpose/use:** select retained logical documents using governed repository semantics.
- **Input schema:** arrays of `firm_ids`, `family_ids`, `canonical_artifact_ids`, `provider_ids`,
  `association_kinds`; `durable_statuses`; optional `source_effective_from/through`; `order` in
  `newest|oldest`; `limit` 1–100; opaque `cursor`.
- **Result:** common envelope containing compact summaries and document/artifact resource URIs,
  total match count, next cursor, repository diagnostics, applied filters/order, and coverage.
- **Authority:** mirrors `ArtifactSummary` authority/basis distinctions; page/order are derived.
- **Underlying contract:** directly reusable `ArtifactQueryService.query()` with thin JSON/MCP
  adaptation and diagnostic-bound cleanup.
- **Failure/empty:** invalid query, unknown type/family, unsupported filter, invalid/stale cursor,
  repository failure, or successful `empty`. Unknown firm behavior must be documented and made
  consistent before experiment.
- **Bounds:** existing limit/cursor; diagnostics report returned/total-or-unknown/truncated.
- **Traceability:** snapshot, normalized query digest, resource links.
- **Why RFI:** canonical filtering and source-effective order cannot be reimplemented safely by a
  generic runtime.

Representative input:

```json
{
  "firm_ids": ["seagate"],
  "family_ids": [],
  "canonical_artifact_ids": ["earnings_transcript", "management_transcript"],
  "provider_ids": [],
  "association_kinds": ["firm-canonical"],
  "durable_statuses": ["durable"],
  "source_effective_from": null,
  "source_effective_through": null,
  "order": "oldest",
  "limit": 25,
  "cursor": null
}
```

### 9.2 `query_artifact_history`

- **Primitive/name:** MCP tool, `query_artifact_history`.
- **Purpose/use:** inspect typed document-to-artifact revisions and artifact-to-observation history
  without exposing event tables or requiring cursor-by-cursor observation navigation.
- **Input schema:** exactly one of `document_id` or `artifact_id`; optional
  `include_observations` and `include_attempt_summaries`; `order=oldest|newest`; limit 1–50; cursor.
- **Result:** typed relationships (`document_revision`, `artifact_observation`,
  `observation_attempt`, `governed_source`) with object URIs, immutable IDs, times, status,
  canonical association at observation, pagination, and diagnostics.
- **Authority:** relationships and observation facts are repository metadata; current-selection and
  display fields are derived.
- **Underlying contract:** acquisition repository retains the records, and artifact detail exposes
  a narrow slice. A normalized public history contract is missing.
- **Failure/empty:** invalid mutually exclusive input, unknown object, unavailable/malformed
  provenance, invalid/stale cursor, or repository failure. A known artifact with no optional
  attempt detail is a successful partial result, not unknown.
- **Bounds:** 50 relationship records/page; diagnostic payload summaries are bounded by name.
- **Traceability:** every edge identifies both endpoints, basis, snapshot, and resource URIs.
- **Why RFI:** document revision and acquisition-observation meaning is repository-specific and
  must not be reconstructed from raw rows by the runtime.

This tool is in the target surface but may be deferred from the first Seagate experiment if the
selected observation resource and document/artifact links are sufficient. Its absence must be
declared in `rfi://capabilities`.

### 9.3 `search_transcript_segments`

- **Primitive/name:** MCP tool, `search_transcript_segments`.
- **Purpose/use:** return compact lexical candidates over the declared retained transcript scope.
- **Input schema:** nonblank `query`; `match=any|all`; `order=relevance|oldest|latest`;
  `firm_ids`; canonical transcript types; optional date bounds and document IDs; `limit` 1–50;
  `max_per_document` 1–10; opaque cursor if the chosen index can support stable pagination.
- **Result:** normalized terms; compact hits with segment/document/artifact URIs, event date and
  basis, type, ordinal, score/rank basis, non-citable snippet; total matches; all applied bounds;
  coverage note; snapshot/access generation and health.
- **Authority:** hit identity and retained metadata link to authority; segment ID/score/snippet are
  deterministic access projections and marked `candidate_only`.
- **Underlying contract:** `TranscriptKnowledgeAccess.search()` is reusable in concept and current
  FTS implementation; its external semantics require typed error, generation, scope, and bound
  cleanup.
- **Failure/empty:** invalid query, unknown document, unsupported ordering/filter, access index
  unavailable/stale/corrupt, repository failure, or successful empty. Empty states that only the
  declared lexical expression matched no indexed segment.
- **Bounds:** report FTS match count, internal candidate cap, diversity cap, response limit,
  pagination state, and truncation separately.
- **Traceability:** query digest, normalized query, generation, snapshot, and exact segment URIs.
- **Why RFI:** tokenization, segment membership, temporal ordering, filters, index health, and
  locator integrity are governed access semantics. Choosing terms and interpreting hits are not.

### 9.4 `read_artifact_bytes`

- **Primitive/name:** MCP tool, `read_artifact_bytes`.
- **Purpose/use:** obtain a bounded exact byte range when no evidence-type resource offers a
  richer structural view or when independently verifying a locator.
- **Input schema:** `artifact_id`; nonnegative `byte_start`; exclusive `byte_end`; optional
  `decode=text|base64|both`; maximum range advertised by capability (recommended 64 KiB initially).
- **Result:** artifact checksum/media type/size, requested range, exact base64 bytes, optional UTF-8
  replacement-decoded inspection text clearly labeled as a rendering, range checksum,
  `complete_for_requested_range=true`, and artifact resource URI.
- **Authority:** bytes are exact source evidence; decoded text is a derived rendering.
- **Underlying contract:** `AcquisitionRepository.read_artifact()` and artifact metadata; requires
  normalized service promotion and range validation.
- **Failure/empty:** invalid range, unknown artifact, named range bound exceeded, exact evidence
  unavailable, checksum mismatch, unsupported decode, or repository failure. A zero-length range
  is invalid rather than misleadingly empty.
- **Bounds:** maximum range and maximum encoded output are explicit; tool never silently clips.
- **Traceability:** whole-artifact and range digests plus immutable resource URI.
- **Why RFI:** exact-byte verification and artifact identity are repository authority. A generic
  runtime must not open storage paths.

## 10. Data dictionary and discoverability design

Tool descriptions should be concise and operational: what the operation returns, why candidates
are not exact evidence, and where exact resources live. JSON input schemas carry types, required
fields, enums, bounds, and mutual-exclusion constraints where expressible. They should not contain
investigative strategy.

The dictionary resource carries the deeper, reusable semantics:

| Topic | Required dictionary statement |
| --- | --- |
| Retained object types | Artifact, logical document, observation, acquisition attempt, governed source, transcript segment, source object, derived object, stream membership, tombstone |
| Canonical identity | Repository IDs are distinct domains; provider IDs, URLs, checksums, and filenames do not substitute for logical document identity |
| Artifact vs document | Artifact is immutable exact content; document is a logical identity whose current artifact projection may change |
| Authoritative metadata | Retained canonical association, observation, source, exact bytes/checksum and retained diagnostics are repository facts |
| Deterministic derived metadata | Normalized date/title, segment locator, counts, rank, snippets, gap summaries and current projections include basis and generation |
| Provenance | Locations and provider identifiers describe origin/discovery; they do not define repository identity; malformed/unavailable are separate states |
| Temporal semantics | Source-effective, observation, ingestion, retrieval, and index-build times remain distinct; source-effective includes a named basis |
| Transcript classification | Canonical artifact type is authoritative append-only history; event kind is deterministic metadata when retained and may be absent; title conflict does not authorize relabeling |
| Relationships | Typed endpoints and relation meaning; membership/selection/derivation relationships do not transfer artifact content authority |
| Query/index semantics | Tokenizer/index identity, `any/all`, order semantics, constraints, health, generation, snapshot, and candidate status |
| Exact content | Search snippets and in-memory text are not exact evidence until verified against immutable artifact bytes |
| Completeness/insufficiency | Successful empty, query completeness, index coverage, retained corpus coverage, and answer sufficiency are different concepts; RFI does not decide the last |
| Filters/order | Per-capability allowlist, date interval convention, stable tie-breakers, and unsupported-filter behavior |
| Bounds | Every hard/soft cap, cursor behavior, truncation flag, and retry/expansion path |

The capability registry carries changing facts: which extensions are ready, generation health,
current maximums, and transport/server limits. Instance resources carry actual gaps and basis. This
separation prevents one giant corpus response from becoming both documentation and data.

All query hits should include resource URIs. An unfamiliar agent can therefore move from selection
to inspection without constructing opaque IDs or memorizing URI formats. Invalid-ID errors may
include a bounded correction hint or relevant resource link, but not the full universe of valid
IDs when that would be excessive.

## 11. Failure and insufficiency taxonomy

| Category | Stable code | MCP/result treatment | Evidence implication |
| --- | --- | --- | --- |
| Invalid request | `invalid_request`, `invalid_range`, `invalid_cursor` | MCP tool/resource error with machine record | Call was not executed correctly; says nothing about evidence |
| Unknown object | `unknown_object` plus object type | Error | Requested identity is not visible in the declared snapshot; not a corpus-wide absence claim |
| Successful no match | `outcome=empty`, no error | Successful result | No match under exact filters/query/index generation |
| Unsupported query | `unsupported_filter`, `unsupported_order`, `unsupported_query` | Error | Capability cannot evaluate request; not evidence absence |
| Derived index unavailable | `access_unavailable` | Error; retryable only if build can become ready | No search result was produced |
| Derived index stale | `access_stale` | Error with authority/access generations | Rebuild/restart needed; old result must not be mixed |
| Derived index corrupt | `access_corrupt` | Fail closed | No trustworthy result |
| Incomplete coverage | `coverage_incomplete` | Successful/partial data with coverage record | Retained inventory or access does not span declared scope |
| Indeterminate coverage | `coverage_indeterminate` | Successful data with coverage record | Repository cannot establish completeness |
| Exact evidence unavailable | `exact_evidence_unavailable` | Error for exact resource/read; candidate remains non-citable | Evidence identity may exist but bytes were not supplied |
| Integrity failure | `integrity_failure` | Fail closed, non-retryable until repair | Returned bytes must not be used |
| Provenance unavailable | `provenance_unavailable` | Partial only where evidence bytes remain valid and limitation is explicit | Content may be exact; origin cannot be fully inspected |
| Provenance malformed | `provenance_malformed` | Error or partial based on requested operation | Repository-authority defect, not evidence absence |
| Named bound | `result_truncated_by_bound` or `page.truncated=true` | Successful partial/page with exact bound | More matching/indexed material exists or was not evaluated |
| Stale page | `stale_cursor` | Error with restart instruction | Pages must not be combined across revisions |
| Repository failure | `repository_read_failure` | Error | No absence inference permitted |
| Access adapter failure | `mcp_adapter_failure` | Error with request/capability correlation | Repository may still contain relevant evidence |

Errors include `category`, `code`, sanitized `message`, `retryable`, `evidence_implication`,
`remediation`, request ID, repository snapshot if known, access generation if relevant, and bounded
details. `evidence_implication` is semantic diagnosis, not investigative advice—for example, “this
request failure is not a no-match result.”

The server must never turn `access_unavailable`, `repository_read_failure`, or `integrity_failure`
into an empty item list. Conversely, a valid lexical zero-match must not be raised as a server
failure.

## 12. Seagate validation walkthrough

The retained proving corpus at the inspected snapshot has 21 documents, 2,268 transcript
segments, source-effective dates from 2024-09-04 through 2026-07-28, canonical type
`earnings_transcript` for every document, no retained event-kind diagnostic, and no retained
speaker labels. Titles include conference and investor events. Coverage does not prove that every
management event was acquired.

### 12.1 Orient and discover the corpus

1. The runtime reads `rfi://about`, `rfi://dictionary`, and `rfi://capabilities`.
2. It learns that transcript lexical access is ready against a named snapshot/generation; that
   snippets are candidates; and that exact segment resources are citable source evidence.
3. It calls `query_artifacts` for firm `seagate`, canonical types `earnings_transcript` and
   `management_transcript`, oldest order, limit 25.
4. It may also read the transcript corpus view to obtain segment availability and aggregated
   metadata gaps.

RFI decides canonical membership, normalized chronology, page order, index health, and reported
gaps. The runtime decides which corpus is relevant to the question and whether to narrow dates or
types.

The classification conflict is visible: a 2024-09-04 “Citi's Global TMT Conference 2024” document
is canonically an earnings transcript because that is retained history, while event kind is
unavailable. RFI reports both facts. The runtime may qualify its analysis but may not ask MCP to
silently reinterpret the document.

### 12.2 Management sentiment over time

The runtime decomposes “How has management sentiment about the business outlook changed?” into
search concepts such as outlook, demand, recovery, constraints, and confidence. It decides to test
early, late, and intermediate periods. Calls to `search_transcript_segments` may use relevance,
oldest, or latest ordering and explicit date/document filters.

RFI returns compact candidates with exact segment URIs, named lexical semantics, counts and
bounds. The runtime reads promising exact segment resources and neighboring document windows,
compares periods, searches for qualifying language, and constructs its own claims. If it omits the
2024-09-04 boundary, that is visible in its trace; RFI does not run TASK-071's adjudicator or
request recovery.

### 12.3 Cloud/nearline demand and constraints

For the TASK-071 demand question, the runtime chooses separate searches for cloud/nearline demand,
customer inventory/qualification behavior, and supply/capacity constraints rather than requiring
all concepts in one paragraph. It expands exact evidence across early and latest relevant dates.

An empty search for “supply constraints” is returned as a successful lexical empty with the exact
index generation and coverage limits. The runtime—not RFI—decides whether to try “capacity,”
“inventory,” or a shorter query, and whether the available evidence supports only part of the
question.

### 12.4 HAMR/Mozaic progress

The runtime searches `HAMR qualification`, `Mozaic`, launch, volume, and production using temporal
ordering. Search hits from 2024-09-04 and later periods are candidates. Reading segment resources
verifies byte spans and provenance. Reading document/observation resources discloses that speaker
attribution is absent even when the passage wording suggests a speaker turn. The runtime can state
“the retained transcript says” or “management commentary” but cannot responsibly attribute a
named speaker unless some other authoritative retained metadata supports it.

### 12.5 First/latest 40-terabyte discussion

The runtime chooses oldest and latest ordering because the question asks chronology. RFI applies
that order across matching segments and reports all truncation/diversity bounds. Exact resource
reads establish the earliest and latest passages found under the declared lexical expression.
The runtime must qualify the result as first/latest *retained indexed match under the searched
wording*, unless corpus/index coverage establishes more.

RFI does not expose a `find_first_and_latest_40tb` tool because chronology is already a generic,
stable ordering semantic.

### 12.6 Contradictory or qualifying evidence

After finding positive demand or technology statements, the runtime independently searches for
delays, risk, constraints, inventory, qualification dependence, and uncertainty. MCP does not have
`find_counterevidence`; it executes the runtime's ordinary governed queries. This preserves a
diagnostic distinction between search quality and investigative strategy.

### 12.7 Recognize insufficiency

For “What did CEO Dave Mosley say about employee attrition by geography?” the runtime sees at
orientation that historical speaker labels are unavailable. It may execute materially distinct
lexical searches such as `attrition`, `employee turnover`, and geography-related terms. Two valid
empty searches remain valid empty searches; an invented document ID would instead be an invalid
request and cannot count as evidence.

The runtime may conclude that the retained corpus is insufficient because (a) no searched wording
matched, (b) speaker identity cannot be established, and (c) corpus coverage is indeterminate.
RFI provides those facts but does not emit an `insufficient` answer status.

### 12.8 Construct the conclusion

The runtime maps each claim to exact segment URIs/artifact ranges, keeps interpretation separate
from retained text, identifies date/classification/speaker/coverage qualifications, and builds its
own answer or report. No generated claim, runtime trace, or report is written to retained RFI truth
by this experiment.

## 13. Diagnostic-attribution analysis

### Repository/MCP failure

Suppose relevant HAMR evidence exists in artifact A. `search_transcript_segments` returns no hit
because the access generation silently omitted A, or the segment resource resolves through a
newer document revision B. The access trace would show A in `query_artifacts`, an access generation
whose indexed-document inventory omits A or whose authority snapshot differs, and an exact read
whose artifact/range digest does not match. This is a repository/MCP failure, not poor model
reasoning. The proposed generation inventory, bounds, resource IDs, and checksums make it visible.

### Investigative-runtime failure

Suppose the search tool returns relevant exact segment URIs under ordinary concepts, but the
runtime never reads them, ignores the earliest date, fails to search qualifiers, or stops after a
single narrow empty search. MCP request logs show correct, available results; the runtime trace
shows its choices. This is investigative-runtime failure. RFI should not add `choose_next_step` to
mask it.

### Repository-authority failure

Suppose the runtime follows the interface correctly but the retained observation gives an
incorrect event date, canonical classification is ambiguous, provenance points to the wrong
source, or exact bytes/checksum are wrong. Resources reveal the authoritative value, basis,
observation ID, checksum, and conflict diagnostics. Correct tool use with bad or ambiguous
authority is a repository-authority failure. The historical conference-title/earnings-type
conflict is a real benign example of ambiguity that must remain visible.

### Synthesis failure

Suppose the runtime finds and verifies early and late passages but concludes that demand improved
continuously, even though evidence only supports two points or contains a qualification. Access
and discovery are adequate; claim mapping and prose are overstated. That is synthesis failure.
Because exact resources, dates, search trace, and coverage facts remain available, an independent
reviewer can identify it without blaming MCP recall.

### Required experiment instrumentation

For each MCP request, record:

- correlation/request ID, capability and schema version, server build;
- normalized input and a deterministic input digest;
- repository snapshot and access generation/health;
- start/end time and outcome/error code;
- returned/total counts, cursor, every applied bound and truncation;
- referenced document/artifact/observation/segment IDs;
- exact-byte and range digests for evidence reads; and
- response digest and byte count.

The Codex Work experiment must preserve its own tool/resource trace, question, final claims, and
citations separately. RFI logs no planner state or hidden sufficiency judgment. The two traces are
correlated by request ID.

## 14. Gap analysis

| Proposed capability | Classification | Evidence and required action |
| --- | --- | --- |
| `query_artifacts` | Thin MCP adaptation required | `ArtifactQueryService.query()` already has typed filters/order/cursors/snapshot; serialize without semantic change and make diagnostic bounds explicit |
| Logical document resource | Thin MCP adaptation required | `detail()` supplies current summary/observation; correct integrity label and attach typed links |
| Immutable artifact resource | Existing capability requiring semantic cleanup | Artifact metadata and exact artifact-ID bytes exist below service; add normalized artifact-ID lookup/read |
| Observation resource | Existing capability requiring semantic cleanup | `ArtifactObservation` exists; direct lookup and normalized failure are missing |
| Artifact history query | Missing repository/IQA capability | Raw authority retains revisions/observations/attempts, but no public normalized history query spans them |
| Exact byte-range tool | Existing capability requiring semantic cleanup | Whole artifact-ID read exists; public range schema, bounds, digests, and normalized errors are missing |
| Data dictionary | Missing repository/IQA capability | TASK-071 prose capability dictionary and dataclasses are inputs, not a separate versioned field-authority contract |
| Capability registry/health | Missing repository/IQA capability | Retrieval has a health precedent; transcript/artifact/common registry is absent |
| Transcript corpus view | Existing capability requiring semantic cleanup | `describe_corpus()` mixes schema and instance, hard-fails at 100, drops diagnostics, and has no cursor/generation health |
| Transcript segment search | Existing capability requiring semantic cleanup | FTS/search/order work; expose scope, access generation, typed errors, cursor or exact truncation, and all internal bounds |
| Exact transcript segment resource | Existing capability requiring semantic cleanup | Stable locator exists; must re-read by artifact ID, verify target digest, and reject stale/corrupt generation |
| Ordered segment window | Existing capability requiring semantic cleanup | `inspect_document()` works; raise bound, use exact verification, and expose typed window/page semantics |
| Canonical identity/type/time | Directly reusable existing contract | Artifact summary and classification contracts preserve identity and source-effective basis; dictionary must explain authority |
| Provenance links | Thin adaptation plus cleanup | Detail/observation provide locations/roles; malformed/unavailable and diagnostic-size behavior need explicit outcomes |
| Retained-corpus coverage | Missing repository/IQA capability | Acquisition interval coverage exists, but no justified aggregation proves corpus completeness; expose indeterminate rather than infer |
| Speaker/event-kind fidelity | Missing upstream retained-truth capability | Historical artifacts lack it; MCP must report gap, not infer or repair |
| Semantic/synonym retrieval | Intentionally deferred | No evaluated transcript semantic index; lexical quality should be measured first |
| Mail/feed/stream/source-object/knowledge extensions | Intentionally deferred from first slice | Real domain contracts exist, but each requires its own semantic design and health/coverage mapping |
| MCP prompts | Intentionally deferred/rejected | Would risk procedural ownership; use descriptions/dictionary |
| Investigation/report tools | Intentionally excluded | TASK-071 harness/adjudication/report behavior belongs to runtime/analysis layer |

### Gaps TASK-071 currently compensates for

TASK-071's harness carries protocol allowlists, valid-ID sets, tool ordering, failed-search
accounting, expanded-evidence admission, temporal boundary checks, final-turn stopping, one recovery
cycle, and closed-record adjudication. Only valid-ID normalization and typed protocol failure belong
near MCP access. The rest must not migrate into RFI merely because it improved the proving runs.

The harness also hides some access weakness: it always calls orientation first, supplies all 21
document IDs to the model, records expanded IDs in process, and runs over a static copied corpus.
An independent runtime/MCP experiment removes those favorable assumptions. That is why resource
links, generation identity, immutable artifact reads, and discoverable schemas are requirements.

## 15. Rejected alternatives and anti-patterns

1. **Generic SQL or database browser.** It leaks persistence and makes every consumer reconstruct
   identity, chronology, provenance, and authority.
2. **Translate TASK-071 one-for-one.** `describe_corpus` mixes dictionary and instance;
   `dispatch` has weak errors; the harness's mandatory order/citation/stopping rules are not
   repository semantics.
3. **One `investigate_question` tool.** It destroys the architectural experiment and makes failure
   attribution impossible.
4. **One universal `search` over all objects.** It would flatten exact source evidence, derived
   knowledge, tombstones, feed summaries, and mail relationships into an ambiguous result class.
5. **One giant evidence package assembled from the question.** Evidence assembly before the
   runtime understands the question reintroduces TASK-007-style procedural constraint.
6. **Question-specific support/counterevidence/sentiment/chronology tools.** Ordinary typed search
   and ordering already provide the stable semantics; these tools would encode strategy.
7. **Expose every Python service method as a tool.** Current code decomposition is not the
   conceptual model; next/previous cursor methods, rebuild methods, and provider operations are
   especially poor MCP primitives.
8. **Make search snippets citable.** Snippets are clipped derived projections; exact resource reads
   are required.
9. **Return all content in every query result.** It defeats progressive disclosure, response bounds,
   and context management.
10. **Return storage paths or original URLs as content identity.** Paths leak internals and URLs are
    provenance only.
11. **Infer missing speaker/event metadata in MCP.** That would create a second truth source.
12. **Treat a search/index outage as zero matches.** This destroys diagnostic attribution.
13. **Expose RFI prompts that tell the model when to stop or how to write a report.** That moves
    investigative behavior across the boundary.

## 16. Minimal first implementation slice

### 16.1 Scope

Implement a local, read-only, transcript-focused MCP server over the retained Seagate corpus. The
implementation task may add the MCP dependency it selects; TASK-072 adds none.

Minimum resources/templates:

- `rfi://about`;
- `rfi://dictionary`;
- `rfi://capabilities`;
- `rfi://documents/{document_id}`;
- `rfi://artifacts/{artifact_id}`;
- `rfi://observations/{observation_id}` for the selected transcript observation;
- transcript corpus view;
- `rfi://transcript-segments/{segment_id}`; and
- bounded ordered transcript document window.

Minimum tools:

- `query_artifacts`;
- `search_transcript_segments`; and
- `read_artifact_bytes`.

`query_artifact_history` may be deferred in the first experiment if the selected observation and
document/artifact links are sufficient, but the capability registry must label it deferred. Do
not replace it with raw acquisition rows.

### 16.2 Required repository/access corrections

1. Add a public normalized artifact-ID metadata/content read at the artifact service boundary.
2. Add a direct normalized observation lookup sufficient for the selected observation resource.
3. Split transcript dictionary metadata from corpus-instance orientation.
4. Give each transcript index a deterministic generation ID and authority snapshot; reject or
   explicitly rebuild on authority change.
5. Reverify segment/resource bytes by immutable artifact ID and exact span digest on every exact
   read.
6. Preserve artifact diagnostics, identify all build/search/result bounds, and expose partial
   access rather than silently dropping documents.
7. Replace generic `ResearchError` at the MCP-facing access boundary with the taxonomy in section
   11. The existing research harness may remain unchanged.

### 16.3 Transport and deployment

Use local MCP `stdio` launched as a child process by Codex Work. The server receives an explicit
RFI state path/configuration, opens repository authorities read-only where supported, performs no
network access, and has no mutation tools. It assumes the current single-user local trust boundary.
HTTP transport, remote deployment, authentication, multi-user authorization, and distributed
indexing are deferred.

The server must not import TASK-071's harness, model adapter, adjudicator, reporting, or OpenAI
transport. It may reuse/refactor the transcript access implementation behind a new access contract.

### 16.4 Tests

Required tests include:

- resource/tool discovery and JSON-schema contract snapshots;
- artifact query differential equality with `ArtifactQueryService`;
- unknown, invalid, unsupported, valid-empty, stale-cursor, and repository-failure cases;
- artifact-ID exact read and range digest verification;
- document revision after index build proving stale detection and preventing artifact drift;
- segment-ID stability and exact byte/digest verification;
- access missing/stale/corrupt health distinctions;
- isolated malformed artifact/provenance and named partial corpus behavior;
- every internal/query/result bound and truncation indicator;
- Seagate inventory parity (21 documents/2,268 segments at the recorded proving snapshot);
- the five TASK-071 questions exercised by an external capable runtime with full MCP traces;
- insufficiency case distinguishing valid empty searches from invalid identifiers;
- no imports from `rfi.research.harness`, adjudication, reporting, OpenAI adapter, SQLite schema, or
  content paths in the MCP adapter; and
- read-only proof: no repository revision, file, or retained record changes across the experiment.

### 16.5 Experiment comparison

Compare the Codex Work run with TASK-071 on evidence discovery, exact citation admission, temporal
coverage, qualification quality, insufficiency calibration, tool/resource errors, total access
trace, and required RFI-specific prompt material. Do not require identical call counts, search
terms, claims, or prose.

The experiment succeeds architecturally if the runtime can orient, search iteratively, verify
evidence, expose qualifications, and build supportable conclusions without repository-side
planning or report tools. A poor conclusion with adequate access remains useful evidence about
runtime proficiency rather than a reason to enlarge MCP immediately.

### 16.6 Explicitly deferred

- semantic embeddings/reranking and retrieval-quality optimization;
- all-domain common search;
- mailing-list, feed, stream, source-object, and knowledge MCP extensions;
- full normalized document revision/attempt history if not needed for the first slice;
- prompts;
- persistent investigation/claim/report state;
- acquisition or correction mutation;
- remote transport/authentication/multi-user policy;
- context/token budgets, recovery, adjudication, and stopping controls; and
- product CLI/UI/workspace composition.

## 17. Unresolved questions and risks

1. Should exact segment URIs remain resolvable after the process-local generation is gone by
   reconstructing from the self-describing locator, or should a generation-qualified URI be
   required? The recommendation is stable unqualified segment identity plus fail-closed rebuild
   verification, with generation recorded in every response.
2. Can a repository snapshot represent content-store corruption that occurs without structured
   revision change? No; exact reads must always verify checksum independently.
3. How should corpus coverage aggregate historical acquisition interval outcomes without
   overstating continuity across source-profile changes? Until a repository contract answers this,
   report retained inventory plus `indeterminate` coverage.
4. Should title be treated as retained metadata, embedded transcript header text, or display
   projection? Existing code falls through all three. MCP must expose the chosen value and basis.
5. How should partial transcript-index construction isolate a malformed document while still
   ensuring the agent sees that omission? Use `partial`, document diagnostics, and indexed versus
   eligible counts; do not fail open or silently omit.
6. MCP client support for resources/templates may be less reliable than tool calling. The
   experiment should record resource discovery/read failures before duplicating resources as get
   tools.
7. An agent may overconsume the dictionary or corpus inventory. Measure this before splitting the
   dictionary or adding summary prompts.
8. Exact content can contain prompt injection. Tool/resource descriptions must state that retained
   source content is untrusted data, while the runtime owns its own prompt-injection defenses.
9. Local `stdio` inherits filesystem authority. The implementation task must ensure the server
   exposes only configured repository reads and never a general file resource.
10. The Seagate corpus is a narrow evaluation. Success does not prove that the same extension
    design fits mail graphs, filings, tables, feeds, or versioned knowledge.

## 18. Next bounded milestone

Authorize **TASK-073 — Implement and evaluate the minimal read-only RFI MCP transcript surface**.
That task should implement only section 16, run Codex Work against the five recorded Seagate
questions without TASK-071's harness prompt/control loop, preserve complete correlated traces, and
produce a comparative attribution report. It should not add a second evidence type until the
experiment shows that the boundary is usable and failures are attributable.

The implementation task should stop and report rather than add convenience tools if the agent
struggles. The post-experiment decision should choose among: accept the boundary, repair a named
repository/access semantic gap, improve transcript retrieval quality, or reject the hypothesis
that the selected general runtime can own investigation proficiently.

## Architectural Status Summary

| Subsystem | Status after TASK-072 | Architectural meaning |
| --- | --- | --- |
| Immutable evidence and acquisition history | Complete for current local product | Remains sole source-byte/observation authority; unchanged by this design |
| Artifact query/read contract | Complete with identified MCP-facing gaps | Query/detail/current-document reads are reusable; immutable artifact-ID and normalized history reads need cleanup |
| Transcript acquisition/classification | Usable with limitations | One provider, indeterminate coverage, missing historical event-kind/speaker fidelity remain visible |
| Transcript knowledge access | Implemented POC; provisional | Lexical/temporal search and locators are useful; generation health, typed errors, bounds, and exact artifact-addressed reads need cleanup |
| Source objects/knowledge/retrieval | Implemented POCs; not first-slice composed | Supply future extension patterns without forcing transcripts through SEC-specific lifecycles |
| Agent-legible MCP design | Complete | Rich, read-only, procedurally weak surface and responsibility boundary are specified |
| MCP server | Not started | No dependency, transport, server, or production behavior is introduced by TASK-072 |
| General-runtime experiment | Not started | TASK-073 recommendation; five Seagate cases and falsification criteria are defined |
| Investigation/report construction | Outside RFI MCP | Remains the capable runtime's responsibility; no generated claim becomes retained truth |

Architectural change: RFI now has an accepted experimental boundary for exposing its epistemic
substrate through MCP, while MCP element names and schemas remain provisional until the bounded
Codex Work experiment. The next milestone is the minimal local read-only implementation and
comparative evaluation, not broader evidence-type coverage or product composition.

Final design disposition: **Proceed with MCP experiment.** Implement only the bounded slice in
section 16, preserve complete diagnostic traces, and attribute any poor result before enlarging
the RFI surface.
