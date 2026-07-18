# TASK-016 — Deterministic SEC Form 10-K Retrieval Vertical Slice

## Status

Complete

## Objective

Implement the first live deterministic retrieval vertical slice from a firm source profile through the existing pull workflow and acquisition pipeline into durable repository evidence.

The vertical slice shall enable the canonical **Annual report on Form 10-K** artifact when configured through identifier-based retrieval and shall retrieve the selected filing from an authoritative SEC source.

This task must establish:

- a durable retrieval-adapter extension boundary;
- one artifact-specific SEC Form 10-K adapter;
- only the shared SEC provider services clearly justified by this vertical slice and likely near-term SEC-backed artifacts.

It must not create a configurable universal SEC filing adapter.

## Context

TASK-014 established canonical artifact definitions, firm source profiles, addressability classes, retrieval candidates, source-profile revisioning, and operator-visible readiness.

TASK-015 established the pull workflow, including per-firm and per-artifact planning, execution, result reporting, and integration with the existing acquisition and repository contracts.

The current operator workflow can identify an enabled Form 10-K artifact configured for `identifier` retrieval, but reports that no compatible adapter exists.

TASK-016 closes that gap with one complete production vertical slice:

```text
firm source-profile revision
    → enabled Form 10-K artifact
    → identifier retrieval candidate
    → artifact-specific SEC Form 10-K adapter
    → deterministic filing selection
    → exact primary filing retrieval
    → existing acquisition pipeline
    → durable repository evidence
    → operator-visible result
```

The implementation program remains architecture-led. Codex shall determine the concrete internal design after reading the governing documents and current repository, subject to the boundaries and completion conditions below.

## Architectural Intent

### Adapters correspond to canonical artifact semantics

Retrieval adapters shall correspond to the semantic contract of a canonical artifact, not merely to a provider API or transport mechanism.

The Form 10-K adapter owns the policy required to retrieve the canonical Form 10-K artifact, including:

- eligible filing forms;
- amendment treatment;
- filing selection semantics;
- multiplicity expectations;
- primary filing artifact selection;
- artifact-specific provenance;
- artifact-specific failure interpretation.

Future SEC-backed artifacts may have materially different semantics. Form 8-K, Form 10-Q, proxy statements, ownership filings, foreign-issuer filings, and filing exhibits shall not be forced into a universal configurable SEC adapter.

### Reuse provider mechanics only where justified

Common SEC provider behavior may be isolated behind a bounded shared service where the reuse is clear, including concerns such as:

- issuer-identifier normalization;
- authoritative SEC endpoint access;
- request identification;
- timeouts and bounded retries;
- rate-limit handling;
- response validation;
- filing-metadata retrieval;
- archive-document retrieval;
- sanitized diagnostics.

The shared provider layer must not absorb artifact-specific selection policy.

### Later retrieval remains broader than SEC filings

RFI-1 will later require retrieval for additional canonical artifacts, potentially including:

- other regulatory filings;
- published annual reports;
- earnings releases and presentations;
- investor-relations materials;
- press releases and corporate news;
- blogs and executive commentary;
- product pages and technical documents;
- social and public commentary;
- conferences and research;
- patents, job postings, organizational signals, and other public evidence.

Those artifacts may be:

- deterministically addressable;
- semi-deterministically discoverable from stable listings or portals;
- discoverable only through bounded search and operator hints.

TASK-016 shall therefore preserve a generic retrieval-adapter extension boundary without attempting to solve every future artifact or retrieval mode.

### Deterministic source structure remains deterministic

Where the source exposes stable identifiers and structured authoritative records, retrieval shall be performed through explicit code and policy rather than an LLM-powered runtime loop.

Codex may use model reasoning during implementation, but the production retrieval path shall not depend on:

- model judgment;
- free-form browsing;
- probabilistic selection;
- natural-language interpretation;
- open-web search;
- autonomous agent loops.

### Repository authority remains unchanged

Retrieval adapters discover and retrieve external material. They do not own:

- repository document identity;
- immutable artifact identity;
- persistence semantics;
- checkpoint authority;
- evidence lifecycle;
- downstream extraction or interpretation.

