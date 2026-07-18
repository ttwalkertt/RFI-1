# TASK-018 — Artifact Repository Query Service and Read-Only Browser

## Status

Complete

## Objective

Establish a repository-owned, read-only artifact query service and prove it through an operator-facing artifact browser.

The browser shall present the repository’s artifact model as a navigable tree, allow deterministic inspection of stored artifact metadata, and render the stored artifact in a safe right-hand preview pane.

This task is primarily a repository query and inspection architecture task. The tree UI is the first consumer and proof of that query surface. Future pull planning, “Bring Repository Up to Date,” historical retrieval, analysis, and reporting shall be able to consume the same repository-owned read contracts without depending on persistence internals.

## Context

RFI-1 now has:

- canonical artifact definitions;
- firm source profiles;
- pull planning and execution;
- retrieval-adapter selection;
- deterministic SEC Form 10-K retrieval;
- durable repository ingress;
- stable document identity;
- immutable stored bytes;
- provenance, checksums, replay, rebuild, and integrity verification;
- operator-visible pull results.

The next architectural need is a complete and coherent repository read surface.

A narrow pull-specific “find the latest artifact” query would satisfy only one immediate use case. RFI-1 ultimately needs a broader artifact browser and query capability that supports:

- operator inspection;
- deterministic latest-artifact lookup;
- source-effective ordering;
- date-bounded queries;
- pagination and lazy expansion;
- future “Bring Repository Up to Date” planning;
- later analysis and reporting consumers.

TASK-018 shall build that read foundation first.

## Architectural Intent

### Repository-owned read contracts

Consumers shall query artifacts through explicit repository-owned read contracts.

The browser, future pull planner, and later analysis components shall not:

- traverse raw repository files directly;
- depend on event-log or index layout;
- interpret storage-specific metadata structures;
- reconstruct repository status from implementation details;
- query SEC-specific provenance fields as though they were generic repository contracts.

The repository read surface shall normalize durable artifact state into stable query and detail contracts.

### The browser exposes the repository mental model

The primary hierarchy shall describe canonical artifact semantics rather than provider-specific transport or form codes.

A representative tree is:

```text
Firms
└── Amazon
    └── Regulatory filings
        ├── Annual reports
        │   └── FY 2025
        ├── Quarterly reports
        └── Current reports
```

Provider-specific facts such as `10-K`, accession number, SEC endpoint, or source filename remain visible in artifact metadata but do not define the primary operator hierarchy.

The hierarchy must be derived from durable repository content and canonical artifact metadata, not from hard-coded SEC assumptions.

### Read-only inspection

Artifacts and repository evidence remain immutable.

TASK-018 supports:

- browse;
- query;
- inspect;
- preview;
- open stored document;
- open original source where available.

It does not support:

- edit;
- rename;
- delete;
- metadata correction;
- provenance mutation;
- source reassignment;
- checksum replacement;
- annotation;
- manual status changes.

Metadata editing shall be introduced only if a demonstrated operational requirement later makes it unavoidable.

### Stored artifact is authoritative for inspection

The primary preview and “Open in new tab” action shall use the stored repository copy.

The original provider location is provenance and may be exposed separately as “Open original source.”

The browser must not substitute a live provider page for the stored immutable artifact.

### Safe rendering boundary

Stored documents are externally sourced and potentially hostile.

The artifact preview shall not execute externally supplied content with admin-console authority.

The architecture must establish a safe rendering boundary suitable not only for SEC filings but for later arbitrary public web material.

## Companion Engineering Guidance

TASK-018 is accompanied by:

`TASK-018-engineering-guidance-artifact-query-contract.md`

Codex shall read this document before designing the implementation and shall copy it into the repository as a durable engineering/design document, adapting its repository path and title to established documentation conventions.

The companion guidance clarifies:

- the intended stability and consumers of the repository query interface;
- separation of query, summary, detail, and content contracts;
- source-effective ordering;
- deterministic pagination and consistency semantics;
- latest-artifact lookup as a projection of the ordinary query contract;
- identity boundaries;
- tree projection versus repository model;
- safe content access and HTML preview isolation;
- evidence expected in the review package.

The guidance is architectural, not prescriptive. Codex may refine the concrete types and endpoints after inspecting the repository, but shall document any material departure and preserve the stated boundaries.

## Required Outcomes

### 1. Artifact query service

Provide a repository-owned query service capable of supporting at least:

- listing firms with durable artifact counts;
- listing artifact families and canonical artifact types for a firm;
- listing artifacts for a firm and canonical artifact type;
- deterministic source-effective ordering;
- ascending and descending ordering where appropriate;
- date-from and date-through filters;
- durable-status filtering;
- provider filtering where justified;
- pagination or cursor-based continuation;
- bounded result limits;
- latest-artifact lookup;
- oldest-artifact lookup where naturally supported;
- empty-result behavior;
- stable artifact detail lookup by repository document identity.

The query service shall return normalized read models rather than raw persistence objects.

### 2. Normalized read contracts

Define explicit contracts for at least:

#### Artifact summary

Sufficient for tree leaves and result lists, including where available:

- document ID;
- firm identity;
- canonical artifact identity;
- artifact family;
- display title;
- source-effective date;
- filing, publication, or period date;
- provider;
- provider artifact type;
- provider identifiers;
- repository status;
- ingestion time;
- immutable checksum;
- media type.

#### Artifact detail

Sufficient for the metadata pane, including where available:

- all summary fields;
- full provenance locations;
- retrieval source and adapter identity;
- source-profile revision or acquisition context;
- provider-native identifiers;
- content size;
- checksum and integrity status;
- stored-content availability;
- original-source availability;
- relevant artifact-specific metadata;
- repository event or revision references only where operator-useful.

Unknown or inapplicable fields shall remain explicit rather than being guessed.

### 3. Deterministic ordering semantics

Artifact ordering shall use source-effective semantics rather than retrieval time.

Examples include:

- SEC filing acceptance time, filing date, and accession tie-breaker;
- publication time for published material;
- source revision or observation time where no source publication date exists.

The repository query contract shall expose normalized source-effective ordering fields without forcing generic consumers to parse provider-specific metadata.

Retrieval time may be displayed but shall not define “latest artifact” unless the canonical artifact semantics explicitly require it.

Tie-breaking must be explicit and deterministic.

### 4. Tree-oriented browser projection

Provide an operator-facing artifact browser in the admin console.

The desktop layout shall use a split pane:

- left pane: repository tree;
- right pane: selected artifact metadata and preview;
- draggable divider;
- reasonable initial split, approximately one-third tree and two-thirds detail;
- full-height use of available browser space;
- responsive fallback for narrow screens.

The tree shall support lazy expansion or equivalent bounded loading so large repositories do not require complete materialization in one response.

The initial semantic hierarchy shall be:

```text
Firm
    Artifact family
        Canonical artifact type
            Artifact instance
```

Codex may refine leaf labels and intermediate grouping where repository semantics justify it, but shall preserve the canonical-artifact-first model.

### 5. Tree behavior

The browser shall support:

- expand and collapse;
- deterministic child ordering;
- loading state;
- empty state;
- query failure state;
- partial availability state;
- retained selection during ordinary refresh where possible;
- clear distinction between expandable category nodes and artifact leaves;
- pagination or “load more” behavior for large artifact streams;
- keyboard-accessible navigation where practical under the existing admin UI approach.

Selecting a category node may show a summary of that subtree.

Selecting an artifact leaf shall populate the right pane.

A modal dialog shall not be the primary desktop interaction.

### 6. Metadata pane

The selected artifact view shall present pertinent metadata in a compact operator-readable form rather than dumping raw JSON.

For SEC filings, the view should naturally include where available:

- firm;
- canonical artifact;
- provider form type;
- source-effective date;
- filing date;
- acceptance time;
- period of report;
- accession number;
- document ID;
- provider;
- media type;
- content size;
- checksum;
- integrity status;
- ingestion time;
- retrieval adapter;
- provenance locations.

The metadata area shall be collapsible so the preview can use more vertical space.

Raw metadata may be available through an explicit advanced disclosure if useful, but it shall not replace the normalized view.

### 7. Stored-document preview

The right pane shall preview the stored repository copy.

Initial supported behavior:

- HTML: render in a sandboxed preview frame;
- PDF: use browser-native embedded PDF rendering where supported;
- plain text and compatible textual formats: escaped read-only text rendering;
- unsupported or binary formats: show metadata and offer open/download behavior without attempting unsafe inline rendering.

The preview shall:

- fill the remaining right-pane space;
- expose clear loading and failure states;
- preserve the selected artifact;
- avoid navigating the admin console away from the browser;
- avoid contacting the original provider merely to render the stored artifact.

### 8. Safe content-serving endpoint

Provide a repository-owned read-only content endpoint for stored artifacts.

It shall:

- resolve content by repository document identity;
- serve only stored repository bytes;
- return the correct or safely normalized media type;
- enforce content-length and range behavior as appropriate;
- prevent arbitrary filesystem path access;
- reject missing, invalid, or unavailable content explicitly;
- preserve immutable checksum and identity semantics;
- emit defensive response headers;
- prevent stored HTML from inheriting admin-console authority;
- avoid leaking internal filesystem paths;
- support opening the stored document in a new tab.

The implementation shall define and verify the security boundary for previewed HTML.

A restrictive sandbox shall be the default. Script execution, same-origin privilege, forms, popups, top navigation, and other capabilities shall remain disabled unless a specific verified need requires a narrowly scoped exception.

### 9. Operator actions

The selected artifact view shall provide:

- **Open stored document in new tab**
- **Open original source**, when an authoritative provenance location exists

The first action is the primary inspection path.

The second is provenance convenience and must be clearly distinguished from the stored artifact.

External links shall use safe new-tab behavior and shall not imply that the live source is identical to the retained bytes.

### 10. Query support for future “Bring Repository Up to Date”

The query service shall be expressive enough for a future request planner to determine the newest durable artifact for:

- one firm;
- one canonical artifact type;
- optional provider or source constraints where semantically required.

The planner shall be able to obtain normalized source-effective ordering information without understanding persistence layout.

TASK-018 does not implement retrieval planning or the “Bring Repository Up to Date” action. It establishes the reusable query capability that future planning will consume.

### 11. Query support for historical and exact inspection

The query service shall support:

- date-bounded artifact listing;
- newest-first and oldest-first ordering;
- exact document lookup by repository identity;
- bounded enumeration of all matching artifacts;
- stable pagination across repeated equivalent queries over an unchanged repository snapshot.

Do not build a general-purpose user-authored query language.

Provide explicit typed query inputs that cover the demonstrated repository and planning use cases.

### 12. Browser-local preferences

Where appropriate, use the existing browser-local admin-preference mechanism for non-authoritative presentation preferences such as:

- split-pane position;
- metadata-pane collapsed state;
- possibly last selected browser view mode.

These preferences shall not enter repository state, artifact metadata, task state, or provenance.

The artifact browser must remain fully functional when no preference exists or browser storage is unavailable.

### 13. Repository integrity and replay

Artifact query and content-serving behavior shall remain valid after:

- process restart;
- repository replay;
- derived-index rebuild;
- network disconnection;
- retrieval adapters unavailable;
- original provider unavailable.

The browser shall inspect durable repository state only.

Derived query indexes may be introduced or extended if justified, but they must be rebuildable from authoritative repository state.

## Functional Proof

Demonstrate:

1. The browser lists firms that have durable artifacts.
2. Firm expansion shows artifact families and canonical artifact types derived from repository content.
3. Artifact-type expansion lists artifact instances in deterministic source-effective order.
4. Amazon and Seagate Form 10-K artifacts can be located through the browser.
5. Selecting an artifact populates a normalized metadata pane.
6. Provider-specific SEC metadata appears as metadata rather than primary tree structure.
7. The stored Amazon or Seagate Form 10-K HTML renders in the right-hand preview pane.
8. Preview content is served from repository storage.
9. The original SEC location remains separately visible as provenance.
10. “Open stored document in new tab” works.
11. “Open original source” works when available.
12. The browser exposes no edit, rename, delete, metadata mutation, or provenance mutation controls.
13. Sandboxed HTML cannot access admin-console state or navigate the parent application.
14. Missing or corrupt stored content produces an explicit read-only error state.
15. Unsupported media types produce a safe fallback.
16. Date-bounded queries return only matching artifacts.
17. Latest-artifact lookup returns the correct source-effective artifact, not the most recently retrieved artifact.
18. Reordered equivalent underlying records do not change query ordering.
19. Pagination or lazy loading remains stable and bounded.
20. Empty firms or artifact types produce clear empty states.
21. Query service and browser work with the network blocked.
22. Replay and index rebuild preserve equivalent query and browser results.
23. Artifact integrity verification remains independent and passes.
24. Existing pull, acquisition, source-profile, and admin-preference behavior remains intact.

## Failure Semantics

The implementation shall distinguish at least:

- invalid query;
- unsupported filter combination;
- unknown firm;
- unknown canonical artifact;
- unknown document ID;
- no matching artifacts;
- unavailable derived index;
- rebuild required;
- missing stored content;
- checksum or integrity mismatch;
- unsupported preview type;
- unsafe or rejected content type;
- malformed provenance;
- original source unavailable;
- pagination cursor invalid or stale;
- repository read failure;
- successful empty result;
- successful artifact summary;
- successful artifact detail;
- successful stored-content response.

Failure responses shall be structured, sanitized, operator-visible, and suitable for API and UI testing.

## Architectural Constraints

- Preserve immutable repository and artifact semantics.
- Keep the browser read-only.
- Do not add metadata editing.
- Do not add artifact deletion.
- Do not expose raw filesystem paths.
- Do not make the browser depend on live provider access.
- Do not render the original provider URL as the primary preview.
- Do not query raw persistence structures directly from admin handlers or browser JavaScript.
- Do not make generic consumers interpret SEC-specific metadata.
- Do not define “latest” by ingestion time when source-effective ordering exists.
- Do not build a universal free-form query language.
- Do not add pull-planning behavior to the artifact browser.
- Do not add analysis, extraction, search, annotations, or report generation.
- Do not broaden browser-local preferences into repository configuration.
- Do not weaken content-security boundaries to make a preview render.
- Do not duplicate existing repository contracts where a public read path can be extended cleanly.
- Stop and report a conflict rather than bypassing established repository authority.

## Non-Goals

TASK-018 does not require:

- the four additional SEC numbered-form adapters;
- “Bring Repository Up to Date” execution;
- historical acquisition;
- exact-accession acquisition;
- scheduled pulling;
- full-text search;
- OCR;
- section extraction;
- document chunking;
- embeddings;
- semantic search;
- concept, claim, position, or projection generation;
- artifact editing;
- metadata repair;
- annotation;
- tagging;
- deletion;
- retention-policy controls;
- user authentication;
- multi-user authorization;
- rich office-document conversion;
- custom PDF rendering;
- custom HTML rewriting;
- external viewer integration beyond normal browser behavior;
- mobile-first redesign;
- speculative query features unsupported by current or near-term consumers.

## Validation Requirements

Validation must include:

