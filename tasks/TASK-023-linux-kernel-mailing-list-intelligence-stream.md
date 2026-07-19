# TASK-023 — Bounded Linux Kernel Mailing-List Intelligence Stream

## Status

Ready

## Summary

Add a bounded, repository-first acquisition and browsing capability for Linux kernel development mailing lists, initially focused on the Linux block-layer list and a Lore/public-inbox-compatible archive.

The task must deliver an end-to-end vertical slice that:

- discovers relevant messages without mirroring the complete archive;
- acquires complete connected discussion context for accepted messages;
- preserves each acquired email as immutable source evidence;
- records native message and discussion relationships in the existing SQLite structured-state backend;
- exposes bounded query mechanisms for messages, discussions, and relationship traversal; and
- integrates development-mailing-list navigation into the existing artifact browser without creating a separate browser or forcing mailing-list material into a firm-centric hierarchy.

Implementation details remain with Codex unless constrained below by an architectural invariant, required behavior, or verification obligation.

---

## Context

RFI-1 now has:

- immutable artifact acquisition and provenance foundations;
- an artifact browser and stored-content inspection surface;
- a SQLite structured-state repository foundation; and
- artifact-specific acquisition adapters.

Linux kernel development remains substantially email-centered. Relevant technical intelligence is distributed across branching reply trees, patch-series messages, maintainer reviews, revision threads, and related discussions. The useful evidence unit is still the individual immutable email, but meaningful interpretation often requires connected discussion context.

RFI-1 must support this source family without importing the complete history of the Linux kernel mailing lists and without storing disconnected fragments that can misrepresent the discussion.

---

## Objective

Implement the first governed development-mailing-list stream over the existing RFI-1 repository and SQLite backend.

The initial operational target is the Linux block-layer mailing list through a Lore/public-inbox-compatible source. The implementation should establish reusable repository contracts and behavior for future mailing lists while avoiding premature generalization beyond demonstrated needs.

---

## Architectural Requirements

### 1. Repository-first evidence model

Each acquired mailing-list message is an immutable source artifact.

The authoritative evidence must preserve the exact retrieved message representation or another lossless archive-provided representation sufficient to reproduce the original message, including its headers, body parts, and attachments where available.

Parsed headers, normalized text, thread organization, patch-series association, and query indexes are derived structured state. They must not replace or mutate the preserved evidence artifact.

All derived mailing-list state must remain traceable to the authoritative artifact and acquisition observation that produced it.

### 2. Existing SQLite backend remains authoritative

Mailing-list structured state and relationships must use the existing SQLite repository boundary introduced by TASK-021.

Do not introduce a graph database, external graph service, second authoritative datastore, or required in-memory graph framework.

The implementation may use relational tables, recursive queries, materialized relationship fields, projections, or other SQLite-compatible mechanisms chosen by Codex. Application and browser code must consume repository contracts rather than depend directly on persistence layout.

### 3. Native relationships are explicit

The repository must represent the relationships necessary to organize and query mailing-list discussions, including at minimum:

- immediate reply relationships derived from message headers;
- discussion/root membership or an equivalent reproducible projection;
- archive/list membership;
- acquisition-run membership and inclusion reason; and
- known unresolved parent references.

Patch-series and revision relationships should be represented when they can be derived deterministically within this task's scope. Heuristic relationships must be distinguishable from relationships established directly from message headers or archive metadata.

Normalized subject lines must not be treated as authoritative thread identity.

### 4. Connected-component admission invariant

RFI-1 must not persist or present a disconnected segment as though it were a complete or connected discussion.

For every accepted seed message, normal acquisition must obtain a connected component containing that seed. At minimum, this requires every available intermediate ancestor needed to connect the seed to the selected stored root.

Within a stored discussion component classified as connected:

- every non-root message must have a resolvable stored path through immediate-reply relationships to exactly one stored root;
- every intermediate message on each stored path must be present;
- immediate-reply relationships must be acyclic; and
- limits must truncate only at a descendant frontier or component boundary, never by removing an intermediate connector.

A date window, relevance query, seed limit, or result limit may constrain seed discovery. It must not remove the ancestor closure required to make an accepted component connected.

If a required ancestor or connector cannot be retrieved, the implementation must fail closed for complete-discussion admission. The affected material may be rejected or retained only in an explicitly incomplete/quarantined state. It must not be silently promoted to a synthetic complete root or joined by subject similarity.

### 5. Bounded acquisition, not archive mirroring

