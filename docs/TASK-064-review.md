# TASK-064 Architectural Review — StockAnalysis Transcript Provider

## Post-completion generic-routing compatibility correction

The firm-configuration schema retains two mutually exclusive transcript forms. Provider-neutral
generic discovery accepts `discovery_class` plus string URL `discovery_hints`; provider-backed
discovery requires `provider=stockanalysis` plus a typed `provider_identifier`. Projection does not
coerce generic URLs into typed hints, provider-backed trials do not fall through to generic
discovery, and `/quote/tyo/...` or `/quote/hkg/...` hints remain outside the strict StockAnalysis
adapter. Legacy generic source-profile revisions continue authenticating under their historical
digest schemas, while provider-backed revisions continue using digest schema 4.

## Result

TASK-064 is complete after a bounded corrective repair. Transcript acquisition retains its
explicit provider boundary: firm configuration selects `provider=stockanalysis`, the
orchestrator dispatches typed configured and learned seeds, and the StockAnalysis adapter owns
only provider-specific identifier resolution, HTTP recovery, parsing, and observations.

The correction adds a provider-neutral `TranscriptMetadataObservation` carrying an opaque event
label, optional trusted artifact date, event disposition, related-artifact observations, and
speaker-turn observations. Full turns, relationships, learning feedback, and trusted date remain
available through the compatible typed `RetrievalResult` fields.
Diagnostics now retain only bounded operational summaries. No transcript paragraph, complete
turn, document body, or provider summary is serialized into diagnostics, logs, failure messages,
live evidence, or this review package.

StockAnalysis archives contain earnings calls and other event transcripts. The repaired provider
preserves deterministic archive order and emits `unknown` because StockAnalysis exposes no tested,
dedicated, artifact-local document-classification field. Related documents remain observations
only and never establish disposition or rank. Titles, headings, URLs, slugs, periods, archive
position, display labels, and enclosing-page conditions likewise have no classification authority.
A separate recall-oriented substance gate uses only parsed turns and normalized artifact text;
uncertain event classification remains eligible when the artifact is structurally substantial.

## Configuration, Dispatch, and Seed Contract

The required firm configuration remains:

```json
{
  "provider": "stockanalysis",
  "discovery_hint": {
    "kind": "provider_identifier",
    "value": "ORCL"
  },
  "discovery_class": "standard"
}
```

`TranscriptSeed` carries `provider`, `kind`, `value`, and `origin`. The orchestrator always
attempts the configured StockAnalysis `provider_identifier` first, then preserves learned FIFO
order and each learned seed's explicit provider association. It never selects a provider by URL
shape. `TranscriptProviderRegistry` remains the single provider-name dispatch definition.
Its registration type is a provider-neutral constructor protocol; adding a second provider no
longer requires changing a StockAnalysis-specific tuple annotation or registry import.

| Provider | Seed kind | Configured | Learned | Operator supplied |
|---|---|---:|---:|---:|
| StockAnalysis | `provider_identifier` | Yes | Feedback only | No |
| StockAnalysis | `url` | No | Yes | Yes |

## Responsibility Map

| Concern | Orchestrator / repository | StockAnalysis provider |
|---|---:|---:|
| Provider dispatch and configured-first seed order | Owns | Receives one seed |
| Escalation, terminal selection, and run budget | Owns | Cannot select successors or reset budget |
| Identifier normalization and canonical archive URL | No provider knowledge | Owns |
| Archive/direct HTTP, retries, and parsing | No provider markup knowledge | Owns |
| Trusted-date qualification | Owns qualification | Emits optional artifact-local observation |
| Full transcript artifact | Persists authoritative bytes | Extracts provider transcript surface |
| Speaker turns, related artifacts, feedback | Carries neutral typed values | Emits observations only |
| Durable learning, replay, checkpoints, conflicts | Owns unchanged | Has no repository dependency |

## Provider-Neutral Result Contract

`RetrievalResult` has five explicit transcript observation surfaces:

- `trusted_event_date`;
- `speaker_turn_observations`;
- `related_artifact_observations`;
- `transcript_learning_feedback`;
- `transcript_metadata_observation`.