Provider identifiers, external URLs, and retrieval references remain provenance. Repository-owned contracts remain authoritative.

## Required Outcomes

### 1. Retrieval-adapter extension boundary

Establish an explicit and inspectable mechanism by which the pull workflow:

- evaluates enabled artifact configuration;
- identifies compatible retrieval candidates;
- selects an adapter through declared capability rather than hard-coded artifact branching;
- invokes retrieval without exposing repository persistence internals to the adapter;
- maps adapter outcomes into the existing acquisition and repository contracts;
- reports configuration, skip, retrieval, duplicate, no-change, partial, and success outcomes accurately.

The architecture shall allow later artifact-specific adapters to be added without requiring the core pull workflow to understand source-specific behavior.

Codex shall document the responsibility split among:

- canonical artifact definition;
- firm source profile;
- retrieval candidate;
- adapter capability and selection;
- artifact-specific retrieval policy;
- shared provider services;
- acquisition orchestration;
- repository ingestion;
- operator-visible run results.

### 2. Artifact-specific SEC Form 10-K adapter

Provide one production adapter capable of satisfying the configured identifier-based retrieval path for the canonical Form 10-K artifact.

The adapter shall use authoritative SEC identity and filing metadata to:

- resolve the configured issuer identity;
- identify the eligible Form 10-K candidate set;
- apply an explicit deterministic selection policy;
- distinguish Form 10-K from Form 10-K/A unless policy explicitly says otherwise;
- select exactly one filing or return a precise non-success result;
- retrieve the intended primary filing artifact;
- preserve provider-native filing identity and retrieval provenance;
- submit the result through the existing acquisition pipeline.

The exact SEC API surface and internal decomposition are implementation decisions. The selected approach must be documented and justified.

### 3. Explicit deterministic selection semantics

The implementation shall define and preserve the operational selector semantics required by the current pull workflow:

- select the latest eligible Form 10-K filing visible under the source-profile policy.

Deterministic selection means that the same:

- source-profile revision;
- retrieval policy;
- eligible provider response;
- applicable temporal or count boundary;

produces the same selected filing.

The external source may legitimately change over time as new filings are published. That is source evolution, not nondeterministic selection.

Any tie-breaking, amendment handling, eligibility filtering, or temporal boundary shall be explicit, documented, and independently testable.

The design shall remain capable of later supporting exact filing selection or bounded historical selection without changing repository identity semantics.

### 4. Stable identity and provenance

Preserve a clear distinction among:

- firm identity;
- SEC issuer identity;
- filing identity;
- filing artifact identity;
- retrieval candidate identity;
- adapter identity;
- provider identity;
- retrieval reference or URL;
- repository document identity;
- immutable content checksum.

Repeated retrieval of the same filing shall not create a second logical document merely because:

- retrieval occurs later;
- provider metadata ordering changes;
- an endpoint or URL representation changes;
- the source profile is reloaded without substantive change.

Unknown, absent, malformed, or conflicting identity fields shall fail visibly rather than being guessed.

### 5. Bounded shared SEC provider service

Introduce only the shared SEC provider capability necessary for the Form 10-K adapter and clearly reusable by likely future SEC-backed adapters.

The shared provider service may own:

- authoritative endpoint access;
- request identification;
- issuer lookup;
- filing metadata retrieval;
- archive artifact retrieval;
- timeout and retry behavior;
- rate-limit handling;
- response and content validation;
- sanitized provider diagnostics.

It shall not own:

- Form 10-K eligibility policy;
- amendment policy;
- latest-filing selection;
- artifact multiplicity;
- canonical artifact mapping;
- Form 10-K-specific failure semantics.

Do not create a general SEC policy engine or a universal form adapter.

### 6. Bounded network and source behavior

The live retrieval path shall address:

- acceptable SEC endpoint scope;
- required request identification or service-use policy;
- connection and read timeouts;
- bounded retries;
- rate limiting;
- response status and shape validation;
- content-type validation;
- bounded artifact size where appropriate;
- redirect behavior;
- sanitized diagnostics;
- deterministic fixture replacement for ordinary tests.

