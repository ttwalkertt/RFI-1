# TASK-022 — Additional SEC Numbered-Form Retrieval Adapters

## Status

Complete

## Objective

Implement production retrieval adapters for the canonical SEC filing artifacts:

- Quarterly report on Form 10-Q;
- Current report on Form 8-K;
- Annual report on Form 20-F;
- Current report on Form 6-K.

The implementation shall reuse the existing Form 10-K adapter, SEC provider services, adapter capability contracts, acquisition pipeline, repository contracts, query surface, and operator workflows wherever their semantics are genuinely common.

Each new adapter shall remain artifact-specific and shall own the filing policy required by its canonical artifact. This task must not collapse the numbered SEC forms into a universal form-parameterized adapter or a generic SEC policy engine.

The new SQLite structured-state backend is an implementation detail below the existing public repository contracts. No adapter shall depend directly on SQLite, SQL schemas, database connections, persistence models, or storage-specific behavior.

## Context

TASK-016 established the first deterministic SEC retrieval vertical slice for Form 10-K, including:

- the retrieval-adapter extension boundary;
- explicit adapter capability and selection;
- a bounded shared SEC provider service;
- authoritative SEC issuer and filing-metadata access;
- deterministic filing selection;
- primary filing artifact retrieval;
- stable filing identity and provenance;
- integration through the acquisition pipeline into durable repository evidence;
- operator-visible pull results;
- fixture-backed offline validation and gated live proof.

TASK-014 already defined canonical artifact items for Form 10-Q, Form 8-K, Form 20-F, and Form 6-K. TASK-018 explicitly deferred these four adapters. TASK-021 replaced structured-state persistence with SQLite behind preserved repository and query contracts.

RFI-1 can currently retrieve Form 10-K filings but reports no compatible adapter for the other configured numbered SEC filing artifacts. TASK-022 closes that gap without changing repository authority or introducing persistence coupling.

The target flow is:

```text
firm source-profile revision
    → enabled canonical SEC filing artifact
    → identifier retrieval candidate
    → artifact-specific SEC adapter
    → explicit filing-form policy
    → deterministic bounded filing selection
    → exact primary filing retrieval
    → existing acquisition pipeline
    → repository public contracts
    → SQLite-backed structured state and content-addressed bytes
    → operator-visible result and browser inspection
```

The implementation remains architecture-led. Codex shall inspect the current repository and completed TASK-016 through TASK-021 work before determining concrete internal decomposition.

## Architectural Intent

### Artifact-specific semantics remain authoritative

The four adapters shall correspond to canonical artifact semantics, not merely to a provider endpoint or a string-valued SEC form code.

Each adapter shall explicitly own, at minimum:

- eligible filing forms;
- amendment treatment;
- filing selection semantics;
- multiplicity expectations;
- primary filing artifact selection;
- source-effective ordering fields;
- artifact-specific provenance;
- artifact-specific failure interpretation;
- canonical artifact mapping.

The implementation may share code, types, provider access, and narrowly defined deterministic algorithms. It shall not hide materially different policies behind configuration tables, arbitrary form strings, or a generic “SEC filing adapter.”

### Reuse the Form 10-K implementation deliberately

Codex shall first identify the current Form 10-K responsibility boundaries and classify them as:

1. generic retrieval-adapter infrastructure;
2. shared SEC provider mechanics;
3. reusable numbered-form mechanics;
4. Form 10-K-specific policy;
5. repository or acquisition behavior that must remain outside adapters.

The implementation shall maximize justified reuse while preserving inspectable policy ownership.

Likely reusable concerns include:

- adapter registration and capability declaration;
- issuer-identifier normalization;
- authoritative SEC endpoint access;
- request identification and service-use compliance;
- connection and read timeouts;
- bounded retry and rate-limit handling;
- filing-metadata retrieval and validation;
- accession and archive-path handling;
- primary-document retrieval;
- content validation and bounded-size checks;
- provider-native identity and provenance mapping;
- sanitized diagnostics;
- deterministic fixture transport;
- acquisition-result mapping.

Likely artifact-specific concerns include:

- exact eligible form set;
- amendment inclusion or exclusion;
- latest-versus-bounded-set selection;
- event or period semantics;
- source-effective date selection;
- multiplicity and duplicate expectations;
- form-specific ambiguity and no-match outcomes.

Codex shall document every material extraction or abstraction and explain why it is shared rather than merely similar.

### No persistence coupling

Adapters retrieve and describe external artifacts. They do not own structured-state persistence.

The new adapters shall interact only through existing public retrieval, acquisition, and repository contracts. They shall not:

