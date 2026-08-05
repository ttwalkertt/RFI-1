# TASK-064 Architectural Review — StockAnalysis Transcript Provider

## Result

TASK-064 is complete after a bounded corrective repair. Transcript acquisition retains its
explicit provider boundary: firm configuration selects `provider=stockanalysis`, the
orchestrator dispatches typed configured and learned seeds, and the StockAnalysis adapter owns
only provider-specific identifier resolution, HTTP recovery, parsing, and observations.

The correction moves full speaker turns, related-artifact observations, learning feedback, and
the optional trusted artifact date onto explicit provider-neutral `RetrievalResult` fields.
Diagnostics now retain only bounded operational summaries. No transcript paragraph, complete
turn, document body, or provider summary is serialized into diagnostics, logs, failure messages,
live evidence, or this review package.

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

`RetrievalResult` now has four explicit optional fields:

- `trusted_event_date`;
- `speaker_turn_observations`;
- `related_artifact_observations`; and
- `transcript_learning_feedback`.

`TranscriptTurnObservation` still preserves ordinal, provider speaker label, optional provider
role, optional explicit section, and ordered paragraphs. Adjacent turns from the same speaker are
not merged. The fixture retains four turns, including two adjacent Safra Catz turns, and the live
artifact emitted 36 turns. No generic segmentation or canonical person identity was introduced.

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
feedback remain available through their typed fields.

## Trusted Metadata and Date Ownership

The provider accepts an event date only from a known artifact-local StockAnalysis representation
and returns it as `trusted_event_date`. A recognized fixture date is returned and the neutral
terminal-selection policy validates it.

When the artifact-local date is absent, malformed, or unrecognized, the provider returns
`trusted_event_date=None` and omits date-derived diagnostic fields. It does not raise a
provider-specific `event_date_unavailable` failure. Repository-owned terminal qualification then
records the neutral `event_date_unavailable` outcome when the selection requires a date.

The negative fixture retains a date-bearing URL slug, fiscal label, archive position and label,
publication timestamp, and related-document URLs. None becomes a fallback event date. Conflicting
trusted artifact metadata continues to fail closed; URL, archive order, fiscal period,
publication metadata, and related documents remain non-authoritative.

## Provenance and Learning

Candidate provenance contains exactly one `provider` key, under
`DiscoveryProvenance.provider_identifiers`, with value `stockanalysis`. Provider dispatch,
retrieval-context lookup, durable learning updates, and no-change replay read that single neutral
location. The duplicate provider copy in discovery metadata was removed.

Durable learning remains transactionally repository-owned. A successful retained artifact still
produces a provider-associated anchor only after validation and persistence; failed or rejected
candidates do not teach or checkpoint.

## Identifier, Archive, Direct Document, and Budgets

`ORCL` deterministically normalizes to `orcl` and constructs:

```text
https://stockanalysis.com/stocks/orcl/transcripts/
```

Archive extraction remains same-firm, transcript-only, observed-order, and first-occurrence
deduplicated. A direct provider-associated transcript URL skips the archive fetch and converges
on the same candidate identity. Deceptive hosts, unrelated firms, invalid paths, credentials,
queries, and fragments fail closed.

One `BudgetedTranscriptTransport` still spans archive retrieval, document retrieval, redirects,
provider-local retries, and response caching. Page, byte, host, elapsed, redirect, retry,
candidate, and diagnostic bounds remain shared and named. No search request occurs.

## Live Acceptance and Byte Authority

The bounded live validation used `provider=stockanalysis`, hint
`provider_identifier=ORCL`, and the zero-search policy. It constructed the Oracle archive,
selected the representative Q4 2026 transcript, retrieved the direct document, and validated the
artifact-local date `2026-06-10` through the neutral selection policy.

Observed bounded evidence:

- pages: 2;
- host count: 1;
- redirects: 0;
- provider retries: 0;
- speaker turns: 36;
- related kinds: annual report, presentation slides, and earnings release;
- search-engine calls: 0; and
- bounds exhausted: false.

Authoritative live transport bytes: `775055`.

The live evidence file is the single byte-count authority. It records SHA-256 identities for the
provider, neutral contracts, orchestrator, and live validator. Package generation verifies those
identities and refuses stale evidence; it also refuses a review whose byte marker differs from
the live JSON. The package report copies the same byte value.

## Package Counting and Verification

27 manifested members verified; 28 total ZIP entries including `manifest.json`.

The verifier now reports these as separate fields: `manifested_members_verified` and
`total_zip_entries`. The manifest's `members` map covers the 27 hashed package members, while the
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
- `latest` and `first_in_date_range` behavior remains under existing selection semantics.
- No transcript body is persisted as diagnostics.
- No `event_group_id`, generic speaker segmentation, search fallback, Crawlee, Playwright,
  browser storage, or crawler state was introduced.

## Validation Results

- Focused TASK-064 suite: PASS (14 tests).
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
- The authoritative retained artifact remains normalized transcript text rather than full page UI.
- Typed turn and relationship observations are not yet projected into a separate durable
  relationship schema; transcript bytes remain authoritative.
- Legacy non-provider transcript paths remain intentionally unchanged.
- Live layout and response size remain outside repository control, so each new package requires a
  fresh identity-bound live capture.

## Architectural Status Summary

| Subsystem | Responsibility | Status | Limitations / next milestone |
|---|---|---|---|
| Transcript provider registry | Explicit name-based dispatch | Complete | One concrete provider |
| Transcript orchestrator | Seed order, escalation, budgets, lifecycle | Complete | Legacy generic path remains |
| StockAnalysis adapter | Identifier, HTTP, parsing, typed observations | Complete | Known static layouts only |
| Neutral retrieval envelope | Artifact, optional date, turns, relations, feedback | Complete | No separate durable projection |
| Trusted-date qualification | Repository-owned acceptance and selection | Complete | Unknown provider forms remain unset |
| Diagnostic boundary | Bounded operational summaries without bodies | Complete | Counts and digests only |
| Learning/persistence/replay | Existing immutable lifecycle | Complete and unchanged | No relationship schema added |
| Review evidence | Identity-bound live bytes and unambiguous member counts | Complete | Fresh live capture per package |

The next architectural milestone may add another explicit provider or a repository projection for
the existing neutral observations. It should not broaden StockAnalysis into a generic crawler.