Do not create a generalized HTTP framework beyond what this vertical slice and likely near-term adapters justify.

### 7. Operator-visible pull behavior

The existing firm pull workflow shall become useful for the configured Form 10-K artifact.

The operator shall be able to:

- see the Form 10-K artifact as runnable when configuration is complete and a compatible adapter is available;
- pull the selected firm;
- observe artifact progress and final outcome;
- inspect selected filing identity and retrieval provenance at an appropriate level;
- distinguish configuration problems from retrieval failures;
- repeat the pull and observe correct duplicate or no-change behavior;
- see other enabled but unconfigured artifacts remain configuration problems rather than being silently ignored.

Preserve the existing multi-firm and per-artifact result structure.

### 8. Offline deterministic proof

Normal validation shall not require network access.

Provide bounded fixtures sufficient to prove:

- adapter capability and selection;
- exact Form 10-K filtering;
- amendment policy;
- deterministic ordering under reordered provider records;
- explicit tie-breaking;
- malformed or incomplete provider metadata;
- no eligible filing;
- primary artifact mapping;
- content validation;
- stable filing and artifact identity;
- repeated-run idempotency;
- repository effects;
- operator-visible outcomes.

Fixture tests must exercise production contracts rather than writing repository state through test-only shortcuts.

### 9. Gated bounded live proof

Provide a gated live demonstration using at least one configured firm with a valid SEC issuer identifier.

The live proof shall:

- validate configuration before network activity;
- identify the bounded expected scope;
- show explicit adapter selection;
- retrieve one eligible Form 10-K primary filing artifact;
- preserve exact bytes and checksum;
- preserve inspectable filing identity and provenance;
- complete through the production pull and acquisition path;
- repeat the equivalent pull;
- demonstrate duplicate or no-change behavior without duplicate evidence;
- verify stored artifact integrity;
- remain excluded from ordinary offline validation.

Amazon may be used for the operator-facing proof because it is already configured in the source-profile UI.

## Failure Semantics

The implementation and verification must distinguish, at minimum:

- source profile missing required locator;
- unsupported retrieval mode;
- no compatible adapter;
- invalid SEC issuer identifier;
- issuer not found;
- no eligible Form 10-K;
- ambiguous result after declared policy;
- malformed provider response;
- missing filing identity;
- unsupported or unexpected artifact representation;
- network timeout;
- rate limit or temporary service failure;
- permanent request failure;
- empty, truncated, or invalid content;
- repository conflict;
- duplicate;
- no change;
- partial firm pull;
- successful retrieval and durable ingestion.

Failures must remain structured, visible, and auditable.

The implementation shall not compensate by:

- searching the open web;
- selecting a plausible substitute;
- retrieving an investor-relations document instead;
- silently including an amendment;
- invoking an LLM.

## Architectural Constraints

- Preserve the acquisition and repository authority boundaries established by earlier tasks.
- Keep SEC-specific behavior outside core pull orchestration and repository substrate.
- Select adapters through explicit capability contracts.
- Implement one artifact-specific SEC Form 10-K adapter.
- Do not create a universal configurable SEC filing adapter.
- Do not hard-code Form 10-K behavior into the generic pull engine.
- Do not pass repository persistence objects into retrieval adapters.
- Do not use an LLM, browser agent, or unbounded search in the production retrieval path.
- Do not treat a mutable URL, filename, ticker, or adapter-local object ID as sufficient repository identity.
- Do not silently include Form 10-K/A under a Form 10-K policy.
- Do not silently widen the requested corpus.
- Do not make ordinary tests depend on live SEC availability.
- Do not commit full live filing artifacts unless repository policy explicitly permits it.
- Keep secrets and unnecessary local paths out of logs, fixtures, manifests, and review artifacts.
- Preserve existing source-profile revision, pull-summary, acquisition, replay, rebuild, and integrity behavior.
- Stop and report a blocker rather than weakening an established invariant.

## Non-Goals

TASK-016 does not require:

- a generic SEC filing adapter;
- implementation of Form 10-Q, Form 8-K, Form 20-F, Form 6-K, proxy, ownership, or other filing adapters;
- retrieval of the glossy published annual-report artifact;
- earnings releases, transcripts, presentations, or webcasts;
- press-release, news, blog, product, social, conference, patent, job, or regulatory-notice retrieval;
- semi-deterministic listing-page discovery;
- broad website crawling or scraping;
- bounded web-search adapters;
- LLM-guided source discovery;
- OCR;
- XBRL parsing;
- filing-section extraction;
- exhibit interpretation;
- document chunking;
- embeddings or retrieval indexing;
- observation, claim, concept, position, or projection generation;
- scheduling, polling, or continuous synchronization;
- generalized plugin loading;
- speculative abstractions for every future source.

Leave clear extension points and deferred-work notes without implementing unsupported placeholders.

## Functional Proof

Demonstrate:

1. A firm source profile contains an enabled and complete identifier-based Form 10-K retrieval candidate.
2. Pull readiness reports the artifact as runnable.
3. The pull workflow selects the compatible artifact-specific adapter explicitly.
4. The adapter resolves the configured SEC issuer identity.
5. The eligible filing set is filtered according to declared Form 10-K and amendment policy.
6. Candidate ordering and tie-breaking are deterministic.
7. Exactly one filing is selected.
8. The intended primary filing artifact is retrieved.
9. Filing identity, artifact identity, provider provenance, retrieval reference, media type, and checksum remain distinct and inspectable.
10. The artifact enters the repository only through public acquisition contracts.
11. The firm pull reports success for the Form 10-K and preserves accurate outcomes for other enabled artifacts.
12. A second equivalent pull does not create duplicate logical evidence.
13. Reordered equivalent provider metadata produces the same selected filing.
14. Missing configuration remains a configuration problem.
15. Provider or network failure remains a retrieval failure.
16. Malformed identity or content fails visibly.
17. Replay and repository inspection work with the adapter and network unavailable.
18. Derived indexes, where applicable, can be rebuilt without contacting the source.
19. Stored artifact integrity verifies independently.
20. Existing multi-firm pull and source-profile behavior remains intact.

## Validation Requirements

Validation must include:

- focused adapter-capability and selection tests;
- deterministic filing-selection tests;
- reordered-response tests;
- tie-break tests;
- amendment-policy tests;
- no-match and ambiguity tests;
- malformed-response and missing-identity tests;
- timeout, retry, rate-limit, and permanent-failure tests;
- content-type, empty-content, truncated-content, and size-bound tests where applicable;
- acquisition-engine integration tests using deterministic transport fixtures;
- stable identity and provenance tests;
- duplicate and no-change tests;
- partial firm-pull tests;
- pull-readiness and admin-console result tests;
- replay with network and adapter unavailable;
- index rebuild and artifact-integrity verification;
- all existing project tests and quality gates;
- isolated-tree or clean-checkout-equivalent validation;
- documentation and design-baseline validation;
- secret and sensitive-output scan;
- review-package manifest and ZIP integrity validation;
- one gated bounded live pull;
- one gated equivalent live rerun.

Tests must assert durable repository effects and operator-visible results, not only adapter return values.

## Required Verification Package

Produce a complete TASK-016 review directory and ZIP under the repository’s established review-package convention.

The package shall contain, at minimum:

- task ticket;
- executive summary;
- implementation summary;
- architecture decisions;
- alternatives considered;
- retrieval-adapter responsibility model;
- adapter capability and selection contract;
- artifact-specific Form 10-K policy;
- shared SEC provider-service boundary;
- SEC source and API-surface record;
- deterministic filing-selection policy;
- identity and provenance model;
- network and service-use boundary;
- failure and result taxonomy;
- source-profile and pull integration summary;
- future adapter extension analysis;
- known limitations and deferred work;
- cumulative task-scoped patch;
- changed-file inventory with rationale;
- repository tree;
- Git branch, base, HEAD, staged, unstaged, and untracked state;
- exact validation commands;
- complete raw focused-validation output;
- complete raw project-validation output;
- deterministic fixture evidence;
- reordered-response and tie-break evidence;
- amendment and no-match evidence;
- failure-injection evidence;
- first live-pull evidence;
- repeated live-pull and idempotency evidence;
- artifact inventory and checksum evidence;
- replay-with-network-blocked evidence;
- rebuild evidence where applicable;
- secret and sensitive-output scan;
- machine-readable review manifest;
- package member checksums;
- ZIP checksum and integrity evidence.