`TranscriptEventDisposition` is closed over `explicit_earnings`,
`explicit_non_earnings`, and `unknown`. `TranscriptMetadataObservation` groups the opaque event
label, trusted date, disposition, related artifacts, and speaker turns without adding a
StockAnalysis-only side channel. Related-link labels are retained as opaque provider text after
bounded whitespace normalization.

`TranscriptTurnObservation` still preserves ordinal, provider speaker label, optional provider
role, optional explicit section, and ordered paragraphs. Adjacent turns from the same speaker are
not merged. The Oracle fixture retains four turns, including two adjacent Safra Catz turns, and
the live WDC artifact emitted 75 turns. No generic segmentation or canonical person identity was
introduced.

Transcript substance is established only from the extracted structure: at least two turns, two
content-bearing turns, eight normalized words, two distinct opaque speaker labels, and exact
equality between normalized text and the contiguous ordered turn paragraphs. Tests prove that an
earnings-looking title cannot rescue an insubstantial artifact, removing every relationship leaves
substance unchanged, and a substantial `unknown` event remains eligible. These deliberately
conservative thresholds minimize false negatives without title, URL, fiscal-period, link-label,
or keyword semantics.

`RelatedArtifactObservation` retains the typed artifact kind, exact observed URL, relationship
kind, and source-page provenance. The fixture exposes earnings release, slides, annual report,
and audio. The provider retrieves none of them. `TranscriptLearningFeedback` remains bounded
advice; the adapter cannot make it durable.

The diagnostic projection contains only:

- turn count and SHA-256 over deterministic canonical turn serialization;
- related-artifact count and bounded kinds;
- learning-feedback count;
- trusted-date availability and the accepted date when present;
- requested/resolved URLs, status, provider classification, and retry counts; and
- bounded provider metadata.

Focused tests prove that complete turn paragraphs remain available through the typed field while
the same text is absent from deterministic diagnostic JSON. Related artifacts and learning
feedback remain available through their typed fields. Provider metadata diagnostics use a fixed
five-field allowlist, cap every retained value at 256 characters, and remain below the existing
serialized diagnostic bound even when an artifact attribute is oversized.

## Trusted Metadata and Date Ownership

The provider accepts an event date only from a known artifact-local StockAnalysis representation
and returns it as `trusted_event_date`. A recognized fixture date is returned and the neutral
terminal-selection policy validates it.

When the artifact-local date is absent, malformed, or unrecognized, the provider returns
`trusted_event_date=None` and omits date-derived diagnostic fields. It does not raise a
provider-specific `event_date_unavailable` failure. Repository-owned durable qualification then
records the neutral `event_date_unavailable` outcome, including for the compatibility `latest`
path, instead of classifying an unset date as a malformed adapter result.

The negative fixture retains a date-bearing URL slug, fiscal label, archive position and label,
publication timestamp, and related-document URLs. None becomes a fallback event date. Multiple
artifact-local date observations are parsed into normalized dates before comparison: equivalent
known formats agree, while malformed, unrecognized, or conflicting observations leave the date
unset independent of DOM order. Other conflicting trusted metadata continues to fail closed;
URL, archive order, fiscal period, publication metadata, and related documents remain
non-authoritative.

## Provenance and Learning

Candidate provenance contains exactly one `provider` key, under
`DiscoveryProvenance.provider_identifiers`, with value `stockanalysis`. Provider dispatch,
retrieval-context lookup, durable learning updates, and no-change replay read that single neutral
location. The duplicate provider copy in discovery metadata was removed.

Durable learning remains transactionally repository-owned. A successful retained artifact still
produces a provider-associated anchor only after validation and persistence; failed or rejected
candidates do not teach or checkpoint.

## Source-Profile Digest Compatibility Repair

The post-TASK-064 live startup regression was traced to immutable source-profile revision
`source-profile-revision-1346e6e31eb2f1cdc28a3f73f660bac7f203b765659f61b535003ad2c81ff93b`.
Its exact persisted Meta payload has no digest-schema marker, no `discovery_class`, and no
provider or typed-hint candidate fields, so the persisted shape selects schema 1. Its original
canonical material is the stored payload minus `source_profile_revision_id`; compact sorted-key
JSON with a trailing newline hashes with SHA-256 to the stored `1346e6...ff93b` identity.

