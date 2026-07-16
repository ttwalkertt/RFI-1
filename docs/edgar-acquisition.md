# Bounded native SEC EDGAR acquisition

Native EDGAR is the TASK-004 live acceptance path. SEC-API.io remains an optional commercial
adapter documented separately. Both use the unchanged acquisition engine and repository facade.

## Fixed corpus

| Source | SEC identity | Inclusive filing interval | Per-form maximum |
|---|---|---|---|
| STX | CIK 1137789 | 2024-01-01 through 2025-12-31 | 1×10-K, 2×10-Q, 2×8-K |
| WDC | CIK 106040 | 2024-01-01 through 2025-12-31 | 1×10-K, 2×10-Q, 2×8-K |

Discovery uses official `data.sec.gov/submissions/CIK##########.json` data. Results are selected
per form by filing date, acceptance timestamp, and accession descending, then exposed one at a
time. The maximum corpus is ten filings and cannot widen with the wall clock.

Exact retrieval uses the official archive path:

```text
https://www.sec.gov/Archives/edgar/data/<CIK>/<accession digits>/<accession>.txt
```

The exact complete-submission bytes become immutable content-addressed repository artifacts.

## Runtime identity and fair access

Set `RFI_SEC_USER_AGENT` only in the invoking process. Its value must contain a descriptive
application identity followed by an operator-controlled contact email. For example, the shape is
`ApplicationName/Version contact-at-operator-domain`; the repository intentionally supplies no
real contact value.

Profiles contain only `env:RFI_SEC_USER_AGENT`. The value is never printed, persisted, copied into
fixtures, placed in URLs, or included in review evidence. Missing or malformed configuration
stops before network access.

The adapter spaces requests by at least 0.5 seconds, limiting it to two requests per second—well
below the current SEC maximum of ten. It also enforces two attempts, a 20-second timeout, a 5 MB
submissions response limit, a 50 MB filing limit, an 80-request acceptance ceiling, status and
content checks, and sanitized errors.

## Commands

Offline scope and tests:

```sh
.venv/bin/python scripts/edgar_operator.py scope
env -u RFI_SEC_USER_AGENT .venv/bin/python -m unittest tests.test_edgar -v
env -u RFI_SEC_USER_AGENT make validate
```

Explicitly live commands:

```sh
RFI_SEC_USER_AGENT='operator-supplied value' \
  .venv/bin/python scripts/edgar_operator.py live-config --probe
RFI_SEC_USER_AGENT='operator-supplied value' \
  .venv/bin/python scripts/edgar_operator.py run-all \
  --state .artifacts/runtime/TASK-004-edgar --run-key first
RFI_SEC_USER_AGENT='operator-supplied value' \
  .venv/bin/python scripts/edgar_operator.py run-all \
  --state .artifacts/runtime/TASK-004-edgar --run-key second
```

Provider-disabled inspection, integrity, replay, and rebuild:

```sh
env -u RFI_SEC_USER_AGENT .venv/bin/python scripts/edgar_operator.py inventory \
  --state .artifacts/runtime/TASK-004-edgar
env -u RFI_SEC_USER_AGENT .venv/bin/python scripts/acquisition_operator.py verify \
  --state .artifacts/runtime/TASK-004-edgar
env -u RFI_SEC_USER_AGENT .venv/bin/python scripts/acquisition_operator.py delete-derived \
  --state .artifacts/runtime/TASK-004-edgar
env -u RFI_SEC_USER_AGENT .venv/bin/python scripts/acquisition_operator.py rebuild \
  --state .artifacts/runtime/TASK-004-edgar
```

The live User-Agent must be supplied directly by the operator. A package generated without it must
mark native live acceptance blocked and must not substitute fixture evidence for real EDGAR data.
