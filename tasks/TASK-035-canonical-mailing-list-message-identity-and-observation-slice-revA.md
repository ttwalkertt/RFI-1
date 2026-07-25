# TASK-035 — Canonical Mailing-List Message Identity and Acquisition Observation Slice

## Status

Ready

## Objective

Implement the smallest useful vertical slice of the global canonical mailing-list message-store design:

1. establish a repository-owned, global canonical identity for retained mailing-list messages; and
2. record each acquisition run's per-message observation independently from that canonical message.

The completed slice must prove that overlapping acquisitions can reuse one retained message while preserving distinct acquisition evidence for every run.

This task is intentionally narrow. It should create a sound implementation seam for later parser, relationship, discussion, patch-series, projection-version, and migration work without implementing those capabilities now.

## Architectural Context

The current mailing-list implementation uses source-scoped message and document identities. As a result, the same `Message-ID` acquired through overlapping runs or multiple mailing-list sources may be represented as separate mailing-list records even when the retained bytes are identical.

The approved design direction is:

```text
immutable artifact
        ↑
canonical mailing-list message
        ↑
per-run acquisition observation
```

The canonical message answers:

> What retained message does the repository recognize for this valid normalized `Message-ID`?

The acquisition observation answers:

> What did this particular run discover or materialize, and how was the canonical content obtained for this run?

Canonical existence must not erase or replace run-specific acquisition history.

## Required Outcomes

### 1. Global canonical message identity

Introduce the minimal durable repository representation needed to resolve a valid normalized mailing-list `Message-ID` to one canonical retained message.

The representation must:

> A canonical mailing-list message represents successfully retained RFC822 message content. Historical unavailable or tombstone observations remain valid acquisition evidence but do not establish, reserve, or conflict with canonical message identity. Such observations may legitimately have no canonical message reference until a later successful acquisition materializes the retained message.


- use a stable repository-owned canonical message identifier;
- retain the normalized external `Message-ID` as a unique external identity;
- reference the existing immutable artifact and logical document records rather than duplicating artifact bytes;
- not include `source_id` in canonical identity;
- permit the same canonical message to be referenced by observations from different runs and, where valid, different mailing-list sources;
- fail closed when the same normalized `Message-ID` is encountered with conflicting retained bytes;
- preserve enough information to inspect and verify the canonical mapping.

The exact table name, identifier format, repository API shape, and placement are implementation decisions, provided the architectural invariants are preserved.

### 2. Independent acquisition observations

Introduce or adapt the minimal per-run/per-message observation representation needed to persist the acquisition outcome for each observed message. The persisted observation must distinguish at least:

- whether content was fetched during the run;
- whether an existing retained artifact was reused;
- whether canonical identity was newly established or reused;
- unavailable or tombstone observations;
- discovery or inclusion reason;
- the run and source that made the observation;
- the normalized external `Message-ID`;
- the referenced canonical message, artifact, and document, where applicable.

Each acquisition run must retain its own observation even when it reuses canonical content from a prior run.

Codex may adapt the existing `mailing_list_run_items` model rather than introducing a parallel replacement table when that is the safer and smaller implementation. The final design must leave one clear authority for active per-run observations and must not create ambiguous dual-write authorities.

### 3. Acquisition-path integration

Integrate canonical resolution into the normal mailing-list acquisition path.

Expected behavior:

1. Normalize and validate the discovered `Message-ID`.
2. Resolve whether the repository already has a canonical message for it.
3. If absent:
   - fetch and retain the message through the existing artifact/document substrate;
   - create the canonical mapping;
   - record this run's observation as newly materialized.
4. If present and the retained bytes are valid:
   - reuse the canonical artifact/document;
   - do not claim that this run downloaded or created the artifact;
   - record this run's independent reuse observation.
5. If the normalized `Message-ID` resolves to conflicting bytes:
   - fail closed for that message or bounded run according to the existing error model;
   - retain actionable diagnostic evidence;
   - do not silently replace canonical content.

> Message-ID normalization used for canonical lookup, canonical registration, migration/backfill, repository validation, and conflict detection shall be performed by one repository-owned normalization implementation. Independent normalization behavior in separate acquisition or migration paths is not permitted.

> During normal acquisition publication, creation or verification of canonical identity and persistence of the corresponding acquisition observation shall succeed or fail as one structured repository transaction. A successful canonical registration must not be committed without the observation that caused it.