The package must distinguish offline validation from gated live operations and retain final evidence for any failed required check.

A passing summary without independently reviewable raw evidence is insufficient.

## Documentation and Durable Design Record

Update repository documentation and create or revise ADRs as warranted.

The durable design record shall explain:

- why deterministic retrieval is used for structured authoritative sources;
- why LLM-powered runtime discovery is excluded from this path;
- why adapters correspond to canonical artifact semantics;
- why a universal SEC adapter was deliberately rejected;
- how adapter capabilities are declared and selected;
- which responsibilities are generic;
- which responsibilities are shared SEC provider mechanics;
- which responsibilities remain Form 10-K-specific;
- how future deterministic, semi-deterministic, and discovery-based adapters can fit without changing repository authority;
- how filing and artifact identity remain stable;
- how temporal change in an external source differs from nondeterministic selection;
- what was learned from the live integration;
- which abstractions were deliberately deferred.

## Completion Record

Update this task ticket as the durable handoff record.

Preserve the original objective and requirements, then add:

- implementation resolution;
- files changed with rationale;
- design decisions and alternatives considered;
- exact verification commands and results;
- live-proof outcome;
- known limitations and deferred work;
- Architectural Status Summary.

The Architectural Status Summary shall report the status and boundaries of:

- canonical acquisition template;
- firm source profiles;
- pull orchestration;
- retrieval-adapter extension boundary;
- artifact-specific SEC Form 10-K adapter;
- shared SEC provider service;
- acquisition engine;
- repository evidence and identity;
- operator inspection;
- future deterministic adapters;
- future semi-deterministic adapters;
- future discovery-based adapters;
- downstream extraction and intelligence.

## Codex Execution Constraints

- Work only within the RFI-1 repository and the prepared TASK-016 branch.
- Read the governing project documents, current pull workflow, acquisition contracts, repository contracts, source-profile model, and TASK-014/TASK-015 completion records before designing changes.
- Treat this task ticket as the architectural requirement, not as an implementation recipe.
- Prefer existing public contracts over parallel infrastructure.
- Keep changes scoped to this vertical slice and its required verification.
- Do not commit, push, merge, delete branches, or perform repository cleanup unless explicitly instructed.
- Do not mark the task Done until every required verification artifact exists and all required validation passes.
- If a requirement conflicts with an established invariant, stop and report the conflict.

## Implementation Resolution

TASK-016 is implemented as an architecture-led vertical slice. The pull planner now selects
retrieval adapters through an explicit, deterministic capability registry keyed by canonical
artifact semantics and retrieval mode. The only new production artifact adapter is
`sec-form-10k`, which declares support for `sec_10k` through `identifier` retrieval. It owns
unamended Form 10-K eligibility, amendment exclusion, candidate ordering, primary-document
selection, multiplicity, stable identity, provenance, and artifact-specific failures.

A bounded shared SEC provider component owns only provider mechanics: CIK normalization,
authoritative endpoint construction, runtime request identity, pacing, timeouts, bounded retries,
same-origin redirects, size ceilings, response decoding, provider-record mapping, exact archive
retrieval, and sanitized usage diagnostics. It does not select filing forms or decide amendment,
multiplicity, or artifact semantics.

The selected primary filing bytes continue to enter through the existing acquisition engine and
repository contracts. The generic workflow contains no Form 10-K branch. It records the selected
adapter, stable filing/document identity, provider identifiers, locations, provenance, progress,
outcome, and sanitized diagnostics. A repeated pull selects the same filing and returns
`no_change` through the existing source checkpoint. Replay, rebuild, and integrity remain local
repository operations.

## Files Changed and Rationale

- `src/rfi/pull/adapters.py`, `planning.py`, `contracts.py`, `workflow.py`, and `__init__.py`
  establish capability declaration/selection and carry generic adapter evidence through planning
  and execution.
