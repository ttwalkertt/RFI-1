# TASK-025 — Revisioned Multi-Level Artifact Streams and Configuration

## Status

Complete

## Summary

Add a first governed, bounded slice of revisioned, multi-level artifact streams to RFI-1.

A stream must be able to consume either:

- an external governed source; or
- one or more upstream RFI streams.

Streams may fan out into multiple downstream streams, apply successive filtering, and materialize distinct artifact memberships over the same immutable evidence. Stream dependencies must form a validated directed acyclic graph. The implementation must include an operator-facing configuration page, bounded execution, durable lineage, deterministic rebuildability, and artifact-browser integration.

The initial operational use case is Linux kernel development mailing-list intelligence, beginning with the Linux block-layer archive. The architecture must remain suitable for a finite but broad family of repository-owned artifact schemas, including regulatory filings and other document-oriented sources, without becoming an unbounded workflow engine or universal query language.

Implementation details remain with Codex unless constrained below by an architectural invariant, required behavior, or verification obligation.

---

## Context

RFI-1 now has:

- immutable content-addressed artifacts and provenance;
- a SQLite structured-state repository;
- bounded Linux mailing-list acquisition and discussion organization;
- firm-oriented acquisition and SEC filing artifacts;
- a shared artifact browser with firm and mailing-list projections; and
- revisioned operator configuration patterns.

TASK-023 established mailing-list acquisition, storage, discussion connectivity, query, and browser projection. It intentionally stopped short of providing a complete operator-facing source and filtering configuration workflow.

The next requirement is broader than a single mailing-list source form. RFI-1 must support multi-level filtering and separate artifact streams derived from one upstream stream. This implies that streams are first-class, revisioned, materialized repository objects that may serve as either source or sink in a bounded processing graph.

The implementation must preserve one copy of immutable evidence while allowing many independently configured stream memberships and complete provenance for why each artifact or connected context belongs to each stream.

---

## Objective

Implement the first governed stream graph and configuration vertical slice.

The task must allow an operator to:

1. configure an external Linux block-layer mailing-list stream;
2. define bounded seed-selection criteria such as keywords, authors, subject/title patterns, dates, and supported structured attributes;
3. configure schema-supported context expansion, including connected mailing-list discussion context;
4. create one or more derived streams that consume an upstream stream;
5. fan out one upstream stream into multiple downstream streams;
6. validate and persist revisioned stream definitions;
7. prevent dependency cycles;
8. execute streams explicitly in dependency order;
9. materialize durable, provenance-rich memberships without copying immutable artifact bytes; and
10. browse streams and their retained artifacts through the existing artifact browser.

The first implementation must prove that the stream substrate is not email-specific by exercising the same generic membership and lineage mechanisms against at least one second artifact schema using repository fixtures or existing SEC artifacts.

---

## Architectural Requirements

### 1. Streams are first-class revisioned repository objects

An RFI stream is a revisioned, bounded, materialized projection over either:

- one governed external source; or
- one or more upstream streams.

A stream definition must have stable repository identity and revision history. At minimum, the repository must retain enough information to determine:

- stream identity, name, and description;
- enabled/disabled state;
- input kind and input identities;
- artifact schema or schema capability expectations;
- selection policy;
- expansion policy;
- execution bounds;
- revision identity and timestamps; and
- the dependencies and downstream consumers associated with the revision.

The browser and execution service must use repository contracts, not browser-only configuration state.

### 2. Streams form a directed acyclic graph

A stream may consume another stream and may feed multiple downstream streams.

The configured dependency topology must be a DAG.

The implementation must:

- prohibit direct self-reference;
- detect indirect cycles before saving or enabling a revision;
- reject invalid topology fail-closed with an actionable explanation;
- support fan-out from one upstream stream to multiple downstream streams;
- support more than one upstream stream where compatible with the first-slice execution model; and
- expose bounded dependency and consumer information through repository/query contracts.

Do not introduce a general workflow scheduler, message broker, or distributed orchestration system.

### 3. Immutable artifacts are not duplicated by downstream streams

A downstream stream normally emits memberships over existing immutable artifacts or connected contexts. It must not copy authoritative artifact bytes merely because an artifact belongs to another stream.

The repository must distinguish:

- authoritative artifacts;
- stream definitions and revisions;
- stream execution runs;
- stream memberships; and
- membership lineage and inclusion reason.

