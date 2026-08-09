# TASK-071 retained-truth instance catalog

This catalog records the substantive retained instance types inspected before establishing the
transcript knowledge-access boundary. It distinguishes repository evidence, deterministic
structural descriptions, versioned interpretation, and non-authoritative analysis. Configuration
catalogs such as firms, concepts, source profiles, and stream definitions are authoritative
governance, but they are not substantive source content and are therefore referenced only where
they associate evidence.

## 1. Immutable acquired artifacts and observations

- **Canonical identity and authority:** `artifact_id` is derived from the SHA-256 of exact bytes;
  `document_id`, immutable `observation_id`, `attempt_id`, governed `source_id`, and canonical
  artifact classification are repository-owned domains. `AcquisitionRepository` is the write
  authority; `ArtifactQueryService` is the normalized public read boundary.
- **Content:** exact immutable bytes in content-addressed storage. SQLite retains checksum, byte
  count, media type, and the internal content reference.
- **Authoritative metadata:** acquisition observation, canonical firm/type association, mechanism,
  ingestion time, durable status, and attempt/source linkage. Provider identifiers, URLs, and
  diagnostics are retained provenance attributes and cannot assign canonical identity.
- **Deterministic metadata:** normalized artifact summaries, source-effective ordering, integrity,
  current-document projection, observation navigation, and display labels.
- **Provenance/source:** governed source, adapter, discovery locations and metadata, retrieval
  diagnostics, selected immutable observation, and original-source location.
- **Time:** source-effective chronology and ingestion chronology are distinct. TASK-071 repairs
  `ArtifactQueryService` to use retained `trusted_event_date`/`validated_event_date` after ordinary
  filing/publication fields and before observation/retrieval fallback.
- **Relationships:** document-to-revisions, artifact-to-observations/attempts, firm/type/source
  association, and observation history.
- **Reads/navigation:** bounded `ArtifactQuery`, summary/detail/content, observation cursors,
  oldest/latest projections, browser and REST content reads.
- **Indexes/projections:** SQLite indexes for document, type, firm, chronology, and observation
  access; current document and query projections; content-addressed byte lookup.
- **Commonality:** stable identity, exact bytes, provenance, time, type, integrity, and bounded read
  are the best common evidence envelope for downstream access.
- **Bespoke behavior:** artifact-family admission, event classification, temporal semantics,
  parsing, and useful segmentation remain type-specific. Exact transcript paragraphs and SEC SGML
  objects should not be forced into one structural grammar.

## 2. Canonical mailing-list messages and source observations

- **Canonical identity and authority:** repository-owned `canonical-mail-*` identity maps one
  normalized Message-ID to authoritative artifact/document identity. Per-run items are the
  source-observation authority; canonical identity is global rather than source-owned.
- **Content:** exact retained `message/rfc822` artifact bytes, including MIME parts and attachments,
  owned by the common artifact store.
- **Authoritative metadata:** normalized Message-ID mapping, source/run observation outcome,
  fetched/reused/unavailable facts, and canonical lineage/quarantine state.
- **Deterministic metadata:** parsed headers and searchable text, normalized participants, reply
  edges, connectivity, discussion membership/depth, and browser organization.
- **Provenance/source:** Lore/public-inbox source, run and item identity, archive locations, and the
  shared acquisition observation.
- **Time:** message date is source-effective; observation/run times describe acquisition history.
- **Relationships:** reply parent, cross-list source observations, canonical lineage, discussion
  component membership, ancestor/descendant connectivity, and stream membership.
- **Reads/navigation:** `MailingListQueryService`, workflow façade, discussion/message browser,
  public acquisition content reads, and canonical/source-observation inspection.
- **Indexes/projections:** message, relationship, discussion, participant, source, date, and
  membership projections in SQLite; projections are rebuildable from retained observations.
- **Commonality:** immutable artifact bytes and provenance fit the common artifact envelope.
- **Bespoke behavior:** Message-ID normalization/conflict quarantine, MIME parsing, reply closure,
  incomplete-component semantics, and discussion traversal justify a mail-specific IQA rather
  than paragraph search alone.

## 3. Confirmed-unavailable mailing-list ancestor evidence

- **Canonical identity and authority:** a repository-owned tombstone artifact records the bounded
  confirmation that an expected ancestor was unavailable; it deliberately has no canonical mail
  message identity.
- **Content:** immutable JSON artifact with media type
  `application/vnd.rfi.mailing-list-tombstone+json`; no email body is synthesized.
- **Metadata/provenance/time:** missing Message-ID, attempted configured and `/all/` archive
  locations, HTTP 404 observations, source/run, and observation timestamps.
- **Relationships:** may occupy the missing connector position in a derived reply path while
  remaining distinguishable from a retrieved message.
- **Reads/indexes:** mailing-list query and browser projections expose the tombstone and incomplete
  discussion state; common artifact content remains inspectable.
- **Commonality and specialization:** it shares identity, exact bytes, provenance, and integrity
  with artifacts, but its negative-evidence meaning and non-message status require a typed access
  path. A generic text index must not present it as quoted email evidence.

## 4. Feed entry observations and unavailable-entry tombstones

- **Canonical identity and authority:** repository feed definitions and entry keys identify
  observed entries; `FeedRepository` retains normalized observations, poll runs, fulfillment, and
  tombstone state. Linked full content, when acquired, is an ordinary immutable artifact.
- **Content:** normalized entry title/summary/link metadata is retained structurally; full source
  bytes belong to linked artifacts rather than the feed projection.