- repository query contract tests;
- deterministic ordering and tie-break tests;
- source-effective versus retrieval-time tests;
- firm, family, type, summary, and detail query tests;
- date-boundary tests;
- latest and oldest artifact lookup tests;
- empty-result tests;
- pagination or cursor stability tests;
- invalid and stale cursor tests;
- replay and rebuild tests;
- network-blocked tests;
- stored-content endpoint tests;
- content-type and size tests;
- path-traversal and arbitrary-file-access tests;
- missing and corrupt content tests;
- checksum and integrity tests;
- HTML sandbox tests;
- parent-navigation and application-state isolation tests;
- PDF and text preview tests;
- unsupported-media fallback tests;
- open-stored and open-source link tests;
- read-only UI tests;
- no-mutation-control tests;
- browser-local preference fallback tests;
- admin-console integration tests;
- regression tests for TASK-015, TASK-016, and TASK-017 behavior where applicable;
- full project validation;
- isolated-tree or clean-checkout-equivalent validation;
- documentation and design-baseline validation;
- sensitive-output scan;
- review-package manifest and ZIP integrity validation.

Tests shall assert durable repository effects and operator-visible behavior, not merely helper-function return values.

## Required Verification Package

Produce a complete TASK-018 review directory and ZIP under the repository’s established review-package convention.

The package shall contain, at minimum:

- task ticket;
- executive summary;
- implementation summary;
- architecture decisions;
- alternatives considered;
- repository query contract;
- normalized summary and detail contracts;
- deterministic ordering policy;
- query filter and pagination model;
- tree projection model;
- browser interaction model;
- content-serving boundary;
- preview security model;
- read-only authority model;
- browser-local preference usage;
- future “Bring Repository Up to Date” consumer analysis;
- known limitations and deferred work;
- cumulative task-scoped patch;
- changed-file inventory with rationale;
- repository tree;
- Git branch, base, HEAD, staged, unstaged, and untracked state;
- exact validation commands;
- complete raw focused-validation output;
- complete raw full-project validation output;
- query fixture and expected-result evidence;
- ordering and pagination evidence;
- artifact detail evidence;
- stored-content response evidence;
- HTML sandbox evidence;
- PDF/text/unsupported-media evidence;
- network-blocked browser evidence;
- replay and rebuild evidence;
- artifact-integrity evidence;
- browser screenshots or equivalent rendered evidence;
- sensitive-output scan;
- machine-readable review manifest;
- package member checksums;
- ZIP checksum and integrity evidence.

A passing summary without independently reviewable raw evidence is insufficient.

## Documentation and Durable Design Record

Update repository documentation and create or revise ADRs as warranted.

The durable design record shall explain:

- why a repository-owned query service precedes pull-specific latest-artifact lookup;
- how the browser and future pull planner share the same read contracts;
- why the tree reflects canonical artifact semantics rather than provider taxonomy;
- how source-effective ordering is normalized;
- how deterministic pagination works;
- why stored content is the primary preview source;
- how stored HTML is isolated from admin-console authority;
- why the browser is read-only;
- how browser-local preferences remain non-authoritative;
- which query capabilities are implemented now;
- which query capabilities are deliberately deferred;
- how future “Bring Repository Up to Date” planning will consume this work.

## Backlog and Deferred Work

Review BACKLOG.md during implementation.

Add genuine newly discovered unscheduled items using the established backlog structure, including the plain-text Comments field where useful.

Do not turn backlog observations into implementation scope unless this ticket explicitly requires them.

## Completion Record

Update this task ticket as the durable handoff record.

Preserve the original objective and requirements, then add:

- implementation resolution;
- files changed with rationale;
- design decisions and alternatives considered;
- exact verification commands and results;
- browser proof;
- preview-security proof;
- replay and rebuild outcome;
- known limitations and deferred work;
- Architectural Status Summary.

The Architectural Status Summary shall report the status and boundaries of:

- canonical artifact model;
- repository ingress;
- repository read/query service;
- normalized artifact summary and detail contracts;
- source-effective ordering;
- artifact tree projection;
- artifact browser;
- stored-content endpoint;
- preview security;
- browser-local preferences;
- pull workflow;
- future “Bring Repository Up to Date” planner;
- future SEC adapter batch;
- downstream extraction and intelligence.

## Codex Execution Constraints

