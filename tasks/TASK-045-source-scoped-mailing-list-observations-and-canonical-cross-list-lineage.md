# TASK-045 — Source-Scoped Mailing-List Observations and Canonical Cross-List Lineage

## Status

Complete

## Objective

Correct the Linux Block/Linux NVMe cross-post acquisition failure while adding the smallest
canonical lineage layer needed to follow one authored message into branches observed through
different mailing-list sources.

Acquisition, relationship work, continuation, and coverage remain source-scoped. A normalized
`Message-ID` identifies one corpus-level logical message, while each source retains its own exact
immutable RFC822 observation and source-specific document. Different bytes across sources are
valid observations; different bytes for the same identity within one source remain fail-closed.

The task also repairs the continuation defect that allowed rejected messages to enter durable
frontiers and provides a deterministic, evidence-preserving repair for the 18 affected Linux NVMe
observations and the invalid saved frontier.

---

## Problem Statement

TASK-035 introduced a global canonical `Message-ID` mapping whose representative artifact currently
controls acquisition admission. A message cross-posted to Linux Block and Linux NVMe has one authored
identity but list-specific RFC822 delivery bytes. The second source observation is consequently
misclassified as `message_id_byte_conflict`, quarantined, and omitted from the source message
projection.

The relationship planner adds fetched identifiers to continuation state before repository retention
succeeds. The affected NVMe run therefore saved reply frames referencing messages that were not
successfully retained for NVMe. Retry loaded that frontier and failed with
`continuation_corrupt: reply parent is missing`.

The corrective model is:

```text
canonical logical message (normalized Message-ID)
    ├── exact Linux Block observation and source discussion membership
    └── exact Linux NVMe observation and source discussion membership

durable observation relationship claims
    └── deterministic canonical lineage projection
```

A shared canonical node may participate in multiple source-specific discussions. Descendants may
diverge by source, and corpus lineage traversal must return all known branches without duplicating
the shared logical message.

---

## Authoritative Identity and Evidence Model

### Canonical Logical Message

`canonical_mailing_list_messages` remains the repository-owned corpus identity authority for one
valid normalized `Message-ID`.

- `canonical_message_id` identifies the logical authored message.
- `normalized_message_id` remains globally unique.
- Existing artifact/document columns may remain as a compatibility representative for the first
  retained observation, but they must not control acquisition admission, relationship traversal,
  continuation, or coverage.
- A canonical message may have multiple exact source observations and multiple source discussion
  memberships.
- A canonical node is created only from a successfully retained RFC822 message observation. A valid
  referenced parent ID without retained message evidence remains an unresolved lineage boundary; it
  must not create a placeholder canonical node.

### Source Observation

The authoritative acquisition identity is:

```text
(source_id, normalized Message-ID)
```

Each successfully retained source observation has:

- one source-scoped message identity and message key;
- one source-specific logical document;
- the exact immutable RFC822 artifact observed through that source path;
- a reference to the corpus canonical message;
- acquisition and delivery provenance; and
- zero or more durable relationship evidence claims.

Content-addressed storage may reuse one artifact object when bytes are exactly identical. Each
source must still retain its own message record, document/provenance, and run observation.

### Source Semantics for Required Ancestors

`source_id` on a retained message means the governed acquisition source whose relationship work
caused the observation to be retained. It does **not** by itself prove that the email was delivered
through that list.

First reuse existing artifact, document, provider, candidate provenance, fallback-location, and run
metadata. Add only the minimum bounded fields that are still necessary to distinguish:

- `configured_archive` — fetched from the configured source archive; this is acquisition provenance
  and evidence of the archive path, but list delivery is asserted only when retained provider/header
  evidence identifies that list;
- `cross_archive_fallback` — fetched from the corpus-wide fallback archive while completing the
  configured source; acquisition provenance belongs to the configured source, while delivery-list
  provenance is unknown or is derived only from explicit retained headers/provider metadata; or
- another already-governed path explicitly represented by the existing provider contract.

The implementation must document the exact existing Lore URL/fallback behavior and persist enough
provenance to distinguish acquisition source from asserted delivery source. It must not label a
required ancestor as delivered through the current list merely because that list's traversal fetched
it. This task does not authorize a generalized provenance framework.

---

## Bounded Relationship Claim Model