The implementation should preserve existing acquisition limits, relationship acquisition behavior, coverage semantics, tombstone behavior, operator fetch history, and derived discussion behavior unless a narrowly required compatibility change is necessary.

### 4. Existing data and compatibility

Provide the smallest safe compatibility approach for repositories created before TASK-035.

Codex has latitude to choose among:

- an additive schema migration with deterministic backfill;
- lazy canonical registration when existing messages are first encountered;
- a bounded combination of both.

The chosen approach must:

- avoid destructive migration;
- detect pre-existing conflicts before collapsing source-scoped records into one canonical identity;
- preserve existing artifacts, documents, runs, run items, and discussion projections;
- where conflicting historical candidates are detected, preserve the existing records without collapsing them into one canonical identity; such conflicts must remain inspectable and prevent silent canonical registration for that Message-ID until resolved;
- leave repository validation and backup/restore behavior intact;
- be explained in the completion report.

A full retirement of existing mailing-list tables is out of scope.

## Architectural Invariants

The implementation must preserve all of the following:

1. **Artifact authority remains unchanged.** Exact bytes remain owned by the existing content-addressed artifact store.

2. **Canonical identity is global to the mailing-list corpus.** `source_id` is provenance, not part of canonical identity.

3. **Message-ID is external identity, not the repository primary key.** The repository owns the canonical message identifier.

4. **One canonical message may have many run observations.**

5. **Reuse does not imply download.** A reuse observation must not increment or report newly created artifact counts.

6. **Acquisition evidence is independent.** Later runs do not overwrite, merge away, or inherit prior run observations.

7. **Identical Message-ID plus identical bytes reuses canonical content.**

8. **Identical Message-ID plus different bytes fails closed.** No last-write-wins behavior is allowed.

9. **Derived projections remain rebuildable and non-authoritative.** This task must not make discussion or relationship projections canonical.

10. **Unavailable evidence remains historical.** Existing tombstone or unavailable observations must not permanently block a later successful acquisition.

11. **No second artifact authority.** Do not duplicate content-addressed bytes or create a competing raw-message store.

## Codex Latitude

This ticket specifies behavior, authority boundaries, and verification obligations rather than a prescribed implementation.

Codex may:

- refine table and column names;
- reuse or evolve existing mailing-list tables where doing so reduces migration risk;
- choose a deterministic canonical ID format consistent with repository conventions;
- introduce focused repository/domain types and APIs;
- adjust transaction boundaries to preserve atomicity;
- choose eager or lazy backfill;
- add narrowly necessary indexes, schema-version changes, and validation checks;
- make small adjacent refactors when they materially reduce risk or duplication.

Codex should not stop merely because the existing design document contains a schema inconsistency or because the smallest correct implementation differs from its illustrative SQL. Resolve such issues using repository evidence, the architectural invariants above, and the narrowest maintainable solution.

Any material departure from the design proposal must be called out explicitly in the completion report with the repository evidence and reasoning that justified it.

## Scope

In scope:

- schema and migration changes required for canonical message identity;
- repository/domain contracts for canonical lookup and registration;
- per-run observation differentiation between newly materialized and reused content;
- acquisition-service integration;
- conflict detection for same Message-ID/different bytes;
- deterministic compatibility/backfill behavior;
- focused indexes and validation;
- tests, documentation updates, and review evidence.

## Non-Goals

Do not implement:

- generic evidence-store abstractions outside the mailing-list domain;
- Message-ID aliasing across rewritten external identifiers;
- semantic or fuzzy deduplication;
- new parsed-metadata tables;
- parser-version or projection-version infrastructure;
- new parent/reference edge schemas;
- discussion identity redesign;
- patch-series or revision-lineage modeling;
- new LLM traversal APIs;
- acquisition-window redesign;
- pruning or archival policy for observation history;
- operator-console redesign;
- retirement of the current mailing-list projection tables;
- redesign of existing source-scoped message keys, relationship identities, or discussion identities beyond narrowly required compatibility adjustments;
- broad performance optimization for tens of millions of messages.

Malformed or missing `Message-ID` handling should retain existing safe behavior unless a minimal compatibility adjustment is required. Do not broaden this task into a complete malformed-message identity policy.

## Acceptance Criteria

### Canonical identity