- Work only within the RFI-1 repository and the prepared TASK-018 branch.
- Read the governing project documents, BACKLOG.md, TASK-015, TASK-016, TASK-017, repository contracts, admin-console structure, and review-package conventions before designing changes.
- Treat this task ticket as an architectural requirement, not an implementation recipe.
- Prefer existing public contracts over parallel infrastructure.
- Keep implementation scoped to query, inspection, and safe preview.
- Do not commit, push, merge, stage, clean, delete branches, or perform unrelated repository cleanup unless explicitly instructed.
- Do not mark the task Done until all required verification evidence exists and every required validation passes.
- If a requirement conflicts with an established invariant, stop and report the conflict rather than weakening the invariant.

## Implementation Resolution

TASK-018 adds `rfi.artifacts` as the repository-owned read boundary. Its typed query, page,
summary, detail, source-effective ordering, provenance-location, and content contracts are
persistence-independent. The service reads only public acquisition repository operations and the
canonical firm/artifact authorities. Admin handlers and browser code never traverse files, derived
index layout, or SEC-specific storage.

Queries support firm, canonical family/type, provider, durable status, source-effective date
bounds, newest/oldest order, limits from 1 through 100, exact document lookup, and snapshot-bound
opaque cursors. `latest()` and `oldest()` delegate to ordinary queries. The future Bring Repository
Up to Date planner can therefore request one firm/type and consume normalized source-effective
facts without parsing SEC metadata or knowing storage layout.

The `/artifacts` console page lazily projects firm → canonical family → canonical artifact type →
artifact document. Its draggable split pane, collapsible normalized metadata, responsive fallback,
load-more behavior, stored/original actions, and preview use the public HTTP projection of the same
service. Split/collapse values use the existing disposable browser preference facility. There are
no mutation controls.

Stored content resolves only by repository document identity and passes repository integrity
verification. The response provides controlled media types, size, range support, path-safe errors,
and defensive headers. HTML is isolated by both an empty iframe sandbox and response CSP
`sandbox; default-src 'none'`; scripts, same-origin authority, forms, popups, navigation, and remote
subresources are denied. The protection also applies when stored HTML opens in a new tab.

## Files Changed with Rationale

- `src/rfi/artifacts/`: normalized repository query/detail/content contracts and service.
- `src/rfi/admin/server.py`, `artifact_browser.html`, and existing console pages: thin read API,
  isolated content response, lazy split-pane browser, and shared navigation.
- `tests/test_task018.py`, `scripts/task018_artifact_browser.py`: focused public-ingress contract,
  ordering, pagination, failure, content, security, network-blocked, replay, and operator proof.
- `docs/artifact-query-service-and-browser.md`, ADR-0014, architecture/design-baseline records,
  README, and TASKS: durable architecture, operations, and milestone status.
- `Makefile`, review generator, baseline/scope inventories, and existing foundation tests: focused,
  full, isolated, and independently reviewable package gates.
- The repository-provided TASK-018 ticket and engineering guidance become durable tracked inputs.

## Design Decisions and Alternatives

- One logical document appears once; if it has multiple byte revisions, its current summary uses
  the latest ingested immutable revision. Cross-document chronology always uses source-effective
  values, then provider-neutral secondary identity, document ID, and artifact ID.
- Cursor continuation binds a query fingerprint and offset to a digest of authoritative source,
  ledger, and artifact metadata. Repository change produces `stale_cursor` instead of mixed pages.
- A current-state scan is proportionate for the POC and avoids a new derived index without measured
  scale evidence. A rebuildable query index remains a later optimization.
- Browser-specific traversal, provider-shaped generic queries, latest-by-ingestion, unbound
  offsets, live-provider preview, HTML rewriting, and unsandboxed same-origin HTML were rejected.

## Verification Record

The complete raw output is retained under `.artifacts/review/TASK-018/validation/`.