- **Metadata/provenance/time:** feed/source identity, entry key, canonical link, published/updated
  time, first/last observation, polling outcome, artifact association, and tombstone lifecycle.
- **Relationships:** feed-to-entry observations, entry-to-artifact fulfillment, firm-pull
  association, and unresolved/dismissed/restored/fulfilled tombstone state.
- **Reads/indexes:** `FeedRepository` and `FeedService`, feed CLI/admin projections, aggregate feed
  query, tombstone status/time indexes, and linked artifact reads.
- **Commonality:** identity, provenance, time, artifact association, and bounded query overlap with
  other evidence.
- **Bespoke behavior:** syndication entry-key normalization, repeated observation, fulfillment,
  and unavailable-entry lifecycle are feed-specific. Summary text is not interchangeable with
  exact full-content evidence.

## 5. Structural source objects

- **Canonical identity and authority:** stable identity derives from immutable artifact identity,
  structural locator, and exact span digest. `SourceObjectRepository` is an independent POC
  catalog and structural evidence-location authority, not semantic truth.
- **Content:** no competing byte copy. Objects point to half-open spans in immutable artifact bytes
  and retain the exact span checksum; normalized field values exist only for structural fields.
- **Metadata/provenance/time:** document/artifact, kind, role, ordinal, parent, span, parser outcome,
  and source-object build generation. Source-effective time remains upstream artifact semantics.
- **Relationships:** structural hierarchy, document membership, bidirectional provenance into
  derived knowledge.
- **Reads/indexes:** `SourceObjectReader`, document/object inventory, parent/child navigation, exact
  bounded context with supplied public artifact bytes, and atomic rebuilt SQLite catalog.
- **Commonality:** stable locators, exact-byte verification, provenance, hierarchy, and bounded
  expansion are directly reusable IQA ideas.
- **Bespoke behavior:** current SEC SGML grammar, header/embedded-document parsing, and hierarchy
  cannot parse retained plain-text transcripts. TASK-071 therefore reuses the locator/expansion
  principles, not the SEC object model or its independent persistence lifecycle.

## 6. Versioned derived knowledge

- **Canonical identity and authority:** semantic object and immutable version identities are owned
  by `KnowledgeRepository`; current generation is selected by an atomic pointer. This is retained
  interpretation, explicitly not source evidence.
- **Content/metadata:** typed payload, status, confidence, derivation identity, source-object
  support, supersession, correction reason, and generation inventory.
- **Provenance/time/relationships:** source-object references, issuer/filing relationships, version
  lineage, knowledge-generation time, and source dates carried in typed observations.
- **Reads/indexes:** public knowledge reader, current/all-version inspection, semantic-key lookup,
  source-to-knowledge navigation, generation integrity, and TASK-006 derived-result indexing.
- **Commonality:** stable identity, authority label, provenance, temporal/status fields, and bounded
  query belong in a harmonized model-facing evidence envelope.
- **Bespoke behavior:** ontology, conflict/uncertainty semantics, correction, and generation
  lifecycle must remain distinct from exact-source search. The transcript slice does not create or
  persist generated claims here.

## 7. Revisioned stream memberships and lineage

- **Canonical identity and authority:** immutable stream revision, run, membership, and lineage
  identities are repository-owned materialized selection records. They are authoritative for what
  a successful stream run selected, not for the referenced artifact's content.
- **Content/metadata:** no transformed evidence copy; memberships reference existing artifacts and
  documents and retain schema, direct/context reason, bounds, inclusion policy, upstream lineage,
  and publication plan.
- **Provenance/time/relationships:** source or upstream-stream input, revision/run request and
  completion times, DAG dependencies, membership lineage, seed/context relationships.
- **Reads/indexes:** stream repository/service, current and historical run/membership reads,
  topology, browser/CLI, typed policy projections, and offline rebuild from durable plans.
- **Commonality:** typed membership can scope an IQA without transferring artifact authority.
- **Bespoke behavior:** schema capability registries, connected-discussion expansion, atomic
  publication, and DAG lineage are stream semantics. TASK-071 does not create a transcript stream
  merely to obtain a corpus already addressable by the artifact contract.

## Explicitly separate non-authoritative retained analysis

TASK-007 intelligence results and TASK-008 workspace investigations, execution records, notes,
comparisons, and exports may be durably retained by their POCs. They are analysis/audit history,
not repository-retained source truth. They must carry authority class, evidence mapping,
uncertainty, and provenance. TASK-071 outputs investigation traces only to an explicit operator
path and does not publish conclusions into artifact, source-object, knowledge, stream, or workspace
authority.

## Harmonization findings

The useful shared model is an evidence envelope, not one universal IQA:

1. stable repository identity and explicit authority class;
2. exact content or a verifiable locator to it;
3. source-effective time separated from observation/build time;
4. canonical type plus type-specific metadata;
5. provenance/source association and retained relationships;
6. bounded discovery followed by exact inspection/expansion; and
7. explicit coverage, integrity, omission, and insufficiency semantics.

Artifact queries, source-object locators, evidence-package authority labels, bounded budgets, and
intelligence traces all earned reuse. Universal vector retrieval, the SEC structural schema, the
TASK-006 generation lifecycle, and the TASK-007 one-follow-up planner did not fit transcript
investigation well enough to compose mechanically. Mail discussion traversal, feed fulfillment,
knowledge versioning, and transcript paragraph chronology remain justified bespoke capabilities
behind the same authority and provenance principles.