An artifact may belong to many streams simultaneously.

Policy changes may change downstream membership without deleting the underlying immutable artifact or unrelated memberships.

Synthetic summaries, extracted claims, generated reports, and other transformed artifacts are out of scope for this task.

### 4. Bounded schema generality

Design the stream engine for a finite but broad family of repository-owned artifact schemas rather than for Linux mailing-list messages alone.

The first implementation may use mailing-list-native context expansion, but these concerns must not depend on email-specific fields or reply-tree semantics:

- stream identity and revisioning;
- dependency topology;
- selection-policy representation;
- execution lifecycle;
- membership materialization;
- lineage and inclusion reason;
- rebuild behavior;
- query contracts; and
- browser stream navigation.

The implementation must not create:

- an unlimited workflow language;
- arbitrary executable filters;
- operator-authored SQL or Python;
- untyped JSON-path filtering over arbitrary fields; or
- a universal document schema that discards native typing.

### 5. Repository-owned artifact projection contract

Selection must operate over an explicit repository-owned artifact projection or equivalent typed contract.

The projection must be broad enough to support demonstrated and anticipated document families while remaining bounded. It should support capabilities equivalent to:

- artifact identity;
- artifact schema/type identity;
- source identity;
- effective timestamp;
- title or subject;
- searchable text where available;
- authors or participants where available;
- firm/entity associations where available;
- registered structured attributes;
- relationship or context identity where available; and
- completeness/connectivity state where applicable.

Codex may refine the exact representation.

Native artifact adapters or schema providers must map their records into the supported projection without mutating authoritative artifacts.

### 6. Explicit schema capabilities and registered attributes

Each supported artifact schema must declare the filter and expansion capabilities it provides.

The first slice must support typed predicates equivalent to:

- text or phrase matching;
- author or participant matching;
- title or subject pattern matching;
- date bounds;
- artifact schema/type matching;
- source matching;
- registered structured-attribute equality or set membership;
- context/completeness predicates where supported; and
- Boolean composition using bounded `all`, `any`, and `not` groups.

Schema-specific fields must be exposed through a registered attribute catalog or equivalent typed capability mechanism. Examples include:

- `mail.list_id`;
- `mail.patch_version` where supported;
- `sec.form_type`;
- `sec.accession`;
- future fields such as publication venue, patent assignee, or repository identity.

Unsupported predicates must fail validation explicitly. They must not silently match nothing.

### 7. Selection and expansion are distinct

The stream system must distinguish:

1. **selection** — determine direct matches using the configured typed policy; and
2. **context expansion** — apply a schema-supported expansion strategy after a match.

Selection may be generic across supported schemas. Expansion remains schema-specific.

For mailing-list messages, the first implementation must support a connected-discussion expansion mode consistent with TASK-023's connectivity guarantees. A directly matching message may cause its connected retained discussion context to enter the output stream.

For schemas that do not support context expansion, `none` must be a valid policy.

The core stream layer must invoke registered expansion behavior rather than embed mailing-list reply-tree logic.

### 8. Governed mailing-list external source configuration

The first live external stream must reference a governed Lore/public-inbox-compatible Linux
mailing-list source, initially `linux-block`.

The external-source profile owns:

- source identity and display name;
- provider and protocol settings;
- archive base or equivalent endpoint;
- list/archive identifier;
- User-Agent, timeout, response-size bound, pacing, concurrency, retries, and backoff;
- enabled state;

The stream revision references that source and owns only:

- stream identity and display name;
- keywords or phrases;
- authors or participants;
- subject/title patterns;
- date bounds;
- hard maximum selected-artifact count;
- hard maximum expanded-message count;
- ancestor-closure behavior required by TASK-023;
- supported descendant/context expansion settings; and
- validation state.

There must be no normal unbounded archive-mirroring operation.

TASK-025 does not implement a durable Lore cursor. `initial_date` and `incremental` are therefore
absent from its operator-visible stream contract and UI. Live acquisition remains explicit and
bounded, but repeated polling can repeat network retrieval. It is not a production-ready polling
facility.

### 9. Multi-level filtering and fan-out

The first slice must allow one external mailing-list stream to feed multiple derived streams.

At minimum, demonstrate a topology equivalent in capability to:

```text
linux-block
  ├── zoned-storage
  └── blk-mq
```

Each derived stream must have its own revisioned policy and durable memberships.

