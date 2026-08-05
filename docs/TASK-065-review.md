# TASK-065 Architectural Review — Explicit Provider Dispatch and Learning Authority

## Result

TASK-065 requires every transcript seed-injection request to name its provider explicitly. The
request-body `provider` is carried unchanged through `PullWorkflow` and
`EarningsTranscriptPullAdapter.injected_trial()` into `AdapterAcquisitionTrial.provider`.
`TranscriptProviderRegistry` validates and dispatches that name. URL shape and firm configuration
do not select or replace the request provider.

Successful acquisition already persisted the selected provider in each discovery anchor's
authoritative canonical JSON. Learning inspection now exposes that persisted association on every
entry. It does not infer provider from URL shape or substitute current firm configuration.

The existing outer acquisition adapter remains `earnings-call-transcript`. No persistence model,
provider registry, provider-specific HTTP branch, transcript search strategy, selector,
checkpoint, replay, candidate extraction, or bounded-resolution behavior was added or changed.

## Public Contracts

`POST /api/transcript-acquisitions/seed` accepts no query parameters and requires:

```json
{
  "firm_id": "oracle",
  "canonical_artifact_id": "earnings_transcript",
  "provider": "stockanalysis",
  "starting_seed": "https://stockanalysis.com/stocks/orcl/transcripts/592465-q4-2026/"
}
```

`provider` must be a non-blank string registered in `TranscriptProviderRegistry`. Missing, blank,
unknown, extra, repeated, or query-parameter provider selection fails with the existing
`invalid_request` client-error vocabulary. The optional existing `selection` object is unchanged.

`GET /api/transcript-acquisitions/learning/{firm_id}` keeps its route, envelope, and existing
discovery-anchor vocabulary. A populated entry now always includes provider:

```json
{
  "firm_id": "oracle",
  "learning": [
    {
      "provider": "stockanalysis",
      "requested_url": "https://stockanalysis.com/stocks/orcl/transcripts/592465-q4-2026/"
    }
  ]
}
```

The actual response includes all existing anchor fields. Empty learning remains `learning: []`,
unknown firms retain the existing HTTP 400 error, and provider path or query filters are rejected.

## Responsibility and Dispatch Review

| Concern | Owner after TASK-065 |
|---|---|
| Request shape and query rejection | Local HTTP adapter |
| Provider-name validation and dispatch | Existing `TranscriptProviderRegistry` |
| Explicit provider propagation | Existing Pull Workflow and transcript adapter trial factory |
| Provider-local URL acceptance | Selected provider implementation |
| Bounded discovery, candidate evaluation, retrieval, and validation | Existing `earnings-call-transcript` acquisition path |
| Provider learning association | Existing discovery-anchor canonical JSON |
| Learning inspection | Existing read-only acquisition repository projection |
| Checkpoint and replay | Existing acquisition engine and repository |

The only provider-selection value is `AdapterAcquisitionTrial.provider`. Normal configured and
learned provider trials already used that field; operator injection now constructs the same field
from the request body. `_discover_provider()` performs the one registry dispatch from that value.
The HTTP layer does not name StockAnalysis or inspect URLs. `injected_trial()` does not read the
firm's configured provider. The provider implementation receives the explicit URL seed and owns
all namespace, archive/document, identifier, and URL-shape validation.

## Persistence and Compatibility Review

Inspection of the version-15 repository schema found no provider column on
`discovery_anchor_history`, but found the authoritative provider association already persisted in
the row's `canonical_json`. `_record_discovery_anchor()` obtains it from successful candidate
provenance, and `_record_discovery_anchor_values()` writes it atomically with the retained learning
entry. TASK-065 therefore requires no schema version, table, column, migration, or backfill.

The read projection decodes that canonical JSON and returns the stored provider unchanged. A
historical row lacking the member is exposed explicitly as `provider: null`; this makes absence
visible without guessing from its URL or current source/firm configuration. A malformed non-null
persisted provider fails closed as repository-integrity corruption. Reads use the existing
read-only connection and do not rewrite the historical row, advance repository revision, or alter
any state.

