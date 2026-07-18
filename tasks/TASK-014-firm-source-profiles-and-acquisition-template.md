# TASK-014 — Firm Source Profiles and Canonical Acquisition Template

## Status

Complete

## Objective

Add firm-specific source profiles as a separate revisioned aggregate, backed by one repository-owned canonical template that defines the source categories and artifact types available for acquisition planning.

The task shall provide a usable administrative interface for selecting desired artifact streams and configuring how each stream may be retrieved for a firm.

This task defines acquisition configuration only. It does not execute acquisition.

## Motivation

Operators need a consistent way to specify which source artifacts should be collected for each target firm.

The available source families should not be hard-coded in Python or duplicated across the service and user interface. They should be defined once in a repository-owned template that can be validated and rendered by the application.

Retrieval methods differ materially across source types:

- some sources are deterministically addressable by a stable identifier or endpoint;
- some expose a stable landing page whose children must be discovered;
- some require bounded search and operator-provided hints.

The source-profile model must represent these differences without coupling retrieval configuration to the immutable target-firm identity record.

## Architectural Decision

Firm source profiles shall be stored as a separate revisioned aggregate keyed by `firm_id`.

Editing source-profile configuration shall create a new source-profile revision. It shall not create a new target-firm revision.

The canonical source-family list shall be stored as one shipped repository resource. The implementation shall not introduce multiple schema or template versions unless a future requirement makes versioning necessary.

## Canonical Template

Add one canonical repository-owned YAML template in a suitable shipped application-resource location, preferably:

```text
src/rfi/resources/source-profile-template.yaml
```

The exact location may differ if an existing repository convention provides a better fit, but the template shall:

- be packaged with the application;
- be source controlled;
- be loaded by the product at runtime;
- be validated by project quality gates;
- remain the single canonical definition used by the service and admin UI;
- not be duplicated as a parallel hard-coded list.

## Canonical Item Definition

Each canonical artifact item shall include at least:

- stable canonical identifier;
- short name;
- display label;
- description;
- category;
- default enabled state;
- addressability class;
- supported retrieval fields or retrieval-candidate shapes.

The `short_name` is intended for compact tables, chips, summaries, and card headers.

Examples:

```yaml
id: sec_10k
short_name: 10-K
label: Annual report on Form 10-K
```

```yaml
id: earnings_transcript
short_name: Call transcript
label: Earnings-call transcript
```

```yaml
id: press_release
short_name: Press release
label: Corporate press release
```

Short names shall be concise, human-readable, unique across canonical items, and suitable for clean UI listings.

## Initial Canonical Categories

The initial template shall include a useful, expanded working set organized into categories such as:

### Regulatory and financial

- Form 10-K
- Form 10-Q
- Form 8-K
- Form 20-F
- Form 6-K
- Proxy statement
- Ownership and insider filings
- Other statutory or exchange filings
- Annual report

### Earnings and investor materials

- Earnings release
- Earnings-call transcript
- Earnings-call audio or webcast
- Prepared remarks
- Earnings presentation
- Supplemental financial tables
- Investor-day presentation
- Analyst or conference presentation

### Corporate communications

- Press release
- Corporate news item
- Corporate blog
- Engineering blog
- Executive commentary
- Customer case study
- Partner announcement

### Product and technical material

- Product page
- Product data sheet
- Architecture guide
- Deployment guide
- Product manual
- Compatibility matrix
- Support bulletin
- Firmware or software release note
- End-of-life notice
- Technical white paper

### Social and public commentary

- X post or thread
- Medium article
- LinkedIn post
- Official video
- Webinar

### Conferences and research

- Conference presentation
- Conference video
- Standards contribution
- Technical paper
- Patent or patent application

### Market and organizational signals

- Job posting
- Government contract or procurement notice
- Subsidy, grant, permit, or expansion notice
- Regulatory or export-control notice

Codex may refine names and grouping for consistency, but shall preserve the breadth and operator intent of this list.

## Addressability

The canonical model shall support these addressability classes:

### Deterministic

A source can be located from a stable identifier, feed, API, or endpoint.

Examples:

- SEC filings by CIK and form;
- RSS or Atom feed;
- stable API;
- known social account;
- known publication feed.

### Semi-deterministic