Relationship assertions are the durable evidence authority. One durable assertion consists of the
child canonical ID, the referenced Message-ID assertion, evidence type, claim role, and exact source
observation provenance. Canonical lineage edges, resolution status, and any nullable resolved parent
canonical ID are derived, or deterministically materialized as rebuildable caches/projections, from
those assertions and the canonical registry. There must be no independent mutable canonical-edge or
resolution truth.

### Claim Roles

The bounded `claim_role` enum is:

- `immediate_parent` — the observation asserts one direct parent;
- `ancestor_reference` — the observation names a broader ancestor without asserting a direct edge.

An `ancestor_reference` must never be promoted to an immediate-parent edge merely because it is the
last or only `References` value.

### Evidence Types

The bounded `evidence_type` enum is:

- `header_in_reply_to` — an ID retained from `In-Reply-To`; it may support
  `immediate_parent` only when parsing yields exactly one normalized ID;
- `header_references` — an ordered ID retained from `References`; it supports
  `ancestor_reference` only;
- `provider_immediate_parent` — provider metadata whose documented adapter contract explicitly
  asserts a direct parent;
- `fallback_heuristic_parent` — an existing, deterministic repository heuristic that explicitly
  asserts a direct parent.

`fallback_heuristic_parent` may be used only if such a heuristic already exists and is documented
with a stable algorithm identifier and bounded inputs. This task does not authorize inventing a new
heuristic. If none exists, this enum value remains unused.

Each valid assertion retains the exact raw header/provider reference value, or a lossless bounded
pointer to equivalent parse evidence, in addition to its nullable normalized referenced ID.

Malformed or multiple-ID `In-Reply-To` values are not relationship claims: they satisfy neither
`immediate_parent` nor `ancestor_reference`. Retain them in bounded observation/parser evidence tied
to the exact artifact, including the raw header value (or lossless parse-evidence pointer), extracted
IDs where available, and parse warning. They must remain inspectable but must not expand the canonical
lineage claim authority.

### Resolution Status

When resolution is materialized, the bounded derived `resolution_status` enum is:

- `resolved` — the referenced normalized ID maps to a retained canonical node;
- `unresolved_parent` — the referenced normalized ID is valid but its canonical node has not been
  retained;
- `invalid_reference` — the asserted reference cannot be normalized or is structurally invalid.

`invalid_reference` evidence may have no normalized Message-ID. The normalized reference is therefore
nullable, while raw parse evidence is required. Malformed `In-Reply-To` parser evidence normally
remains outside the relationship-claim authority as specified above.

Any stored `resolution_status` and resolved parent canonical ID must be reproducible from the durable
assertion plus the canonical registry and validated on repository validation/rebuild. No numeric
confidence or undefined authority/certainty scale may be introduced.

Claims must preserve at least:

- child canonical message ID;
- raw referenced value or lossless bounded parse-evidence pointer;
- nullable normalized referenced Message-ID;
- claim role and evidence type;
- source observation/message key and exact artifact;
- acquisition source and delivery-provenance classification;
- `References` ordinal where applicable;
- provider or heuristic algorithm identifier where applicable;
- first observation time and immutable/run provenance.

Nullable resolved canonical ID and resolution status, if persisted, belong to the rebuildable
resolution projection rather than the durable assertion identity.

Later acquisition may resolve an `unresolved_parent` by deterministic projection/backfill from the
original claim. It must not rewrite or erase the observation evidence that established the claim.

### Ambiguous Immediate Parentage

When valid observations of one canonical child assert different immediate parents:

- retain every claim;
- derive every supported canonical branch;
- expose the immediate-parent set as ambiguous;
- attach source/artifact evidence to each branch;
- do not select a winner; and
- do not automatically classify the condition as a substantive content conflict.

Agreement across observations yields one derived canonical edge supported by multiple claims.

---

## Canonical Lineage and Source Discussion Projections

### Canonical Lineage

Canonical lineage is the deterministic graph projection of resolved `immediate_parent` claims.

- Nodes are canonical messages.
- A distinct child/parent pair is returned once with all supporting claims.
- Corpus traversal returns every known parent and child branch.
- Each canonical node is returned once even when it has multiple source observations.
- Unresolved immediate-parent claims appear as explicit lineage boundaries containing the referenced
  normalized ID and supporting observation evidence.
- `ancestor_reference` claims remain inspectable ancestry evidence but are not traversable direct
  edges.