- `src/rfi/acquisition/sec_provider.py` and `sec_form_10k.py` implement bounded SEC mechanics and
  the single artifact-semantic Form 10-K policy; acquisition exports and failure codes expose the
  result through existing public contracts.
- `src/rfi/admin/server.py` and `pull_sources.html` expose readiness, selected adapter, progress,
  outcomes, provenance, and diagnostics without reading persistence files directly.
- `fixtures/sec-10k/`, `tests/test_task016.py`, and `scripts/task016_sec_10k.py` provide deterministic
  offline selection, failure, rerun, replay, rebuild, and integrity proof plus a separately gated
  live command.
- `scripts/generate_task016_review.py` and the Makefile produce independently reviewable raw
  evidence, checksums, manifest, final patch, sensitive-output scan, and verified ZIP.
- The TASK-015 tests/proof and foundation inventories were updated only to consume and recognize
  the new explicit extension boundary; all prior behavior remains regression-covered.
- README, TASKS, the pull/application/source-profile guides, ADR 0012, and
  `docs/deterministic-sec-form-10k-retrieval.md` make the boundary, operations, alternatives, and
  deferred scope durable.
- Root `BACKLOG.md`, ROADMAP/TASKS role notes, design-baseline records, and review packaging make
  unscheduled TASK-016 observations durable without converting them into sequenced or authorized
  work.

## Design Decisions and Alternatives Considered

1. Adapter capabilities are explicit immutable data. Adapter identity is unique, and registrations
   must not overlap on the effective `(canonical artifact_id, retrieval candidate mode)` selection
   key. Acquisition mechanism is downstream routing metadata and may be shared. Ambiguous
   capability configuration fails closed instead of depending on registration order.
2. The Form 10-K adapter consumes authoritative issuer identity from the firm/source-profile
   context, accepts only exact `10-K`, excludes `10-K/A`, sorts descending by filing date,
   acceptance datetime, and accession number, and retrieves exactly the selected
   `primaryDocument`.
3. Filing identity is SEC accession-based and document identity is stable across metadata order,
   pull run, and process restart. Temporal provider change may select a newly published filing;
   reordered identical provider data cannot change selection.
4. A universal configurable SEC filing adapter was rejected because it would move artifact policy
   into provider configuration. Form-specific branching in pull orchestration was rejected because
   it would defeat the extension boundary. Browser automation, open-web search, probabilistic or
   LLM selection, and complete-submission retrieval were rejected as non-authoritative or broader
   than this artifact contract.
5. Provider history pagination, other SEC forms, configurable amendment policies, generic
   discovery, extraction, analysis, and intelligence generation are deliberately deferred.

ADR 0012 contains the full decision and consequences. The operations guide contains the exact
responsibility model, failure taxonomy, identity model, and future-adapter analysis.

## Verification Record

Ordinary verification was run with live SEC credentials removed and uses only checked-in fixtures.
The exact raw output of every command is retained in the TASK-016 review directory and ZIP.

- `env -u RFI_SEC_USER_AGENT -u SEC_API_IO_API_KEY .venv/bin/python -m unittest tests.test_task016 -v`
  — PASS, 15 tests, including the shared-mechanism hardening matrix.
- `env -u RFI_SEC_USER_AGENT -u SEC_API_IO_API_KEY .venv/bin/python -m unittest tests.test_task015 -v`
  — PASS, 7 regression tests.
- `env -u RFI_SEC_USER_AGENT -u SEC_API_IO_API_KEY .venv/bin/python scripts/task016_sec_10k.py fixture-proof`
  — PASS; exact form/amendment policy, deterministic selection, provenance, first-pull success,
  repeated-pull `no_change`, and offline replay/rebuild/integrity verified.
- `git diff --check` — PASS.
- `.venv/bin/python scripts/check_docs.py` — PASS, 62 Markdown files and 16 local links.
- `.venv/bin/python scripts/check_baseline.py` — PASS, 8 design documents and 6 repository
  boundaries.
- `env -u RFI_SEC_USER_AGENT -u SEC_API_IO_API_KEY make validate` — PASS, 186 tests, every
  fixture proof, lint/format/typecheck over 119 Python files, import, documentation, baseline, and
  source-archive build/integrity.