A direct match in a derived mailing-list stream may retain the complete connected context according to its expansion policy. Membership metadata must distinguish the direct matches from context-only inclusions.

### 10. Membership lineage and inclusion reason

Every materialized membership must answer why it exists.

At minimum, durable lineage must identify:

- stream identity and revision;
- execution run identity;
- artifact or context identity;
- direct or context-only inclusion reason;
- upstream stream identity where applicable;
- upstream membership or seed identity where applicable;
- policy revision used;
- expansion strategy used; and
- any relevant truncation or completeness classification.

The exact vocabulary is left to Codex, but it must distinguish cases equivalent to:

- direct match;
- inherited upstream candidate;
- ancestor/connector context;
- descendant context;
- series/context expansion;
- manual inclusion, if Codex includes it; and
- no-longer-matching or superseded membership state where needed for revision history.

### 11. Materialized projections and explicit execution

Streams are durable materialized repository projections, not transient queues.

For this first slice:

- execution is operator-initiated;
- upstream dependencies must execute or be validated in topological order;
- downstream propagation must be explicit and bounded;
- execution runs must be durable and inspectable;
- repeated execution against unchanged inputs and revisions must be idempotent; and
- failed runs must not partially publish misleading membership state.

Automatic background scheduling and continuous propagation are out of scope.

### 12. Deterministic rebuildability

Stream memberships and lineage must be rebuildable from retained authoritative artifacts, durable source/acquisition metadata, stream revisions, and execution metadata without contacting remote providers, except where the original run depended on evidence that was never retained.

Rebuild must preserve or reproducibly derive:

- membership identity;
- stream and revision association;
- direct/context inclusion classification;
- dependency lineage;
- completeness/truncation state; and
- deterministic ordering.

### 13. SQLite remains the authoritative structured backend

Use the existing SQLite structured-state repository and migration conventions.

Do not introduce:

- a graph database;
- a second authoritative persistence engine;
- an external rules service;
- a message broker; or
- a browser-only policy store.

Codex may choose relational tables, recursive CTEs, materialized projections, and repository abstractions consistent with existing architecture.

### 14. Operator-facing Stream Configuration page

Deliver a usable administrative configuration page as part of this task.

The page must support at least:

- listing existing streams;
- creating an external-source stream;
- creating a derived stream from one or more compatible upstream streams;
- editing identity, name, description, and enabled state;
- selecting source type and upstream streams;
- configuring typed filters;
- composing bounded `all`, `any`, and `not` groups;
- selecting schema-supported expansion behavior;
- setting execution bounds;
- validating source settings, policy capabilities, and DAG topology;
- saving a revisioned configuration;
- viewing current revision and revision history;
- viewing upstream dependencies and downstream consumers;
- previewing a bounded set of matches or fixture-backed evaluation before saving or running;
- explicitly running a selected stream; and
- explicitly running a bounded dependency chain in topological order.

The page must render controls from repository/schema capability contracts wherever practical. It must not hard-code the entire page around email-only fields.

Mailing-list-specific source and expansion controls may appear only when the selected schema/provider supports them.

No configuration action may trigger an implicit profile write outside the explicit save operation.

### 15. Artifact-browser integration

Extend the existing artifact browser rather than creating a parallel browser.

The browser must allow an operator to navigate:

- streams;
- upstream/downstream lineage;
- stream runs;
- retained artifact or discussion memberships; and
- the underlying immutable artifact detail/content.

The browser must distinguish direct matches from context-only memberships and show why an artifact belongs to the selected stream.

For mailing-list streams, browsing must continue to preserve connected discussion semantics from TASK-023.

Existing firm-oriented and mailing-list projections must remain functional.

### 16. Cross-schema proof

Demonstrate that the generic stream engine, membership model, lineage, and browser/query contracts work for at least one non-mail artifact schema.

This proof may use deterministic fixtures or existing retained SEC artifacts. It does not require a new live provider.

A sufficient example would be a derived stream equivalent to:

```text
annual-regulatory-reports
  input: retained firm artifacts
  filter:
    schema = sec.filing
    sec.form_type in [10-K, 20-F]
  expansion: none
```

The proof must use the same generic execution and lineage mechanisms as mailing-list-derived streams.

### 17. Compatibility and migration

Existing TASK-021 through TASK-024 workspaces must migrate according to current repository policy.