A stable listing, archive, landing page, or portal exists, but individual artifacts must be discovered from it.

Examples:

- press-release archive;
- investor-events page;
- corporate blog index;
- product-documentation portal.

### Discovery-based

No stable complete endpoint exists, or relevant artifacts may appear across multiple locations.

Examples:

- third-party call transcripts;
- employee-authored Medium posts;
- conference talks;
- job postings;
- executive social posts.

The addressability class is acquisition metadata. It shall not be treated as an artifact classification beyond retrieval planning.

## Firm Source-Profile Aggregate

A firm source profile shall be independently revisioned and shall include:

- firm identifier;
- source-profile revision identifier and revision number;
- creation and update timestamps;
- superseded revision reference where applicable;
- one configuration entry per selected canonical artifact item;
- enabled or disabled state;
- retrieval candidates;
- operator notes;
- optional item-specific hints or locators.

The aggregate shall preserve immutable revision history using repository conventions already established for target firms.

## Retrieval Configuration

A source-profile item may contain zero or more retrieval candidates.

Each candidate shall support the fields appropriate to its retrieval mode, including where applicable:

- retrieval mode;
- URL or endpoint;
- stable locator, such as CIK, account, publication, or feed;
- preferred domains;
- discovery hints or search phrases;
- expected media type;
- parser or adapter hint;
- priority;
- operator notes.

The model shall support direct URL retrieval, stable listing-page discovery, feeds, identifiers, and bounded discovery hints without assuming that every source is deterministically addressable.

The configured retrieval URL is not the same as the URL ultimately used for a retrieved source object. Actual retrieval provenance remains outside this task.

## Administrative Interface

Add a firm-level source-profile interface in the admin console.

The UI should present the canonical source template as a categorized accordion or expandable card stack.

Each canonical item shall provide:

- checkbox or equivalent enabled control;
- short name;
- display label and description;
- addressability indicator;
- concise configuration-status summary;
- expandable retrieval configuration.

Collapsed rows should remain compact and scannable.

Example:

```text
[x] 10-K                 Deterministic · configured
[x] Press release        Semi-deterministic · 2 candidates
[ ] Medium               Discovery-based · not configured
```

Expanded configuration should allow applicable URLs, locators, hints, priorities, and notes to be entered or edited.

The UI shall load the canonical categories and items from the repository template rather than a duplicated hard-coded list.

## Persistence and Validation

The implementation shall:

- validate the canonical template before use;
- fail clearly if the shipped template is malformed or internally inconsistent;
- validate source-profile edits before publication;
- reject unknown canonical item identifiers;
- enforce unique canonical item identifiers and short names;
- preserve deterministic ordering;
- create immutable source-profile revisions;
- retain readable revision history;
- preserve the prior valid profile when publication fails.

A firm may initially have no explicit source-profile revision. The product shall define clear behavior for displaying canonical defaults before the first profile is saved.

## Cross-Firm Isolation

Each firm shall have an independent source profile and future acquisition pipeline.

This task shall not implement cross-firm artifact deduplication, shared source-profile objects, global reference counting, or cross-firm acquisition optimization.

The design shall not prevent future use of content hashes or other deduplication mechanisms, but no cross-firm deduplication behavior is required here.

## Alias Usability Refinement

When this area is next modified, normalize redundant firm aliases rather than rejecting an alias that is equal to the canonical name.

At firm creation and import boundaries:

- remove aliases equal to the canonical name after normalization;
- deduplicate aliases case-insensitively;
- preserve genuinely distinct aliases;
- reject only ambiguous or conflicting aliases;
- report normalized or dropped aliases where practical.

Apply the behavior consistently across applicable admin, API, starter-data, and catalog-import paths.

This refinement may be included in TASK-014 if it remains small and well-contained. It shall not displace the primary source-profile scope.

## Non-Goals

This task does not include:

- source acquisition execution;
- polling or scheduling;
- network retrieval;
- automatic URL discovery;
- parsing retrieved documents;
- source-object creation;
- claim or evidence extraction;
- source-quality ranking;
- credentialed social-platform access;
- cross-firm deduplication;
- migration among multiple template versions.

## Verification Requirements

Produce a complete verification package demonstrating:

### Canonical template