- The review generator repeats the focused, regression, fixture, diff, documentation, baseline,
  and full project gates and runs an equivalent copied-tree validation without `.git`, environment
  contents, `.artifacts`, `.rfi`, or caches, recreating only the installed `rfi` console shim
  required by the existing entry-point parity test. It writes the final package to
  `.artifacts/review/TASK-016-review.zip` and its SHA-256 sidecar only after every check passes.

## Gated Live Proof

Live use was explicit and bounded:

```text
.venv/bin/python scripts/task016_sec_10k.py live-config
.venv/bin/python scripts/task016_sec_10k.py live-pull \
  --state .artifacts/runtime/TASK-016-sec-10k-v2 \
  --evidence .artifacts/review-input/TASK-016-live-v2.json \
  --confirm-live-sec
```

The passing run used authoritative SEC issuer CIK `1137789`, selected accession
`0001137789-25-000157`, and fetched exact primary document `stx-20250627.htm`. The artifact is
2,461,150 bytes with SHA-256
`b7649778590f8a953aa1002253b04f6722c07f441ff8009b595d2002bb6a3960`; its stable repository
document ID is `document-sec-1137789-000113778925000157`. The first pull was `success`; the
equivalent rerun was `no_change`. Total live use was three requests, zero retries, below the
six-request ceiling. Integrity passed before and after replay/rebuild, and replay/rebuild ran with
network access actively blocked.

The initial gated run exposed a real-provider distinction: unrelated recent-submission rows may
legitimately leave optional `reportDate` or `primaryDocument` columns blank. The original strict
provider-wide mapping rejected that response before artifact selection. The failed command and
durable failed run journals are retained. Validation was narrowed only for optional provider
columns; the selected eligible Form 10-K still requires an exact primary document. The corrected
run used a fresh state directory and passed.

No request identity, credential, API key, header, or downloaded filing bytes are present in the
review package. Live bytes remain only in the ignored runtime state.

## Known Limitations and Deferred Work

- Selection is intentionally limited to the SEC recent-submissions surface; older filing history
  pagination is not part of this slice.
- The artifact contract is unamended Form 10-K only. Amendments are explicitly excluded, not
  runtime-configurable.
- The local workflow remains single-process and single-writer.
- Capability priority, fallback ordering, and multiple-match resolution are deliberately absent;
  overlapping artifact/mode claims fail during registry construction. This is a fail-closed
  boundary, not a limitation on sharing downstream acquisition mechanisms.
- Other forms, exhibits, other artifacts, generic crawling/discovery, extraction, XBRL analysis,
  and intelligence generation remain out of scope.
- Availability and temporal freshness of the live SEC service remain external conditions; the
  offline fixture suite is the ordinary deterministic quality gate.

The actionable unscheduled limitations above are recorded as backlog candidates BLG-001 through
BLG-006. Their presence in `BACKLOG.md` does not authorize implementation, establish sequence, or
change TASK-016 scope.

## Architectural Status Summary

| Subsystem | Status | Boundary after TASK-016 |
| --- | --- | --- |
| Canonical acquisition template | Complete, unchanged authority | Defines the canonical artifact and allowed retrieval candidates; contains no SEC runtime policy. |
| Firm source profiles | Complete, integrated | Revision snapshot supplies enabled artifact, candidate, and authoritative issuer identifier. |
| Pull orchestration | Complete for this slice | Plans all enabled artifacts and executes selected capabilities generically; no Form 10-K branch. |
| Retrieval-adapter extension boundary | Complete | Adapter identity is unique; artifact/mode claim overlap is rejected; acquisition mechanism may be shared; selection is inspectable and fail-closed. |
| Artifact-specific SEC Form 10-K adapter | Complete for stated scope | Owns exact `10-K` policy, amendment exclusion, ordering, multiplicity, primary document, provenance, and failures. |
| Shared SEC provider service | Complete for justified mechanics | Owns bounded SEC transport and record mapping only; it is not a general SEC policy engine. |
| Acquisition engine | Complete, reused | Accepts adapter candidates, persists immutable evidence, exposes stable failure codes, and advances checkpoints. |
| Repository evidence and identity | Complete, reused | Accession-based logical identity, content-addressed artifacts, immutable attempts, replay, rebuild, and integrity. |
| Operator inspection | Complete for this slice | Readiness, capabilities, selections, progress, outcome, provenance, and sanitized diagnostics are visible. |
| Backlog governance | Complete | Unscheduled observations and deferred improvements are recorded separately from roadmap sequencing and authorized tasks. |
| Future deterministic adapters | Extension point ready | Add a unique adapter with a non-overlapping artifact/mode claim; downstream acquisition mechanisms may be reused without changing repository authority. |
| Future semi-deterministic adapters | Deferred | May use the same ingress after defining bounded candidate semantics and explicit operator-visible uncertainty. |
| Future discovery-based adapters | Deferred | Must remain separately governed; no browser, search, or probabilistic discovery entered this path. |
| Downstream extraction and intelligence | Unchanged and out of scope | Consumes repository evidence through existing downstream boundaries; retrieval performs no interpretation. |