- import SQLite libraries for repository access;
- receive database connections, transactions, cursors, or ORM objects;
- issue SQL;
- depend on table names or schema versions;
- make selection decisions based on persistence layout;
- bypass the acquisition pipeline to insert repository records.

SQLite-backed state shall matter only insofar as existing integration and regression tests prove public behavior remains correct.

### Deterministic authoritative retrieval

The production path shall use structured authoritative SEC records and explicit code. It shall not use:

- LLM judgment;
- browser automation;
- open-web search;
- probabilistic ranking;
- autonomous agent loops;
- investor-relations substitutes;
- inferred or guessed filing identity.

External source evolution is expected. Given the same source-profile revision, adapter policy, provider response, and retrieval boundary, selection shall remain deterministic.

## Required Outcomes

### 1. Current Form 10-K behavior remains intact

Before adding new adapters, establish the current Form 10-K production contract and regression baseline.

The completed implementation shall preserve:

- Form 10-K adapter capability and selection;
- exact Form 10-K filtering;
- amendment policy;
- deterministic ordering and tie-breaking;
- primary-document retrieval;
- stable identity and provenance;
- duplicate and no-change behavior;
- operator-visible pull results;
- repository query and browser behavior;
- gated live retrieval behavior.

Refactoring for reuse is permitted only with complete regression evidence.

### 2. Form 10-Q adapter

Provide one production adapter for the canonical Form 10-Q artifact.

The adapter shall:

- declare compatibility only with the canonical Form 10-Q artifact and supported identifier retrieval candidates;
- identify exact eligible Form 10-Q filings;
- distinguish Form 10-Q from Form 10-Q/A unless an explicit documented policy includes amendments;
- select the latest eligible filing under the source-profile policy;
- use explicit deterministic tie-breaking;
- retrieve the intended primary filing document;
- preserve accession, filing date, acceptance time, period of report, primary-document identity, source location, and other available provider-native provenance;
- submit the retrieved artifact through the existing acquisition pipeline;
- produce normalized source-effective ordering suitable for repository queries and browser display.

The task shall document how quarter and period-of-report semantics affect selection and display without introducing accounting interpretation into the adapter.

### 3. Form 8-K adapter

Provide one production adapter for the canonical Form 8-K artifact.

The adapter shall:

- declare compatibility only with the canonical Form 8-K artifact and supported identifier retrieval candidates;
- identify exact eligible Form 8-K filings;
- distinguish Form 8-K from Form 8-K/A unless an explicit documented policy includes amendments;
- select the latest eligible filing under the current pull policy;
- use explicit deterministic tie-breaking;
- retrieve the intended primary filing document;
- preserve accession, filing date, acceptance time, period or event date where available, primary-document identity, source location, and provider-native provenance;
- submit the artifact through the existing acquisition pipeline.

Form 8-K is a high-frequency current-report stream. The adapter and tests shall not assume one filing per quarter or one filing per reporting period. The latest selector may return one filing for the current pull workflow, but the design shall remain compatible with later bounded historical acquisition without changing repository identity.

This task does not require exhibit extraction, item-number interpretation, event classification, or retrieval of every attachment.

### 4. Form 20-F adapter

Provide one production adapter for the canonical Form 20-F artifact.

The adapter shall:

- declare compatibility only with the canonical Form 20-F artifact and supported identifier retrieval candidates;
- identify exact eligible Form 20-F filings;
- distinguish Form 20-F from Form 20-F/A unless an explicit documented policy includes amendments;
- select the latest eligible filing under the source-profile policy;
- use explicit deterministic tie-breaking;
- retrieve the intended primary filing document;
- preserve accession, filing date, acceptance time, period of report, primary-document identity, source location, and provider-native provenance;
- submit the artifact through the existing acquisition pipeline.

The implementation shall treat Form 20-F as a distinct canonical foreign-private-issuer annual filing, not as an alias for Form 10-K. Shared annual-report mechanics may be reused, but eligibility, form identity, canonical mapping, and failure semantics shall remain explicit.

### 5. Form 6-K adapter

Provide one production adapter for the canonical Form 6-K artifact.

The adapter shall:

- declare compatibility only with the canonical Form 6-K artifact and supported identifier retrieval candidates;
- identify exact eligible Form 6-K filings;
- distinguish Form 6-K from Form 6-K/A if such records are encountered and define explicit treatment;
- select the latest eligible filing under the current pull policy;
- use explicit deterministic tie-breaking;
- retrieve the intended primary filing document;
- preserve accession, filing date, acceptance time, period or event date where available, primary-document identity, source location, and provider-native provenance;
- submit the artifact through the existing acquisition pipeline.