- the template is packaged and loadable;
- all canonical item identifiers are unique;
- all short names are present, concise, and unique;
- categories and item ordering are deterministic;
- malformed templates fail clearly;
- the service and UI consume the same canonical template;
- no parallel hard-coded canonical item list exists.

### Revisioned aggregate

- a firm with no saved profile displays documented defaults;
- first save creates source-profile revision 1;
- editing creates revision 2 without revising the target-firm record;
- prior source-profile revisions remain readable;
- failed publication preserves the prior profile and leaves no partial artifacts;
- profiles are isolated by firm.

### Retrieval configuration

- deterministic locator configuration;
- semi-deterministic listing-page configuration;
- discovery-based hints;
- multiple prioritized retrieval candidates;
- unknown canonical item rejection;
- invalid candidate-shape rejection;
- operator notes persistence.

### Admin interface

- categorized accordion or card-stack rendering;
- checkbox enable and disable behavior;
- compact short-name display;
- expandable configuration fields;
- configuration-status summaries;
- create, edit, reload, and revision-history behavior.

### Regressions

- existing target-firm revision behavior remains unchanged;
- existing catalog import remains unchanged;
- full project validation passes;
- installed `rfi` and `python -m rfi` behavior remains consistent where applicable.

### Optional alias refinement

If the alias refinement is included, demonstrate:

- canonical-name aliases are normalized away;
- aliases are deduplicated case-insensitively;
- distinct aliases remain;
- behavior is consistent across all modified entry points;
- existing records remain readable.

## Documentation

Document:

- the purpose of the canonical source-profile template;
- template location and maintenance expectations;
- canonical item and short-name rules;
- addressability classes;
- firm source-profile revision behavior;
- retrieval-candidate semantics;
- explicit non-goals;
- the separation between acquisition configuration and retrieved source objects.

## Completion Record

Update this task ticket as the durable record for future maintainers.

Preserve the original objective and requirements, then add:

- implementation resolution;
- files changed with rationale;
- design decisions and alternatives considered;
- verification commands and results;
- known limitations;
- Architectural Status Summary.

Do not commit, push, or merge unless separately instructed.

## Implementation Resolution

TASK-014 is implemented as three deliberately separate responsibilities:

1. `src/rfi/resources/source-profile-template.yaml` is shipped application data and the only
   acquisition-catalog authority. It defines 7 ordered categories, 48 artifact types, canonical
   identifiers, concise unique short names, labels, descriptions, defaults, addressability,
   retrieval fields, retrieval-mode shapes, and item-supported modes.
2. `rfi.source_profiles` is an independent immutable aggregate keyed by `firm_id`. It has its own
   catalog pointer, revision artifacts, content-derived revision identifiers, optimistic
   publication, atomic rollback, history, and integrity verification. It reads firm identity only
   to reject unknown firms and never publishes a firm revision.
3. `/source-profiles` renders categories, items, summaries, and candidate controls by iterating the
   validated runtime template. Firm-specific enabled state, notes, and candidates are stored only
   in the source-profile aggregate.

Before first save, the service returns template defaults as an unsaved `revision_number: 0` view.
This is not durable history. Publication creates revision 1 and later edits append revisions. Item
entries are normalized into canonical template order and candidates into unique priority order.

The single global default policy is deliberately conservative and universal. Exactly five items
default enabled: `annual_report`, `earnings_release`, `press_release`, `corporate_news`, and
`product_page`. Every other item defaults off, including all jurisdiction-specific filings,
ownership and insider filings, proxy statements, prepared remarks, earnings-call transcripts,
supplemental financial tables, data sheets, and end-of-life notices. These defaults provide a
broadly useful starting point across public, foreign, private, subsidiary, hyperscaler, component,
and enterprise-vendor firms without inferring jurisdiction or company type. An operator can still
enable any supported item explicitly in a saved firm profile. No firm-type inference,
jurisdiction rules, alternate templates, or dynamic default profiles were introduced.

No acquisition, network retrieval, scheduling, polling, parsing, source-object creation, or
cross-firm deduplication was added. The optional alias refinement was not included because it was
not necessary for the primary architectural milestone.

## Files Changed with Rationale

- `src/rfi/resources/source-profile-template.yaml`: single repository-owned canonical acquisition
  catalog and retrieval-field/mode authority, including the exact five-item conservative universal
  default set.
