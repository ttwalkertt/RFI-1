# TASK-065 Architectural Review — Explicit Transcript Provider Injection

## Result

TASK-065 requires every transcript seed-injection request to name its provider explicitly. The
request-body `provider` is carried unchanged through `PullWorkflow` and
`EarningsTranscriptPullAdapter.injected_trial()` into `AdapterAcquisitionTrial.provider`.
`TranscriptProviderRegistry` validates and dispatches that name. URL shape and firm configuration
do not select or replace the request provider.

The existing outer acquisition adapter remains `earnings-call-transcript`. No persistence model,
provider registry, provider-specific HTTP branch, transcript search strategy, selector,
checkpoint, replay, learning, candidate extraction, or bounded-resolution behavior was added or
changed.

## Public Contract

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

## Responsibility and Dispatch Review

| Concern | Owner after TASK-065 |
|---|---|
| Request shape and query rejection | Local HTTP adapter |
| Provider-name validation and dispatch | Existing `TranscriptProviderRegistry` |
| Explicit provider propagation | Existing Pull Workflow and transcript adapter trial factory |
| Provider-local URL acceptance | Selected provider implementation |
| Bounded discovery, candidate evaluation, retrieval, and validation | Existing `earnings-call-transcript` acquisition path |
| Persistence, checkpoint, replay, and learning | Existing acquisition engine and repository |

The only provider-selection value is `AdapterAcquisitionTrial.provider`. Normal configured and
learned provider trials already used that field; operator injection now constructs the same field
from the request body. `_discover_provider()` performs the one registry dispatch from that value.
The HTTP layer does not name StockAnalysis or inspect URLs. `injected_trial()` does not read the
firm's configured provider. The provider implementation receives the explicit URL seed and owns
all namespace, archive/document, identifier, and URL-shape validation.

## Complexity and Robustness Review

- **One provider-selection mechanism:** confirmed. All provider-backed trials dispatch from
  `AdapterAcquisitionTrial.provider` through the existing registry.
- **No duplicate abstractions:** confirmed. One small registry `resolve()` operation centralizes
  name validation and is also used by the existing `create()` operation; no second registry or
  request-specific dispatcher exists.
- **No URL inference:** confirmed by focused behavior and the committed architecture guard. A
  StockAnalysis-shaped URL paired with an unknown provider is rejected before transport.
- **No firm-configuration fallback:** confirmed. Injection uses only its `provider` argument;
  provider-specific source prerequisites may still be validated by the selected implementation,
  but configuration never chooses the provider.
- **No provider-specific HTTP logic:** confirmed. The HTTP adapter validates only generic request
  fields and delegates provider resolution downstream.
- **No behavior change beyond explicit dispatch:** confirmed. Historical generic resolver tests
  continue outside the new public dispatch boundary, and failure/success learning, checkpoint,
  selection, and bounded-session regressions remain unchanged.

No additional architectural opportunity was required for this milestone. Any future provider
implementation should register with the existing registry and retain provider-local URL rules.

## Validation Evidence

The final-head review package records complete raw output for:

- focused TASK-065 API, registry, propagation, direct-injection, and learning/checkpoint tests;
- the deterministic TASK-065 proof and architecture guard;
- operator Help rendering and Markdown documentation checks;
- TASK-060 regressions;
- TASK-061 learning regressions;
- TASK-063 bounded-resolution regressions;
- TASK-064 provider regressions;
- `git diff --check`; and
- full `make validate`.

Pre-package validation completed with 6 focused TASK-065 tests, 133 TASK-060 regression tests,
5 TASK-061 regression tests, 11 TASK-063 regression tests, 33 TASK-064 regression tests, 8 Help
tests, and all 645 repository tests. The complete package generator reruns and records these gates
from the committed final head rather than relying on this summary.

The focused tests explicitly demonstrate missing, blank, and unknown provider rejection; registry
resolution; propagation into `AdapterAcquisitionTrial.provider`; rejection of query-parameter
provider selection; absence of URL inference; successful direct StockAnalysis document injection;
and unchanged failure learning/checkpoint behavior.

StockAnalysis archive/document URL acceptance is unchanged. In particular, the currently observed
StockAnalysis archive-URL seed-injection failure remains an expected limitation of this task;
TASK-065 does not repair or reinterpret it.

## Architectural Status Summary

| Subsystem | Responsibility | Status | Important limitation |
|---|---|---|---|
| Transcript seed-injection HTTP contract | Require body provider and reject query selection | Complete | Local API only |
| Transcript provider registry | Validate and create explicitly named providers | Complete | StockAnalysis is the only production registration today |
| Pull Workflow transcript injection | Resolve governed firm/source and propagate explicit provider | Complete | Requires an existing runnable transcript configuration |
| Earnings transcript outer adapter | Convert the explicit request into one provider-backed acquisition trial | Complete | Provider-specific prerequisites remain provider-owned |
| StockAnalysis provider | Validate StockAnalysis URL/identifier surfaces and retrieve transcript evidence | Usable with Limitations | Existing archive URL failure is unchanged |
| Acquisition engine and repository | Preserve validation, checkpoint, replay, learning, and persistence | Complete and unchanged | Existing bounded policies remain authoritative |

Architectural change introduced: operator seed injection now joins the existing provider-backed
trial path through an explicit provider name. No new subsystem was introduced. The next
architectural milestone is outside TASK-065 and should address provider-local URL acceptance only
under a separately approved ticket.