There must be no normal operation that implicitly imports an entire mailing list or its complete history.

Every acquisition run must be bounded by one or more explicit selection controls, such as:

- one or more external message identifiers;
- a date/time interval;
- a remote archive query;
- configured topic terms;
- selected authors or maintainers;
- patch subjects or other explicit criteria; or
- an incremental cursor that begins from an explicitly established boundary.

The implementation must support hard, operator-visible limits for seed discovery and context expansion. Limits and their effects must be recorded in the acquisition result.

Once a seed is accepted, acquisition may expand beyond the discovery window only as required to establish connected ancestor context and other explicitly configured discussion context.

Historical backfill must require an explicit operator action and explicit bounds. Incremental operation must not silently imply retrospective archive import.

### 6. Two-stage acquisition semantics

The implementation must separate these concepts, whether or not they become separate classes or commands:

1. **Seed discovery** — identify candidate messages using bounded criteria against the remote archive.
2. **Context closure and expansion** — acquire the connected ancestor closure and any configured descendant, patch-series, or revision context around accepted seeds.

The acquisition manifest must distinguish seed matches from messages admitted only to supply context.

At minimum, inclusion reasons must allow an operator or reviewer to determine whether a message was acquired because it:

- directly matched selection criteria;
- was explicitly requested;
- was required as ancestor/connector context;
- was included as descendant context; or
- was included through another supported relationship expansion.

Codex may refine the exact vocabulary.

### 7. Idempotency and integrity

Repeated acquisition of the same remote message must not create duplicate authoritative artifacts or duplicate structured relationships.

External `Message-ID` is the primary external message identity where valid and available. RFI-owned identifiers remain authoritative internally.

The implementation must handle and report malformed, absent, duplicate, or conflicting message identifiers without silently corrupting discussion organization.

Artifact integrity, provenance, and acquisition history must use the existing repository conventions.

### 8. Offline reconstruction

Mailing-list queryable state and discussion organization must be rebuildable from retained repository evidence and durable acquisition metadata without contacting the remote archive.

Offline rebuild need not reproduce information that was never acquired. It must reproduce the same stored message identities, header-derived relationships, connected-component classifications, and inclusion provenance for the retained corpus.

### 9. Shared artifact-browser integration

Development mailing lists must appear in the existing artifact browser, not in a separate application.

The browser must support more than one repository-owned navigation projection. The existing firm-oriented artifact projection remains intact. Mailing-list discussions must receive a semantically appropriate projection rather than being forced beneath a firm or flattened into an unstructured message list.

The mailing-list projection must support lazy, bounded navigation equivalent in spirit to:

```text
Development mailing lists
  Linux block layer
    Discussions
      Discussion or patch-series root
        Message
          Reply
            Reply branch
    Incomplete or quarantined material
```

This is illustrative, not a mandated widget or exact hierarchy.

The browser must not reconstruct the relationship graph independently from raw artifact data. It must consume repository/query contracts that provide the authoritative projection.

### 10. Browser detail behavior

The shared artifact-detail and stored-content mechanisms should be reused wherever practical.

For a selected email artifact, the browser must expose at least:

- mailing-list identity;
- subject;
- sender identity as represented in the message;
- message date/time;
- external Message-ID;
- immediate parent reference, when present;
- stored discussion/root context;
- acquisition inclusion reason;
- connectivity/completeness state;
- provenance and integrity information; and
- safe inspection of the retained message content.

For a selected discussion/root projection, the browser must expose a bounded summary sufficient to understand:

- discussion identity or root;
- date range;
- message count;
- connectivity/completeness state;
- whether expansion was truncated;
- available child branches; and
- any supported patch-series/revision context.

A discussion projection is not required to become a synthetic immutable artifact.

### 11. Completeness and truncation are explicit

The repository and browser must distinguish states equivalent to:

- complete connected discussion;
- connected bounded discussion with descendant-frontier truncation;
- incomplete discussion because required context is unavailable;
- quarantined/orphan material; and
- relationship derivation uncertainty where applicable.

Exact names and representation are left to Codex.

No disconnected material may be labeled or rendered as a complete connected discussion.

### 12. Query capabilities

Expose bounded repository/query mechanisms sufficient to support at least:

- list configured mailing-list sources;
- discover or list retained discussions;
- retrieve a discussion/root summary;
- retrieve direct children of a message lazily;
- retrieve an ancestor path to the stored root;
- retrieve a bounded connected discussion projection;
- search retained messages by useful metadata and text criteria supported by the existing stack;
- inspect why a message was retained;
- identify incomplete/orphaned material and missing-parent references; and
- retrieve the underlying artifact detail and stored content.