- A valid normalized `Message-ID` resolves to one repository-owned canonical message identifier.
- Canonical identity is not source-scoped.
- The canonical record references the existing artifact and document authorities.
- Re-registering the same normalized `Message-ID` with the same artifact is idempotent.
- Re-registering the same normalized `Message-ID` with different bytes fails closed and leaves inspectable diagnostics.
- Repository validation detects broken canonical references and invalid duplicate mappings.

### Observation independence

- Two separate runs observing the same message retain two separate per-run observation records.
- The first run can report a newly created artifact.
- A later overlapping run reports canonical reuse without reporting a new artifact download or creation.
- Inclusion reason, seed status, source, connectivity state, and run provenance remain independently queryable for each run.
- Existing unavailable/tombstone history remains intact and does not suppress later success.

### Compatibility

- Existing repositories can be opened and upgraded safely.
- Existing mailing-list acquisitions and result browsing continue to work.
- Existing discussion and relationship projections remain available.
- No existing immutable artifact or acquisition record is rewritten or deleted.
- Backup/restore and repository integrity validation continue to pass.

### Boundedness

- The implementation does not introduce the deferred projection, patch-series, alias, or generalized evidence-store work listed under Non-Goals.
- Any adjacent refactor is justified as necessary for this slice and is covered by tests.

## Required Test Scenarios

At minimum, add automated tests covering:

1. **First materialization**
   - acquire a fixture message with a valid `Message-ID`;
   - create one canonical mapping;
   - record one newly materialized run observation;
   - retain one artifact.

2. **Overlapping-run reuse**
   - acquire the same fixture through a second run;
   - reuse the same canonical message, artifact, and document;
   - record a distinct second-run observation;
   - create no additional artifact.

3. **Cross-source canonical reuse**
   - where existing source contracts permit, observe the same valid `Message-ID` and identical bytes through two mailing-list sources;
   - resolve both observations to one canonical message;
   - preserve both source/run provenances.

4. **Conflicting bytes**
   - present the same normalized `Message-ID` with different bytes;
   - verify fail-closed behavior;
   - verify canonical content is not replaced;
   - verify the conflict is diagnosable.

5. **Migration or lazy backfill**
   - start with representative pre-TASK-035 repository state;
   - upgrade or first-access it;
   - create deterministic canonical mappings;
   - preserve existing run items and projections;
   - detect conflicting pre-existing candidates.

6. **Unavailable then available**
   - preserve an earlier unavailable/tombstone observation;
   - later retain the real message;
   - create the canonical mapping without erasing the earlier evidence.

7. **Repository integrity**
   - missing artifact/document references fail validation;
   - duplicate external identity or conflicting mapping is rejected;
   - normal backup/restore retains canonical mappings and observations.

8. **Regression**
   - existing focused mailing-list acquisition, relationship, discussion, fetch-history, and browser/API tests continue to pass.

## Review Actions

The reviewer must be able to verify:

1. The schema and migration establish only one active canonical mapping authority.
2. Canonical identity excludes `source_id`.
3. Existing artifact/document authority is reused rather than copied.
4. Run observations remain independent and immutable.
5. Newly fetched and reused materializations are distinguishable from persisted evidence, not inferred only from aggregate counters.
6. Conflict handling cannot silently replace bytes.
7. Existing tombstone/unavailable history is preserved.
8. Migration/backfill cannot silently collapse conflicting source-scoped messages.
9. The implementation remains bounded to the vertical slice.
10. Documentation accurately explains any departure from the design proposal.

## Validation

Run and capture:

```sh
make validate
```

Also run focused tests that prove the required scenarios above. Record the exact focused commands and complete results.

Where practical, provide a small repository-level proof showing:

- two runs;
- one normalized `Message-ID`;
- one canonical message;
- one artifact;
- two independent observations;
- first observation marked newly materialized;
- second observation marked reused.

## Documentation

Update the existing appropriate architecture or mailing-list design documentation to record the implemented authority boundary and actual schema/API choices.

Do not create a new documentation directory solely for this task.

The design proposal remains a proposal; document material departures rather than silently rewriting history.

## Completion and Review Package

Before completion:

- mark this ticket `Done`;
- commit all task-scoped implementation and documentation changes;
- generate the standard TASK-035 review package;
- include:
  - ticket;
  - changed-file inventory;
  - commit and branch information;
  - schema/migration summary;
  - focused test commands and outputs;
  - full `make validate` output;
  - canonical reuse proof;
  - conflict proof;
  - migration/backfill proof;
  - repository status;
  - known limitations and deferred decisions.

Do not push or merge unless separately instructed.