Startup selected schema 1 correctly, but constructed the current `RetrievalCandidate` before
authentication. Current dataclass defaults added empty `provider`, `discovery_hint_kind`, and
`discovery_hint_value` fields, while the schema-1 digest projection removed only
`discovery_class`. The first canonical divergence was `discovery_hint_kind` at byte 175, and the
incorrect recomputation was `d1a2eb...a12d6`.

The repository now authenticates exact persisted JSON before constructing current dataclasses.
Markerless schemas 1 and 2 retain their historical projections; explicitly marked schema 3
retains `discovery_class` but excludes TASK-064 provider fields; schema 4 authenticates
`discovery_class`, provider, and typed-hint fields. An available schema marker remains
authoritative, partial or cross-schema field representations fail closed, and a second
reconstructed-contract verification remains in place. No hash alternatives, revision rewrites,
silent migration, or weakened comparison were introduced.

The exact admin-server construction path was exercised against the live repository and
succeeded. SHA-256 values for `repository.sqlite3`, its WAL, and SHM were identical before and
after. The production-derived fixture recreates the exact reported revision ID, authenticates it
through admin startup, and proves the canonical payload and database bytes remain unchanged.
Firm-configuration import and reload code was not modified.

## Identifier, Archive, Direct Document, and Budgets

`ORCL` deterministically normalizes to `orcl` and constructs:

```text
https://stockanalysis.com/stocks/orcl/transcripts/
```

Archive extraction remains same-firm, transcript-only, first-occurrence deduplicated, and retains
the opaque label plus original archive position. Admission deterministically groups explicit
earnings first and unknown fallback second while preserving archive order within each group. A
direct provider-associated transcript URL skips the archive fetch and converges on the same
candidate identity. Deceptive hosts, unrelated firms, invalid paths, credentials, queries, and
fragments fail closed.

One `BudgetedTranscriptTransport` still spans archive retrieval, document retrieval, redirects,
provider-local retries, and response caching. Page, byte, host, elapsed, redirect, retry,
candidate, and diagnostic bounds remain shared and named. The candidate ledger is updated only
immediately before the engine evaluates a unique document. Archive observations themselves do not
consume evaluation budget, and candidates outside remaining admission capacity consume none.
Duplicate archive and learned occurrences converge on one identity and remain bounded
trial-local provenance rather than an ambiguous-candidate failure. No search request occurs.

Relationship labels are read only from actual candidate- or transcript-associated relationship
records inside a tested `Downloads` surface, or from an explicit provider relationship
attribute. Exact observed URL, typed kind, opaque label, relationship provenance, and ordering are
retained, but none is a transcript-classification input. The container's presence or absence is
not classification evidence. Links in navigation, footers, or other global page regions cannot
become observations; false-positive global “Slides” and “Annual Report” fixtures are ignored.

## Live Acceptance and Byte Authority

The bounded live validation used `provider=stockanalysis`, hint
`provider_identifier=WDC`, and the zero-search policy. It constructed the Western Digital archive,
kept candidates in observed order with `unknown` disposition, evaluated substantial transcript
artifacts without retrieving related documents, and selected the artifact-local date `2026-04-30`
through repository-owned `first_in_date_range` qualification.

Observed bounded evidence:

- pages: 6 (archive plus five transcript artifacts evaluated in observed order);
- host count: 1;
- redirects: 0;
- provider retries: 0;
- speaker turns: 75;
- normalized transcript words: 7,014;
- related-artifact observations: 3 (quarterly report, earnings release, and slides from the
  transcript-associated `Downloads` surface);
- event disposition: `unknown`;
- search-engine calls: 0; and
- bounds exhausted: false.

Authoritative live transport bytes: `1501817`.

The live evidence file is the single byte-count authority. It records SHA-256 identities for the
provider, neutral contracts, engine, orchestrator, and live validator. Package generation verifies
those identities and refuses stale evidence; it also refuses a review whose byte marker differs
from the live JSON. The package report copies the same byte value.

## Package Counting and Verification

34 manifested members verified; 35 total ZIP entries including `manifest.json`.