Codex should select interfaces consistent with existing repository, service, CLI, and browser conventions. Do not create an unrestricted general-purpose graph-query language.

---

## Initial Functional Scope

The delivered vertical slice must prove the capability with one configured Linux kernel development mailing list, initially the Linux block-layer list, using a Lore/public-inbox-compatible retrieval surface.

The implementation must support fixture-backed deterministic tests and a separately gated live proof against the public source.

The live proof must use narrow, reviewable bounds and must not acquire a large corpus merely to demonstrate functionality.

A useful proof should show:

1. bounded seed discovery;
2. connected ancestor closure;
3. at least one branching discussion structure;
4. immutable message retention;
5. SQLite relationship organization;
6. idempotent repeated acquisition;
7. offline query/rebuild behavior; and
8. browser navigation and content inspection through the shared artifact browser.

---

## Required Operator Behavior

Codex must extend the existing operator interfaces rather than invent an unrelated parallel workflow.

Operators must be able to:

- preview or dry-run a bounded acquisition before persistence;
- see seed count, proposed context expansion, applicable limits, and warnings;
- execute the bounded acquisition explicitly;
- inspect the acquisition manifest and inclusion reasons;
- query retained discussions and messages without network access; and
- distinguish connected, truncated, incomplete, and quarantined results.

Exact command names, API routes, and UI controls are implementation decisions, provided they are coherent with existing conventions and fully documented.

---

## Failure and Safety Behavior

The implementation must fail safely and diagnostically for at least:

- unavailable archive service;
- invalid or unsupported source configuration;
- malformed archive response;
- missing or malformed Message-ID;
- missing required ancestor or connector;
- conflicting messages that claim the same external identifier;
- cycle-producing or otherwise invalid reply metadata;
- configured seed or expansion limit reached;
- unsupported MIME/content representation;
- SQLite transaction or integrity failure; and
- offline query when required structured state is absent or invalid.

Partial persistence must not leave a discussion falsely classified as connected or complete.

Where practical, persistence of one acquisition unit should be transactional. Codex must document the chosen acquisition-unit and rollback semantics.

---

## Explicit Non-Goals

This task does not include:

- mirroring LKML or the complete history of any mailing list;
- continuous daemon ingestion;
- an always-on mail subscription or IMAP mailbox collector;
- a graph database or external graph service;
- automatic concept extraction or AI summarization;
- participant identity resolution across aliases and addresses;
- comprehensive patch parsing or application;
- full cross-list federation;
- broad historical backfill;
- graph visualization as a separate product;
- deletion or pruning policies for already admitted evidence;
- unrestricted graph analytics; or
- redesign of completed TASK-014, TASK-018, TASK-021, or TASK-022 capabilities beyond the extensions needed for this task.

---

## Implementation Freedom

Codex owns implementation choices that do not violate the requirements above, including:

- module and package boundaries;
- SQLite schema and migration details;
- repository and service interfaces;
- use of recursive SQL versus materialized relationship projections;
- retrieval protocol details supported by Lore/public-inbox;
- MIME parsing libraries;
- batching and transaction boundaries;
- dry-run representation;
- browser route and component structure;
- fixture organization;
- exact CLI syntax;
- exact completeness-state names; and
- whether deterministic patch-series support belongs in the initial implementation or is deferred with explicit evidence that reply-tree capability is complete.

Prefer the smallest coherent architecture that satisfies the functional and evidentiary requirements. Avoid speculative generalization.

---

## Acceptance Criteria

TASK-023 is complete only when all of the following are demonstrated:

1. A configured Linux block-layer mailing-list source can perform bounded seed discovery against fixtures and through a separately gated live path.
2. Normal acquisition cannot implicitly import the complete source archive.
3. Every persisted discussion classified as connected satisfies the stored path-to-root invariant.
4. No test or live proof persists a disconnected segment as a complete connected discussion.
5. Missing required connector context causes explicit rejection, incompleteness, or quarantine rather than silent subject-based attachment.
6. Discovery limits and expansion limits preserve intermediate connectivity and report any descendant-frontier truncation.
7. Each retained message has immutable artifact evidence, provenance, external identity handling, and structured mailing-list metadata.
8. Repeated acquisition is idempotent for artifacts, messages, and relationships.
9. Acquisition manifests identify seeds, contextual messages, applicable limits, and inclusion reasons.
10. SQLite-backed queries can traverse ancestors, direct replies, and bounded discussion projections without application code depending on raw database layout.
11. Header-derived and inferred relationships are distinguishable.
12. Retained mailing-list structured state can be rebuilt offline from repository evidence and durable metadata.
13. The existing artifact browser presents a mailing-list discussion projection alongside the existing firm/artifact projection.
14. The browser lazily navigates branching message structures and reuses shared artifact detail/content behavior.
15. Browser and query results visibly distinguish connected, truncated, incomplete, and quarantined states.
16. Existing SEC acquisition, SQLite repository, artifact browser, and baseline validation continue to pass without regression.
17. Documentation explains source configuration, bounded acquisition, connectivity semantics, operator workflow, rebuild behavior, and known limitations.
18. A complete review package is generated and independently inspectable.

---

## Required Verification Package

Codex must provide a complete TASK-023 review package using the repository's established review-package conventions.

The package must include at minimum:

### Repository evidence

- task ticket;
- branch and HEAD identity;
- reviewed base commit;
- changed-file inventory;
- staged or committed diff evidence as appropriate;
- repository status; and
- confirmation that generated review artifacts are not accidentally included in product changes unless repository conventions require them.

### Design evidence

- concise implementation summary;
- implemented architecture and major boundaries;
- SQLite migration/schema summary;
- relationship and connectivity model;
- acquisition-unit and transaction semantics;
- bounded discovery and expansion semantics;
- browser projection design;
- implementation alternatives considered;
- why a separate graph database was not introduced; and
- known limitations and deferred work.

### Deterministic fixture evidence

Fixtures and tests must demonstrate at least:

- a linear ancestor chain;
- a branching reply tree;
- multiple seeds converging on one retained connected component;
- a seed whose ancestor lies outside the discovery date window but is acquired for closure;
- a missing intermediate ancestor;
- an orphan or malformed-parent case;
- a cycle-producing invalid case;
- descendant-frontier truncation that preserves connectivity;
- prevention of a disconnected retained segment;
- duplicate acquisition/idempotency;
- conflicting external identity handling;
- offline reconstruction; and
- browser/query projection behavior.

### Live bounded proof

The live proof must be opt-in and must record:

- exact command or operator action;
- source and bounded selection criteria;
- seed count;
- expanded/context message count;
- persisted message and relationship count;
- inclusion-reason breakdown;
- connectivity validation result;
- truncation or incompleteness result;
- repeated-run idempotency result; and
- enough identifiers and metadata to reproduce or review the proof without embedding unnecessary bulk content.

The live proof must not rely on importing a broad historical corpus.

### Validation outputs

Include exact commands and complete outputs for:

- focused TASK-023 tests;
- repository lint/static checks;
- schema/migration validation;
- baseline/document consistency checks;
- full test suite or canonical `make validate` equivalent;
- offline rebuild verification;
- browser/API smoke verification; and
- review-package integrity verification.

### Negative proof

The package must explicitly demonstrate that:

- an unbounded archive-import request is unavailable or rejected;
- a missing connector cannot yield a discussion marked complete;
- a limit cannot create a disconnected complete component;
- normalized subject alone cannot attach messages authoritatively;
- browser code does not independently infer the graph from raw messages; and
- no graph database or second authoritative persistence engine was introduced.

---

## Documentation Requirements

Update the repository's authoritative documentation and baseline records as required by project conventions.

Documentation must clearly explain:

- the purpose and scope of development-mailing-list sources;
- why the remote archive remains the broad corpus while RFI retains a selected evidence set;
- how seed discovery differs from context closure;
- the connected-component admission invariant;
- how incomplete and quarantined material are handled;
- relationship authority and inference labeling;
- operator limits and dry-run behavior;
- how mailing lists appear in the shared artifact browser;
- offline reconstruction; and
- limitations of the initial Linux block-layer vertical slice.

---

## Completion Report

Codex's completion report must include:

- branch and commit status;
- concise functional summary;
- files changed grouped by responsibility;
- implemented operator workflow;
- connectivity and bounded-acquisition behavior;
- browser integration summary;
- validation results with exact pass counts;
- live-proof outcome;
- review-package path and integrity result;
- deviations from this ticket, if any;
- known limitations; and
- confirmation that no commit, push, merge, branch deletion, or cleanup was performed unless separately authorized.