Form 6-K is a potentially high-frequency foreign-private-issuer current-report stream. The adapter shall not assume annual or quarterly multiplicity. The implementation shall remain capable of later bounded historical acquisition without changing identity semantics.

This task does not require exhibit extraction, furnished-document classification, event interpretation, or retrieval of every attachment.

### 6. Explicit amendment policies

For each form, define and test one explicit amendment policy.

The default expectation is exact base-form matching:

- `10-Q` does not silently include `10-Q/A`;
- `8-K` does not silently include `8-K/A`;
- `20-F` does not silently include `20-F/A`;
- `6-K` does not silently include amended or alternate forms.

If the current canonical artifact model or established policy requires different behavior, Codex shall stop and report the conflict before broadening eligibility.

Amendments shall never be included merely because they are newer.

### 7. Deterministic selection semantics

For the current pull workflow, each adapter shall select the latest eligible filing visible under the source-profile policy.

Selection shall define and independently test:

- exact form eligibility;
- filing-date and acceptance-time use;
- period-of-report or event-date treatment where applicable;
- explicit tie-breaking;
- behavior when metadata records are reordered;
- behavior when required ordering or identity fields are absent;
- behavior when two records remain ambiguous after declared policy;
- temporal boundaries supplied by current contracts, if any.

Do not use ingestion time, provider response order, mutable URL order, or dictionary iteration order as implicit selectors.

### 8. Stable identity and provenance

Preserve clear separation among:

- firm identity;
- SEC issuer identity;
- canonical artifact identity;
- provider form identity;
- filing accession identity;
- filing primary-document identity;
- retrieval candidate identity;
- adapter identity;
- provider identity;
- retrieval location;
- repository document identity;
- ArtifactObservation identity;
- immutable content checksum.

Equivalent retrievals of the same filing shall reuse the same logical artifact and bytes under current repository contracts. Distinct pulls may create observations where current repository semantics require them.

Unknown, malformed, conflicting, or incomplete identity shall fail visibly rather than being guessed.

### 9. Shared SEC implementation boundary

Refactor or extend the shared SEC provider layer only where required to support all five numbered-form adapters cleanly.

The shared layer may own:

- provider transport and endpoint behavior;
- SEC request identification;
- issuer lookup and identifier normalization;
- filing metadata normalization;
- archive location construction or resolution;
- primary-document retrieval mechanics;
- response and content validation;
- timeout, retry, redirect, and rate-limit behavior;
- sanitized provider diagnostics;
- deterministic fixture interfaces.

The shared layer shall not own:

- arbitrary form-string dispatch;
- canonical artifact mapping by configuration;
- amendment policy;
- latest-filing policy;
- form-specific multiplicity assumptions;
- form-specific source-effective semantics;
- artifact-specific failure interpretation.

A small shared base, helper, policy protocol, or composition model is acceptable if its boundaries are explicit and typed. A universal configurable adapter is not.

### 10. Adapter registration and capability selection

Register all four adapters through the established adapter extension mechanism.

Prove that:

- each canonical artifact selects exactly its compatible adapter;
- Form 10-K still selects the existing Form 10-K adapter;
- unsupported SEC artifacts do not select a numbered-form adapter accidentally;
- source profiles missing required identifiers remain configuration problems;
- ambiguous adapter capability is detected rather than resolved by registration order;
- the generic pull engine contains no hard-coded branching for individual SEC forms.

### 11. Operator-visible behavior

The existing source-profile and pull workflows shall recognize configured 10-Q, 8-K, 20-F, and 6-K artifacts as runnable when a compatible adapter and required issuer identifier are present.

The operator shall be able to:

- see accurate readiness per artifact;
- run a firm pull through the existing production path;
- observe per-artifact selection, progress, and result;
- distinguish no eligible filing, retrieval failure, duplicate, no change, partial pull, and success;
- inspect normalized metadata and provenance in the artifact browser;
- repeat the pull and observe current idempotency and ArtifactObservation semantics;
- continue using the system with network access blocked for repository browsing and inspection.

No form-specific UI branching is required unless current normalized contracts cannot express necessary metadata.

### 12. SQLite-backend independence

Prove that the adapters remain independent of the SQLite backend.

Evidence shall include:

- no adapter import or dependency on SQLite persistence modules;
- no database handle or persistence object passed into adapter APIs;
- adapter fixture tests executable without a repository database where current contracts permit;
- acquisition integration through public contracts only;
- successful operation on fresh SQLite-backed state;
- repository query and browser results equivalent to established normalized behavior;
- no SQL or schema assumptions in form-selection tests.

Do not add an alternative persistence implementation merely to prove abstraction.

### 13. Offline deterministic fixture proof

Ordinary validation shall require no network access.

Provide bounded fixtures for each form sufficient to prove:

- adapter capability and selection;
- exact base-form filtering;
- amendment exclusion or declared treatment;
- latest selection;
- reordered provider-record determinism;
- tie-breaking;
- missing ordering metadata;
- malformed provider records;
- missing filing identity;
- no eligible filing;
- ambiguous result after policy;
- primary-document mapping;
- archive retrieval reference construction or use;
- content-type and content validation;
- stable identity and provenance;
- acquisition integration;
- durable repository effects;
- duplicate, no-change, and observation behavior;
- operator-visible results;
- artifact query and browser visibility.

Fixtures shall exercise production contracts and shared provider interfaces rather than inserting final repository state through test-only shortcuts.

### 14. Gated bounded live proof

Provide gated live demonstrations using firms with valid SEC issuer identifiers and actual eligible filings.

At minimum, the live proof shall retrieve:

- one Form 10-Q filing;
- one Form 8-K filing;
- one Form 20-F filing;
- one Form 6-K filing.

A single firm need not support all forms. Select a bounded set of configured firms appropriate to domestic issuers and foreign private issuers.

Each live proof shall:

- validate configuration before network activity;
- identify the exact firm, issuer identifier, canonical artifact, and expected bounded scope;
- show explicit adapter selection;
- retrieve one eligible primary filing document;
- preserve exact bytes and checksum;
- preserve filing identity and provenance;
- complete through the production pull and acquisition path into fresh SQLite-backed state;
- verify repository query and browser visibility;
- repeat the equivalent pull;
- demonstrate correct artifact reuse, duplicate/no-change, and observation behavior;
- verify stored artifact integrity;
- remain excluded from ordinary offline validation.

Live evidence shall record the filing accession and source-effective ordering fields selected. Full filing bytes shall not be committed unless repository policy explicitly permits them.

## Failure Semantics

The implementation and verification shall distinguish, at minimum:

- source profile missing required SEC issuer identifier;
- unsupported retrieval mode;
- no compatible adapter;
- ambiguous compatible adapters;
- invalid SEC issuer identifier;
- issuer not found;
- no eligible Form 10-Q;
- no eligible Form 8-K;
- no eligible Form 20-F;
- no eligible Form 6-K;
- amendment excluded by policy;
- ambiguous result after declared policy;
- malformed filing metadata;
- missing filing accession identity;
- missing primary-document identity;
- unsupported or unexpected artifact representation;
- network timeout;
- rate limit or temporary provider failure;
- permanent request failure;
- redirect-policy failure;
- empty content;
- truncated content;
- invalid content type;
- artifact-size bound exceeded;
- repository conflict;
- duplicate artifact;
- no content change;
- successful artifact reuse with a new observation where applicable;
- partial firm pull;
- successful retrieval and durable ingestion.

Failures shall remain structured, sanitized, operator-visible, auditable, and suitable for fixture testing.

The implementation shall not compensate by:

- searching the open web;
- choosing a nearby or plausibly equivalent form;
- retrieving an investor-relations copy;
- silently including an amendment;
- retrieving an exhibit instead of the primary filing document;
- guessing missing identity;
- invoking an LLM.

## Architectural Constraints

- Preserve the acquisition, repository, ArtifactObservation, query, browser, and integrity authority boundaries established by completed tasks.
- Preserve the public contracts implemented over the SQLite structured-state backend.
- Keep SEC-specific behavior outside core pull orchestration and repository persistence.
- Select adapters through explicit capability contracts.
- Implement four artifact-specific adapters: Form 10-Q, Form 8-K, Form 20-F, and Form 6-K.
- Preserve the Form 10-K adapter as an artifact-specific adapter.
- Do not create one universal SEC filing adapter.
- Do not create an arbitrary form-code adapter configured by strings or tables.
- Do not create a generic SEC policy engine.
- Do not hard-code individual SEC forms into the generic pull engine.
- Do not pass repository persistence objects into adapters.
- Do not make adapters aware of SQLite, SQL, tables, schema versions, or transaction handling.
- Do not use an LLM, browser agent, or unbounded search in the production path.
- Do not treat ticker, filename, mutable URL, response order, or adapter-local identifiers as sufficient artifact identity.
- Do not silently include amendments.
- Do not retrieve filing exhibits or all attachments as part of this task.
- Do not silently widen latest-only retrieval into historical corpus acquisition.
- Do not make ordinary tests depend on live SEC availability.
- Do not weaken existing repository invariants to simplify adapter implementation.
- Stop and report a blocker if completed task contracts or current repository behavior materially conflict with this ticket.

## Non-Goals

TASK-022 does not require:

- proxy-statement adapters;
- ownership or insider filing adapters;
- registration-statement adapters;
- other SEC form families;
- generic statutory or exchange filing retrieval;
- exhibit retrieval or attachment graphs;
- XBRL facts or inline-XBRL extraction;
- filing section extraction;
- 8-K item classification;
- 6-K furnished-document interpretation;
- accounting analysis;
- historical backfill or complete filing-stream synchronization;
- exact-accession operator workflows;
- scheduled polling;
- change notifications;
- feed subscriptions;
- bulk SEC corpus download;
- investor-relations annual reports;
- earnings releases, presentations, transcripts, or webcasts;
- open-web or discovery-based retrieval;
- new repository persistence abstractions;
- SQLite schema redesign unrelated to proven adapter needs;
- migration from legacy POC state;
- report generation, claims, observations derived from document content, embeddings, or semantic search.

## Functional Proof

Demonstrate all of the following through production contracts:

1. Existing Form 10-K retrieval remains correct after any refactoring.
2. Form 10-Q configuration selects the Form 10-Q adapter and no other adapter.
3. Form 8-K configuration selects the Form 8-K adapter and no other adapter.
4. Form 20-F configuration selects the Form 20-F adapter and no other adapter.
5. Form 6-K configuration selects the Form 6-K adapter and no other adapter.
6. Exact base-form filtering excludes amendments by default.
7. Reordered equivalent provider records produce the same selected filing for each form.
8. Tie-breaking is explicit and deterministic.
9. Missing required identity fails visibly.
10. No eligible filing produces a form-specific non-success result.
11. The intended primary filing document is retrieved rather than an exhibit.
12. Provider-native identity and provenance are retained.
13. The acquisition pipeline stores the artifact through public repository contracts.
14. Artifact bytes remain in the content-addressed filesystem.
15. SQLite contains structured references through repository implementation, not adapter behavior.
16. Repeated retrieval reuses the logical artifact and exact bytes.
17. ArtifactObservation behavior matches the current repository contract.
18. Pull summaries distinguish success, duplicate/no-change, partial, and failure outcomes.
19. Artifact query results use deterministic source-effective ordering.
20. The artifact browser displays the new filing types and stored previews.
21. Browsing and preview remain functional with network access blocked.
22. Restart preserves repository and query behavior.
23. Integrity verification passes.
24. Gated live retrieval succeeds for all four new forms.
25. Equivalent live reruns prove current idempotency and observation semantics.
26. Full project validation and isolated-tree validation pass.

## Validation Requirements

Validation shall include, at minimum:

- current Form 10-K regression tests;
- adapter registry and capability tests;
- one focused policy suite per new form;
- exact-form and amendment-policy tests;
- latest-selection tests;
- reordered-response tests;
- tie-break tests;
- no-match and ambiguity tests;
- malformed-response and missing-identity tests;
- primary-document selection tests;
- timeout, retry, rate-limit, redirect, and permanent-failure tests;
- content-type, empty-content, truncated-content, and size-bound tests;
- shared SEC provider-service tests;
- proof that shared provider code contains no canonical artifact policy;
- acquisition integration tests using deterministic transport fixtures;
- stable filing, artifact, and provenance identity tests;
- duplicate, no-change, and ArtifactObservation tests;
- partial firm-pull tests;
- pull-readiness and admin-console result tests;
- artifact-query and browser tests for all new forms;
- SQLite fresh-state integration tests;
- proof of no adapter-to-SQLite dependency;
- process-restart tests;
- network-blocked browser and repository-query tests;
- integrity verification;
- applicable replay or rebuild tests under current repository architecture;
- all existing project tests and quality gates;
- documentation and design-baseline validation;
- isolated-tree or clean-checkout-equivalent validation;
- secret and sensitive-output scan;
- review-package manifest validation;
- package member checksums;
- ZIP checksum and ZIP integrity validation;
- four gated bounded live pulls;
- four gated equivalent live reruns.

Tests must assert durable repository effects and operator-visible outcomes, not merely adapter return values.

## Required Verification Package

Produce a complete TASK-022 review directory and ZIP under the repository’s established review-package convention.

The package shall contain, at minimum:

- task ticket;
- executive summary;
- implementation summary;
- architecture decisions;
- alternatives considered;
- existing Form 10-K responsibility analysis;
- reuse and refactoring map;
- adapter capability and registration model;
- shared SEC provider-service boundary;
- numbered-form adapter responsibility matrix;
- Form 10-K regression record;
- Form 10-Q policy record;
- Form 8-K policy record;
- Form 20-F policy record;
- Form 6-K policy record;
- amendment-policy matrix;
- deterministic selection and tie-break matrix;
- source-effective ordering matrix;
- identity and provenance model;
- primary-document selection model;
- network and SEC service-use boundary;
- failure and result taxonomy;
- acquisition and repository integration summary;
- SQLite independence analysis;
- query and browser integration summary;
- future historical-acquisition compatibility analysis;
- known limitations and deferred work;
- cumulative task-scoped patch including untracked files;
- changed-file inventory with rationale;
- relevant repository tree;
- Git branch, base, HEAD, staged, unstaged, untracked, and worktree state;
- exact validation commands;
- complete raw focused-validation output;
- complete raw full-project validation output;
- deterministic fixture inventory;
- capability-selection evidence;
- exact-form and amendment evidence;
- reordered-response and tie-break evidence;
- no-match, ambiguity, and malformed-metadata evidence;
- primary-document mapping evidence;
- failure-injection evidence;
- SQLite fresh-state integration evidence;
- no-adapter-persistence-coupling evidence;
- duplicate, no-change, and ArtifactObservation evidence;
- artifact query and browser evidence;
- network-blocked inspection evidence;
- restart evidence;
- integrity evidence;
- Form 10-Q live-pull evidence;
- Form 10-Q live-rerun evidence;
- Form 8-K live-pull evidence;
- Form 8-K live-rerun evidence;
- Form 20-F live-pull evidence;
- Form 20-F live-rerun evidence;
- Form 6-K live-pull evidence;
- Form 6-K live-rerun evidence;
- live artifact inventory and checksum evidence;
- documentation and design-baseline validation evidence;
- isolated-tree validation evidence;
- secret and sensitive-output scan;
- machine-readable review manifest;
- package member checksums;
- ZIP member listing;
- ZIP checksum;
- ZIP integrity evidence.

The package must distinguish offline deterministic validation from gated live operations. It shall retain final evidence for every failed required check as well as the eventual passing rerun.

A passing summary without independently reviewable raw evidence is insufficient.

## Documentation and Durable Design Record

Update repository documentation and create or revise ADRs where warranted.

The durable design record shall explain:

- how the existing Form 10-K adapter was decomposed;
- which implementation elements were reused unchanged;
- which elements were extracted into shared SEC mechanics;
- which policies remain artifact-specific;
- why a universal SEC filing adapter remains rejected;
- why an arbitrary form-code configuration model remains rejected;
- how adapter capability selection prevents core pull branching;
- how amendment policies differ or remain consistent across forms;
- how source-effective ordering is defined for annual, quarterly, and current reports;
- how high-frequency Form 8-K and Form 6-K streams fit the latest-only current workflow;
- how later historical acquisition can be added without changing filing or repository identity;
- how primary documents are distinguished from exhibits;
- how provider-native identity maps into repository contracts;
- why adapters remain independent of SQLite and all persistence substrates;
- what was learned from live retrieval of domestic and foreign-private-issuer filings;
- which abstractions were deliberately deferred.

## Completion Record Requirements

Update this task ticket as the durable handoff record while preserving the original objective, requirements, constraints, and non-goals.

Add:

- final status;
- implementation summary;
- actual architecture and responsibility split;
- changed-file inventory;
- validation commands and outcomes;
- live proof firms and selected accessions;
- review directory and ZIP paths;
- ZIP size, checksum, and integrity result;
- Git branch, base, HEAD, staged, unstaged, untracked, and worktree state;
- known limitations;
- deferred work;
- any material departure from the ticket and its rationale;
- explicit confirmation that no universal SEC filing adapter was created;
- explicit confirmation that adapters do not depend on SQLite or persistence internals;
- explicit confirmation that no commit, push, merge, branch deletion, or cleanup was performed unless separately authorized.

## Codex Execution Constraints

- Work only in the prepared TASK-022 branch and the RFI-1 repository.
- Read the governing design documents and completed TASK-016 through TASK-021 records before implementation.
- Treat the current repository and completed task contracts as evidence; report material contradictions rather than guessing.
- Do not create or switch branches unless explicitly authorized.
- Do not commit, push, merge, delete branches, or perform cleanup.
- Do not modify unrelated repositories or user files.
- Do not introduce real credentials or secrets.
- Do not use network access during ordinary fixture tests, replay, repository queries, browser tests, or full validation.
- Gate live SEC operations explicitly and keep them bounded.
- Do not implement later historical-acquisition, scheduling, exhibit, extraction, or analysis capabilities merely because they appear convenient.
- Do not weaken an invariant to reduce implementation effort.
- Produce the complete verification package even when all checks pass.
- Stop and report a blocker if the branch, repository state, design baseline, or completed contracts are materially inconsistent.

## Expected Handoff

At completion, report:

- branch name and HEAD;
- concise implementation summary;
- Form 10-K refactoring summary;
- adapter and shared-provider contracts introduced or changed;
- per-form selection and amendment policies;
- identity and provenance decisions;
- SQLite independence evidence;
- focused and full validation outcomes;
- live pull and rerun outcomes for all four forms;
- review directory and ZIP path;
- ZIP size, checksum, and integrity result;
- changed-file count;
- staged, unstaged, untracked, and worktree state;
- known limitations and deferred work;
- explicit confirmation that no universal SEC filing adapter was created;
- explicit confirmation that no commit, push, merge, branch deletion, or cleanup was performed.

## Completion Record

### Implementation resolution

TASK-022 adds concrete `SecForm10QAdapter`, `SecForm8KAdapter`, `SecForm20FAdapter`, and
`SecForm6KAdapter` capabilities to production composition. Each claims exactly one canonical
artifact through identifier retrieval, exact base-form eligibility, explicit amendment exclusion,
artifact-specific multiplicity, and a form-specific no-match result. `SecForm10KAdapter` remains a
concrete policy class and its complete TASK-016 regression suite passes.

The demonstrably identical numbered-form algorithms were extracted to
`SecNumberedFormAdapter`: duplicate-accession conflict detection, descending filing-date /
acceptance-time / accession ordering, primary-document candidate construction, provider-native
provenance, profile/CIK validation, and retrieval-result projection. The base accepts no runtime
form or canonical-artifact configuration. `SecProviderClient` remains transport/provider
mechanics only. Pull Workflow, acquisition ingress, repository identity and publication,
ArtifactObservation, queries, browser projection, restart, and integrity remain outside adapters.

Live evidence corrected one shared-provider assumption: an accession prefix is not required to
equal the issuer CIK because the issuer's authoritative submissions record can contain filings
submitted through another EDGAR filer. Accession syntax remains strict and archive paths remain
beneath the authoritative issuer CIK directory.

### Policy and identity resolution

- Form 10-Q: exact `10-Q`, exclude `10-Q/A`, latest quarterly report; retain period of report
  without fiscal interpretation.
- Form 8-K: exact `8-K`, exclude `8-K/A`, latest item in a high-frequency stream; no quarterly or
  one-per-period assumption.
- Form 20-F: exact `20-F`, exclude `20-F/A`, distinct foreign-private-issuer annual artifact;
  never a Form 10-K alias.
- Form 6-K: exact `6-K`, exclude `6-K/A`, latest item in an irregular high-frequency foreign
  current-report stream; no domestic periodic assumption.
- All four order descending by filing date, acceptance time, and accession. Provider record order
  and ingestion time do not select filings. Conflicting metadata for one accession is ambiguous.
- Issuer CIK, canonical artifact, provider form, accession, primary document, candidate, adapter,
  provider, repository document, observation, and immutable checksum remain separate identities.
- Equivalent latest-only reruns return `no_change` at the source checkpoint before retrieval and
  therefore add no observation. A separate successful acquisition can still add an observation
  under the TASK-019 contract.

### Changed-file inventory and rationale

The task changes 31 repository paths:

- six acquisition modules add the shared mechanics and four concrete adapters while preserving
  the concrete Form 10-K class; provider and exports/composition are narrowly updated;
- one focused test module, two existing scope inventories, one fixture directory, and one operator
  script prove policy, provider, pull, repository, query/browser, restart, integrity, and live use;
- one review generator and Makefile targets provide reproducible complete evidence;
- the operations/design guide, ADR-0018, governing records, baseline records, README, roadmap
  table, and this ticket make the architectural change durable.

No unrelated subsystem implementation, persistence redesign, historical retrieval, scheduling,
exhibit extraction, interpretation, or analysis was added.

### Validation and live proof

- Focused TASK-022: PASS, 7 tests.
- Existing TASK-016 Form 10-K regression: PASS, 15 tests.
- Shared SEC failure/content/provider coverage: PASS through TASK-016 and TASK-022 suites.
- Full `env -u RFI_SEC_USER_AGENT -u SEC_API_IO_API_KEY make validate`: PASS, 216 tests plus all
  deterministic operator proofs, lint, format, typecheck, import, documentation, design baseline,
  source archive, checksums, and archive integrity.
- Documentation and design-baseline checks: PASS (82 Markdown files, 27 local links, 8 governing
  design documents, 6 repository boundaries, complete product inventory).
- Isolated copied-tree validation: required and retained by the final review generator.
- Sensitive-output, review manifest, member checksums, ZIP listing, ZIP checksum, and ZIP
  integrity: required and retained by the final review generator.