## Focused Hardening Record — Shared Acquisition Mechanisms

Pre-commit review found that the initial registry implementation rejected any two retrieval
registrations whose source adapters exposed the same acquisition `mechanism`. That was the wrong
uniqueness boundary: mechanism is not consulted by pull planning or retrieval capability
selection, and distinct artifact-specific adapters may legitimately use the same downstream
acquisition route.

The corrected invariant is:

- `adapter_id` uniquely identifies a retrieval adapter registration;
- canonical `artifact_id` plus retrieval candidate `mode` is the effective selection key already
  used by `compatible()` and `select()`;
- claims that overlap on that effective key are rejected during registry construction;
- acquisition `mechanism` is retained as operator-visible routing/integration metadata and may be
  shared by registrations with distinct capabilities; and
- after selection, the generic workflow projects only the selected source adapter into the
  acquisition engine's mechanism-keyed registry for that run.

No capability priority, fallback ordering, or multiple-match resolution was added. Registration
order cannot affect selection. The workflow remains independent of SEC and Form 10-K behavior.
Focused coverage proves shared-mechanism registration for distinct Form 10-K/Form 10-Q capability
claims, duplicate adapter-identity rejection, same-effective-capability rejection, deterministic
selection across reversed registration order, selected-adapter acquisition projection, and the
unchanged complete Form 10-K pull/rerun/replay path.

The retained live proof remains applicable. The hardening changes only generic registry
construction and per-run acquisition-adapter projection. Production Form 10-K still selects the
same `sec-form-10k` registration, constructs the same acquisition source mechanism, and invokes the
same adapter/provider path. Offline end-to-end proof covers that exact path, so no additional SEC
request was justified.

## Backlog Governance Record

`BACKLOG.md` is established as the durable repository backlog. It records unscheduled candidates,
review observations, deferred improvements, and future feature ideas. `ROADMAP.md` remains the
record of intended direction and sequencing. `TASKS.md` and detailed tickets remain the only
records of authorized implementation work.

The documented lifecycle is:

```text
observation → backlog candidate → periodic triage
    → reject, retain, move to ROADMAP, or authorize as a task in TASKS
```

Each backlog entry records backlog ID, title, status, area, source, problem, potential value,
trigger, constraints, disposition, and optional Comments. Comments are a single plain-text field
for informal operator context only. They are not parsed as metadata, instructions, Markdown
substructure, links, acceptance criteria, or authoritative requirements.

The initial TASK-016 candidates are:

- BLG-001: exact-accession Form 10-K retrieval;
- BLG-002: historical SEC submissions retrieval;
- BLG-003: amended Form 10-K artifact semantics;
- BLG-004: additional artifact-specific SEC form adapters;
- BLG-005: scheduled or concurrent pull operation; and
- BLG-006: governed semi-deterministic and discovery adapters.

All six remain `Candidate`. None was moved into ROADMAP, authorized in TASKS, scheduled, or
implemented. `BACKLOG.md` is included in the design baseline, documentation validation, source
archive, cumulative patch, review manifest, member checksums, and final TASK-016 review ZIP.