Existing artifact acquisition, source profiles, pull results, mailing-list discussion projection, and browser behavior must remain intact.

Do not silently reinterpret existing mailing-list sources or memberships as configured streams unless the migration is deterministic, documented, and verified.

---

## Initial Functional Scope

The first slice must include:

- one external Lore/public-inbox-compatible stream configuration;
- one or more derived streams sourced from another stream;
- fan-out from one upstream stream;
- typed predicates for keywords/text, authors/participants, title/subject, dates, schema/type, source, and registered attributes;
- bounded Boolean composition;
- schema capability validation;
- mailing-list connected-discussion expansion;
- no-expansion support for a second schema;
- DAG validation;
- revisioned stream definitions;
- explicit topological execution;
- durable runs, memberships, and lineage;
- deterministic offline rebuild;
- administrative configuration and execution page;
- artifact-browser integration; and
- a cross-schema proof using SEC artifacts or fixtures.

---

## Explicit Non-Goals

Do not implement in this task:

- a universal workflow engine;
- arbitrary executable user filters;
- SQL, Python, JavaScript, or regular-expression programs supplied by operators beyond any safely bounded pattern support already conventional in the repository;
- continuous background scheduling;
- distributed execution;
- Kafka or another message broker;
- a graph database;
- semantic embeddings or vector search;
- LLM classification or summarization;
- transformed/synthetic artifact generation;
- automatic report generation;
- unrestricted multi-source joins across incompatible schemas;
- retention deletion or garbage collection;
- full LKML archive mirroring;
- automatic cross-list federation;
- broad participant identity resolution; or
- implementation of every anticipated artifact schema.

---

## Functional Requirements

### A. Stream administration

The operator can create, validate, save, revise, enable, disable, and inspect streams from the admin console.

### B. Linux block-layer external stream

The operator can configure a bounded `linux-block` external stream and preview its configured criteria without importing the complete archive.

### C. Derived streams

The operator can create at least two derived streams from `linux-block`, each with independent policy and memberships.

### D. Multi-level filtering

A derived stream can serve as the upstream input to another derived stream, subject to DAG validation and compatible schema capabilities.

### E. Connected context

When a mailing-list message matches and connected-discussion expansion is enabled, the output stream receives a connected context projection without disconnected segments being presented as complete.

### F. Cross-schema operation

The same generic engine can materialize and browse a non-mail stream over SEC artifacts or deterministic non-mail fixtures.

### G. Explainability

The operator can inspect why an artifact or discussion belongs to a stream, which policy revision selected it, and which upstream membership or direct match caused inclusion.

### H. Idempotency

Re-running an unchanged stream over unchanged inputs does not duplicate artifacts, runs incorrectly, memberships, or lineage records.

### I. Failure isolation

Invalid configuration, unsupported predicates, cycles, provider failures, and incomplete mailing-list context fail explicitly without publishing misleading final memberships.

---

## Query and Service Requirements

Expose bounded repository/service contracts sufficient to:

- list streams;
- retrieve a stream and current revision;
- retrieve revision history;
- list dependencies and consumers;
- validate a draft stream definition;
- preview bounded matches;
- execute one stream;
- execute a bounded dependency chain in topological order;
- inspect run status and result summary;
- list memberships with bounded pagination;
- inspect membership lineage and inclusion reason;
- retrieve direct-match versus context-only classifications;
- rebuild materialized memberships offline;
- list schema capabilities and registered attributes; and
- support artifact-browser navigation.

Do not expose an unrestricted graph-query or arbitrary rules-execution API.

---

## CLI Requirements

Provide CLI operations consistent with existing conventions for at least:

- listing streams;
- validating stream configuration;
- previewing a bounded stream evaluation;
- running one stream;
- running a bounded dependency chain;
- inspecting a run;
- listing memberships; and
- rebuilding stream projections offline.

Exact command names and grouping are left to Codex.

The CLI and admin page must use the same service and repository contracts.

---

## Acceptance Criteria

TASK-025 is complete only when all of the following are demonstrated:

1. A fresh workspace can create and save a bounded external `linux-block` stream through the admin page.
2. The stream configuration supports keywords, authors/participants, title/subject patterns, date bounds, and hard acquisition/expansion limits.
3. The operator can create at least two independent derived streams from `linux-block`.
4. A derived stream can itself serve as the source of another derived stream.
5. A cycle attempt is rejected before persistence or enablement.
6. Unsupported schema predicates are rejected explicitly.
7. The stream engine does not depend on email-specific fields for generic selection, execution, membership, lineage, or browsing.
8. Mailing-list connected-discussion expansion preserves TASK-023 connectivity invariants.
9. One immutable artifact may belong to multiple streams without byte duplication.
10. Membership records explain direct versus context-only inclusion and identify upstream lineage.
11. Repeated unchanged execution is idempotent.
12. Failed execution does not publish a misleading partial final membership set.
13. Stream definitions and memberships are revisioned/durable and can be rebuilt offline.
14. The admin page shows stream topology, validation, revision history, preview, and explicit run operations.
15. The artifact browser shows streams, memberships, lineage, inclusion reason, and underlying artifact content.
16. Existing firm, pull, source-profile, artifact-browser, and TASK-023 mailing-list behavior remains intact.
17. A second, non-mail artifact schema is filtered and materialized through the same generic engine and lineage contracts.
18. No normal operation can mirror the complete Linux mailing-list archive without explicit bounded configuration.
19. No graph database, second structured store, message broker, or browser-only policy representation is introduced.
20. A complete review and verification package is produced.

---

## Verification Requirements

Provide a complete verification package consistent with the established RFI-1 workflow.

The package must include:

### 1. Focused functional proof

Demonstrate:

- external stream creation and revision;
- derived stream creation;
- multi-level derivation;
- fan-out;
- typed filtering;
- connected mailing-list expansion;
- cross-schema execution;
- explicit topological execution;
- membership lineage; and
- offline rebuild equivalence.

### 2. Negative architectural proof

Demonstrate that:

- cycles are rejected;
- self-reference is rejected;
- unsupported predicates fail validation;
- unbounded archive mirroring is unavailable;
- disconnected mailing-list fragments cannot be presented as complete;
- browser-only unsaved policy state cannot affect execution;
- downstream stream membership does not duplicate immutable content;
- failed runs do not partially publish final memberships; and
- no second persistence boundary is introduced.

### 3. Browser proof

Use a real browser or established browser harness to prove:

- stream listing and creation;
- capability-driven controls;
- governed Linux mailing-list source selection and policy display;
- derived stream configuration;
- cycle-validation feedback;
- revision history;
- bounded preview;
- explicit run;
- topology/dependency display;
- artifact-browser stream navigation;
- membership explanation; and
- preservation of existing browser projections.

Capture browser warnings and errors and require zero unexpected warnings or errors.

### 4. Persistence and migration proof

Demonstrate:

- SQLite migration from the current schema;
- durable stream revisions;
- durable runs and memberships;
- idempotent rerun;
- offline rebuild;
- recovery from interrupted or failed publication; and
- unchanged authoritative artifact hashes when artifacts enter multiple streams.

### 5. Regression validation

Run:

- focused TASK-025 tests;
- stream, mailing-list, storage, pull, source-profile, and artifact-browser regressions;
- the complete repository validation target; and
- isolated copied-tree validation where supported by current workflow.

### 6. Review artifact contents

Include at least:

- task ticket;
- implementation summary;
- architectural decision summary;
- exact changed-file inventory and rationale;
- validation commands and outputs;
- database/migration evidence;
- stream topology fixtures;
- browser proof;
- cross-schema proof;
- negative proofs;
- repository status;
- cumulative patch or equivalent diff evidence;
- ZIP integrity listing; and
- SHA-256 checksum.

---

## Documentation Requirements

Update the repository documentation to describe:

- the stream abstraction;
- external versus derived streams;
- DAG topology and cycle prevention;
- artifact projection and schema capabilities;
- typed filter policy;
- schema-specific expansion;
- stream revisions and execution runs;
- membership lineage;
- offline rebuild;
- operator configuration and execution workflow;
- artifact-browser behavior; and
- explicit non-goals and deferred capabilities.

Add an ADR if the repository's architectural decision conventions indicate one is warranted.

Update the design baseline and roadmap/task index according to repository policy.

---

## Completion Report

At completion, report:

1. implementation summary;
2. architectural decisions made;
3. stream and schema capabilities delivered;
4. files modified;
5. migration behavior;
6. validation results;
7. browser proof result;
8. cross-schema proof result;
9. review package location and checksum;
10. known limitations; and
11. recommendations for the next increment.