- Valid unresolved references do not create canonical nodes. They remain boundaries until a
  successfully retained observation establishes the referenced canonical message.

If lineage edges are materialized for query performance, the materialization must be repository-owned,
fully rebuildable from claims, transactionally refreshed, and validated against the claims. It must
not become a second authority.

### Source Discussion View

Existing source message relationships and discussions remain source-scoped projections.

- A source discussion represents the graph retained while satisfying that configured source's
  acquisition policy. Membership is not proof that every member was delivered through that mailing
  list.
- A source relationship connects source message keys only within that source projection.
- A source-filtered thread returns only that source's messages, memberships, and evidence.
- Each returned source message exposes its canonical message ID so a caller can move from the source
  view to corpus lineage.
- One canonical message may be represented by multiple source message keys and may therefore belong
  to multiple source discussion projections without becoming multiple logical nodes.
- A required ancestor fetched from the configured archive or corpus fallback receives a
  source-scoped message and may receive membership in this acquisition-policy discussion when needed
  to close the retained graph. Its acquisition-path and evidenced-delivery metadata must preserve
  that membership does not assert delivery through the configured list.

---

## Required Schema and Repository Changes

Use the smallest additive migration that satisfies the model.

1. Associate every successful non-tombstone `mailing_list_messages` row with a
   `canonical_message_id`. A nullable compatibility path is permitted only during migration;
   successful post-migration RFC822 observations must have the association.
2. Add one durable relationship-claim authority with the bounded roles, evidence types, raw reference
   evidence, observation provenance, and uniqueness needed to retain agreeing and differing claims.
   Any resolved canonical ID or resolution status stored beside it is a validated rebuildable
   projection.
3. Do not add an independently mutable canonical lineage-edge authority. Prefer deterministic query
   derivation unless a rebuildable materialization is proven necessary.
4. Preserve existing source relationship/discussion tables as rebuildable source projections.
5. Remove global representative-artifact equality from normal acquisition admission and publication.
6. Enforce same-source byte equality using `(source_id, normalized Message-ID)` before accepting a
   new source observation.
7. Preserve `mailing_list_run_items.canonical_message_id` and existing canonical lookup callers where
   they remain useful, while documenting that representative artifact/document fields are not
   acquisition authority.
8. Update repository validation to prove canonical links, claim references, enum validity,
   nullable-reference rules, raw parse evidence, source-observation provenance, resolution-cache
   agreement with the canonical registry, and any deterministic lineage materialization.

No content fingerprint, header normalization, graph database, or generalized evidence abstraction is
authorized.

---

## Acquisition, Continuation, and Coverage

Acquisition planning may hold provider identifiers provisionally, but durable continuation state may
reference only successfully retained observations for the current source.

Required sequencing:

1. Fetch and parse a candidate.
2. Retain or reuse the exact source-scoped observation.
3. Associate it with the canonical node.
4. Persist its relationship claims.
5. Only then admit the identifier to `acquired_ids`, completed IDs, or a stack frame that assumes
   retained content.

Before publishing any frontier, validate all retained-state references against
`(source_id, normalized Message-ID)` in the successful source observation authority. Provider IDs
that have not yet been retained may exist only in an explicitly pending-fetch position whose
semantics do not claim acquisition.

A rejected, quarantined, unresolved repository candidate, or same-source byte conflict must never
become a durable acquired reference. A genuine blocking conflict must produce a truthful,
non-retryable `message_id_conflict` outcome, withhold coverage, and save no resumable frontier that
depends on the rejected message. Valid evidence retained earlier in the bounded run remains
inspectable.

Coverage remains a property of one configured source, window, discovery page, and relationship
policy. Canonical graph enrichment does not retroactively advance or invalidate another source's
coverage.

---

## Deterministic Repair of the Affected NVMe State

The repair must run only against an explicit copied state database during development and review.
Live state mutation is not authorized by this ticket's creation or design phase.

A historical conflict is eligible for cross-source reclassification only when all of the following
are proven from durable repository evidence:

1. The preserved candidate artifact is exactly the artifact recorded for the affected NVMe run's
   conflict observation.
2. Parsing those exact bytes yields the same normalized `Message-ID` recorded by the conflict.
3. No successful Linux NVMe source observation already exists for that normalized ID.
4. The rejection reason is solely the existing global representative-artifact byte mismatch.
5. The representative canonical artifact was established by a successful observation from a
   different source.