- `PYTHONPATH=src .venv/bin/python -m unittest tests.test_task018 -v` — PASS, 5 focused
  tests covering normalized queries/details/content, dates, latest/oldest, stable and stale
  cursors, tree projection, empty semantics, range responses, security, replay, integrity, and
  network blocking.
- TASK-015 through TASK-018 regression matrix — PASS, 30 tests.
- `env -u RFI_SEC_USER_AGENT -u SEC_API_IO_API_KEY make validate` — PASS, 194 tests plus all
  deterministic proofs, lint, format, type, import, docs, baseline, and source archive gates.
- Copied-tree validation without Git, state, artifacts, caches, or environment credentials — PASS.
- `scripts/generate_task018_review.py` — PASS, including sensitive-output scan, manifest, member
  checksums, exact ZIP listing, ZIP checksum, and member integrity.

## Browser, Security, Replay, and Stored-Content Proof

Rendered inspection against the retained TASK-016 Seagate state located the canonical Form 10-K,
displayed normalized source-effective and SEC metadata, and rendered the 2,461,150-byte stored HTML
copy in the right pane. The stored and original-source actions remained visibly separate. The
rendered screenshot is packaged as `evidence/artifact-browser-rendered.png`.

Fixture proof locates Amazon and Seagate artifacts, shows that the 2025 Seagate filing is latest
even though the 2024 filing was ingested later, verifies bounded page continuation, and reads exact
hostile-test HTML bytes from repository storage. Tests assert empty iframe sandbox capabilities,
the CSP sandbox/default denial, defensive headers, single byte ranges, unsupported-media fallback,
and absence of mutation controls. Network-blocked replay and a new service instance produce the
same query page and integrity remains PASS.

## Known Limitations and Deferred Work

- Current queries scan POC authoritative records and derive snapshot digests per request; a
  rebuildable performance index awaits measured corpus need.
- Lists expose the current immutable revision of each logical document, not retrieval-attempt
  history. Prior revisions remain authoritative and replayable but lack a dedicated browser view.
- Retrieval-time fallback is permitted only when no valid source publication/observation field
  exists and is labeled explicitly.
- Exact stored HTML may look less polished because remote subresources are deliberately blocked.
- Full-text/semantic search, extraction, arbitrary predicates, metadata repair, annotations,
  mutation, Bring Repository Up to Date, and analysis remain out of scope.

## Architectural Status Summary

| Subsystem | Status | Boundary after TASK-018 |
| --- | --- | --- |
| Canonical artifact model | Complete, reused | Owns family/type semantics; provider taxonomy remains metadata. |
| Repository ingress | Complete, unchanged | Sole immutable evidence write path. |
| Repository read/query service | Complete | Typed normalized read surface over public authoritative repository reads. |
| Summary/detail/content contracts | Complete | Separate bounded models for enumeration, inspection, and bytes. |
| Source-effective ordering | Complete | Normalized chronology with explicit deterministic tie-breakers and fallback basis. |
| Artifact tree projection | Complete | Lazy canonical hierarchy; not the repository model. |
| Artifact browser | Complete | Read-only split-pane operator inspection with responsive fallback. |
| Stored-content endpoint | Complete | Identity-only, integrity-checked, ranged, path-private exact bytes. |
| Preview security | Complete | Empty iframe sandbox plus CSP sandbox/default denial and no remote loads. |
| Browser-local preferences | Complete, reused | Disposable split/collapse presentation state only. |
| Pull workflow | Complete, unchanged | Remains the sole acquisition orchestration path. |
| Bring Repository Up to Date planner | Not started; contract ready | May consume ordinary latest query without provider/storage knowledge. |
| Future SEC adapter batch | Not started | Provider metadata can use the same normalized read model. |
| Downstream extraction/intelligence | Unchanged and out of scope | May consume repository reads without browser or storage coupling. |

Architectural change: durable artifact state now has one reusable repository-owned read boundary
shared by human inspection and future automated consumers. Next architectural milestone: implement
Bring Repository Up to Date planning against this latest-artifact contract, or authorize the next
roadmap milestone based on current governance.