The initial sandboxed live attempt retained four bounded `temporary_service_failure` outcomes.
The first network-enabled attempt selected all four filings but exposed the accession-prefix defect:
Form 10-Q succeeded while Form 8-K, Form 20-F, and Form 6-K failed visibly. After the provider
correction and complete offline regression, a fresh bounded proof passed with 12 requests and zero
retries:

| Form | Firm / CIK | Selected accession | Primary document | First / rerun |
| --- | --- | --- | --- | --- |
| 10-Q | Seagate / 1137789 | `0001137789-26-000088` | `stx-20260403.htm` | success / no_change |
| 8-K | Seagate / 1137789 | `0001193125-26-268170` | `d24300d8k.htm` | success / no_change |
| 20-F | ASML / 937966 | `0001628280-26-011378` | `asml-20251231.htm` | success / no_change |
| 6-K | ASML / 937966 | `0001628280-26-048235` | `form6-kquarterlyfilings.htm` | success / no_change |

The passing live state contains four exact content-addressed artifacts and four observations;
query/browser visibility, network-blocked restart equivalence, and repository integrity all pass.
Downloaded filing bytes remain only in ignored runtime state and are not packaged.

### Review package and Git state

- Review directory: `.artifacts/review/TASK-022/`
- Review ZIP: `.artifacts/review/TASK-022-review.zip`
- ZIP size, SHA-256, member listing, and integrity result: generated and recorded by the final
  package, its `verification-summary.json`, and `.zip.sha256` sidecar. The checksum is intentionally
  not embedded as a literal inside the archive-bearing ticket because doing so would recursively
  change the archive checksum.
- Branch: `codex/task-022-sec-numbered-form-adapters`
- Base and unchanged HEAD: `87d7380d31a71d31843ac0e640a4e86fc073f6fb`
- Staged: this TASK-022 ticket only, as explicitly requested before implementation.
- Unstaged: tracked TASK-022 implementation/documentation changes.
- Untracked: new TASK-022 implementation, fixtures, tests, scripts, guide, and ADR.
- Overall worktree: intentionally dirty and uncommitted for review.

### Known limitations and deferred work

Only recent submissions and latest-visible selection are supported. Exact-accession retrieval,
historical traversal/backfill, polling/scheduling, exhibits and attachment graphs, XBRL, 8-K item
classification, 6-K furnished-document interpretation, accounting analysis, extraction, semantic
retrieval, and intelligence remain deferred. External SEC availability remains outside repository
control; ordinary validation is fully offline.

No universal SEC filing adapter, arbitrary form-code configuration engine, or generic SEC policy
engine was created. No adapter imports SQLite, issues SQL, receives persistence objects, depends on
schemas, or bypasses public acquisition/repository contracts. No commit, push, merge, branch
deletion, or repository cleanup was performed.

## Architectural Status Summary

| Subsystem | Status | Boundary after TASK-022 |
| --- | --- | --- |
| Retrieval-adapter registry and Pull Workflow | Complete | Selects explicit artifact/mode capabilities; contains no SEC form branching. |
| Shared SEC provider mechanics | Complete for current numbered forms | Bounded official transport, metadata and primary-document mechanics; no canonical policy. |
| Reusable numbered-form mechanics | Complete | Deterministic typed algorithms only; no runtime form configuration. |
| Form 10-K policy | Complete, regression preserved | Concrete exact-form annual artifact policy remains inspectable. |
| Form 10-Q policy | Complete | Concrete exact-form quarterly latest policy with period provenance. |
| Form 8-K policy | Complete | Concrete latest high-frequency current-report policy. |
| Form 20-F policy | Complete | Concrete distinct foreign-private-issuer annual policy. |
| Form 6-K policy | Complete | Concrete latest irregular foreign current-report policy. |
| Acquisition and immutable evidence | Complete, reused | Sole public ingress; document/artifact/attempt/observation/checkpoint authority unchanged. |
| SQLite structured state | Complete, implementation detail | Public repositories hide schema and transactions from every adapter. |
| Artifact query and browser | Complete, reused | All five numbered forms use normalized source-effective read/inspection contracts. |
| Live domestic and foreign proof | Complete | Four first pulls and four equivalent reruns passed within bounded service use. |
| Historical corpus acquisition | Not Started | Requires a separate bounded selector/workflow without changing filing identity. |
| Exhibits, interpretation, extraction, intelligence | Not Started / out of scope | Remain downstream or separately governed capabilities. |

Architectural change: five SEC numbered-form artifacts now share provider and deterministic
mechanics without sharing canonical policy, while the acquisition/repository/query stack remains
the common storage-independent authority. The next architectural milestone should be separately
authorized from roadmap evidence; historical acquisition is not implied by this latest-only work.