6. No evidence shows a previously accepted, byte-different observation for the same NVMe source.

If any predicate is absent or ambiguous, leave the conflict unresolved and report it; do not guess.

For eligible rows, the repair shall:

- preserve the candidate and representative artifacts unchanged;
- create or associate the source-specific NVMe document and publish the successful source message
  under a new repair or acquisition provenance record;
- link it to the existing canonical node;
- derive durable relationship claims from the exact candidate observation;
- mark the historical conflict resolved with an explicit cross-source-reclassification reason and
  repair provenance; and
- preserve the historical failed run, its conflict observation, and its manifest unchanged; the
  repair must not retrofit a successful run item or successful observation into that run; and
- preserve all historical conflict observations and failed manifests.

The saved offset-105 frontier must be validated, rejected as a legacy invalid frontier because its
retained-state references do not resolve for NVMe, and superseded append-only. Retry must restart the
same discovery offset, reuse repaired/accepted source observations, and advance neither offset nor
date coverage until the relationship work reaches a valid terminal state.

The repair must be idempotent and produce a bounded report listing eligible, repaired, skipped, and
still-unresolved records.

---

## Scope

### In Scope

- source-observation-to-canonical linkage;
- source-scoped acquisition identity and byte-conflict enforcement;
- bounded durable immediate-parent and ancestry-reference claims;
- deterministic canonical lineage derivation and unresolved boundaries;
- source-filtered relationship/discussion compatibility;
- continuation admission and frontier validation;
- deterministic copied-state repair of the 18 NVMe false conflicts and invalid frontier;
- schema migration, compatibility, repository validation, documentation, and review evidence.

### Out of Scope

- content signatures or fingerprints;
- header normalization or semantic equivalence;
- automated relationship winner selection;
- confidence scoring;
- generic graph analysis, ranking, or visualization;
- unrelated UI work;
- broad mailing-list parser redesign;
- patch-series modeling;
- non-Lore acquisition changes;
- rewriting or deleting immutable artifacts or historical acquisition evidence;
- modifying the operator's live state as part of implementation or verification.

---

## Acceptance Criteria

1. Acquisition and same-source conflict checks use `(source_id, normalized Message-ID)`.
2. Byte-different observations from different sources attach to one canonical node without conflict.
3. Byte-different observations within one source remain fail-closed and inspectable.
4. Every successful RFC822 source message links to one canonical logical message.
5. Relationship claims use only the defined roles and evidence types; any stored resolution fields
   are deterministic, rebuildable, and validated against the canonical registry.
6. `In-Reply-To`, `References`, provider metadata, and any existing heuristic remain distinct evidence;
   `References` never silently creates an immediate-parent edge.
7. Canonical lineage is deterministically derived from resolved immediate-parent claims and returns
   all known branches without duplicating canonical nodes.
8. Unresolved parent claims remain visible and resolve later without loss or rewriting of original
   observation evidence.
9. Differing immediate-parent claims remain visible as ambiguous parentage with complete provenance.
10. Source-filtered discussions remain source-scoped and link back to canonical nodes.
11. Acquisition provenance and delivery-list provenance are distinguishable for required ancestors
    and fallback archive retrieval.
12. Only successfully retained source observations enter durable acquired/frontier state.
13. A genuine blocking conflict saves no corrupt resumable frontier and does not advance coverage.
14. The copied-state repair applies all eligibility predicates, repairs only proven cross-source
    cases, preserves immutable/history records, and is idempotent.
15. The affected discovery offset restarts safely and coverage advances only after valid completion.
16. Existing backup/restore, artifact integrity, repository queries, Linux mailing-list workflows,
    and unrelated acquisition behavior remain valid.
17. Malformed and multi-ID `In-Reply-To` evidence remains inspectable as parser/observation evidence
    but creates no canonical relationship claim.
18. Canonical nodes are created only by successfully retained RFC822 observations, never by an
    unresolved reference alone.
19. A fallback-acquired required ancestor may participate in the configured source's
    acquisition-policy discussion without that membership asserting delivery through the configured
    list.

---

## Required Tests and Evidence

### Focused Schema and Repository Tests

- schema migration from the current version preserves all artifacts, documents, messages, runs,
  observations, conflicts, relationships, and discussions;
- migration deterministically backfills canonical links for successful source observations;
- one canonical node accepts exact byte-different Block and NVMe observations;
- exact-byte cross-source observations retain separate source documents/provenance even when the
  content-addressed artifact is shared;