The verifier now reports these as separate fields: `manifested_members_verified` and
`total_zip_entries`. The manifest's `members` map covers the 34 hashed package members, while the
manifest is the additional ZIP entry and cannot hash itself. The generated package report,
review text, verifier output, and final implementation report use the same wording and counts.

## Compatibility and Architecture Review

- Configured-first seed ordering and provider dispatch semantics are unchanged.
- The orchestrator contains no StockAnalysis hostname, route, selector, or markup knowledge.
- Provider-local retries cannot select seeds, switch providers, or reset the shared budget.
- Durable validation, persistence, learning, replay, checkpoints, duplicates, and conflicts
  remain with their prior owners.
- Existing diagnostics-only validated-date evidence remains compatible for legacy transcript
  adapters; StockAnalysis uses the new typed trusted-date observation.
- `latest` and `first_in_date_range` remain under existing selection semantics; an unset provider
  date is a neutral validation rejection rather than a malformed-adapter failure.
- The provider registry accepts provider-neutral factories and has no first-provider type leak.
- Related-link label fallback is restricted to a fixture-covered explicit relationship surface.
- No transcript body is persisted as diagnostics.
- No `event_group_id`, generic speaker segmentation, search fallback, Crawlee, Playwright,
  browser storage, or crawler state was introduced.

## Validation Results

- Focused TASK-064 suite: PASS (29 tests).
- Source-profile digest compatibility: PASS (6 tests).
- CLI startup and firm-configuration regressions: PASS (24 tests).
- TASK-059 through TASK-063 transcript regressions: PASS (45 tests).
- Review-package verifier regressions: PASS.
- Deterministic fixture replay twice: PASS with identical typed observations and summaries.
- Static architecture and dependency checks: PASS.
- Bounded live acceptance and identity verification: PASS.
- Full `make validate`: PASS.

The regenerated package retains the exact command outputs, implementation patch, changed-file
inventory, live evidence, and SHA-256 manifest.

## Complexity, Limitations, and Technical Debt

- Static server-rendered HTML remains sufficient; unknown future layouts fail explicitly.
- Parser complexity remains linear in bounded response size; metadata projection, relationship
  scope, candidate admission, retry counts, and serialized diagnostics all have explicit caps.
- The authoritative retained artifact remains normalized transcript text rather than full page UI.
- Typed turn and relationship observations are not yet projected into a separate durable
  relationship schema; transcript bytes remain authoritative.
- Event disposition remains `unknown` whenever explicit candidate/artifact metadata is absent;
  this is an intentional recall-preserving fallback rather than a provider-classification guess.
- Legacy non-provider transcript paths remain intentionally unchanged.
- Digest schemas 1–3 remain explicit compatibility code and must be preserved while their
  immutable revisions remain retained; new publications use schema 4 only.
- Live layout and response size remain outside repository control, so each new package requires a
  fresh identity-bound live capture.

## Architectural Status Summary

| Subsystem | Responsibility | Status | Limitations / next milestone |
|---|---|---|---|
| Transcript provider registry | Explicit name-based dispatch through neutral factories | Complete | One concrete provider |
| Transcript orchestrator | Seed order, escalation, budgets, lifecycle | Complete | Legacy generic path remains |
| StockAnalysis adapter | Identifier, HTTP, parsing, typed observations | Complete | Known static layouts only |
| Transcript substance gate | Recall-oriented validation from parsed turns and normalized text | Complete | Conservative fixed thresholds |
| Neutral retrieval envelope | Artifact, optional date, turns, relations, feedback | Complete | No separate durable projection |
| Trusted-date qualification | Repository-owned acceptance and selection | Complete | Unknown provider forms remain unset |
| Diagnostic boundary | Bounded operational summaries without bodies | Complete | Counts and digests only |
| Learning/persistence/replay | Existing immutable lifecycle | Complete and unchanged | No relationship schema added |
| Source-profile digest authentication | Authenticate immutable schema 1–4 revisions before default projection | Complete | Historical schema branches intentionally retained |
| Review evidence | Identity-bound live bytes and unambiguous member counts | Complete | Fresh live capture per package |

The next architectural milestone may add another explicit provider or a repository projection for
the existing neutral observations. It should not broaden StockAnalysis into a generic crawler.