- `src/rfi/source_profiles/contracts.py`: immutable public template, candidate, item, draft,
  revision, view, and repository contracts.
- `src/rfi/source_profiles/template.py`: packaged runtime loading plus fail-closed template
  validation.
- `src/rfi/source_profiles/repository.py`: independent revision persistence, normalization,
  candidate validation, atomic publication, history, digest verification, and rollback.
- `src/rfi/source_profiles/service.py`: firm-existence boundary, defaults-before-save behavior,
  strict JSON decoding, validation, publication, history, and template projection.
- `src/rfi/source_profiles/__init__.py`: public subsystem surface.
- `src/rfi/admin/source_profiles.html`: template-driven categorized accordion/card-stack editor,
  multiple candidate editing, summaries, and history inspection.
- `src/rfi/admin/server.py`, `src/rfi/admin/console.html`, `src/rfi/admin/firms.html`: source-profile
  composition, APIs, page route, and console navigation.
- `src/rfi/cli.py`, `pyproject.toml`: application-state lifecycle integration and explicit package
  data for YAML and browser assets. Existing valid states receive an empty additive profile catalog.
- `tests/test_task014.py`: canonical, aggregate, retrieval-shape, rollback, isolation, API, and UI
  acceptance evidence.
- `scripts/task014_source_profiles.py`: deterministic acceptance proof.
- `scripts/generate_task014_review.py`, `Makefile`: complete review-package generation and quality
  gate integration.
- `docs/firm-source-profiles-and-acquisition-template.md`, `docs/application-cli.md`: template
  maintenance, semantics, boundaries, lifecycle, UI, and operator documentation.
- `TASKS.md`, `docs/design-baseline.json`, `scripts/check_baseline.py`,
  `tests/test_foundation.py`, `tests/test_acquisition.py`: governed milestone and explicit package
  boundary inventories updated for the new subsystem and application resource.
- `tasks/TASK-014-firm-source-profiles-and-acquisition-template.md`: durable completion record.

## Design Decisions and Alternatives Considered

- **One YAML authority, not YAML plus Python constants.** Python validates structural vocabulary
  but contains no category or artifact list. The browser consumes the service projection of the
  same loaded object. A generated Python catalog was rejected because it would create a second
  definition with synchronization risk.
- **Separate profile repository, not fields on `FirmRevision`.** Retrieval intent changes at a
  different cadence from identity and recognition metadata. Embedding it in firms would violate
  the required revision independence.
- **Template-defined mode shapes.** Retrieval field definitions and required/supported fields live
  with the application-data template. Hard-coded per-artifact browser forms or Python mode/item
  matrices were rejected.
- **Full normalized snapshot revisions.** Saved revisions contain a deterministic entry for every
  canonical item, filling omitted items from defaults. This makes each revision independently
  readable and prevents interpretation from depending on mutable UI ordering.
- **Defaults are a view, not revision 0 persistence.** This provides clear first-run behavior
  without fabricating history or creating state merely by viewing a firm.
- **Universal conservative defaults, not inferred profiles.** Only annual reports, earnings
  releases, press releases, corporate news, and product pages are broadly applicable enough to
  enable globally. More specific material remains available but opt-in. Firm classification,
  jurisdiction matrices, and multiple templates were rejected as out of scope and as additional
  policy authorities.
- **Additive lifecycle initialization for older valid state.** The new empty aggregate is created
  when absent, while existing concept and firm catalogs retain their established open/verify and
  seed behavior.
- **Strict configured URL boundary.** Candidate URLs accept credential-free HTTP(S) locations.
  Retrieved URLs and provenance remain future acquisition records, not profile configuration.

## Verification Commands and Results

- `PYTHONPATH=src .venv/bin/python -m unittest tests.test_task014 -v` — **PASS**, 8 focused tests,
  including the exact five-item default set, jurisdiction-specific defaults off, unsaved
  revision-0 defaults, and explicit saved configuration remaining stable.
- `.venv/bin/python scripts/task014_source_profiles.py fixture-proof` — **PASS**, 18 deterministic
  acceptance checks across 48 artifacts and 5 retrieval modes, including exact conservative
  defaults and revision-0 parity with the template.