Provider remains part of each independently returned retained entry. Entries for different
providers remain distinguishable while the existing source/adapter grouping, strict LIFO order,
URL identity behavior, and three-entry retention bound are unchanged.

## Complexity and Robustness Review

- **One provider-selection mechanism:** confirmed. All provider-backed trials dispatch from
  `AdapterAcquisitionTrial.provider` through the existing registry.
- **No duplicate abstractions:** confirmed. Registry `resolve()` centralizes name validation and
  is used by existing `create()`; no request-specific dispatcher exists.
- **No URL inference:** confirmed by focused behavior and the architecture guard. A
  StockAnalysis-shaped URL paired with an unknown provider is rejected before transport.
- **No firm-configuration fallback:** confirmed. Injection uses only its `provider` argument.
- **No provider-specific HTTP logic:** confirmed. HTTP validates generic request fields and
  delegates provider resolution downstream.
- **One authoritative learning association:** confirmed. Successful candidate provenance is
  written into the existing discovery-anchor payload and read from that payload.
- **No read-time reconstruction:** confirmed. Learning inspection contains no URL parser, registry
  dispatch, or firm-configuration lookup.
- **No duplicate persistence abstraction:** confirmed. The existing row remains authoritative; no
  provider table, mapping, model, or schema migration exists.
- **No behavior change beyond explicit dispatch and provider exposure:** confirmed. Learning
  ranking, order, eviction, checkpoint, selector, replay, and bounded-session behavior are
  unchanged.

No additional in-scope change or separate architectural opportunity was identified.

## Validation Evidence

The final-head review package records complete raw output for:

- focused TASK-065 API, registry, propagation, direct-injection, persistence, compatibility,
  ordering, retention, and failure tests;
- the deterministic TASK-065 proof and architecture guard;
- operator Help rendering and Markdown documentation checks;
- TASK-060 regressions;
- TASK-061 learning-inspection regressions;
- TASK-063 bounded-resolution regressions;
- TASK-064 provider regressions;
- `git diff --check`; and
- full `make validate`.

The package generator reruns and records every gate from the committed final head. Focused evidence
demonstrates successful explicit injection persistence, unchanged provider inspection, absence of
learning after failure, no URL or configuration inference, distinction of multiple providers for
one firm, unchanged strict LIFO ordering and retention bound, explicit-null historical
compatibility, read-only inspection, and unchanged empty/unknown-firm behavior.

StockAnalysis archive/document URL acceptance is unchanged. The currently observed StockAnalysis
archive-URL seed-injection failure remains an expected limitation; TASK-065 does not reinterpret it.

## Architectural Status Summary

| Subsystem | Responsibility | Status | Important limitation |
|---|---|---|---|
| Transcript seed-injection HTTP contract | Require body provider and reject query selection | Complete | Local API only |
| Transcript provider registry | Validate and create explicitly named providers | Complete | StockAnalysis is the only production registration today |
| Pull Workflow transcript injection | Resolve governed firm/source and propagate explicit provider | Complete | Requires an existing runnable transcript configuration |
| Earnings transcript outer adapter | Convert the request into one provider-backed acquisition trial | Complete | Provider-specific prerequisites remain provider-owned |
| StockAnalysis provider | Validate StockAnalysis URL/identifier surfaces and retrieve evidence | Usable with Limitations | Existing archive URL failure is unchanged |
| Acquisition engine and repository | Persist successful provider provenance in existing learning authority | Complete | Historical missing associations are exposed as null |
| Learning inspection API | Expose persisted provider association read-only | Complete | No provider filter; malformed non-null authority fails closed |

Architectural change introduced: operator injection joins the existing provider-backed trial path
through an explicit provider name, and learning inspection exposes the resulting authoritative
persisted association. No new subsystem was introduced.
