# TASK-064 Architectural Review — StockAnalysis Transcript Provider

## Result

TASK-064 is complete. Transcript acquisition now has an explicit provider boundary. Firm
configuration selects `provider=stockanalysis` and supplies one typed
`provider_identifier` hint. The transcript orchestrator orders configured and learned seeds,
dispatches each seed by its recorded provider, shares the run budget, and retains all existing
terminal, validation, persistence, learning, replay, and checkpoint ownership.

The StockAnalysis provider is the first concrete implementation. It uses bounded `urllib` HTTP,
constructs the canonical archive URL from the configured identifier, handles direct documents,
extracts only trusted artifact-local metadata and the complete transcript, and emits optional
provider-neutral turn, related-artifact, and learning-feedback observations. No Crawlee,
Playwright, browser state, generic crawl framework, search request, event group, or generic
speaker segmentation was introduced.

## Configuration, Dispatch, and Seed Contract

External firm configuration requires this shape and fails closed if any field is absent or
unsupported:

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

The immutable source-profile projection carries `provider`, `discovery_hint_kind`, and
`discovery_hint_value`. Digest schema 4 authenticates these new fields while repository loading
continues to authenticate schema 1, 2, and 3 history.

`TranscriptSeed` is the provider-neutral contract: `provider`, `kind`, `value`, and `origin`.
The supported matrix for this milestone is:

| Provider | Kind | Configured | Learned | Operator supplied |
|---|---|---:|---:|---:|
| StockAnalysis | `provider_identifier` | Yes | Feedback only | No |
| StockAnalysis | `url` | No | Yes | Yes |

The orchestrator always emits the configured StockAnalysis `provider_identifier` trial first.
It then retains learned FIFO order and explicit provider association; entries without a durable
provider association are not reclassified by URL inspection. `TranscriptProviderRegistry` is the
single provider-name dispatch definition. The StockAnalysis module defensively validates every
URL after dispatch.

## Responsibility Map

| Concern | Orchestrator / engine | StockAnalysis provider |
|---|---:|---:|
| Provider dispatch and seed ordering | Owns | Receives one seed |
| Configured-before-learned escalation | Owns | Cannot choose successor |
| Run pages, bytes, elapsed, hosts, redirects, candidates | Owns shared budget | Consumes it |
| Provider-local transient retries | Observes result | Owns, maximum two retries |
| Identifier normalization and archive URL | No knowledge | Owns |
| Archive/direct HTTP and parsing | No knowledge | Owns |
| Trusted metadata and content extraction | Durable validation remains authoritative | Observes provider form |
| Speaker turns and related artifacts | Carries neutral values | Extracts optional observations |
| Learning feedback | Decides eligibility and persistence | Emits bounded advice only |
| Persistence, replay, checkpoint, duplicate/conflict behavior | Owns unchanged | No repository reference |
| Terminal selection (`latest`, range) | Owns unchanged | Supplies validated date evidence |

## Identifier, Archive, and Direct-Document Proof

`ORCL` is conservatively normalized to `orcl`; whitespace and case are normalized while slash,
query, traversal, credential, deceptive-host, cross-host, unrelated-path, and unrelated-ticker
forms fail closed. The provider constructs:

```text
https://stockanalysis.com/stocks/orcl/transcripts/
```

The captured archive admits Q4 2026 then Q3 2026 in observed order and excludes navigation,
filings, financial pages, and another ticker. Duplicate archive links converge on one normalized
candidate. A direct document seed performs no archive fetch. Archive and direct paths produce the
same `CandidateIdentity`, while exact requested and resolved URLs remain in provenance.

## Trusted Metadata and Authoritative Content

Fixture-covered StockAnalysis forms supply document title, company, ticker, event type, fiscal
period, and event date. The live page additionally proves the server-rendered Corporation JSON-LD,
artifact heading, artifact date header, and transcript article forms. Conflicting ticker/date
metadata fails closed. Missing, malformed, or unknown artifact-local dates remain unavailable and
cannot be recovered from a URL slug, archive position, fiscal label, related link, or adjacent
document.

The retained UTF-8 artifact contains the complete extracted transcript paragraphs plus observed
artifact metadata. Provider summary, navigation, controls, related links, subscription content,
and footer text are excluded. The provider does not summarize or repair transcript text.

## Speaker Turns and Related Artifacts

`TranscriptTurnObservation` is provider-neutral and contains ordinal, provider speaker label,
optional role, optional structurally explicit section, and ordered paragraphs. The sanitized
fixture proves four turns, including two adjacent Safra Catz turns that remain separate. The live
Q4 2026 artifact produced 36 ordered turns. No canonical person identity or generic segmentation
fallback exists.

`RelatedArtifactObservation` contains typed kind, exact observed URL, relationship kind, and
source-page provenance. The fixture proves earnings release, slides, annual report, and audio.
The live artifact exposed annual report, slides, and earnings release links. The provider reports
these links and fetched zero related artifacts; retrieval and independent artifact primary keys
remain orchestrator/repository decisions. No `event_group_id` exists.

