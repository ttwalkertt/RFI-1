# Deterministic SEC Form 10-K retrieval

TASK-016 connects one identifier-based canonical artifact to the existing Pull Workflow,
acquisition engine, and immutable repository. Normal validation is fixture-backed and offline.
Live validation is a separate, explicitly gated operator operation.

## Responsibility model

| Responsibility | Authority |
|---|---|
| Canonical artifact identity and supported configuration shapes | Canonical source-profile template |
| Firm-specific enablement, CIK locator, priority, and revision | Firm source-profile aggregate |
| Unique adapter identity, artifact/mode capability declaration, and unique selection | Retrieval-adapter registry |
| Form 10-K eligibility, amendment policy, ordering, multiplicity, primary-document role, and artifact failures | `SecForm10KAdapter` |
| SEC HTTPS, CIK normalization, request identity, pacing, retry, response decoding, archive retrieval, and transport diagnostics | `SecProviderClient` |
| Run snapshot, independent artifact execution, aggregation, and durable operator journal | Pull Workflow |
| Candidate processing and public repository calls | Acquisition engine |
| Document/artifact/attempt/checkpoint authority, immutable bytes, replay, rebuild, and integrity | Acquisition repository |

The Pull Workflow contains no SEC or Form 10-K branch. Its plan records the adapter selected for
each runnable candidate. A registry declaration can be artifact-specific or intentionally generic,
as with direct URL retrieval. The effective selection key is canonical `artifact_id` plus candidate
`mode`, which are the fields the planner and workflow already use. Overlapping claims on that key
fail closed. Acquisition mechanism is routing metadata used only after selection; distinct
artifact-specific adapters may share it. The workflow gives the acquisition engine a registry
containing only the selected adapter for the current run, preserving the engine's established
mechanism-based routing without making mechanism the retrieval-adapter identity.

## Form 10-K policy

The adapter accepts only canonical artifact `sec_10k` with mode `identifier` and a one-to-ten digit
SEC CIK locator, optionally prefixed by `CIK:`. It retrieves the issuer's official recent
submissions record and selects only rows whose form is exactly `10-K`. `10-K/A` rows are counted
and excluded.

Eligible rows are deduplicated by accession. Conflicting metadata for one accession is ambiguous
and fails. The remaining rows are ordered descending by:

1. filing date;
2. acceptance timestamp; and
3. accession number.

The first row is the one selected filing. The adapter exposes exactly one primary-document
candidate. Its monotonic engine position derives from acceptance time and accession sequence, so a
later filing can advance source progress while an equivalent rerun remains no-change. Provider
record order has no effect.

The exact archive target is:

```text
https://www.sec.gov/Archives/edgar/data/<normalized CIK>/<accession digits>/<primaryDocument>
```

No complete-submission text, filing exhibit, investor-relations substitute, amendment, other form,
search result, browser selection, or model judgment can enter this path.

## SEC provider boundary

The shared provider service permits only HTTPS requests to `data.sec.gov` and `www.sec.gov`.
Submissions use `https://data.sec.gov/submissions/CIK##########.json`. The primary artifact uses
the official archive path above. Cross-origin redirects fail; same-origin redirects are limited to
three.

Each request has a 20-second timeout, at most two attempts, and at least 0.5 seconds between
attempts. Metadata is bounded at 5 MB and the primary artifact at 50 MB. HTTP 429 and selected 5xx
responses receive one retry. Timeouts, rate limits, temporary service failures, issuer absence,
permanent failures, unsafe redirects, malformed metadata, unsupported content, empty content,
truncation, invalid HTML signatures, and size violations remain distinct failure codes.

`RFI_SEC_USER_AGENT` is resolved immediately before live network activity from the environment or
the private ignored `.rfi/runtime.env` file. Its value is never placed in a source profile,
repository record, fixture, diagnostic, or review artifact.

## Identity and provenance

The source-profile revision and retrieval candidate remain configuration intent. SEC CIK and
accession identify the issuer and filing. The selected primary filename and artifact role remain
provider provenance. Repository document identity is stable across provider record order and URL
representation changes. Exact artifact identity remains content-derived SHA-256.

The pull result includes adapter identity, document and candidate identities, provider identifiers,
discovery and archive locations, selected form/accession/primary document, retrieval diagnostics,
and immutable artifact identity. The operator console renders these details under each attempt.

## Operator commands

Offline and deterministic:

```sh
make task016-test
make task016-proof
```

Validate live prerequisites without network access:

```sh
.venv/bin/python scripts/task016_sec_10k.py live-config
```

The gated live command refuses existing state/evidence paths and requires explicit confirmation:

```sh
.venv/bin/python scripts/task016_sec_10k.py live-pull \
  --state .artifacts/runtime/TASK-016-sec-10k \
  --evidence .artifacts/review-input/TASK-016-live.json \
  --confirm-live-sec
```

The first pull requires one submissions operation and one primary-document operation. The
equivalent rerun requires one submissions operation. With two attempts per operation, the combined
ceiling is six HTTP attempts. Ordinary tests and `make validate` do not make network requests.

## Failure taxonomy

Configuration and selection distinguish missing candidate fields, unsupported modes, no compatible
adapter, ambiguous capability declarations, and invalid SEC issuer identifiers. Provider and
artifact failures distinguish issuer absence, no eligible Form 10-K, ambiguous filing metadata,
missing filing identity, malformed response, timeout, rate limit, temporary service failure,
permanent request failure, unsafe redirect, unsupported representation, empty/truncated/invalid
content, and size bounds. Repository conflicts and integrity failures retain the acquisition
engine's established classifications. Firm and run aggregation continues to distinguish success,
duplicate, no change, skipped, configuration problem, retrieval failure, partial, and failed.

## Extensions and deferred work

Future deterministic adapters register new artifact-semantic capabilities and may reuse bounded
provider mechanics or one downstream acquisition mechanism. Adapter identity must remain unique,
and artifact/mode claims must not overlap. There is no priority, fallback ordering, or
multiple-match resolution for ambiguous capability registrations. Semi-deterministic adapters can
use the same registry while owning listing or portal semantics. Discovery-based adapters can also
fit the boundary later, but must remain bounded, governed, and separate from repository
persistence.

No other SEC form, exact historical selector, published annual report, exhibit, crawling, search,
LLM selection, extraction, XBRL processing, observation, claim, or intelligence capability is
implemented by TASK-016.