Do not commit, push, merge, stage, create or delete branches, or perform repository cleanup.

## Completion record

Completed 2026-07-19.

- Added stable, revisioned external and derived artifact streams with durable DAG edges, typed
  capability-driven policies, explicit bounded execution, atomic membership publication, lineage,
  idempotent reruns, and network-free rebuild.
- Added `mail.message` and `sec.filing` schema adapters, including fail-closed connected-discussion
  expansion for complete TASK-023 mailing-list evidence and a generic SEC membership proof.
- Added the `/streams` operator editor, REST and CLI workflows, and a read-only Artifact streams
  projection in the existing artifact browser without changing firm or mailing-list authority.
- Migrated the single SQLite structured-state authority from schema version 2 through version 4;
  version 4 adds explicit mailing acquisition lifecycle outcomes. No
  second store, graph database, scheduler, archive mirror, or artifact-byte duplication was added.
- Focused and regression tests, deterministic fixture proof, complete project validation, isolated
  copied-tree checks, and real in-app-browser proof pass with no unexpected browser warnings or
  errors.
- Review directory: `.artifacts/review/TASK-025`.
- Review archive and checksum: `.artifacts/review/TASK-025-review.zip` and
  `.artifacts/review/TASK-025-review.zip.sha256`.

Known limitations: provider acquisition remains an explicit upstream TASK-023 operation; stream
execution is explicit rather than scheduled; and the SEC proof uses a deterministic adapter-backed
projection rather than automatically projecting every historical provider record.

### Architectural Status Summary

| Subsystem | Responsibility | Status |
|---|---|---|
| Stream contracts and service | Validate capabilities and policies, order the DAG, preview, execute, and rebuild | Complete |
| Stream repository | Retain revisions, edges, runs, publication plans, memberships, and lineage | Complete |
| SQLite schema | Own version-4 stream/run state and migrate supported version-1/2/3 repositories | Complete |
| Mail projection and expansion | Select retained messages and expand only complete connected discussions | Complete |
| SEC projection | Prove generic filtering and membership over a second schema | Complete for deterministic adapter-backed proof |
| Stream operator UI and REST | Configure, validate, preview, save, execute, and inspect streams | Complete |
| Stream CLI | Provide explicit scriptable stream lifecycle and inspection operations | Complete |
| Artifact browser | Navigate stream topology, runs, membership reasons, lineage, and retained content | Complete |
| Governed external-source profile | Own provider/list/endpoint/User-Agent/transport policy | Complete for Lore/public-inbox |
| External acquisition | Explicit bounded retrieval before stream evaluation, with governed pacing/retry and truthful run outcomes | Complete for explicit Message-ID acquisition; durable cursor/polling deferred |
| Scheduling and continuous propagation | Automate acquisition or downstream execution | Deferred; explicit non-goal |

The implementation keeps immutable artifact bytes and all structured stream state in their existing
authorities. It introduces no universal workflow engine, executable query language, background
execution, or new persistence boundary.

### Hardening addendum — 2026-07-20

- Made the governed external-source profile the executable authority for provider, endpoint, list
  identity, User-Agent, timeout, response size, pacing, source-wide in-process concurrency, retry,
  and backoff policy. Stream revisions retain only source identity, selection, expansion,
  dependencies, and output bounds.
- Added bounded Lore handling for HTTP 429/503, `Retry-After`, timeout, response-size rejection,
  retry exhaustion, and per-source policy variance.
- Added explicit `succeeded`, `partial`, `retryable_failure`, and `terminal_failure` acquisition-run
  lifecycle states. `truncated` now describes valid bounded/incomplete results, never an empty
  transport failure.
- Removed `initial_date` and `incremental` from the active stream contract and UI because this task
  does not implement a durable archive cursor. Explicit live acquisition may repeat network work
  and is not production-ready polling.
- Moved mail projection, schema capability, and connected-context behavior behind a finite
  repository-owned registry; the generic stream service and repository contain no mailing-list
  table or reply-tree dependency.
- Added permanent recomputation coverage proving that a new no-match run changes only the current
  stream view and preserves immutable bytes, artifact rows, acquisition provenance, historical
  memberships, and lineage.
- Preserved the original review package and produced a separate hardened review package so prior
  evidence remains immutable: `.artifacts/review/TASK-025-HARDENED` and
  `.artifacts/review/TASK-025-HARDENED-review.zip`.