- `PYTHONPATH=src .venv/bin/python -m unittest tests.test_task011 tests.test_task012
  tests.test_task013 -v` — **PASS** within the complete suite; existing firm, CLI, and catalog
  import behavior remains valid.
- `.venv/bin/rfi init --state <temporary>` and `.venv/bin/python -m rfi init --state <temporary>` —
  **PASS** with matching lifecycle behavior; both initialize the profile aggregate.
- `.venv/bin/rfi --help` and `.venv/bin/python -m rfi --help` — **PASS** with matching command
  behavior.
- Live initialized administration walkthrough at `http://127.0.0.1:8874/source-profiles` —
  **PASS**: 7 categories and all 48 unique artifacts rendered; readable short names and revised
  pre-save defaults were visible; accordion and checkbox interaction were independent;
  deterministic, semi-deterministic, and discovery controls changed with mode; candidates were
  added, reprioritized, and removed; operator notes persisted; invalid configuration returned
  `retrieval mode identifier requires fields: locator`; Seagate revisions 1 and 2 were published
  and displayed; reload preserved revision 2; the target-firm revision remained
  `firm-revision-9ff104a39c52f2b29ac757a869bafad7c2c9ddf8db262521e82295ac10e24987`;
  and a Western Digital revision 1 remained independent. Four representative screenshots and the
  machine-readable walkthrough record are in the review package under `ui/`.
- `make validate` — **PASS**: 164 tests plus acquisition, engine, offline provider, TASK-005
  through TASK-011 and TASK-014 proofs, lint, format, type policy, import, docs, design baseline,
  and deterministic source archive gates.
- `git diff --check` — **PASS**.
- `make review-package` — **PASS**; evidence is under `.artifacts/review/TASK-014/` with archive
  `.artifacts/review/TASK-014-review.zip` and SHA-256 sidecar.

The review package contains command transcripts, canonical YAML, documentation, this ticket,
complete cumulative patch including untracked task files, the generated 24-file changed-file
inventory, exact repository status, deterministic default-policy proof, live rendered-UI
walkthrough data and screenshots, verification summary, manifest hashes, and ZIP integrity
evidence.

## Known Limitations

- The canonical template intentionally has one schema version and no migration mechanism.
- The administration server remains a local, unauthenticated, single-operator interface.
- Template changes can make previously valid saved candidates invalid on repository open; this is
  deliberate fail-closed behavior until template migration is explicitly designed.
- Candidate configuration is operator-authored planning intent; it is not tested against networks
  or external providers in this task.
- The optional firm-alias normalization refinement remains unimplemented.
- Acquisition execution, source provenance, source objects, scheduling, parsing, automatic
  discovery, credentials, and cross-firm deduplication remain separate future concerns.

## Architectural Status Summary

| Subsystem | Responsibility | Status |
|---|---|---|
| Canonical acquisition template | Repository-owned categories, artifacts, addressability, defaults, fields, modes, and ordering | Complete |
| Template loader and validation | Package resource loading and fail-closed structural/semantic integrity | Complete |
| Firm source-profile aggregate | Independent immutable configuration revisions, history, atomic publication, rollback, and isolation | Complete |
| Source-profile service | Firm existence, defaults view, strict decoding, publication, and template projection | Complete |
| Administrative rendering | Template-driven categorized item and prioritized candidate editing | Complete |
| Target-firm identity aggregate | Identity and recognition revisions with no source-profile write coupling | Complete; unchanged |
| Existing catalog import | External firm import with no source-profile revision coupling | Complete; unchanged |
| Acquisition execution | Interpret published configuration and retrieve artifacts | Not Started |
| Retrieved provenance and source objects | Record actual retrieval URLs, immutable evidence, parsing, and lineage | Not Started in this milestone |

Architectural change: acquisition planning now has a repository-owned canonical vocabulary and a
firm-scoped immutable configuration authority distinct from identity and retrieved evidence.

Important limitations and debt: template migration and multi-operator authorization do not exist;
future acquisition must define how it snapshots or references the template and profile revision it
consumes without weakening immutable retrieved provenance.

Next architectural milestone: implement acquisition execution as a separate consumer of an
explicit source-profile revision, producing independent retrieval attempts, artifacts, and source
objects with complete provenance and without mutating profile or firm history.