- same-source exact reuse is idempotent;
- same-source changed bytes fail closed;
- repository validation detects broken canonical links and invalid claim references;
- repository validation detects resolution caches that disagree with the canonical registry;
- backup/restore preserves the new authority and passes validation.

### Relationship and Lineage Tests

- one canonical message has Block and NVMe source observations and memberships in two source
  discussions;
- Block-only and NVMe-only descendants form two corpus branches from the shared canonical node;
- corpus traversal returns the shared node once and both branches with claim provenance;
- source-filtered traversal returns only the selected source projection;
- agreeing immediate-parent claims derive one edge with multiple supporting claims;
- differing immediate-parent claims derive all branches and expose ambiguous parentage without a
  winner or content-conflict label;
- `References` values are retained in order as `ancestor_reference` claims and do not become direct
  edges;
- multiple-ID `In-Reply-To` produces no direct edge and remains inspectable as ambiguous evidence;
- malformed reference evidence preserves its raw value with a nullable normalized reference;
- an unresolved parent boundary becomes resolved after later acquisition without rewriting the
  original evidence claim;
- an unresolved reference alone creates no placeholder canonical node;
- configured-archive and fallback ancestor cases prove acquisition-source versus delivery-provenance
  semantics.

### Continuation and Coverage Tests

- every durable `acquired_ids`, ancestry stack, reply stack, and completed-ID reference resolves to a
  successful observation under the continuation source;
- injected rejection/quarantine cannot enter a saved frontier;
- genuine same-source conflict produces a truthful non-retryable outcome and withholds coverage;
- a legacy invalid frontier is rejected and restarts the same discovery offset;
- retry completes relationship work without `continuation_corrupt` and advances offset/window
  coverage exactly once;
- canonical graph enrichment alone does not advance source coverage.

### Copied-State Repair Tests

- run the repair against a disposable copy of the affected state database and content store;
- prove all six eligibility predicates independently, including negative cases for each predicate;
- prove exactly the eligible NVMe false conflicts are repaired and ineligible/genuine conflicts
  remain unresolved;
- prove candidate artifacts parse to their recorded normalized IDs;
- prove no immutable artifact or historical manifest is rewritten or deleted;
- prove the historical failed NVMe run receives no retrofitted successful run observation and the
  accepted source observation has new repair/acquisition provenance;
- prove repeated repair is a no-op with the same report;
- prove the repaired copy retries from offset 105 and reaches valid coverage;
- run repository validation and backup/restore against the repaired copy.

### Regression and Full Validation

- focused TASK-045 tests;
- TASK-023, TASK-030, TASK-031, TASK-035, TASK-037, TASK-028, TASK-029, TASK-032, TASK-038, and
  TASK-039 mailing-list/configuration regression suites;
- full `make validate`;
- exact commands, outputs, counts, schema version, integrity results, and copied-state identity are
  retained in the review package.

---

## Required Documentation and Review Package

Produce a complete TASK-045 review package containing:

- the authoritative task ticket;
- an ADR documenting canonical logical identity, source observations, claim authority, lineage
  derivation, ambiguity, and compatibility with TASK-035;
- schema and migration description;
- repository/service sequencing and transaction boundaries;
- acquisition-source versus delivery-provenance analysis for configured and fallback ancestor paths;
- continuation/frontier invariant and failure-outcome documentation;
- deterministic repair eligibility specification and copied-state repair report;
- focused and regression test outputs;
- full validation output;
- repository integrity and backup/restore evidence;
- documented limitations and deferred opportunities; and
- the required Architectural Status Summary from
  `docs/framework-task-operating-model.md`.

The review package must be independently reproducible and must clearly state that no live operator
state was modified during implementation or validation.

---

## Architectural Invariants

- SQLite remains the sole structured application authority.
- Exact artifacts remain immutable and content-addressed.
- Canonical identity is corpus-level; acquisition admission and coverage are source-scoped.
- Claims are durable evidence authority; lineage edges are derived.
- Source discussions remain rebuildable projections.
- Every model-facing lineage result is operator-inspectable with source/artifact provenance.
- Historical runs, observations, conflicts, and immutable artifacts are preserved.
- Provider interaction remains bounded and governed.
- No task completion may be claimed without copied-state repair evidence, focused tests, full
  validation, and the complete review package.
