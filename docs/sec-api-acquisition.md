# Optional bounded SEC-API.io acquisition

TASK-004 retains this commercial provider behind the unchanged TASK-003 adapter contract as an
optional acceleration path. The authorized native EDGAR amendment makes
[native EDGAR](edgar-acquisition.md) the required live acceptance path. SEC-API.io remains fully
implemented and offline-tested, but its live behavior is untested and does not determine amended
TASK-004 completion.

## Deterministic corpus

The checked-in profiles under `config/sources/` govern exactly:

| Source | SEC identity | Fixed interval | Per-form cap |
|---|---|---|---|
| STX | CIK 1137789 | 2024-01-01 through 2025-12-31 | 1×10-K, 2×10-Q, 2×8-K |
| WDC | CIK 106040 | 2024-01-01 through 2025-12-31 | 1×10-K, 2×10-Q, 2×8-K |

Within each form, results are sorted by acceptance time and accession descending. Page size one
proves provider offset pagination. The maximum corpus is ten filings, and each retrieved artifact
is the exact complete-submission text referenced by `linkToTxt`. The fixed end date and per-form
caps prevent silent widening.

## Identity and provenance

Issuer identity is normalized SEC CIK. Filing identity is `document-sec-<CIK>-<accession digits>`.
Accession number is the durable SEC key; a separately filed amendment has its own accession and
therefore its own document identity. The candidate adds the `submission` artifact role. Exact
artifact identity remains repository content SHA-256, allowing one filing to have distinct exact
artifacts if a provider ever returns changed bytes without rewriting prior evidence.

SEC-API.io IDs, endpoints, download references, offsets, and response fields never enter repository
identity. Provenance preserves SEC accession, CIK, ticker, form, acceptance timestamp, period of
report, amendment flag, original SEC URLs, provider surface, retrieval timestamp, and sanitized
request/quota evidence. Missing required accession, CIK, form, acceptance time, or complete-
submission URL fails closed; optional absent fields remain null rather than being guessed.

## Credential and network boundary

Set `SEC_API_IO_API_KEY` only in the invoking process environment. The source profiles contain only
`env:SEC_API_IO_API_KEY`. The adapter sends the value as the raw `Authorization` header required by
SEC-API.io and never places it in a URL, diagnostic, fixture, repository record, or review artifact.

The standard-library transport enforces a 20-second connection/read timeout, a 50 MB artifact
limit, two bounded attempts, a process-wide 80-request ceiling for the complete two-run acceptance,
HTTP status checks, JSON/content-type checks, and complete-submission signature checks. 429 and
transient 5xx responses are retried once. Authentication and permanent request failures do not
retry. Provider error bodies are deliberately discarded.

## Operator workflow

Offline and credential-free:

```sh
.venv/bin/python scripts/sec_api_operator.py scope
env -u SEC_API_IO_API_KEY make validate
.venv/bin/python -m unittest tests.test_sec_api -v
```

The following commands are explicitly live and quota-consuming:

```sh
SEC_API_IO_API_KEY=... .venv/bin/python scripts/sec_api_operator.py live-config --probe
SEC_API_IO_API_KEY=... .venv/bin/python scripts/sec_api_operator.py run-source \
  --state data/runtime/TASK-004 --source source-sec-stx --run-key first
SEC_API_IO_API_KEY=... .venv/bin/python scripts/sec_api_operator.py run-all \
  --state data/runtime/TASK-004 --run-key first
SEC_API_IO_API_KEY=... .venv/bin/python scripts/sec_api_operator.py run-all \
  --state data/runtime/TASK-004 --run-key second
```

Inspect, verify, disable provider access, and rebuild without network:

```sh
.venv/bin/python scripts/sec_api_operator.py inventory --state data/runtime/TASK-004
env -u SEC_API_IO_API_KEY .venv/bin/python scripts/acquisition_operator.py history \
  --state data/runtime/TASK-004
env -u SEC_API_IO_API_KEY .venv/bin/python scripts/acquisition_operator.py verify \
  --state data/runtime/TASK-004
env -u SEC_API_IO_API_KEY .venv/bin/python scripts/acquisition_operator.py delete-derived \
  --state data/runtime/TASK-004
env -u SEC_API_IO_API_KEY .venv/bin/python scripts/acquisition_operator.py rebuild \
  --state data/runtime/TASK-004
```

Generate `.artifacts/review/TASK-004/` and its ZIP with `make review-package`. Absence of the
commercial credential does not block amended TASK-004 completion, but the package must identify
the SEC-API.io path as offline-only unless it was independently exercised.