## Learning, Budgets, and Determinism

The provider emits bounded `TranscriptLearningFeedback` values for the confirmed identifier and
reusable direct URL. It has no repository dependency and cannot update durable learning. Existing
successful-persistence logic records provider-associated anchors transactionally after durable
validation. Engine evidence proves the resulting anchor retains `provider=stockanalysis`.

One `BudgetedTranscriptTransport` spans archive discovery, direct retrieval, redirects, retries,
and response caching. Named limits cover pages, bytes, elapsed time, distinct hosts, redirects,
candidate evaluations, and the provider retry ceiling. Diagnostics contain counts, digests, URLs,
and classifications, never transcript bodies or sensitive request data.

The sanitized fixture replay was executed twice with identical ordered candidate canonical forms,
retained bytes, speaker turns, related artifacts, metadata, and diagnostics. Candidate order is
observed archive order with first-observation deduplication, independent of request completion.

## Live Acceptance

On 2026-08-05 the bounded static HTTP validation used provider `stockanalysis`, hint kind
`provider_identifier`, exact value `ORCL`, and a zero-search policy. It constructed and resolved
the canonical Oracle archive, discovered the representative Q4 2026 document first, requested and
resolved the exact representative URL, and validated the artifact.

Observed safe evidence:

- event date: `2026-06-10`, from the artifact header;
- speaker turns: 36;
- transcript content SHA-256:
  `c1baaa6413e3c32b62148b010cc814a98ee254cdc70c5cf772474a91181bc98f`;
- related kinds: annual report, slides, and earnings release;
- requests: 2 pages, 775,055 bytes, one host, zero redirects, zero retries;
- search-engine calls: zero; and
- bounds exhausted: false.

Live content and layout remain outside repository control. A future unrecognized layout must fail
with `provider_layout_changed`; it is not permission to infer metadata or add a browser framework.

## Compatibility and Architecture Review

- Provider dispatch has one registry definition and uses configured/recorded provider names only.
- The orchestrator contains no StockAnalysis hostname, path, selector, or markup knowledge.
- All StockAnalysis URL construction, selectors, structured data, parsing, retries, and recovery
  are isolated in `rfi.acquisition.providers.stockanalysis` and focused tests.
- Provider retries receive one seed, cannot reorder seeds, and cannot reset the shared budget.
- Durable validation, terminal selection, persistence, learning writes, replay, checkpoints,
  duplicate detection, and conflict handling did not move.
- `latest` and `first_in_date_range` continue through the existing engine policy.
- No search call occurs on the provider path.
- No `event_group_id`, generic speaker segmentation, Crawlee, Playwright, browser storage, or
  crawler state was introduced.
- Legacy non-provider transcript configuration continues through the existing implementation.

## Validation Results

- `make task064-test`: PASS (13 focused tests).
- TASK-059 through TASK-063 regression modules: PASS.
- Relevant acquisition, engine, repository, API, learning, replay, checkpoint, identity,
  persistence, duplicate, and conflict tests: PASS.
- Deterministic fixture replay twice: PASS.
- Static dependency/runtime verification: PASS.
- Bounded live acceptance: PASS.
- Full `make validate`: PASS.

The generated review package retains the complete command output and final results manifest.

## Complexity, Limitations, and Technical Debt

- Static server-rendered HTML is sufficient today; provider-local parsers intentionally cover only
  captured and live-observed StockAnalysis forms.
- Transcript content is normalized to stable UTF-8 text; exact original page bytes are not retained
  because the authoritative artifact excludes surrounding provider UI.
- Audio is emitted only when an exact artifact-local URL exists; a button without an observable URL
  is not fabricated as a relationship.
- Existing legacy generic transcript discovery remains for non-provider configurations and should
  be migrated only by a separately authorized milestone.
- Related observations currently travel in neutral retrieval diagnostics; a future first-class
  relationship persistence milestone may project them without changing provider extraction.

## Architectural Status Summary

| Subsystem | Responsibility | Status | Limitations / next milestone |
|---|---|---|---|
| Transcript provider registry | Explicit name-based dispatch | Complete | One concrete provider |
| Transcript orchestrator | Seed order, escalation, budgets, terminal lifecycle | Complete | Legacy generic path remains |
| StockAnalysis provider | Identifier, HTTP, archive/direct parsing, observations | Complete | Captured/live static layouts only |
| Trusted metadata authority | Accept known artifact-local provider forms | Complete | Unknown forms remain unset/fail closed |
| Speaker observations | Ordered optional provider labels/roles/paragraphs | Complete | No person canonicalization |
| Related-artifact observations | Typed exact links and provenance | Complete | Retrieval/projection intentionally deferred |
| Learning feedback | Neutral bounded provider advice | Complete | Durable eligibility remains orchestrator-owned |
| Persistence/replay/checkpoints | Existing immutable lifecycle | Complete and unchanged | No relationship schema added |

The next architectural milestone should add another explicit transcript provider or a repository
projection for neutral related-artifact observations. It should not broaden the StockAnalysis
adapter into a generic crawler.
